# Sistema de Scraping - La Data Justa

Sistema de scraping modular con gestión de fuentes desde la base de datos.

## Arquitectura

```
scraping/
├── run_scrapers.py          # Orquestador principal
├── lagaceta/
│   ├── scrape_lagaceta_db.py  # Scraper de La Gaceta
│   ├── prepare_for_ai.py      # Prepara items para IA
│   ├── process_ai.py          # Procesa items con IA
│   └── .env                   # Configuración
└── [otros_medios]/            # Futuros scrapers
```

## Flujo de Trabajo

1. **Configuración de Fuentes** (`scraping_sources` table)
   - Gestión via interfaz admin: `/admin/fuentes`
   - Habilitar/deshabilitar fuentes
   - Configurar parámetros de scraping

2. **Scraping** (`scraping_items` table)
   ```bash
   cd scraping
   python run_scrapers.py
   ```
   - Lee fuentes activas de la BD
   - Ejecuta scrapers configurados
   - Guarda items con status `scraped`
   - Actualiza estadísticas de fuentes

3. **Preparación para IA**
   ```bash
   cd scraping/lagaceta
   python prepare_for_ai.py
   ```
   - Marca items como `ready_for_ai`
   - Opciones: último 24h, 48h, 7 días, o todos

4. **Procesamiento IA**
   ```bash
   cd scraping/lagaceta
   python process_ai.py
   ```
   - Procesa items con OpenAI
   - Genera 3 niveles de lectura
   - Extrae categorías y tags
   - Status final: `ai_completed` o `discarded`

5. **Publicación**
   - Via interfaz admin: `/admin/scraping`
   - Editar items si es necesario
   - Publicar manualmente

## Configuración

### Variables de Entorno

Crear `scraping/lagaceta/.env`:

```env
# Database
DB_HOST=localhost
DB_PORT=5432
DB_NAME=ladatajusta
DB_USER=ladatajusta
DB_PASSWORD=ladatajusta

# OpenAI (para process_ai.py)
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini
```

### Agregar Nueva Fuente

1. **Crear el scraper**:
   ```bash
   mkdir scraping/nuevo_medio
   cd scraping/nuevo_medio
   # Crear scraper.py con función main() async
   ```

2. **Estructura del scraper**:
   ```python
   async def main():
       """
       Returns dict with:
       {
           'status': 'success' | 'error',
           'items_scraped': int,
           'message': str
       }
       """
       # Tu código de scraping aquí
       return {
           'status': 'success',
           'items_scraped': 10,
           'message': 'Scraped 10 items'
       }
   ```

3. **Registrar en la base de datos**:
   - Ir a `/admin/fuentes`
   - Crear nueva fuente
   - Configurar path del scraper: `nuevo_medio/scraper.py`
   - Activar la fuente

4. **Probar**:
   ```bash
   python run_scrapers.py
   ```

## Estados de Items

| Estado | Descripción |
|--------|-------------|
| `scraped` | Recién scrapeado |
| `ready_for_ai` | Listo para IA |
| `processing_ai` | Procesando con IA |
| `ai_completed` | IA completada ✓ |
| `ready_to_publish` | Listo para publicar |
| `published` | Publicado |
| `discarded` | Descartado |
| `error` | Error en pipeline |

## Campos Importantes

### scraping_sources
- `is_active`: Habilita/deshabilita fuente
- `sections_to_scrape`: Secciones a scrapear
- `max_articles_per_run`: Límite por ejecución
- `scraper_script_path`: Path al script Python
- `consecutive_errors`: Auto-deshabilita si >= `max_consecutive_errors`

### scraping_items
- `source_media`: Medio de origen
- `content_hash`: SHA-256 para dedup
- `status`: Estado en el pipeline
- `ai_title`, `ai_summary`, `ai_category`, `ai_tags`: IA generada
- `ai_metadata.sin_vueltas`: Nivel 1 (40-60 palabras)
- `ai_metadata.lo_central`: Nivel 2 (80-120 palabras)
- `ai_metadata.en_profundidad`: Nivel 3 (200-300 palabras)

## Automatización

### Cron Job (Linux/Mac)
```bash
# Scrapear cada hora
0 * * * * cd /path/to/scraping && python run_scrapers.py >> logs/scraping.log 2>&1

# Procesar IA cada 2 horas
0 */2 * * * cd /path/to/scraping/lagaceta && python process_ai.py >> logs/ai.log 2>&1
```

### Task Scheduler (Windows)
```powershell
# Crear tarea para scraping
schtasks /create /tn "Scraping" /tr "python C:\path\to\scraping\run_scrapers.py" /sc hourly

# Crear tarea para IA
schtasks /create /tn "AI Processing" /tr "python C:\path\to\scraping\lagaceta\process_ai.py" /sc hourly /mo 2
```

## Monitoreo

### Ver estadísticas
```sql
SELECT
    name,
    is_active,
    last_scraped_at,
    last_scrape_status,
    total_items_scraped,
    total_scrape_runs,
    consecutive_errors
FROM scraping_sources
ORDER BY name;
```

### Items por estado
```sql
SELECT
    status,
    COUNT(*) as count,
    MIN(scraped_at) as first,
    MAX(scraped_at) as last
FROM scraping_items
WHERE source_media = 'lagaceta'
GROUP BY status
ORDER BY count DESC;
```

### Costos de IA
```sql
SELECT
    source_media,
    COUNT(*) as items_processed,
    SUM(ai_tokens_used) as total_tokens,
    SUM(ai_cost_usd) as total_cost,
    AVG(ai_processing_duration_ms) as avg_duration_ms
FROM scraping_items
WHERE ai_processed_at >= NOW() - INTERVAL '30 days'
GROUP BY source_media;
```

## Troubleshooting

### Scraper no encuentra items
- Verificar que la fuente esté activa en `/admin/fuentes`
- Revisar logs de ejecución
- Verificar credenciales si es necesario

### Duplicados
- El sistema usa `content_hash` y `url_hash` para deduplicación automática
- Items duplicados se marcan como `SKIP` en logs

### Errores consecutivos
- Si una fuente alcanza `max_consecutive_errors`, se desactiva automáticamente
- Revisar `last_scrape_message` en la BD
- Corregir el problema y reactivar manualmente

### IA no procesa
- Verificar que `OPENAI_API_KEY` esté configurada
- Ejecutar `prepare_for_ai.py` primero
- Verificar que haya items con status `ready_for_ai`

## Desarrollo

### Agregar nuevo scraper
1. Copiar estructura de `lagaceta/scrape_lagaceta_db.py`
2. Adaptar a la nueva fuente
3. Asegurar que retorne dict con resultado
4. Registrar en `/admin/fuentes`

### Testing
```bash
# Test individual scraper
cd scraping/lagaceta
python scrape_lagaceta_db.py

# Test orquestador
cd scraping
python run_scrapers.py

# Test IA
cd scraping/lagaceta
python process_ai.py
```
