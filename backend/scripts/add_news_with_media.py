"""
Script para agregar noticias de ejemplo con imágenes y videos.
Ejecutar: python -m scripts.add_news_with_media
"""
import asyncio
import sys
from pathlib import Path
from datetime import datetime, timedelta

# Fix for Windows event loop
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db.models import Publication, Agent, ScrapedArticle
from app.db.session import AsyncSessionLocal
from sqlalchemy import select
import hashlib


# Noticias con multimedia
SAMPLE_NEWS_WITH_MEDIA = [
    {
        "title": "La NASA revela nuevas imágenes del telescopio James Webb",
        "category": "Ciencia",
        "tags": ["astronomía", "NASA", "espacio", "tecnología"],
        "sin_vueltas": "El telescopio James Webb captó impresionantes imágenes de la Nebulosa de Carina.",
        "lo_central": "La NASA publicó nuevas imágenes del telescopio espacial James Webb mostrando la Nebulosa de Carina con detalles sin precedentes. Las fotografías revelan regiones de formación estelar nunca antes vistas con tal claridad.",
        "en_profundidad": "La NASA publicó nuevas imágenes capturadas por el telescopio espacial James Webb, mostrando la Nebulosa de Carina con un nivel de detalle sin precedentes en la historia de la astronomía. Las fotografías, tomadas con la cámara infrarroja NIRCam, revelan regiones de formación estelar activa, con columnas de gas y polvo que se elevan entre estrellas recién nacidas. Los científicos destacan que estas imágenes permitirán comprender mejor los procesos de nacimiento estelar y la evolución de las galaxias. El telescopio, lanzado en diciembre de 2021, continúa superando las expectativas de la comunidad científica internacional con descubrimientos que replantean nuestra comprensión del universo temprano.",
        "media": [
            {
                "type": "image",
                "url": "https://images.unsplash.com/photo-1462331940025-496dfbfc7564?w=1200",
                "caption": "Nebulosa de Carina capturada por el telescopio James Webb",
                "order": 0
            },
            {
                "type": "image",
                "url": "https://images.unsplash.com/photo-1543722530-d2c3201371e7?w=1200",
                "caption": "Detalle de región de formación estelar",
                "order": 1
            }
        ]
    },
    {
        "title": "Energías renovables alcanzan récord histórico en Argentina",
        "category": "Economía",
        "tags": ["energía", "renovables", "sustentabilidad", "economía"],
        "sin_vueltas": "Argentina genera 15% de su energía con fuentes renovables, nuevo récord nacional.",
        "lo_central": "Argentina alcanzó un récord histórico al generar el 15% de su energía eléctrica a partir de fuentes renovables. Parques eólicos en la Patagonia y plantas solares en el norte lideran la transición energética del país.",
        "en_profundidad": "Argentina alcanzó un hito histórico al generar el 15% de su matriz energética a partir de fuentes renovables durante el mes de noviembre de 2025, superando la meta del 12% establecida para el año. Los parques eólicos de la Patagonia aportaron el 8% del total, mientras que las plantas solares del NOA contribuyeron con el 5%, y la energía hidráulica el 2% restante. Según datos de CAMMESA, se evitó la emisión de 2.3 millones de toneladas de CO2 equivalente. El crecimiento se atribuye a la puesta en marcha de 12 nuevos parques en Chubut, Río Negro y Neuquén, con inversiones que superan los USD 1,800 millones. El gobierno anunció licitaciones para proyectos que añadirán 3,000 MW adicionales en 2026, consolidando la transición hacia una matriz más limpia.",
        "media": [
            {
                "type": "image",
                "url": "https://images.unsplash.com/photo-1509391366360-2e959784a276?w=1200",
                "caption": "Parque eólico en la Patagonia argentina",
                "order": 0
            },
            {
                "type": "image",
                "url": "https://images.unsplash.com/photo-1508514177221-188b1cf16e9d?w=1200",
                "caption": "Planta solar en el noroeste argentino",
                "order": 1
            }
        ]
    },
    {
        "title": "Descubren ciudad maya oculta en la selva de Guatemala",
        "category": "Cultura",
        "tags": ["arqueología", "historia", "Guatemala", "cultura maya"],
        "sin_vueltas": "Arqueólogos descubrieron una ciudad maya de 1,500 años en la selva guatemalteca.",
        "lo_central": "Un equipo internacional de arqueólogos descubrió una extensa ciudad maya de 1,500 años de antigüedad en la selva de Petén, Guatemala. La ciudad incluye pirámides, plazas y una compleja red de calzadas.",
        "en_profundidad": "Un equipo internacional de arqueólogos liderado por la Universidad de Brown descubrió una extensa ciudad maya de aproximadamente 1,500 años de antigüedad en la densa selva de Petén, Guatemala. El hallazgo fue posible gracias a tecnología LiDAR (detección por luz y radar) que penetró el denso follaje revelando estructuras ocultas durante siglos. La ciudad, temporalmente denominada 'K'awiil', abarca más de 20 km² e incluye al menos 6 pirámides, 3 grandes plazas ceremoniales, un campo de juego de pelota y una red de calzadas elevadas que conectaban distintos sectores urbanos. Los investigadores estiman que pudo albergar entre 40,000 y 60,000 habitantes en su apogeo, entre los años 600 y 900 d.C. Hallazgos preliminares de cerámica y estelas con inscripciones jeroglíficas sugieren que fue un importante centro político y comercial en la región del Petén. El descubrimiento reescribe la comprensión sobre la densidad poblacional y la complejidad urbana de la civilización maya clásica.",
        "media": [
            {
                "type": "image",
                "url": "https://images.unsplash.com/photo-1518638150340-f706e86654de?w=1200",
                "caption": "Vista aérea de las ruinas mayas descubiertas",
                "order": 0
            },
            {
                "type": "image",
                "url": "https://images.unsplash.com/photo-1569163139394-de4798aa62b6?w=1200",
                "caption": "Detalle de inscripciones jeroglíficas encontradas",
                "order": 1
            }
        ]
    }
]


