"""
Scraper de Infobae para guardar en la tabla scraping_items
Incluye deduplicación automática, hashes SHA-256 y manejo del pipeline
"""

import asyncio
import hashlib
import os
import sys
import json
import re
from datetime import datetime
from urllib.parse import urlparse, urlunparse
from pathlib import Path
from dotenv import load_dotenv
from playwright.async_api import async_playwright
import asyncpg

# Load environment variables from .env file
env_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=env_path)

# Reconfigure stdout for Windows unicode support
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

# ===== CONFIGURACIÓN =====
URL_ULTIMAS_NOTICIAS = "https://www.infobae.com/ultimas-noticias/"
CONCURRENCY = 5
MAX_ARTICLES = 50  # Límite de artículos por ejecución

# Database connection
DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", "5432")),
    "database": os.getenv("DB_NAME", "ladatajusta"),
    "user": os.getenv("DB_USER", "ladatajusta"),
    "password": os.getenv("DB_PASSWORD", "ladatajusta"),
}

# Scraper metadata
SCRAPER_NAME = "infobae_playwright"
SCRAPER_VERSION = "1.0.0"
SOURCE_MEDIA = "infobae"

# Global state
lock = asyncio.Lock()
db_pool = None
scraping_run_id = None


def normalize_url(url: str) -> str:
    """
    Normaliza una URL para deduplicación:
    - Convierte a minúsculas
    - Elimina fragmentos (#)
    - Ordena query parameters
    - Elimina trailing slash
    """
    parsed = urlparse(url.lower().strip())
    # Reconstruir sin fragmento y sin trailing slash
    normalized = urlunparse((
        parsed.scheme,
        parsed.netloc,
        parsed.path.rstrip('/'),
        parsed.params,
        parsed.query,
        ''  # Sin fragmento
    ))
    return normalized


def calculate_hash(text: str) -> str:
    """
    Calcula SHA-256 hash de un texto normalizado
    """
    if not text:
        return hashlib.sha256(b'').hexdigest()

    # Normalizar: minúsculas, sin espacios extra, sin saltos de línea múltiples
    normalized = ' '.join(text.lower().strip().split())
    return hashlib.sha256(normalized.encode('utf-8')).hexdigest()


def extract_section_from_url(url: str) -> str:
    """
    Extrae la sección de una URL de Infobae
    Ejemplo: /deportes/2026/01/30/slug/ -> deportes
    """
    try:
        path = urlparse(url).path
        parts = [p for p in path.split('/') if p]
        if parts:
            # La primera parte suele ser la sección
            section = parts[0]
            # Verificar que no sea una fecha (año)
            if not section.isdigit():
                return section
    except:
        pass
    return None


async def check_duplicate(pool, url_hash: str, content_hash: str) -> bool:
    """
    Verifica si ya existe un artículo con el mismo URL o contenido
    Retorna True si es duplicado
    """
    async with pool.acquire() as conn:
        result = await conn.fetchval(
            """
            SELECT EXISTS(
                SELECT 1 FROM scraping_items
                WHERE url_hash = $1 OR content_hash = $2
            )
            """,
            url_hash, content_hash
        )
        return result


