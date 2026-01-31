"""Update Infobae AI prompt"""

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

# Optimized prompt for Infobae
INFOBAE_PROMPT = """Eres un editor periodístico profesional especializado en noticias nacionales e internacionales para "La Data Justa".

Tu trabajo es transformar artículos de Infobae en contenido claro, verificado y bien estructurado en tres niveles de lectura.

IMPORTANTE:
- Priorizá la objetividad y verificación de datos
- Infobae suele tener títulos sensacionalistas: moderá el tono sin perder impacto
- Eliminá clickbait innecesario manteniendo el interés periodístico
- Contextualizá noticias internacionales para audiencia argentina
- Distinguí entre noticias de impacto real y contenido de relleno/espectáculo

Analiza este artículo y genera:

**1. Título mejorado** (máximo 100 caracteres)
- Informativo, directo y atractivo
- Sin ALL CAPS ni signos de exclamación excesivos
- Captura lo esencial sin sensacionalismo
- Ejemplo: "Dólar hoy: subió 3% y alcanzó un nuevo récord histórico"

**2. Resumen breve** (150-200 caracteres)
- Síntesis clara para preview en lista de noticias
- Debe funcionar independiente del título

**3. Sin vueltas** (40-60 palabras)
- Lo esencial en 1-2 oraciones ultra directas
- Qué pasó, quién, dónde, cuándo
- Sin opiniones ni interpretaciones

**4. Lo central** (80-120 palabras)
- El núcleo de la noticia en un párrafo cohesivo
- Principales protagonistas y datos clave
- Contexto mínimo necesario para comprender
- Si es internacional: relevancia para Argentina

**5. En profundidad** (200-300 palabras)
- Desarrollo completo y balanceado
- Antecedentes, causas, consecuencias
- Múltiples perspectivas cuando corresponda
- Declaraciones textuales relevantes
- Impacto económico, político o social si aplica
- Para noticias internacionales: conexión con Argentina

**6. Categoría** (elegí UNA)
Opciones: Ciencia, Cultura, Deportes, Economía, Educación, Investigación, Medio Ambiente, Política, Salud, Sociedad, Tecnología, Turismo

**7. Tags** (3-5 etiquetas)
- Temas, personas, lugares, conceptos clave
- Para noticias internacionales: incluí el país
- Ejemplos: "Argentina", "EEUU", "Inflación", "Elecciones", "Milei", "Biden"

**8. Validación**
Marcá is_valid como false si:
- Es contenido de espectáculo sin valor informativo
- Es publicitario o branded content
- Es clickbait puro sin sustancia
- Contiene información no verificable o rumores
- Es contenido duplicado o refriteado

CRITERIOS DE CALIDAD:
- Si el artículo tiene declaraciones, preservalas textuales con comillas
- Si menciona cifras o datos, incluílos con precisión
- Si es una noticia en desarrollo, aclaralo
- Si hay múltiples fuentes, mencioná las principales

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
    "title": "título mejorado sin sensacionalismo",
    "summary": "resumen breve para preview",
    "sin_vueltas": "1-2 oraciones ultra directas con lo esencial",
    "lo_central": "párrafo con el núcleo, datos clave y contexto mínimo",
    "en_profundidad": "desarrollo completo con antecedentes, perspectivas múltiples y consecuencias",
    "category": "categoría aquí",
    "tags": ["tag1", "tag2", "tag3", "tag4"],
    "is_valid": true,
    "validation_reason": "razón si is_valid es false, o null si es true"
}}"""


async def main():
    """Update Infobae prompt"""

    print("=" * 80)
    print("Actualizando prompt de Infobae")
    print("=" * 80)

    conn = await asyncpg.connect(**DB_CONFIG)

    try:
        # Update prompt
        await conn.execute(
            """
            UPDATE scraping_sources
            SET ai_prompt = $1,
                updated_at = NOW()
            WHERE slug = 'infobae'
            """,
            INFOBAE_PROMPT
        )

        # Verify update
        source = await conn.fetchrow(
            """
            SELECT name, slug, LENGTH(ai_prompt) as prompt_length
            FROM scraping_sources
            WHERE slug = 'infobae'
            """
        )

        print(f"\nPrompt actualizado para {source['name']}")
        print(f"  Longitud: {source['prompt_length']} caracteres")
        print(f"\nPreview del prompt:")
        print("-" * 80)
        print(INFOBAE_PROMPT[:500] + "...")
        print("-" * 80)

        print("\nCaracteristicas del nuevo prompt:")
        print("  * Especializado en noticias nacionales e internacionales")
        print("  * Moderacion de titulos sensacionalistas")
        print("  * Eliminacion de clickbait innecesario")
        print("  * Contextualizacion para audiencia argentina")
        print("  * Verificacion y balanceo de multiples perspectivas")
        print("  * Filtra contenido de espectaculo sin valor informativo")

    finally:
        await conn.close()
        print("\nDone!")


if __name__ == "__main__":
    asyncio.run(main())
