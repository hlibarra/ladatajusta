import asyncio
from playwright.async_api import async_playwright
import csv
import os

USERNAME = "hugo.l.ibarra@gmail.com"
PASSWORD = "HugoLuis"
OUTPUT_CSV = "noticias_lagaceta.csv"
URL_ULTIMO_MOMENTO = "https://www.lagaceta.com.ar/ultimo-momento"
INTENTOS_CERRAR_POPUP = 3
INTENTOS_LOGIN = 3
CONCURRENCY = 5

lock = asyncio.Lock()
existentes = set()

async def verificar_y_cerrar_popup(page):
    for intento in range(INTENTOS_CERRAR_POPUP):
        try:
            if await page.locator("text=Aceptar").is_visible():
                await page.locator("text=Aceptar").click()
                return
            await page.wait_for_timeout(500)
        except:
            pass

async def login(page):
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
            return
        except:
            await verificar_y_cerrar_popup(page)
    await page.goto("https://www.lagaceta.com.ar/", timeout=60000)

async def procesar_noticia(context, enlace):
    global existentes
    if enlace in existentes:
        return
    page = await context.new_page()
    try:
        print(f"🔎 Procesando: {enlace}")
        await page.goto(enlace, timeout=60000)
        await verificar_y_cerrar_popup(page)

        for _ in range(8):
            await page.mouse.wheel(0, 1500)
            await page.wait_for_timeout(300)

        await page.wait_for_selector("h1[itemprop='headline'], h1#spktitle", timeout=15000)
        selector_h1 = page.locator("h1[itemprop='headline'], h1#spktitle")
        titulo = await selector_h1.text_content()

        # NUEVO SELECTOR de resumen
        resumen = ""
        if await page.locator("h2#spksumary").is_visible():
            resumen = await page.locator("h2#spksumary").inner_text()

        # NUEVO SELECTOR de categoría
        categoria = ""
        if await page.locator("div.breadcrumb a b").is_visible():
            categoria = await page.locator("div.breadcrumb a b").inner_text()

        minutos = await page.locator(".timeago").inner_text() if await page.locator(".timeago").is_visible() else ""

        await page.wait_for_selector("#articleContent", timeout=15000)
        contenido = await page.locator("#articleContent").inner_text()
        fecha = await page.locator("meta[property='article:published_time']").get_attribute("content")

        if contenido:
            async with lock:
                with open(OUTPUT_CSV, "a", encoding="utf-8-sig", newline="") as f:
                    writer = csv.writer(f)
                    writer.writerow([enlace, titulo.strip(), resumen.strip(), categoria.strip(), minutos.strip(), fecha, contenido.strip()])
    except Exception as e:
        print(f"⚠️ Error en {enlace}: {e}")
    finally:
        await page.close()

async def main():
    global existentes
    if os.path.exists(OUTPUT_CSV):
        with open(OUTPUT_CSV, "r", encoding="utf-8-sig") as f:
            reader = csv.reader(f)
            next(reader, None)
            for row in reader:
                existentes.add(row[0])
    else:
        with open(OUTPUT_CSV, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["URL", "Título", "Resumen", "Categoría", "Minutos", "Fecha", "Contenido"])

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
            tareas = [procesar_noticia(context, url) for url in grupo]
            await asyncio.gather(*tareas)

        print(f"📦 Proceso terminado. Noticias guardadas en {OUTPUT_CSV}")
        await context.close()

if __name__ == "__main__":
    asyncio.run(main())
