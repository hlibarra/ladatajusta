"""
Scraper de La Gaceta adaptado para guardar en la tabla scraping_items
Incluye deduplicación automática, hashes SHA-256 y manejo del pipeline
"""

import asyncio
import hashlib
import os
import sys
import json
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
USERNAME = "hugo.l.ibarra@gmail.com"
PASSWORD = "HugoLuis"
URL_ULTIMO_MOMENTO = "https://www.lagaceta.com.ar/ultimo-momento"
INTENTOS_CERRAR_POPUP = 3
INTENTOS_LOGIN = 3
CONCURRENCY = 5

# Database connection
DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", "5432")),
    "database": os.getenv("DB_NAME", "ladatajusta"),
    "user": os.getenv("DB_USER", "ladatajusta"),
    "password": os.getenv("DB_PASSWORD", "ladatajusta"),
}

# Scraper metadata
SCRAPER_NAME = "lagaceta_playwright"
SCRAPER_VERSION = "2.0.0"
SOURCE_MEDIA = "lagaceta"

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


async def verificar_y_cerrar_popup(page):
    """Cierra popups molestos de La Gaceta"""
    for intento in range(INTENTOS_CERRAR_POPUP):
        try:
            if await page.locator("text=Aceptar").is_visible():
                await page.locator("text=Aceptar").click()
                return
            await page.wait_for_timeout(500)
        except:
            pass


async def login(page):
    """Login automático en La Gaceta"""
    for intento in range(INTENTOS_LOGIN):
        try:
            await page.goto("https://cuenta.lagaceta.com.ar/usuarios/acceso/", timeout=60000)
            await page.wait_for_selector("input[name='email']", timeout=5000)
            await page.fill("input[name='email']", USERNAME)
            await page.locator("button:has-text('Ingresar')").click()
            await page.wait_for_selector("input[name='pass']", timeout=10000)
            await page.fill("input[name='pass']", PASSWORD)
            await page.locator("button:has-text('Ingresar')").click()
            await page.wait_for_url("https://www.lagaceta.com.ar/", timeout=20000)
            print("[OK] Login exitoso")
            return
        except Exception as e:
            print(f"[WARN] Intento de login {intento + 1}/{INTENTOS_LOGIN} falló: {e}")
            await verificar_y_cerrar_popup(page)

    # Fallback: ir a home aunque no haya login exitoso
    await page.goto("https://www.lagaceta.com.ar/", timeout=60000)


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
        await page.goto(enlace, timeout=60000)
        await verificar_y_cerrar_popup(page)

        # Scroll para cargar contenido lazy
        for _ in range(8):
            await page.mouse.wheel(0, 1500)
            await page.wait_for_timeout(300)

        # Extraer datos
        await page.wait_for_selector("h1[itemprop='headline'], h1#spktitle", timeout=15000)
        titulo = await page.locator("h1[itemprop='headline'], h1#spktitle").text_content()

        # Resumen
        resumen = ""
        if await page.locator("h2#spksumary").is_visible():
            resumen = await page.locator("h2#spksumary").inner_text()

        # Categoría
        categoria = ""
        if await page.locator("div.breadcrumb a b").is_visible():
            categoria = await page.locator("div.breadcrumb a b").inner_text()

        # Contenido principal
        await page.wait_for_selector("#articleContent", timeout=15000)
        contenido = await page.locator("#articleContent").inner_text()

        # Fecha de publicación
        fecha_str = await page.locator("meta[property='article:published_time']").get_attribute("content")
        article_date = None
        if fecha_str:
            try:
                article_date = datetime.fromisoformat(fecha_str.replace('Z', '+00:00'))
            except:
                pass

        # Calcular hash del contenido
        content_hash = calculate_hash(contenido)

        # Verificar duplicado por contenido
        if await check_duplicate(db_pool, url_hash, content_hash):
            print(f"[SKIP] Duplicado (contenido): {enlace}")
            await page.close()
            return

        # Calcular duración del scraping
        end_time = datetime.now()
        duration_ms = int((end_time - start_time).total_seconds() * 1000)

        # Preparar datos para insertar
        data = {
            'source_media': SOURCE_MEDIA,
            'source_section': categoria or None,
            'source_url': enlace,
            'source_url_normalized': url_normalized,
            'title': titulo.strip() if titulo else None,
            'subtitle': None,  # La Gaceta no tiene subtitle claro
            'summary': resumen.strip() if resumen else None,
            'content': contenido.strip() if contenido else "",
            'author': None,  # TODO: extraer autor si está disponible
            'article_date': article_date,
            'tags': [],  # TODO: extraer tags si están disponibles
            'image_urls': [],  # TODO: extraer imágenes
            'content_hash': content_hash,
            'url_hash': url_hash,
            'scraper_name': SCRAPER_NAME,
            'scraper_version': SCRAPER_VERSION,
            'scraping_run_id': scraping_run_id,
            'scraped_at': start_time,
            'scraping_duration_ms': duration_ms,
            'status': 'scraped',
            'status_message': 'Successfully scraped from La Gaceta',
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

        # Registrar el error en la BD (opcional)
        # TODO: implementar insert de error en scraping_items con status='error'
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

    print(f"[START] Iniciando scraper de La Gaceta")
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
        return

    try:
        # Iniciar Playwright
        async with async_playwright() as p:
            is_headless = os.environ.get("HEADLESS", "true").lower() == "true"
            context = await p.chromium.launch_persistent_context(
                user_data_dir=".user_data",
                headless=is_headless
            )
            page = await context.new_page()

            # Login
            await login(page)
            await verificar_y_cerrar_popup(page)

            # Navegar a "Último Momento"
            await page.goto(URL_ULTIMO_MOMENTO, timeout=60000)
            await verificar_y_cerrar_popup(page)
            await page.mouse.wheel(0, 2000)
            await page.wait_for_timeout(1500)

            # Extraer todos los enlaces de noticias
            enlaces = await page.eval_on_selector_all(
                "a[href^='https://www.lagaceta.com.ar/nota/']",
                "els => els.map(e => e.href).filter(h => h.endsWith('.html'))"
            )
            enlaces = list(dict.fromkeys(enlaces))  # Eliminar duplicados
            print(f"[LINKS] {len(enlaces)} enlaces únicos encontrados")

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

            # Cerrar contexto
            await context.close()

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
