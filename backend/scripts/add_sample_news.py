"""
Script para agregar 15 noticias de ejemplo a la base de datos.
Ejecutar: python -m scripts.add_sample_news
"""
import asyncio
import sys
from pathlib import Path
from datetime import datetime, timedelta
import random

# Fix for Windows event loop
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db.models import Publication, Agent, ScrapedArticle
from app.db.session import AsyncSessionLocal
from sqlalchemy import select
import hashlib


# 15 noticias de ejemplo variadas
SAMPLE_NEWS = [
    {
        "title": "Récord histórico de inversión en energías renovables en Argentina",
        "summary": "El país alcanza cifras sin precedentes en proyectos de energía solar y eólica, posicionándose como líder regional en transición energética.",
        "body": "Argentina registró un incremento del 45% en inversiones destinadas a proyectos de energía renovable durante el último trimestre. Las provincias de San Juan, Mendoza y Chubut lideran la instalación de nuevos parques solares y eólicos, generando más de 3,000 empleos directos en el sector.",
        "category": "Economía",
        "tags": ["energía", "renovables", "inversión", "medio ambiente"]
    },
    {
        "title": "Nuevo sistema de salud digital reduce tiempos de espera en hospitales públicos",
        "summary": "La implementación de turnos online y expedientes digitales mejora la atención en centros de salud de todo el país.",
        "body": "Más de 200 hospitales públicos adoptaron el nuevo sistema digital de gestión de pacientes, reduciendo los tiempos de espera promedio en un 40%. La plataforma permite acceder a historias clínicas, solicitar turnos y recibir resultados de estudios de forma remota.",
        "category": "Salud",
        "tags": ["salud", "tecnología", "digitalización", "hospitales"]
    },
    {
        "title": "Científicos argentinos desarrollan vacuna contra el dengue de bajo costo",
        "summary": "Un equipo del CONICET logra un avance significativo en la prevención de la enfermedad que afecta a millones en la región.",
        "body": "Investigadores del CONICET presentaron una vacuna contra el dengue que podría producirse a un tercio del costo de las alternativas actuales. Los ensayos clínicos fase 2 muestran una eficacia del 85% en la prevención de los cuatro serotipos del virus.",
        "category": "Ciencia",
        "tags": ["ciencia", "salud", "dengue", "CONICET", "vacuna"]
    },
    {
        "title": "Boom del turismo rural: las estancias registran ocupación récord",
        "summary": "El turismo de estancias y establecimientos rurales experimenta un crecimiento del 60% comparado con el año anterior.",
        "body": "Las estancias y establecimientos de turismo rural en las provincias de Buenos Aires, Córdoba y Entre Ríos reportan niveles de ocupación superiores al 90%. La tendencia se atribuye a la búsqueda de experiencias al aire libre y contacto con la naturaleza post-pandemia.",
        "category": "Turismo",
        "tags": ["turismo", "rural", "economía", "campo"]
    },
    {
        "title": "Startups tecnológicas argentinas captan 200 millones de dólares en inversiones",
        "summary": "El ecosistema de emprendimientos tech continúa en expansión con récord de financiamiento extranjero.",
        "body": "Empresas de tecnología con base en Argentina recibieron inversiones por 200 millones de dólares en el primer semestre del año. Los sectores de fintech, agtech y healthtech concentran el 70% del capital invertido, consolidando al país como hub de innovación en Latinoamérica.",
        "category": "Tecnología",
        "tags": ["startups", "inversión", "tecnología", "innovación"]
    },
    {
        "title": "Plan nacional de reforestación planta 5 millones de árboles nativos",
        "summary": "Iniciativa público-privada busca recuperar bosques degradados y combatir el cambio climático.",
        "body": "El programa de reforestación alcanzó la meta de plantar 5 millones de árboles nativos en zonas afectadas por incendios y deforestación. Más de 10,000 voluntarios participaron en las jornadas de plantación realizadas en 15 provincias durante los últimos seis meses.",
        "category": "Medio Ambiente",
        "tags": ["medio ambiente", "reforestación", "cambio climático", "bosques"]
    },
    {
        "title": "Exportaciones agrícolas crecen 25% impulsadas por la soja y el trigo",
        "summary": "El sector agropecuario registra números positivos con aumento significativo en ventas al exterior.",
        "body": "Las exportaciones de granos alcanzaron los 18,000 millones de dólares en lo que va del año, con incrementos notables en soja (30%) y trigo (20%). China, Brasil y la Unión Europea se mantienen como principales destinos de los productos argentinos.",
        "category": "Economía",
        "tags": ["exportaciones", "agricultura", "economía", "comercio exterior"]
    },
    {
        "title": "Récord de matrícula en carreras de programación y data science",
        "summary": "Las universidades reportan aumento del 80% en inscripciones para carreras tecnológicas.",
        "body": "Instituciones educativas de todo el país registran cifras históricas de estudiantes en carreras relacionadas con programación, ciencia de datos e inteligencia artificial. La demanda del mercado laboral y los salarios competitivos impulsan esta tendencia entre los jóvenes.",
        "category": "Educación",
        "tags": ["educación", "programación", "universidades", "tecnología"]
    },
    {
        "title": "Nueva ley de movilidad sostenible incentiva el uso de bicicletas y transporte público",
        "summary": "Legislación busca reducir emisiones y mejorar la calidad del aire en grandes ciudades.",
        "body": "El Congreso aprobó una ley que establece beneficios fiscales para quienes utilicen medios de transporte sustentables. Incluye subsidios para compra de bicicletas, expansión de ciclovías y modernización de flotas de colectivos con vehículos eléctricos.",
        "category": "Política",
        "tags": ["movilidad", "sustentabilidad", "transporte", "medio ambiente"]
    },
    {
        "title": "Argentina lidera producción de litio en América Latina",
        "summary": "La extracción del mineral estratégico alcanza niveles récord posicionando al país como proveedor clave global.",
        "body": "Las exportaciones de litio superaron las 50,000 toneladas anuales, consolidando a Argentina entre los tres principales productores mundiales. La demanda de baterías para vehículos eléctricos impulsa inversiones millonarias en las provincias del norte.",
        "category": "Economía",
        "tags": ["litio", "minería", "exportaciones", "economía"]
    },
    {
        "title": "Plataforma de telemedicina pública alcanza 2 millones de consultas",
        "summary": "El servicio gratuito de atención médica a distancia se consolida como alternativa accesible para zonas rurales.",
        "body": "La plataforma estatal de telemedicina procesó 2 millones de consultas desde su lanzamiento, brindando atención especializada a pacientes de localidades alejadas de centros urbanos. Más de 1,500 profesionales de la salud participan del programa voluntariamente.",
        "category": "Salud",
        "tags": ["telemedicina", "salud", "tecnología", "acceso"]
    },
    {
        "title": "Descubrimiento paleontológico en Patagonia revela nueva especie de dinosaurio",
        "summary": "Científicos hallan fósiles de un herbívoro gigante que habitó la región hace 90 millones de años.",
        "body": "Un equipo de paleontólogos argentinos descubrió restos fósiles de una especie desconocida de dinosaurio en Neuquén. El ejemplar, bautizado como 'Patagotitan mayorensis', mediría aproximadamente 30 metros de largo y es considerado uno de los más grandes encontrados en Sudamérica.",
        "category": "Ciencia",
        "tags": ["paleontología", "dinosaurios", "Patagonia", "ciencia"]
    },
    {
        "title": "Programa de huertas urbanas comunitarias se expande a 50 ciudades",
        "summary": "Iniciativa promueve la producción de alimentos frescos en espacios públicos recuperados.",
        "body": "El programa nacional de huertas urbanas alcanzó 50 municipios, transformando terrenos en desuso en espacios productivos que abastecen a más de 15,000 familias. Los participantes reciben capacitación en agricultura orgánica y gestión comunitaria.",
        "category": "Medio Ambiente",
        "tags": ["huertas", "agricultura urbana", "sustentabilidad", "comunidad"]
    },
    {
        "title": "Industria del software argentino crece 35% y genera 140,000 empleos",
        "summary": "El sector tecnológico se consolida como uno de los principales motores de la economía del conocimiento.",
        "body": "La industria del software y servicios informáticos reportó un crecimiento del 35% en facturación, alcanzando exportaciones por 7,800 millones de dólares. El sector emplea a 140,000 profesionales y se espera continuar la expansión con incentivos fiscales renovados.",
        "category": "Tecnología",
        "tags": ["software", "tecnología", "empleo", "exportaciones"]
    },
    {
        "title": "Red nacional de bancos de alimentos reduce el desperdicio en 40%",
        "summary": "Organización logra distribuir excedentes de producción a comedores y familias vulnerables.",
        "body": "La Red Argentina de Bancos de Alimentos rescató 12,000 toneladas de alimentos que iban a ser descartados, distribuyéndolos entre 800 organizaciones sociales. El programa involucra a supermercados, productores agrícolas y empresas de la industria alimenticia.",
        "category": "Sociedad",
        "tags": ["solidaridad", "alimentos", "desperdicio", "organizaciones"]
    }
]


