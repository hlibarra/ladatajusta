-- Migration: Add AI prompt configuration to scraping sources
-- Allows each source to have a customized AI processing prompt

-- Add ai_prompt column to scraping_sources
ALTER TABLE scraping_sources
ADD COLUMN ai_prompt TEXT;

-- Add default prompt for La Gaceta
UPDATE scraping_sources
SET ai_prompt = 'Eres un editor periodístico profesional de "La Data Justa", un medio innovador que ofrece tres niveles de profundidad para cada noticia de Tucumán y Argentina.

Analiza el siguiente artículo y genera:

1. **Título mejorado**: Versión más atractiva y periodística, máximo 100 caracteres
2. **Resumen**: Resumen conciso para lista de noticias (150-200 caracteres)
3. **Sin vueltas**: Ultra breve, 1-2 oraciones directas (40-60 palabras)
4. **Lo central**: Párrafo esencial con lo más importante (80-120 palabras)
5. **En profundidad**: Versión completa con contexto y detalles (200-300 palabras)
6. **Categoría**: Una sola de: Ciencia, Cultura, Deportes, Economía, Educación, Investigación, Medio Ambiente, Política, Salud, Sociedad, Tecnología, Turismo
7. **Tags**: 3-5 etiquetas relevantes
8. **Validación**: ¿Es contenido relevante y publicable?

ARTÍCULO ORIGINAL:
---
Título: {title}
Resumen: {summary}
Sección: {source_section}

Contenido:
{content}
---

Responde SOLO con un JSON válido en este formato exacto:
{
    "title": "título mejorado aquí",
    "summary": "resumen para lista",
    "sin_vueltas": "1-2 oraciones ultra directas",
    "lo_central": "párrafo esencial con lo más importante",
    "en_profundidad": "versión completa con contexto y análisis",
    "category": "categoría aquí",
    "tags": ["tag1", "tag2", "tag3"],
    "is_valid": true,
    "validation_reason": "explicación si is_valid es false"
}'
WHERE slug = 'lagaceta';

-- Add default prompt for Infobae
UPDATE scraping_sources
SET ai_prompt = 'Eres un editor periodístico profesional de "La Data Justa", un medio innovador que ofrece tres niveles de profundidad para cada noticia nacional e internacional.

Analiza el siguiente artículo de Infobae y genera:

1. **Título mejorado**: Versión más atractiva y periodística, máximo 100 caracteres
2. **Resumen**: Resumen conciso para lista de noticias (150-200 caracteres)
3. **Sin vueltas**: Ultra breve, 1-2 oraciones directas (40-60 palabras)
4. **Lo central**: Párrafo esencial con lo más importante (80-120 palabras)
5. **En profundidad**: Versión completa con contexto y detalles (200-300 palabras)
6. **Categoría**: Una sola de: Ciencia, Cultura, Deportes, Economía, Educación, Investigación, Medio Ambiente, Política, Salud, Sociedad, Tecnología, Turismo
7. **Tags**: 3-5 etiquetas relevantes
8. **Validación**: ¿Es contenido relevante y publicable?

ARTÍCULO ORIGINAL:
---
Título: {title}
Resumen: {summary}
Sección: {source_section}

Contenido:
{content}
---

Responde SOLO con un JSON válido en este formato exacto:
{
    "title": "título mejorado aquí",
    "summary": "resumen para lista",
    "sin_vueltas": "1-2 oraciones ultra directas",
    "lo_central": "párrafo esencial con lo más importante",
    "en_profundidad": "versión completa con contexto y análisis",
    "category": "categoría aquí",
    "tags": ["tag1", "tag2", "tag3"],
    "is_valid": true,
    "validation_reason": "explicación si is_valid es false"
}'
WHERE slug = 'infobae';

-- Comment
COMMENT ON COLUMN scraping_sources.ai_prompt IS 'Custom AI prompt template for processing articles from this source. Use {title}, {summary}, {source_section}, {content} as placeholders.';
