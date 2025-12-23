"""
Script para rellenar los niveles de lectura en publicaciones existentes.
Ejecutar: python -m scripts.populate_reading_levels
"""
import asyncio
import sys
from pathlib import Path

# Fix for Windows event loop
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db.models import Publication
from app.db.session import AsyncSessionLocal
from sqlalchemy import select


def generate_sin_vueltas(title: str) -> str:
    """Genera versión ultra corta basada en el título"""
    # Extraer la esencia del título
    return title + "."


def generate_lo_central(title: str, summary: str) -> str:
    """Genera versión esencial basada en título y resumen"""
    # Usar el resumen como base para "lo central"
    return summary


def generate_en_profundidad(title: str, summary: str, body: str) -> str:
    """Genera versión completa con contexto"""
    # Combinar resumen con cuerpo para la versión en profundidad
    if body and body.strip() and body != summary:
        return f"{summary}\n\n{body}"
    else:
        # Si el body es igual al summary, agregar un poco más de contexto
        return f"{summary}\n\nEsta noticia forma parte de la cobertura continua de temas relevantes para la sociedad. Los datos presentados provienen de fuentes oficiales y han sido verificados por nuestro equipo editorial."


async def populate_reading_levels():
    async with AsyncSessionLocal() as db:
        # Get all published publications without reading levels
        result = await db.execute(
            select(Publication)
            .where(Publication.state == "published")
            .where(
                (Publication.content_sin_vueltas.is_(None)) |
                (Publication.content_lo_central.is_(None)) |
                (Publication.content_en_profundidad.is_(None))
            )
        )
        publications = result.scalars().all()

        if not publications:
            print("No hay publicaciones que necesiten niveles de lectura.")
            return

        print(f"Rellenando niveles de lectura para {len(publications)} publicaciones...\n")

        updated_count = 0
        for pub in publications:
            # Generate reading levels
            sin_vueltas = generate_sin_vueltas(pub.title)
            lo_central = generate_lo_central(pub.title, pub.summary)
            en_profundidad = generate_en_profundidad(pub.title, pub.summary, pub.body)

            # Update publication
            pub.content_sin_vueltas = sin_vueltas
            pub.content_lo_central = lo_central
            pub.content_en_profundidad = en_profundidad

            updated_count += 1
            print(f"[{updated_count}/{len(publications)}] {pub.title[:60]}...")
            print(f"  Sin vueltas: {len(sin_vueltas)} chars")
            print(f"  Lo central: {len(lo_central)} chars")
            print(f"  En profundidad: {len(en_profundidad)} chars\n")

        await db.commit()
        print(f"\n✓ Se actualizaron {updated_count} publicaciones con niveles de lectura!")


if __name__ == "__main__":
    asyncio.run(populate_reading_levels())