async def add_sample_news():
    async with AsyncSessionLocal() as db:
        # Get all agents
        agents = (await db.scalars(select(Agent))).all()

        if not agents:
            print("No hay agentes en la base de datos. Ejecuta primero: python -m scripts.create_agents")
            return

        print(f"Agregando 15 noticias de ejemplo...\n")

        # Base date - start from 3 days ago
        base_date = datetime.now() - timedelta(days=3)

        added_count = 0
        for i, news_data in enumerate(SAMPLE_NEWS):
            # Assign agent in round-robin
            agent = agents[i % len(agents)]

            # Create scraped article first
            text_content = f"{news_data['title']}\n\n{news_data['summary']}\n\n{news_data['body']}"
            text_hash = hashlib.sha256(text_content.encode()).hexdigest()

            scraped = ScrapedArticle(
                source_name="Sample News",
                source_url=f"https://example.com/news/{i+1}",
                title=news_data["title"],
                extracted_text=text_content,
                text_hash=text_hash,
                scraped_at=base_date + timedelta(hours=i * 5)
            )
            db.add(scraped)
            await db.flush()  # Get the scraped article ID

            # Create publication with varying dates (spread over 3 days)
            pub = Publication(
                scraped_article_id=scraped.id,
                state="published",
                title=news_data["title"],
                summary=news_data["summary"],
                body=news_data["body"],
                category=news_data["category"],
                tags=news_data["tags"],
                agent_id=agent.id,
                created_at=base_date + timedelta(hours=i * 5),  # Space them out
                published_at=base_date + timedelta(hours=i * 5)
            )

            db.add(pub)
            added_count += 1
            print(f"[{added_count}/15] {news_data['title'][:60]}...")
            print(f"         Categoría: {news_data['category']} | Agente: {agent.name}")

        await db.commit()
        print(f"\n✓ Se agregaron {added_count} noticias exitosamente!")
        print(f"  Total de agentes usados: {len(agents)}")


if __name__ == "__main__":
    asyncio.run(add_sample_news())
