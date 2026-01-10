"""
Script para crear datos de prueba en la tabla scraping_items.
Útil para testear la interfaz de admin.

Uso:
    cd backend
    python -m scripts.seed_scraping_items
"""
import asyncio
import random
import uuid
from datetime import datetime, timedelta

import httpx

# Configuración
API_BASE_URL = "http://localhost:8000/api"
NUM_ITEMS = 10  # Número de items a crear

# Datos de ejemplo
MEDIOS = ["lagaceta", "clarin", "infobae", "lanacion", "pagina12"]
SECCIONES = ["politica", "economia", "deportes", "sociedad", "cultura", "tecnologia"]
ESTADOS = ["scraped", "ready_for_ai", "ai_completed", "error", "published"]

TITULOS = [
    "Gobierno anuncia nuevas medidas económicas para el próximo trimestre",
    "Histórica victoria del equipo local en el torneo internacional",
    "Científicos descubren nueva especie en la región",
    "Cambios importantes en la legislación laboral",
    "Crisis energética: se esperan cortes programados",
    "Avances tecnológicos revolucionan la industria agrícola",
    "Escándalo político sacude al Congreso",
    "Inflación muestra signos de desaceleración según últimos datos",
    "Festival cultural reúne a miles de personas",
    "Alerta climática: se esperan tormentas severas",
    "Nueva inversión extranjera genera empleos",
    "Debate sobre reforma educativa divide opiniones",
    "Récord histórico en exportaciones del sector",
    "Protestas sociales exigen mejores condiciones",
    "Innovación tecnológica transforma el sector salud",
]

CONTENIDOS = [
    "En una conferencia de prensa realizada esta mañana, autoridades anunciaron un paquete de medidas destinadas a reactivar la economía. Las medidas incluyen incentivos fiscales y reducción de tasas de interés.",
    "El equipo local consiguió una victoria histórica al vencer por 3 a 2 en la final del torneo. Miles de hinchas celebraron en las calles el logro del equipo.",
    "Un grupo de investigadores descubrió una nueva especie que habita en la región norte del país. El hallazgo representa un avance importante para la ciencia.",
    "El Congreso aprobó modificaciones significativas a la ley laboral. Los cambios entrarán en vigencia el próximo mes y afectarán a millones de trabajadores.",
    "Debido a problemas en el suministro, se esperan cortes de energía programados durante las próximas semanas. Las autoridades piden a la población reducir el consumo.",
]


def generate_hash(text: str) -> str:
    """Genera un hash SHA-256 simple (no normalizado, solo para testing)"""
    import hashlib
    return hashlib.sha256(text.encode()).hexdigest()


async def create_sample_item(session: httpx.AsyncClient, index: int) -> dict:
    """Crea un item de prueba"""
    medio = random.choice(MEDIOS)
    seccion = random.choice(SECCIONES)
    titulo = random.choice(TITULOS)
    contenido = random.choice(CONTENIDOS)
    estado = random.choice(ESTADOS)

    # Crear URL única
    url = f"https://www.{medio}.com.ar/nota/{index}/{seccion}/test-article-{index}"

    # Fecha aleatoria en los últimos 7 días
    days_ago = random.randint(0, 7)
    hours_ago = random.randint(0, 23)
    article_date = datetime.utcnow() - timedelta(days=days_ago, hours=hours_ago)
    scraped_at = article_date + timedelta(hours=random.randint(1, 4))

    # Datos del item
    item = {
        "source_media": medio,
        "source_section": seccion,
        "source_url": url,
        "source_url_normalized": url.lower(),
        "canonical_url": None,
        "title": f"{titulo} - {index}",
        "subtitle": f"Detalles sobre {titulo.lower()}",
        "summary": f"Resumen: {contenido[:100]}...",
        "content": contenido * 3,  # Contenido más largo
        "raw_html": f"<html><body><h1>{titulo}</h1><p>{contenido}</p></body></html>",
        "author": random.choice(["Juan Pérez", "María González", "Carlos Rodríguez", "Ana Martínez", None]),
        "article_date": article_date.isoformat(),
        "tags": random.sample(["política", "economía", "sociedad", "argentina", "actualidad"], k=random.randint(1, 3)),
        "image_urls": [f"https://example.com/image{i}.jpg" for i in range(random.randint(0, 3))],
        "video_urls": [],
        "content_hash": generate_hash(contenido + str(index)),
        "url_hash": generate_hash(url),
        "scraper_name": "test_scraper",
        "scraper_version": "1.0.0",
        "scraping_run_id": None,
        "scraping_duration_ms": random.randint(500, 3000),
        "scraper_ip_address": None,
        "scraper_user_agent": "TestScraper/1.0",
        "extra_metadata": {"test": True, "batch": "seed_script"},
    }

    # Crear item
    response = await session.post(f"{API_BASE_URL}/scraping-items/upsert", json=item)

    if response.status_code != 200:
        print(f"❌ Error creando item {index}: {response.status_code} - {response.text}")
        return None

    created_item = response.json()
    item_id = created_item["id"]

    # Si el estado no es "scraped", actualizar
    if estado != "scraped":
        update_data = {"status": estado}

        # Agregar datos de IA si está en estados avanzados
        if estado in ["ai_completed", "ready_to_publish", "published"]:
            update_data.update({
                "ai_title": f"IA: {titulo} - {index}",
                "ai_summary": f"Resumen generado por IA: {contenido[:80]}...",
                "ai_tags": random.sample(["política", "economía", "sociedad", "tecnología"], k=2),
                "ai_category": seccion,
                "ai_model": "gpt-4o-mini",
                "ai_tokens_used": random.randint(800, 2000),
                "ai_cost_usd": round(random.uniform(0.001, 0.01), 6),
            })

        # Agregar error si el estado es error
        if estado == "error":
            update_data.update({
                "last_error": "Error de prueba: Timeout al procesar contenido",
                "error_trace": "Traceback (fake):\n  File 'test.py', line 123\n    raise TimeoutError()",
            })

        # Actualizar
        await session.patch(f"{API_BASE_URL}/scraping-items/{item_id}", json=update_data)

    return created_item


async def main():
    """Función principal"""
    print("=" * 60)
    print("  Seed Script - Crear Items de Prueba")
    print("=" * 60)
    print(f"\nCreando {NUM_ITEMS} items de prueba...")
    print()

    async with httpx.AsyncClient(timeout=30.0) as session:
        # Crear items
        created = 0
        failed = 0

        for i in range(1, NUM_ITEMS + 1):
            print(f"  [{i}/{NUM_ITEMS}] Creando item...", end=" ")

            item = await create_sample_item(session, i)

            if item:
                print(f"✅ {item['title'][:50]}... (Estado: {item['status']})")
                created += 1
            else:
                print("❌ Error")
                failed += 1

            # Pequeño delay para no saturar
            await asyncio.sleep(0.1)

    print()
    print("=" * 60)
    print(f"  ✅ Creados: {created}")
    print(f"  ❌ Fallidos: {failed}")
    print("=" * 60)
    print()
    print("🎉 ¡Datos de prueba creados!")
    print()
    print("Ahora puedes ver los items en:")
    print("  👉 http://localhost:4321/admin/scraping")
    print()


if __name__ == "__main__":
    asyncio.run(main())
