# AI Processing Agent - La Data Justa

Sistema de procesamiento inteligente que transforma artículos scrapeados en contenido optimizado para publicación.

## Características

El agente de AI procesa automáticamente los artículos y genera:

1. **Títulos mejorados**: Versión más atractiva y periodística del título original
2. **Resúmenes optimizados**: Resúmenes concisos de 2-3 oraciones (150-200 caracteres)
3. **Categorización inteligente**: Asigna la categoría más adecuada
4. **Tags relevantes**: Genera 3-5 etiquetas para mejorar la búsqueda
5. **Validación de contenido**: Detecta y descarta contenido no relevante

## Requisitos

### 1. Instalar dependencias

```bash
cd scraping/lagaceta
pip install -r requirements.txt
```

### 2. Configurar API de OpenAI

Necesitas una API key de OpenAI. Crea un archivo `.env` basado en `.env.example`:

```bash
cp .env.example .env
```

Edita `.env` y configura tu API key:

```env
OPENAI_API_KEY=sk-tu-api-key-aqui
OPENAI_MODEL=gpt-4o-mini
```

> **Nota**: El modelo `gpt-4o-mini` es más económico. Puedes usar `gpt-4` para mayor calidad.

## Uso

### Ejecutar procesamiento AI

```bash
python process_ai.py
```

### Salida esperada

```
======================================================================
[START] AI Processing Agent for La Data Justa
======================================================================
Model: gpt-4o-mini
Prompt Version: 1.0.0
Concurrency: 3

[DB] Connecting to PostgreSQL...
[DB] Connected successfully

[FETCH] Getting items to process...
[FETCH] Found 26 items to process

[1/26] Processing: Salí con el paraguas: Tucumán se encuentra en alerta...
    ID: fb4e7cc0...
    Section: Sociedad
    [OK] AI Title: Alerta meteorológica en Tucumán: lluvias y tormentas
    [OK] Category: Sociedad
    [OK] Tags: clima, alerta, Tucumán
    [OK] Tokens: 245, Cost: $0.000089

[2/26] Processing: Aguilares, la zona cero del temporal...
    ID: 1b5c497a...
    Section: Sociedad
    [OK] AI Title: Aguilares bajo el agua: crisis tras el temporal
    [OK] Category: Sociedad
    [OK] Tags: temporal, inundación, Aguilares
    [OK] Tokens: 312, Cost: $0.000124

...

======================================================================
[DONE] Processing completed
======================================================================
Total items: 26
Successful: 24
Failed: 2

Recent AI Stats (last hour):
  Completed: 24
  Discarded: 2
  Total tokens: 6847
  Total cost: $0.002456

[DB] Connection closed
```

## Pipeline de Estados

Los artículos pasan por estos estados:

```
scraped → ready_for_ai → processing_ai → ai_completed → ready_to_publish
                                                ↓
                                           discarded (si no es válido)
```

### Estados explicados

- **scraped**: Recién scrapeado, listo para procesamiento
- **ready_for_ai**: Marcado manualmente para procesamiento prioritario
- **processing_ai**: En proceso (estado temporal)
- **ai_completed**: Procesamiento completado exitosamente
- **discarded**: Descartado por contenido no relevante
- **ready_to_publish**: Listo para convertir en publicación

## Configuración Avanzada

### Cambiar modelo de AI

En el archivo `.env`:

```env
# Más económico (recomendado)
OPENAI_MODEL=gpt-4o-mini

# Mayor calidad
OPENAI_MODEL=gpt-4o

# Alternativa
OPENAI_MODEL=gpt-3.5-turbo
```

### Cambiar concurrencia

En `process_ai.py`, línea 30:

```python
CONCURRENCY = 3  # Procesa 3 artículos simultáneamente
```

> ⚠️ **Precaución**: Mayor concurrencia = mayor costo de API

### Personalizar categorías

Edita la lista `VALID_CATEGORIES` en `process_ai.py`:

```python
VALID_CATEGORIES = [
    "Ciencia", "Cultura", "Deportes", "Economía",
    # Agrega tus categorías personalizadas aquí
]
```

### Modificar el prompt

Edita la función `create_processing_prompt()` en `process_ai.py` para ajustar cómo la AI procesa el contenido.

## Costos Estimados

Usando `gpt-4o-mini`:

- **Input**: $0.150 por 1M tokens
- **Output**: $0.600 por 1M tokens

Costo aproximado por artículo:

- Artículo corto (500 palabras): ~$0.0001
- Artículo medio (1000 palabras): ~$0.0002
- Artículo largo (2000 palabras): ~$0.0004

**Ejemplo**: Procesar 100 artículos medianos ≈ $0.02

## Verificar Resultados

### Ver items procesados por AI

```sql
SELECT
    id,
    title,
    ai_title,
    ai_summary,
    ai_category,
    ai_tags,
    status,
    ai_cost_usd
FROM scraping_items
WHERE source_media = 'lagaceta'
  AND status = 'ai_completed'
ORDER BY ai_processed_at DESC
LIMIT 10;
```

### Estadísticas de procesamiento

```sql
SELECT
    status,
    COUNT(*) as count,
    SUM(ai_tokens_used) as total_tokens,
    SUM(ai_cost_usd) as total_cost
FROM scraping_items
WHERE source_media = 'lagaceta'
  AND ai_processed_at IS NOT NULL
GROUP BY status;
```

## Troubleshooting

### Error: "OPENAI_API_KEY environment variable not set"

Asegúrate de tener un archivo `.env` con tu API key:

```bash
echo "OPENAI_API_KEY=sk-tu-key" > .env
```

### Error: "Failed to parse AI response as JSON"

El modelo puede estar generando respuestas inválidas. Intenta:

1. Usar `gpt-4o` o `gpt-4` en lugar de `gpt-4o-mini`
2. Reducir la temperatura en el código (línea con `temperature=0.7`)

### Items quedan en "processing_ai"

Si el script se interrumpe, algunos items pueden quedar en este estado. Resetéalos:

```sql
UPDATE scraping_items
SET status = 'ready_for_ai'
WHERE status = 'processing_ai';
```

### Alto costo de API

- Usa `gpt-4o-mini` en lugar de `gpt-4`
- Reduce `CONCURRENCY` para procesar menos items simultáneamente
- Limita el contenido enviado a la API (línea con `[:2000]`)

## Próximos Pasos

Una vez procesados los artículos con AI:

1. **Revisar en el admin**: [http://localhost:4321/admin/scraping](http://localhost:4321/admin/scraping)
2. **Marcar como listos para publicar**:
   ```sql
   UPDATE scraping_items
   SET status = 'ready_to_publish'
   WHERE status = 'ai_completed'
     AND article_date >= NOW() - INTERVAL '24 hours';
   ```
3. **Convertir a publicaciones**: Usar el endpoint del backend o crear manualmente

## Referencias

- [Documentación OpenAI API](https://platform.openai.com/docs/api-reference)
- [Precios OpenAI](https://openai.com/pricing)
- [Pipeline de Scraping](README_DB.md)
