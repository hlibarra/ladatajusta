"""
Script para insertar publicaciones de ejemplo.
Ejecutar: python -m scripts.insert_sample_publications
"""
import asyncio
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Fix for Windows event loop
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import hashlib

from app.db.models import Publication, ScrapedArticle
from app.db.session import AsyncSessionLocal
from app.db.init_db import init_db


async def insert_sample_publications():
    # Initialize database tables first
    await init_db()

    async with AsyncSessionLocal() as db:
        # Sample data
        sample_data = [
            {
                "title": "Nueva ley de transparencia entra en vigor",
                "summary": "El Congreso aprobó una nueva ley que obliga a todas las entidades públicas a publicar sus presupuestos en línea.",
                "body": "La nueva legislación marca un hito en la transparencia gubernamental. A partir del próximo mes, todas las instituciones del Estado deberán publicar detalladamente sus ingresos y gastos en portales web accesibles al público. Esta medida busca combatir la corrupción y permitir que los ciudadanos fiscalicen el uso de los recursos públicos.",
                "category": "Política",
                "tags": ["transparencia", "gobierno", "anticorrupción"],
                "source_url": "https://ejemplo.com/transparencia-ley",
                "hours_ago": 2,
            },
            {
                "title": "Récord de inversión en energías renovables",
                "summary": "El país invirtió más de $500 millones en proyectos solares y eólicos durante el último trimestre.",
                "body": "Las inversiones en energía limpia alcanzaron cifras históricas. Según datos del Ministerio de Energía, se instalaron 150 MW de capacidad solar y 200 MW de capacidad eólica. Expertos celebran el avance, aunque advierten que aún falta camino para cumplir las metas climáticas de 2030.",
                "category": "Medio Ambiente",
                "tags": ["energía", "renovables", "clima"],
                "source_url": "https://ejemplo.com/energia-renovable",
                "hours_ago": 5,
            },
            {
                "title": "Aumenta el desempleo juvenil en zonas rurales",
                "summary": "El INEI reporta que la tasa de desempleo en jóvenes de 18 a 25 años en áreas rurales subió al 18%.",
                "body": "El último informe del Instituto Nacional de Estadística revela una preocupante tendencia. La falta de oportunidades laborales en el campo impulsa la migración hacia las ciudades. Organizaciones sociales exigen políticas públicas que promuevan el desarrollo rural y la creación de empleo local.",
                "category": "Economía",
                "tags": ["empleo", "juventud", "rural"],
                "source_url": "https://ejemplo.com/desempleo-rural",
                "hours_ago": 8,
            },
            {
                "title": "Investigación revela uso indebido de fondos en municipalidad",
                "summary": "Auditoría detectó irregularidades por más de $2 millones en contratos con empresas fantasma.",
                "body": "Un equipo de periodistas y auditores independientes descubrió una red de corrupción en la Municipalidad Provincial. Los hallazgos incluyen contratos sobrevalorados, pagos a proveedores inexistentes y desvío de fondos destinados a obras públicas. El alcalde negó las acusaciones y anunció acciones legales contra los investigadores.",
                "category": "Investigación",
                "tags": ["corrupción", "auditoría", "municipalidad"],
                "source_url": "https://ejemplo.com/corrupcion-municipal",
                "hours_ago": 12,
            },
            {
                "title": "Nuevo hospital público abrirá sus puertas en marzo",
                "summary": "La moderna infraestructura sanitaria atenderá a más de 200,000 habitantes de la región sur.",
                "body": "Tras cuatro años de construcción, el Hospital Regional del Sur está listo para iniciar operaciones. Con 300 camas, equipamiento de última generación y especialidades como oncología y cardiología, la institución promete mejorar significativamente el acceso a salud de calidad en la región. El ministro de Salud destacó que este es solo el primero de cinco hospitales planificados.",
                "category": "Salud",
                "tags": ["salud", "infraestructura", "hospital"],
                "source_url": "https://ejemplo.com/hospital-sur",
                "hours_ago": 24,
            },
        ]

        # Create scraped articles and publications
        for data in sample_data:
            # Create scraped article
            text = f"{data['title']}. {data['summary']} {data['body']}"
            text_hash = hashlib.sha256(text.encode()).hexdigest()

            scraped = ScrapedArticle(
                source_name="Ejemplo News",
                source_url=data["source_url"],
                title=data["title"],
                extracted_text=text,
                text_hash=text_hash,
                published_at=datetime.now() - timedelta(hours=data["hours_ago"]),
            )
            db.add(scraped)
            await db.flush()  # Get the scraped article ID

            # Create publication linked to scraped article
            publication = Publication(
                scraped_article_id=scraped.id,
                state="published",
                title=data["title"],
                summary=data["summary"],
                body=data["body"],
                category=data["category"],
                tags=data["tags"],
                published_at=datetime.now() - timedelta(hours=data["hours_ago"]),
            )
            db.add(publication)

        await db.commit()

        print(f"Se insertaron {len(sample_data)} publicaciones de ejemplo exitosamente!")
        print("\nPublicaciones creadas:")
        for i, data in enumerate(sample_data, 1):
            print(f"{i}. {data['title']} ({data['category']})")


if __name__ == "__main__":
    asyncio.run(insert_sample_publications())