async def insert_scraping_item(pool, data: dict) -> bool:
    """
    Inserta un nuevo item en la tabla scraping_items
    Returns True if inserted, False if was duplicate
    """
    async with pool.acquire() as conn:
        result = await conn.execute(
            """
            INSERT INTO scraping_items (
                source_media,
                source_section,
                source_url,
                source_url_normalized,
                title,
                subtitle,
                summary,
                content,
                author,
                article_date,
                tags,
                image_urls,
                content_hash,
                url_hash,
                scraper_name,
                scraper_version,
                scraping_run_id,
                scraped_at,
                scraping_duration_ms,
                status,
                status_message,
                extra_metadata
            ) VALUES (
                $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19, $20, $21, $22
            )
            ON CONFLICT (url_hash) DO NOTHING
            """,
            data['source_media'],
            data['source_section'],
            data['source_url'],
            data['source_url_normalized'],
            data['title'],
            data['subtitle'],
            data['summary'],
            data['content'],
            data['author'],
            data['article_date'],
            data['tags'],
            data['image_urls'],
            data['content_hash'],
            data['url_hash'],
            data['scraper_name'],
            data['scraper_version'],
            data['scraping_run_id'],
            data['scraped_at'],
            data['scraping_duration_ms'],
            data['status'],
            data['status_message'],
            data['extra_metadata']
        )
        # Check if row was inserted (result will be "INSERT 0 1" if inserted, "INSERT 0 0" if duplicate)
        return "INSERT 0 1" in result


