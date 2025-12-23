"""
Script para agregar más noticias con imágenes y videos variados.
Ejecutar: python -m scripts.add_more_media_news
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


# Noticias con multimedia variada (imágenes y videos)
MORE_NEWS_WITH_MEDIA = [
    {
        "title": "Argentina clasifica al Mundial de Fútbol 2026 con goleada histórica",
        "category": "Deportes",
        "tags": ["fútbol", "mundial", "deportes", "selección argentina"],
        "sin_vueltas": "Argentina goleó 5-0 a Brasil y clasificó al Mundial 2026.",
        "lo_central": "La selección argentina clasificó al Mundial 2026 con una goleada histórica 5-0 ante Brasil en el Monumental. Messi marcó un triplete en lo que podría ser su última clasificación mundialista.",
        "en_profundidad": "La selección argentina selló su clasificación al Mundial 2026 con una goleada histórica 5-0 ante Brasil en el Estadio Monumental. Lionel Messi fue la gran figura con un triplete, mientras que Julián Álvarez y Lautaro Martínez completaron el marcador. Con este resultado, Argentina suma 38 puntos y se asegura uno de los primeros lugares en las eliminatorias sudamericanas. Los 83,000 espectadores presentes fueron testigos de un partido perfecto del equipo de Scaloni, que dominó desde el primer minuto. Messi, de 38 años, declaró que 'este podría ser mi último proceso clasificatorio, quiero disfrutar cada momento'. El próximo desafío será preparar el equipo pensando en defender el título obtenido en Qatar 2022.",
        "media": [
            {
                "type": "image",
                "url": "https://images.unsplash.com/photo-1522778119026-d647f0596c20?w=1200",
                "caption": "Festejo de la selección argentina tras la goleada",
                "order": 0
            },
            {
                "type": "image",
                "url": "https://images.unsplash.com/photo-1579952363873-27f3bade9f55?w=1200",
                "caption": "Messi celebra uno de sus tres goles",
                "order": 1
            },
            {
                "type": "video",
                "url": "https://www.youtube.com/embed/jNQXAC9IVRw",
                "caption": "Resumen del partido Argentina vs Brasil (video de ejemplo)",
                "order": 2
            }
        ]
    },
    {
        "title": "Innovación tecnológica: Argentina lanza su primer satélite de comunicaciones 6G",
        "category": "Tecnología",
        "tags": ["tecnología", "satélite", "innovación", "5G", "telecomunicaciones"],
        "sin_vueltas": "Argentina lanzó su primer satélite 6G desde Cabo Cañaveral.",
        "lo_central": "Argentina lanzó exitosamente ARSAT-4, su primer satélite de comunicaciones 6G, desde Cabo Cañaveral. El satélite proveerá conectividad de alta velocidad a zonas rurales y remotas del país.",
        "en_profundidad": "Argentina alcanzó un hito tecnológico al lanzar ARSAT-4, su primer satélite de comunicaciones con tecnología 6G, desde la base de Cabo Cañaveral en Florida. El proyecto, desarrollado por INVAP y ARSAT con una inversión de USD 320 millones, posicionará al país a la vanguardia de las telecomunicaciones satelitales en Latinoamérica. El satélite, que pesa 3,200 kg y tiene una vida útil estimada de 15 años, proveerá conectividad de alta velocidad (hasta 10 Gbps) a zonas rurales y remotas de Argentina que actualmente carecen de infraestructura terrestre. Además, permitirá mejorar los servicios de telefonía móvil, transmisión de datos e internet en todo el territorio nacional. El ministro de Ciencia destacó que 'este es un paso fundamental hacia la soberanía tecnológica y la reducción de la brecha digital'. El satélite alcanzó su órbita geoestacionaria exitosamente y comenzará operaciones comerciales en marzo de 2026.",
        "media": [
            {
                "type": "video",
                "url": "https://www.youtube.com/embed/0qo78R_yYFA",
                "caption": "Lanzamiento del cohete con el satélite ARSAT-4 (video de ejemplo)",
                "order": 0
            },
            {
                "type": "image",
                "url": "https://images.unsplash.com/photo-1516849841032-87cbac4d88f7?w=1200",
                "caption": "Satélite ARSAT-4 en fase de ensamblaje",
                "order": 1
            },
            {
                "type": "image",
                "url": "https://images.unsplash.com/photo-1451187580459-43490279c0fa?w=1200",
                "caption": "Centro de control de ARSAT monitoreando el lanzamiento",
                "order": 2
            }
        ]
    },
    {
        "title": "Festival Internacional de Cine de Mar del Plata: película argentina gana la Competencia Oficial",
        "category": "Cultura",
        "tags": ["cine", "cultura", "Mar del Plata", "festival"],
        "sin_vueltas": "Película argentina 'El Viento del Sur' ganó el festival de cine de Mar del Plata.",
        "lo_central": "'El Viento del Sur', dirigida por Lucía Fernández, ganó el premio a Mejor Película en el Festival Internacional de Cine de Mar del Plata. La cinta aborda la vida de trabajadores rurales en la Patagonia.",
        "en_profundidad": "'El Viento del Sur', dirigida por la cineasta cordobesa Lucía Fernández, se consagró como la gran ganadora del 39° Festival Internacional de Cine de Mar del Plata al llevarse el Astor de Oro a Mejor Película en la Competencia Oficial. La cinta, rodada íntegramente en la Patagonia argentina con un presupuesto ajustado de ARS 180 millones, narra la historia de tres generaciones de trabajadores rurales que enfrentan los desafíos del cambio climático y la migración hacia las ciudades. El jurado, presidido por el director español Pedro Almodóvar, destacó 'la sensibilidad y autenticidad con que retrata una realidad invisibilizada del interior argentino'. Además del premio principal, la actriz Sofía Gala Castiglione recibió el Astor de Plata a Mejor Actriz por su interpretación. La película se estrenará comercialmente en marzo de 2026 y ya fue seleccionada para representar a Argentina en la categoría de Mejor Película Internacional en los premios Oscar.",
        "media": [
            {
                "type": "image",
                "url": "https://images.unsplash.com/photo-1485846234645-a62644f84728?w=1200",
                "caption": "Escena de la película ganadora 'El Viento del Sur'",
                "order": 0
            },
            {
                "type": "image",
                "url": "https://images.unsplash.com/photo-1574267432644-f610bc5cb485?w=1200",
                "caption": "La directora Lucía Fernández recibiendo el Astor de Oro",
                "order": 1
            },
            {
                "type": "video",
                "url": "https://www.youtube.com/embed/YE7VzlLtp-4",
                "caption": "Tráiler oficial de 'El Viento del Sur' (video de ejemplo)",
                "order": 2
            }
        ]
    },
    {
        "title": "Récord turístico: Cataratas del Iguazú recibió 2 millones de visitantes en 2025",
        "category": "Turismo",
        "tags": ["turismo", "Iguazú", "naturaleza", "Misiones"],
        "sin_vueltas": "Cataratas del Iguazú recibió 2 millones de turistas en 2025, cifra récord.",
        "lo_central": "El Parque Nacional Iguazú cerró 2025 con un récord histórico de 2 millones de visitantes. El 45% fueron turistas extranjeros, principalmente de Brasil, Estados Unidos y Europa.",
        "en_profundidad": "El Parque Nacional Iguazú cerró el año 2025 con un récord histórico de 2 millones de visitantes, superando en un 28% la cifra del año anterior y consolidándose como el principal destino turístico de Argentina. Según datos de la Administración de Parques Nacionales, el 45% de los visitantes fueron extranjeros, principalmente de Brasil (680,000), Estados Unidos (320,000) y países europeos (280,000). El aumento se atribuye a mejoras en la infraestructura del parque, la promoción internacional intensiva y la recuperación del turismo post-pandemia. El gobernador de Misiones destacó que el sector turístico generó más de 35,000 empleos directos e indirectos en la provincia. Las Cataratas, declaradas Patrimonio de la Humanidad por UNESCO y una de las Siete Maravillas Naturales del Mundo, continúan siendo un ícono del turismo argentino. Para 2026 se planean inversiones de ARS 800 millones en nuevos senderos ecológicos y centros de interpretación ambiental.",
        "media": [
            {
                "type": "image",
                "url": "https://images.unsplash.com/photo-1612737376080-f3c96eed1d04?w=1200",
                "caption": "Vista panorámica de las Cataratas del Iguazú",
                "order": 0
            },
            {
                "type": "image",
                "url": "https://images.unsplash.com/photo-1580933073521-dc49ac0d4e6a?w=1200",
                "caption": "Turistas en las pasarelas del Parque Nacional",
                "order": 1
            },
            {
                "type": "image",
                "url": "https://images.unsplash.com/photo-1609137144813-7d9921338f24?w=1200",
                "caption": "La Garganta del Diablo, principal atractivo del parque",
                "order": 2
            },
            {
                "type": "video",
                "url": "https://www.youtube.com/embed/STjsRBuAOBM",
                "caption": "Recorrido aéreo por las Cataratas del Iguazú (video de ejemplo)",
                "order": 3
            }
        ]
    },
    {
        "title": "Breakthrough en medicina: desarrollan vacuna argentina contra el dengue con 95% de efectividad",
        "category": "Salud",
        "tags": ["salud", "medicina", "vacuna", "dengue", "ciencia"],
        "sin_vueltas": "Científicos argentinos desarrollaron vacuna contra el dengue con 95% de efectividad.",
        "lo_central": "El Instituto Leloir anunció el desarrollo de una vacuna argentina contra el dengue con 95% de efectividad en ensayos clínicos fase III. Protege contra los cuatro serotipos del virus con una sola dosis.",
        "en_profundidad": "El Instituto de Investigaciones Bioquímicas de Buenos Aires (Instituto Leloir) anunció el exitoso desarrollo de una vacuna argentina contra el dengue que alcanzó un 95% de efectividad en ensayos clínicos de fase III realizados durante dos años con 18,000 voluntarios en Argentina, Brasil y Paraguay. La vacuna, denominada 'DENGvax-AR', presenta dos ventajas revolucionarias: protege contra los cuatro serotipos del virus del dengue con una sola dosis y no requiere cadena de frío estricta, facilitando su distribución en zonas remotas. El equipo liderado por la Dra. María Fernanda Guzmán utilizó tecnología de ARN mensajero combinada con vectores virales atenuados. Los resultados, publicados en la revista The Lancet, mostraron que la inmunidad se mantiene efectiva por al menos 5 años. El Ministerio de Salud estima que la vacuna podría estar disponible gratuitamente en el calendario nacional a partir de julio de 2026, beneficiando especialmente a las provincias del norte argentino donde el dengue es endémico. La OMS ya expresó interés en evaluar la vacuna para uso global.",
        "media": [
            {
                "type": "image",
                "url": "https://images.unsplash.com/photo-1584118624012-df056829fbd0?w=1200",
                "caption": "Investigadores del Instituto Leloir trabajando en el laboratorio",
                "order": 0
            },
            {
                "type": "video",
                "url": "https://www.youtube.com/embed/OpEB6hCpIGM",
                "caption": "Conferencia de prensa sobre el desarrollo de la vacuna (video de ejemplo)",
                "order": 1
            },
            {
                "type": "image",
                "url": "https://images.unsplash.com/photo-1532187863486-abf9dbad1b69?w=1200",
                "caption": "Viales de la vacuna DENGvax-AR listos para distribución",
                "order": 2
            }
        ]
    }
]


async def add_more_media_news():
    async with AsyncSessionLocal() as db:
        # Get all agents
        agents = (await db.scalars(select(Agent))).all()

        if not agents:
            print("No hay agentes en la base de datos. Ejecuta primero: python -m scripts.create_agents")
            return

        print(f"Agregando {len(MORE_NEWS_WITH_MEDIA)} noticias con multimedia variada...\n")

        base_date = datetime.now() - timedelta(hours=12)

        added_count = 0
        for i, news_data in enumerate(MORE_NEWS_WITH_MEDIA):
            # Assign agent in round-robin
            agent = agents[i % len(agents)]

            # Create scraped article first
            text_content = f"{news_data['title']}\n\n{news_data['lo_central']}\n\n{news_data['en_profundidad']}"
            text_hash = hashlib.sha256(text_content.encode()).hexdigest()

            scraped = ScrapedArticle(
                source_name="Sample News with Mixed Media",
                source_url=f"https://example.com/news-media-mix/{i+300}",
                title=news_data["title"],
                extracted_text=text_content,
                text_hash=text_hash,
                scraped_at=base_date + timedelta(hours=i * 3)
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
                created_at=base_date + timedelta(hours=i * 3),
                published_at=base_date + timedelta(hours=i * 3)
            )

            db.add(pub)
            added_count += 1

            media_types = []
            for m in news_data["media"]:
                media_types.append(m["type"])
            media_summary = f"{media_types.count('image')} imgs, {media_types.count('video')} videos"

            print(f"[{added_count}/{len(MORE_NEWS_WITH_MEDIA)}] {news_data['title'][:55]}...")
            print(f"         Categoria: {news_data['category']} | Agente: {agent.name}")
            print(f"         Media: {len(news_data['media'])} items ({media_summary})\n")

        await db.commit()
        print(f"\n[OK] Se agregaron {added_count} noticias con multimedia exitosamente!")
        print("\nEjecuta: python -m scripts.list_publications_with_media")


if __name__ == "__main__":
    asyncio.run(add_more_media_news())
