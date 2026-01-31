# Scraper de La Gaceta con Base de Datos

Versión mejorada del scraper que guarda directamente en la tabla `scraping_items` de PostgreSQL.

## 🆕 Mejoras vs. Versión CSV

| Característica | Versión CSV | Versión DB |
|----------------|-------------|------------|
| Almacenamiento | CSV local | PostgreSQL |
| Deduplicación | Manual | Automática (SHA-256 hashes) |
| Pipeline | No | Sí (estados: scraped → ready_for_ai → etc) |
| Trazabilidad | Limitada | Completa (run_id, timestamps, duración) |
| Procesamiento AI | Manual | Integrado en pipeline |
| Manejo de errores | Básico | Avanzado (retry, error tracking) |
| Escalabilidad | Baja | Alta (pool de conexiones) |

## 📋 Requisitos

### 1. Python y Dependencias

```bash
# Instalar dependencias
pip install -r requirements.txt

# Instalar navegador de Playwright
playwright install chromium
```

### 2. Base de Datos

La tabla `scraping_items` debe existir. Si no existe, ejecutar las migraciones:

```bash
cd ../../backend/migrations
psql -U postgres -d ladatajusta -f 001_create_scraping_items.sql
```

### 3. Variables de Entorno (Opcional)

Crear archivo `.env` en el directorio `scraping/lagaceta/`:

```env
DB_HOST=localhost
DB_PORT=5432
DB_NAME=ladatajusta
DB_USER=postgres
DB_PASSWORD=postgres
```

Si no se configuran, usa valores por defecto (localhost).

## 🚀 Uso

### Ejecutar el scraper

```bash
python scrape_lagaceta_db.py
```

### Salida esperada

```
🚀 Iniciando scraper de La Gaceta
📦 Run ID: a1b2c3d4e5f6...
✅ Conectado a PostgreSQL
✅ Login exitoso
🔗 45 enlaces únicos encontrados

📊 Procesando lote 1/9
🔎 Procesando: https://www.lagaceta.com.ar/nota/...
✅ Guardado: Nueva ley de protección animal establece penas más sev...
⏭️ Duplicado (URL): https://www.lagaceta.com.ar/nota/...

✅ Proceso terminado
📦 Run ID: a1b2c3d4e5f6...
🔌 Conexión a PostgreSQL cerrada
```

## 🔍 Verificar Datos Scrapeados

### Ver últimos items scrapeados

```sql
SELECT
    id,
    source_media,
    title,
    status,
    scraped_at,
    article_date
FROM scraping_items
WHERE source_media = 'lagaceta'
ORDER BY scraped_at DESC
LIMIT 10;
```

### Estadísticas de scraping

```sql
SELECT
    status,
    COUNT(*) as count,
    MIN(scraped_at) as first_scrape,
    MAX(scraped_at) as last_scrape
FROM scraping_items
WHERE source_media = 'lagaceta'
GROUP BY status;
```

### Items listos para procesar con AI

```sql
SELECT
    id,
    title,
    summary,
    scraped_at
FROM scraping_items
WHERE source_media = 'lagaceta'
  AND status = 'scraped'
  AND retry_count < max_retries
ORDER BY article_date DESC
LIMIT 20;
```

## 📊 Estructura de Datos Guardados

Cada artículo scrapeado incluye:

### Datos del Artículo
- `title`: Título del artículo
- `summary`: Resumen (si existe)
- `content`: Contenido completo
- `article_date`: Fecha de publicación original
- `source_section`: Categoría (Política, Economía, etc.)

### Metadatos del Scraper
- `source_url`: URL original
- `source_url_normalized`: URL normalizada
- `content_hash`: SHA-256 del contenido (deduplicación)
- `url_hash`: SHA-256 de la URL (deduplicación)
- `scraper_name`: "lagaceta_playwright"
- `scraper_version`: "2.0.0"
- `scraping_run_id`: ID único de esta ejecución
- `scraping_duration_ms`: Tiempo que tomó scrapear este artículo

### Estado del Pipeline
- `status`: 'scraped' (recién scrapeado)
- `status_message`: Mensaje de estado
- `retry_count`: Número de reintentos (0 inicial)

## 🔧 Configuración Avanzada

### Cambiar concurrencia

En `scrape_lagaceta_db.py`, modificar:

```python
CONCURRENCY = 5  # Número de artículos a procesar en paralelo
```

⚠️ **Precaución**: Valores muy altos pueden sobrecargar el sitio web.

### Cambiar fuente de noticias

Modificar la URL base:

```python
URL_ULTIMO_MOMENTO = "https://www.lagaceta.com.ar/ultimo-momento"
# Otras opciones:
# URL_BASE = "https://www.lagaceta.com.ar/politica"
# URL_BASE = "https://www.lagaceta.com.ar/economia"
```

### Agregar extracción de imágenes

En la función `procesar_noticia()`, agregar:

```python
# Extraer imágenes
image_urls = await page.eval_on_selector_all(
    "#articleContent img",
    "imgs => imgs.map(img => img.src)"
)

# Luego en data:
'image_urls': image_urls,
```

### Agregar extracción de autor

```python
# Buscar elemento de autor (ajustar selector según La Gaceta)
author = None
if await page.locator(".article-author").is_visible():
    author = await page.locator(".article-author").inner_text()

# Luego en data:
'author': author,
```

## 🔄 Flujo del Pipeline

Después del scraping, los items pasan por este pipeline:

```
scraped → ready_for_ai → processing_ai → ai_completed → ready_to_publish → published
```

Para mover items al siguiente estado, usar:

```sql
-- Marcar como listos para AI
UPDATE scraping_items
SET status = 'ready_for_ai'
WHERE source_media = 'lagaceta'
  AND status = 'scraped'
  AND article_date >= NOW() - INTERVAL '24 hours';
```

## ⚠️ Troubleshooting

### Error: "relation scraping_items does not exist"

Ejecutar la migración:

```bash
psql -U postgres -d ladatajusta -f ../../backend/migrations/001_create_scraping_items.sql
```

### Error: "asyncpg connection failed"

Verificar:
1. PostgreSQL está corriendo: `pg_ctl status`
2. Credenciales correctas en `.env` o código
3. Firewall/permisos de PostgreSQL

### Error: "playwright not installed"

```bash
playwright install chromium
```

### Duplicados no se detectan

Verificar que los índices existan:

```sql
SELECT indexname FROM pg_indexes WHERE tablename = 'scraping_items';
```

Debe incluir: `idx_scraping_items_url_hash` y `idx_scraping_items_content_hash`

## 📚 Próximos Pasos

1. **Procesar con AI**: Usar el pipeline para generar títulos/resúmenes con IA
2. **Crear Publicaciones**: Convertir items `ready_to_publish` en publicaciones
3. **Automatizar**: Crear cron job para scraping periódico
4. **Expandir**: Adaptar para otras fuentes (Clarín, Infobae, etc.)

## 📖 Referencias

- [Documentación de asyncpg](https://magicstack.github.io/asyncpg/)
- [Playwright Python](https://playwright.dev/python/)
- [Pipeline de Scraping (ver migrations)](../../backend/migrations/001_create_scraping_items.sql)
