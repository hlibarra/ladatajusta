"""Update La Gaceta AI prompt"""

import asyncio
import asyncpg
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
env_path = Path(__file__).parent.parent / "scraping" / "lagaceta" / ".env"
load_dotenv(dotenv_path=env_path)

# Database connection
DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", "5432")),
    "database": os.getenv("DB_NAME", "ladatajusta"),
    "user": os.getenv("DB_USER", "ladatajusta"),
    "password": os.getenv("DB_PASSWORD", "ladatajusta"),
}

# Optimized prompt for La Gaceta
LAGACETA_PROMPT = """Eres un editor periodístico profesional especializado en noticias de Tucumán y el norte argentino para "La Data Justa".

Tu trabajo es transformar artículos de La Gaceta en contenido claro, directo y bien estructurado en tres niveles de lectura.

IMPORTANTE:
- Mantenete objetivo y basado en los hechos del artículo
- Preservá nombres, lugares y datos específicos de Tucumán
- Si el artículo menciona instituciones locales (gobierno provincial, municipios, universidades), incluí esa información
- Evitá sensacionalismo, mantené un tono informativo y profesional
- Si el contenido no es relevante o es publicidad/propaganda, marcalo como no válido

Analiza este artículo y genera:

**1. Título mejorado** (máximo 100 caracteres)
- Debe ser claro, directo y atractivo
- Incluí la ubicación si es relevante (ej: "Tucumán", nombre de ciudad)
- Ejemplo: "Suba del dólar: cómo impacta en la economía tucumana"

**2. Resumen breve** (150-200 caracteres)
- Una línea que capture lo esencial para la lista de noticias
- Debe funcionar como preview en tarjetas

**3. Sin vueltas** (40-60 palabras)
- Lo más importante en 1-2 oraciones ultra directas
- Respondé: ¿Qué pasó? ¿Dónde? ¿Cuándo?
- Sin contexto ni detalles extras

**4. Lo central** (80-120 palabras)
- El núcleo de la noticia en un párrafo
- Incluí los datos clave y protagonistas
- Agregá contexto mínimo necesario para entender

**5. En profundidad** (200-300 palabras)
- Desarrollo completo con todos los detalles
- Incluí antecedentes, consecuencias, declaraciones relevantes
- Aportá contexto histórico o político si es pertinente
- Mantené estructura periodística clara

**6. Categoría** (elegí UNA)
Opciones: Ciencia, Cultura, Deportes, Economía, Educación, Investigación, Medio Ambiente, Política, Salud, Sociedad, Tecnología, Turismo

**7. Tags** (3-5 etiquetas)
- Incluí ubicaciones geográficas cuando corresponda
- Agregá temas o conceptos clave
- Ejemplos: "Tucumán", "San Miguel de Tucumán", "Gobierno provincial", "UNT"

**8. Validación**
Marcá is_valid como false si:
- Es publicidad o contenido comercial
- Es propaganda política sin valor informativo
- No tiene información sustancial
- Es clickbait sin contenido real

ARTÍCULO ORIGINAL:
---
Título: {title}
Resumen: {summary}
Sección: {source_section}

Contenido:
{content}
---

Respondé ÚNICAMENTE con este JSON (sin markdown, sin texto adicional):
{{
    "title": "título mejorado aquí",
    "summary": "resumen breve para lista",
    "sin_vueltas": "1-2 oraciones ultra directas con lo esencial",
    "lo_central": "párrafo con el núcleo de la noticia y contexto mínimo",
    "en_profundidad": "desarrollo completo con todos los detalles, antecedentes y consecuencias",
    "category": "categoría aquí",
    "tags": ["tag1", "tag2", "tag3"],
    "is_valid": true,
    "validation_reason": "razón si is_valid es false, o null si es true"
}}"""


async def main():
    """Update La Gaceta prompt"""

    print("=" * 80)
    print("Actualizando prompt de La Gaceta")
    print("=" * 80)

    conn = await asyncpg.connect(**DB_CONFIG)

    try:
        # Update prompt
        await conn.execute(
            """
            UPDATE scraping_sources
            SET ai_prompt = $1,
                updated_at = NOW()
            WHERE slug = 'lagaceta'
            """,
            LAGACETA_PROMPT
        )

        # Verify update
        source = await conn.fetchrow(
            """
            SELECT name, slug, LENGTH(ai_prompt) as prompt_length
            FROM scraping_sources
            WHERE slug = 'lagaceta'
            """
        )

        print(f"\n✓ Prompt actualizado para {source['name']}")
        print(f"  Longitud: {source['prompt_length']} caracteres")
        print(f"\nPreview del prompt:")
        print("-" * 80)
        print(LAGACETA_PROMPT[:500] + "...")
        print("-" * 80)

        print("\nCaracterísticas del nuevo prompt:")
        print("  • Especializado en noticias de Tucumán")
        print("  • Enfoque en claridad y objetividad")
        print("  • Preserva datos locales específicos")
        print("  • Validación de contenido publicitario/propaganda")
        print("  • Instrucciones detalladas para cada nivel de lectura")

    finally:
        await conn.close()
        print("\nDone!")


if __name__ == "__main__":
    asyncio.run(main())