async def procesar_noticia(context, enlace):
    """
    Procesa una noticia individual y la guarda en la BD
    Returns True if item was inserted, False otherwise
    """
    global db_pool, scraping_run_id

    start_time = datetime.now()
    page = await context.new_page()

    try:
        print(f"[SCRAPE] Procesando: {enlace}")

        # Calcular hashes para verificar duplicados
        url_normalized = normalize_url(enlace)
        url_hash = calculate_hash(url_normalized)

        # Verificar si ya existe
        if await check_duplicate(db_pool, url_hash, ""):
            print(f"[SKIP] Duplicado (URL): {enlace}")
            await page.close()
            return False

        # Navegar a la página
        await page.goto(enlace, timeout=60000, wait_until="domcontentloaded")

        # Esperar a que cargue el contenido principal
        await page.wait_for_timeout(2000)

        # Scroll para cargar contenido lazy
        for _ in range(5):
            await page.mouse.wheel(0, 1000)
            await page.wait_for_timeout(300)

        # Extraer título
        titulo = None
        titulo_selectors = [
            "h1.article-headline",
            "h1[class*='headline']",
            "h1.d23-title",
            "article h1",
            "h1"
        ]
        for selector in titulo_selectors:
            try:
                if await page.locator(selector).first.is_visible(timeout=1000):
                    titulo = await page.locator(selector).first.text_content()
                    if titulo:
                        break
            except:
                continue

        if not titulo:
            print(f"[SKIP] No se encontró título: {enlace}")
            await page.close()
            return False

        # Extraer subtítulo/bajada
        subtitulo = None
        subtitulo_selectors = [
            "h2.article-subheadline",
            "h2[class*='subheadline']",
            ".article-deck",
            "article h2"
        ]
        for selector in subtitulo_selectors:
            try:
                if await page.locator(selector).first.is_visible(timeout=500):
                    subtitulo = await page.locator(selector).first.text_content()
                    if subtitulo:
                        break
            except:
                continue

        # Extraer contenido principal
        contenido = ""
        contenido_selectors = [
            "article .article-body",
            "[class*='article-body']",
            "article .body",
            ".article-content",
            "article p"
        ]
        for selector in contenido_selectors:
            try:
                elementos = page.locator(selector)
                count = await elementos.count()
                if count > 0:
                    textos = []
                    for i in range(count):
                        texto = await elementos.nth(i).text_content()
                        if texto:
                            textos.append(texto.strip())
                    contenido = "\n\n".join(textos)
                    if contenido:
                        break
            except:
                continue

        # Si no hay contenido, intentar con todos los párrafos del artículo
        if not contenido:
            try:
                parrafos = page.locator("article p")
                count = await parrafos.count()
                textos = []
                for i in range(count):
                    texto = await parrafos.nth(i).text_content()
                    if texto and len(texto.strip()) > 20:
                        textos.append(texto.strip())
                contenido = "\n\n".join(textos)
            except:
                pass

        if not contenido:
            print(f"[SKIP] No se encontró contenido: {enlace}")
            await page.close()
            return False

        # Extraer autor
        autor = None
        autor_selectors = [
            ".author-name",
            "[class*='author']",
            "a[rel='author']",
            ".byline"
        ]
        for selector in autor_selectors:
            try:
                if await page.locator(selector).first.is_visible(timeout=500):
                    autor = await page.locator(selector).first.text_content()
                    if autor:
                        autor = autor.strip()
                        break
            except:
                continue

        # Extraer fecha de publicación
        article_date = None
        try:
            fecha_meta = await page.locator("meta[property='article:published_time']").get_attribute("content")
            if fecha_meta:
                article_date = datetime.fromisoformat(fecha_meta.replace('Z', '+00:00'))
        except:
            pass

        if not article_date:
            try:
                time_elem = await page.locator("time[datetime]").first.get_attribute("datetime")
                if time_elem:
                    article_date = datetime.fromisoformat(time_elem.replace('Z', '+00:00'))
            except:
                pass

        # Extraer sección
        seccion = extract_section_from_url(enlace)

        # Extraer tags
        tags = []
        try:
            tag_elements = page.locator("a[href*='/tag/'], .article-tags a")
            count = await tag_elements.count()
            for i in range(min(count, 10)):  # Máximo 10 tags
                tag = await tag_elements.nth(i).text_content()
                if tag:
                    tags.append(tag.strip())
        except:
            pass

        # Calcular hash del contenido
        content_hash = calculate_hash(contenido)

        # Verificar duplicado por contenido
        if await check_duplicate(db_pool, url_hash, content_hash):
            print(f"[SKIP] Duplicado (contenido): {enlace}")
            await page.close()
            return False

        # Calcular duración del scraping
        end_time = datetime.now()
        duration_ms = int((end_time - start_time).total_seconds() * 1000)

        # Preparar datos para insertar
        data = {
            'source_media': SOURCE_MEDIA,
            'source_section': seccion,
            'source_url': enlace,
            'source_url_normalized': url_normalized,
            'title': titulo.strip() if titulo else None,
            'subtitle': subtitulo.strip() if subtitulo else None,
            'summary': subtitulo.strip() if subtitulo else None,  # Usar subtítulo como resumen
            'content': contenido.strip() if contenido else "",
            'author': autor,
            'article_date': article_date,
            'tags': tags,
            'image_urls': [],
            'content_hash': content_hash,
            'url_hash': url_hash,
            'scraper_name': SCRAPER_NAME,
            'scraper_version': SCRAPER_VERSION,
            'scraping_run_id': scraping_run_id,
            'scraped_at': start_time,
            'scraping_duration_ms': duration_ms,
            'status': 'scraped',
            'status_message': 'Successfully scraped from Infobae',
            'extra_metadata': json.dumps({
                'user_agent': await page.evaluate('navigator.userAgent'),
                'viewport': page.viewport_size,
            })
        }

        # Insertar en la base de datos
        async with lock:
            inserted = await insert_scraping_item(db_pool, data)
            if inserted:
                print(f"[OK] Guardado: {titulo[:60]}...")
                return True
            else:
                print(f"[SKIP] Duplicado: {titulo[:60]}...")
                return False

    except Exception as e:
        print(f"[WARN] Error en {enlace}: {e}")
        return False

    finally:
        await page.close()


