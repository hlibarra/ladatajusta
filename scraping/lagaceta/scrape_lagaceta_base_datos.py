import asyncio
from playwright.async_api import async_playwright
import asyncpg
from datetime import datetime
from dateutil import parser

# Configuración base de datos
DB_CONFIG = {
    "user": "postgres",
    "password": "hugoluis",
    "database": "datajusta",
    "host": "localhost",
    "port": 5432,
}

# Otros parámetros
URL_ULTIMO_MOMENTO = "https://www.lagaceta.com.ar/ultimo-momento"
CONCURRENCY = 5

async def crear_tabla(conn):
    await conn.execute("""
    CREATE TABLE IF NOT EXISTS noticias_scrapeadas (
        id SERIAL PRIMARY KEY,
        url TEXT UNIQUE NOT NULL,
        titulo TEXT,
        resumen TEXT,
        resumen_ia TEXT,
        categoria TEXT,
        minutos TEXT,
        fecha TIMESTAMP,
        contenido TEXT,
        publicada BOOLEAN DEFAULT FALSE,
        fecha_ingreso TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

async def verificar_y_cerrar_popup(page):
    for _ in range(3):
        try:
            if await page.locator("text=Aceptar").is_visible():
                await page.locator("text=Aceptar").click()
                return
            await page.wait_for_timeout(500)
        except:
            pass

async def login(page):
    for _ in range(3):
        try:
            await page.goto("https://cuenta.lagaceta.com.ar/usuarios/acceso/", timeout=60000)
            await page.wait_for_selector("input[name='email']", timeout=5000)
            await page.fill("input[name='email']", "hugo.l.ibarra@gmail.com")
            await page.locator("button:has-text('Ingresar')").click()
            await page.wait_for_selector("input[name='pass']", timeout=10000)
            await page.fill("input[name='pass']", "HugoLuis")
            await page.locator("button:has-text('Ingresar')").click()
            await page.wait_for_url("https://www.lagaceta.com.ar/", timeout=20000)
            return
        except:
            await verificar_y_cerrar_popup(page)
    await page.goto("https://www.lagaceta.com.ar/", timeout=60000)

async def guardar_en_db(conn, noticia):
    query = """
    INSERT INTO noticias_scrapeadas
    (url, titulo, resumen, categoria, minutos, fecha, contenido)
    VALUES ($1, $2, $3, $4, $5, $6, $7)
    ON CONFLICT (url) DO NOTHING
    """
    await conn.execute(query, *noticia)

async def procesar_noticia(context, url, conn):
    page = await context.new_page()
    try:
        await page.goto(url, timeout=60000)
        await verificar_y_cerrar_popup(page)

        for _ in range(8):
            await page.mouse.wheel(0, 1500)
            await page.wait_for_timeout(300)

        await page.wait_for_selector("h1[itemprop='headline'], h1#spktitle", timeout=15000)
        titulo = await page.locator("h1[itemprop='headline'], h1#spktitle").text_content()

        resumen = ""
        if await page.locator("h2#spksumary").is_visible():
            resumen = await page.locator("h2#spksumary").inner_text()

        categoria = ""
        if await page.locator("div.breadcrumb a b").is_visible():
            categoria = await page.locator("div.breadcrumb a b").inner_text()

        minutos = await page.locator(".timeago").inner_text() if await page.locator(".timeago").is_visible() else ""

        await page.wait_for_selector("#articleContent", timeout=15000)
        contenido = await page.locator("#articleContent").inner_text()

        fecha_meta = await page.locator("meta[property='article:published_time']").get_attribute("content")
        fecha = None
        if fecha_meta:
            try:
                fecha = parser.isoparse(fecha_meta).replace(tzinfo=None)
            except Exception as e:
                print(f"⚠️ Fecha inválida en {url}: {fecha_meta} – {e}")
                fecha = None

        noticia = [url, titulo.strip(), resumen.strip(), categoria.strip(), minutos.strip(), fecha, contenido.strip()]
        await guardar_en_db(conn, noticia)
    except Exception as e:
        raise Exception(f"{url} → {str(e)}")
    finally:
        await page.close()

async def main():
    conn = await asyncpg.connect(**DB_CONFIG)
    await crear_tabla(conn)

    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(user_data_dir=".user_data", headless=False)
        page = await context.new_page()
        await login(page)
        await verificar_y_cerrar_popup(page)

        await page.goto(URL_ULTIMO_MOMENTO, timeout=60000)
        await verificar_y_cerrar_popup(page)
        await page.mouse.wheel(0, 2000)
        await page.wait_for_timeout(1500)

        enlaces = await page.eval_on_selector_all(
            "a[href^='https://www.lagaceta.com.ar/nota/']",
            "els => els.map(e => e.href).filter(h => h.endsWith('.html'))"
        )
        enlaces = list(dict.fromkeys(enlaces))
        print(f"🔗 {len(enlaces)} enlaces únicos encontrados.")

        for i in range(0, len(enlaces), CONCURRENCY):
            grupo = enlaces[i:i + CONCURRENCY]
            tareas = [procesar_noticia(context, url, conn) for url in grupo]
            resultados = await asyncio.gather(*tareas, return_exceptions=True)
            for j, resultado in enumerate(resultados):
                if isinstance(resultado, Exception):
                    print(f"❌ Error procesando {grupo[j]}: {resultado}")

        await conn.close()
        await context.close()
        print("✅ Scraping finalizado y guardado en PostgreSQL.")

if __name__ == "__main__":
    asyncio.run(main())
