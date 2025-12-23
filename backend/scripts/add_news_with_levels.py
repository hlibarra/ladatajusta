"""
Script para agregar noticias de ejemplo con los 3 niveles de lectura.
Ejecutar: python -m scripts.add_news_with_levels
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


# Noticias con contenido diferenciado por nivel
SAMPLE_NEWS_WITH_LEVELS = [
    {
        "title": "Argentina aprueba ley de movilidad sustentable",
        "category": "Política",
        "tags": ["movilidad", "sustentabilidad", "transporte", "medio ambiente"],
        "sin_vueltas": "El Congreso aprobó una ley que incentiva el uso de bicicletas y transporte público.",
        "lo_central": "El Congreso aprobó una ley de movilidad sustentable con 142 votos a favor. Incluye subsidios para compra de bicicletas, expansión de ciclovías y renovación de flotas de colectivos con vehículos eléctricos. Beneficia a quienes usen medios de transporte no contaminantes.",
        "en_profundidad": "El Congreso aprobó la Ley de Movilidad Sustentable con 142 votos a favor y 98 en contra, tras 6 meses de debate. La normativa establece beneficios fiscales para quienes utilicen medios de transporte no contaminantes, como reducción del 20% en impuestos para compradores de bicicletas eléctricas y pases gratuitos de transporte público para quienes abandonen el auto particular. Se destinarán $50,000 millones para expandir 500 km de ciclovías en 40 ciudades y modernizar 2,000 colectivos con tecnología eléctrica. La ley también crea un Fondo Nacional de Movilidad Verde financiado con un impuesto del 5% a combustibles fósiles. Entidades ambientalistas celebraron la medida, mientras sectores del transporte privado cuestionan el impacto en la industria automotriz. La implementación comenzará en marzo de 2026."
    },
    {
        "title": "Descubren fósil de dinosaurio gigante en Neuquén",
        "category": "Ciencia",
        "tags": ["paleontología", "dinosaurios", "Patagonia", "ciencia"],
        "sin_vueltas": "Paleontólogos hallaron restos de un dinosaurio de 30 metros de largo en la Patagonia.",
        "lo_central": "Un equipo de paleontólogos argentinos descubrió fósiles de una nueva especie de dinosaurio herbívoro en Neuquén. El ejemplar, bautizado 'Patagotitan neuquensis', mediría 30 metros de largo y es uno de los más grandes encontrados en Sudamérica. Vivió hace 90 millones de años.",
        "en_profundidad": "Un equipo de 12 paleontólogos del CONICET y el Museo Paleontológico Egidio Feruglio descubrió restos fósiles de una nueva especie de dinosaurio en la formación geológica Candeleros, cerca de Plaza Huincul, Neuquén. El ejemplar, denominado 'Patagotitan neuquensis', habría vivido hace 90 millones de años durante el período Cretácico Superior. Los restos incluyen un fémur de 2.4 metros, vértebras dorsales completas y fragmentos de costillas que permiten estimar un largo total de 30 metros y un peso aproximado de 70 toneladas. Se trata de un saurópodo herbívoro de cuello largo, similar al Argentinosaurus pero con características anatómicas únicas en sus vértebras caudales. El descubrimiento se produjo en 2023 pero recién ahora se publicó en la revista Nature tras completar la datación y el análisis comparativo con otras especies. Los científicos destacan que la región neuquina fue un ecosistema rico en megafauna durante ese período. El fósil será exhibido en el museo a partir de abril de 2026."
    },
    {
        "title": "Récord de exportaciones de litio posiciona a Argentina como líder regional",
        "category": "Economía",
        "tags": ["litio", "minería", "exportaciones", "economía"],
        "sin_vueltas": "Argentina exportó 50,000 toneladas de litio este año, cifra récord histórica.",
        "lo_central": "Las exportaciones de litio superaron las 50,000 toneladas anuales, consolidando a Argentina entre los tres principales productores mundiales. La demanda de baterías para vehículos eléctricos impulsa inversiones millonarias en proyectos mineros del norte del país.",
        "en_profundidad": "Argentina alcanzó un récord histórico en exportaciones de litio con 50,127 toneladas durante 2025, representando un incremento del 35% respecto al año anterior. El país se posiciona como tercer productor global detrás de Australia y Chile, concentrando el 18% de las reservas mundiales conocidas. Las provincias de Catamarca, Jujuy y Salta lideran la extracción, con 14 proyectos operativos y 32 en fase de exploración avanzada. El precio promedio del carbonato de litio se ubicó en USD 28,000 por tonelada, generando ingresos por USD 1,400 millones en divisas. La demanda global creció un 40% impulsada por la industria de vehículos eléctricos, especialmente de fabricantes chinos, europeos y estadounidenses. Empresas como Livent, Allkem y Ganfeng invirtieron USD 3,200 millones en nuevas plantas de procesamiento. El gobierno provincial de Jujuy implementó un régimen de regalías del 3% destinado a infraestructura y programas sociales. Organizaciones ambientalistas advierten sobre el consumo hídrico de los proyectos, que utilizan hasta 500,000 litros de agua por tonelada extraída en zonas áridas. El sector generó 12,000 empleos directos y 35,000 indirectos. Se espera que para 2028 Argentina duplique su capacidad productiva con la entrada en operación de 8 nuevos yacimientos."
    }
]


async def add_news_with_levels():
    async with AsyncSessionLocal() as db:
        # Get all agents
        agents = (await db.scalars(select(Agent))).all()

        if not agents:
            print("No hay agentes en la base de datos. Ejecuta primero: python -m scripts.create_agents")
            return

        print(f"Agregando {len(SAMPLE_NEWS_WITH_LEVELS)} noticias con 3 niveles de lectura...\n")

        base_date = datetime.now() - timedelta(hours=6)

        added_count = 0
        for i, news_data in enumerate(SAMPLE_NEWS_WITH_LEVELS):
            # Assign agent in round-robin
            agent = agents[i % len(agents)]

            # Create scraped article first
            text_content = f"{news_data['title']}\n\n{news_data['lo_central']}\n\n{news_data['en_profundidad']}"
            text_hash = hashlib.sha256(text_content.encode()).hexdigest()

            scraped = ScrapedArticle(
                source_name="Sample News with Levels",
                source_url=f"https://example.com/news-levels/{i+100}",
                title=news_data["title"],
                extracted_text=text_content,
                text_hash=text_hash,
                scraped_at=base_date + timedelta(hours=i * 2)
            )
            db.add(scraped)
            await db.flush()

            # Create publication with all reading levels
            pub = Publication(
                scraped_article_id=scraped.id,
                state="published",
                title=news_data["title"],
                summary=news_data["lo_central"],  # Use "Lo central" as summary
                body=news_data["en_profundidad"],  # Use "En profundidad" as body
                category=news_data["category"],
                tags=news_data["tags"],
                agent_id=agent.id,
                # Reading levels
                content_sin_vueltas=news_data["sin_vueltas"],
                content_lo_central=news_data["lo_central"],
                content_en_profundidad=news_data["en_profundidad"],
                created_at=base_date + timedelta(hours=i * 2),
                published_at=base_date + timedelta(hours=i * 2)
            )

            db.add(pub)
            added_count += 1
            print(f"[{added_count}/{len(SAMPLE_NEWS_WITH_LEVELS)}] {news_data['title'][:60]}...")
            print(f"         Categoría: {news_data['category']} | Agente: {agent.name}")
            print(f"         ✓ 3 niveles: Sin vueltas ({len(news_data['sin_vueltas'])} chars) | Lo central ({len(news_data['lo_central'])} chars) | En profundidad ({len(news_data['en_profundidad'])} chars)\n")

        await db.commit()
        print(f"\n✓ Se agregaron {added_count} noticias con niveles de lectura exitosamente!")


if __name__ == "__main__":
    asyncio.run(add_news_with_levels())