async def main():
    """
    Función principal del scraper
    Returns dict with scraping results for orchestrator
    """
    global db_pool, scraping_run_id

    # Generar ID único para esta ejecución
    scraping_run_id = hashlib.sha256(
        f"{SCRAPER_NAME}_{datetime.now().isoformat()}".encode()
    ).hexdigest()[:32]

    print(f"[START] Iniciando scraper de Infobae")
    print(f"[INFO] Run ID: {scraping_run_id}")

    items_scraped = 0
    start_time = datetime.now()

    # Conectar a la base de datos
    try:
        db_pool = await asyncpg.create_pool(**DB_CONFIG, min_size=5, max_size=20)
        print("[OK] Conectado a PostgreSQL")
    except Exception as e:
        print(f"[ERROR] Error conectando a PostgreSQL: {e}")
        print(f"   Config: {DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}")
        return {
            'status': 'error',
            'items_scraped': 0,
            'message': f'Database connection failed: {str(e)}'
        }

    try:
        # Iniciar Playwright
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            page = await context.new_page()

            # Navegar a "Últimas Noticias"
            print(f"[NAV] Navegando a {URL_ULTIMAS_NOTICIAS}")
            await page.goto(URL_ULTIMAS_NOTICIAS, timeout=60000, wait_until="domcontentloaded")

            # Esperar a que cargue el contenido
            await page.wait_for_timeout(3000)

            # Scroll para cargar más noticias
            for _ in range(5):
                await page.mouse.wheel(0, 2000)
                await page.wait_for_timeout(1000)

            # Extraer todos los enlaces de noticias
            # Infobae usa enlaces con el patrón /{seccion}/{año}/{mes}/{dia}/{slug}/
            enlaces = await page.eval_on_selector_all(
                "a[href]",
                """els => els.map(e => e.href)
                    .filter(h => {
                        // Filtrar solo URLs de artículos de Infobae
                        const pattern = /infobae\\.com\\/[a-z-]+\\/\\d{4}\\/\\d{2}\\/\\d{2}\\/[a-z0-9-]+\\/?$/i;
                        return pattern.test(h);
                    })
                """
            )

            # Eliminar duplicados y limitar cantidad
            enlaces = list(dict.fromkeys(enlaces))[:MAX_ARTICLES]
            print(f"[LINKS] {len(enlaces)} enlaces únicos encontrados")

            if len(enlaces) == 0:
                print("[WARN] No se encontraron enlaces. Intentando método alternativo...")
                # Método alternativo: buscar cualquier enlace interno
                enlaces = await page.eval_on_selector_all(
                    "a[href*='infobae.com']",
                    """els => els.map(e => e.href)
                        .filter(h => {
                            // Excluir páginas de sección, home, etc.
                            return h.includes('/20') && !h.includes('/ultimas-noticias');
                        })
                    """
                )
                enlaces = list(dict.fromkeys(enlaces))[:MAX_ARTICLES]
                print(f"[LINKS] Método alternativo: {len(enlaces)} enlaces encontrados")

            # Procesar noticias en lotes (concurrencia controlada)
            for i in range(0, len(enlaces), CONCURRENCY):
                grupo = enlaces[i:i + CONCURRENCY]
                print(f"\n[BATCH] Procesando lote {i // CONCURRENCY + 1}/{(len(enlaces) - 1) // CONCURRENCY + 1}")
                tareas = [procesar_noticia(context, url) for url in grupo]
                resultados = await asyncio.gather(*tareas)
                # Count successful insertions
                items_scraped += sum(1 for r in resultados if r)

            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()

            print(f"\n[OK] Proceso terminado")
            print(f"[INFO] Run ID: {scraping_run_id}")
            print(f"[INFO] Items scrapeados: {items_scraped}/{len(enlaces)}")
            print(f"[INFO] Duración: {duration:.2f} segundos")

            # Cerrar navegador
            await browser.close()

            # Return results for orchestrator
            return {
                'status': 'success',
                'items_scraped': items_scraped,
                'total_links': len(enlaces),
                'duration_seconds': duration,
                'message': f'Scraped {items_scraped} new items out of {len(enlaces)} links'
            }

    except Exception as e:
        error_msg = f"Fatal error in scraper: {str(e)}"
        print(f"[ERROR] {error_msg}")
        return {
            'status': 'error',
            'items_scraped': items_scraped,
            'message': error_msg
        }

    finally:
        # Cerrar pool de conexiones
        if db_pool:
            await db_pool.close()
            print("[DB] Conexión a PostgreSQL cerrada")


if __name__ == "__main__":
    asyncio.run(main())