async def add_news_with_media():
    async with AsyncSessionLocal() as db:
        # Get all agents
        agents = (await db.scalars(select(Agent))).all()

        if not agents:
            print("No hay agentes en la base de datos. Ejecuta primero: python -m scripts.create_agents")
            return

        print(f"Agregando {len(SAMPLE_NEWS_WITH_MEDIA)} noticias con multimedia...\\n")

        base_date = datetime.now() - timedelta(hours=3)

        added_count = 0
        for i, news_data in enumerate(SAMPLE_NEWS_WITH_MEDIA):
            # Assign agent in round-robin
            agent = agents[i % len(agents)]

            # Create scraped article first
            text_content = f"{news_data['title']}\\n\\n{news_data['lo_central']}\\n\\n{news_data['en_profundidad']}"
            text_hash = hashlib.sha256(text_content.encode()).hexdigest()

            scraped = ScrapedArticle(
                source_name="Sample News with Media",
                source_url=f"https://example.com/news-media/{i+200}",
                title=news_data["title"],
                extracted_text=text_content,
                text_hash=text_hash,
                scraped_at=base_date + timedelta(hours=i * 2)
            )
            db.add(scraped)
            await db.flush()

            # Create publication with media
            pub = Publication(
                scraped_article_id=scraped.id,
                state="published",
                title=news_data["title"],
                summary=news_data["lo_central"],
                body=news_data["en_profundidad"],
                category=news_data["category"],
                tags=news_data["tags"],
                agent_id=agent.id,
                # Reading levels
                content_sin_vueltas=news_data["sin_vueltas"],
                content_lo_central=news_data["lo_central"],
                content_en_profundidad=news_data["en_profundidad"],
                # Media
                media=news_data["media"],
                created_at=base_date + timedelta(hours=i * 2),
                published_at=base_date + timedelta(hours=i * 2)
            )

            db.add(pub)
            added_count += 1
            print(f"[{added_count}/{len(SAMPLE_NEWS_WITH_MEDIA)}] {news_data['title'][:60]}...")
            print(f"         Categoria: {news_data['category']} | Agente: {agent.name}")
            print(f"         Media: {len(news_data['media'])} items\\n")

        await db.commit()
        print(f"\\n[OK] Se agregaron {added_count} noticias con multimedia exitosamente!")


if __name__ == "__main__":
    asyncio.run(add_news_with_media())
