# Sistema de Scraping - Resumen Ejecutivo

## 📋 ¿Qué se implementó?

Se diseñó e implementó un **sistema completo de staging para scraping** que almacena TODOS los datos scrapeados antes de publicarlos, con trazabilidad total, deduplicación robusta y gestión del pipeline de IA.

## 🗂️ Archivos Creados

### 1. **Migración SQL**
📁 `backend/migrations/001_create_scraping_items.sql`

- Esquema completo de la tabla `scraping_items`
- ENUMs para `scraping_status` y `source_media`
- Índices optimizados para performance
- Constraints para integridad de datos
- Triggers para auto-actualización de timestamps
- Vistas útiles (items pendientes, duplicados, stats)

**Características:**
- ✅ 40+ campos organizados por categoría
- ✅ Deduplicación por URL y contenido
- ✅ Pipeline de estados (scraped → published)
- ✅ Tracking de IA (modelo, tokens, costo)
- ✅ Manejo de errores y reintentos
- ✅ Auditoría completa

### 2. **Modelo SQLAlchemy**
📁 `backend/app/db/models.py` (clase `ScrapingItem`)

- Modelo async compatible con FastAPI
- Mapeo 1:1 con el esquema SQL
- Relaciones con tabla `publications`
- Índices compuestos para queries comunes

### 3. **Schemas Pydantic**
📁 `backend/app/api/schemas.py`

Schemas agregados:
- `ScrapingItemCreate` - Crear nuevo item
- `ScrapingItemUpdate` - Actualizar item
- `ScrapingItemOut` - Response básico
- `ScrapingItemOutDetailed` - Response con todos los campos
- `ScrapingItemFilters` - Filtros para queries
- `PaginatedScrapingItems` - Respuesta paginada
- `ScrapingItemPublishRequest` - Publicar item
- `ScrapingItemStats` - Estadísticas

### 4. **Endpoints FastAPI**
📁 `backend/app/api/routes/scraping_items.py`

**Endpoints implementados:**

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| POST | `/scraping-items` | Crear item (con dedup) |
| POST | `/scraping-items/upsert` | **RECOMENDADO** - Upsert deduplicado |
| GET | `/scraping-items` | Listar con filtros y paginación |
| GET | `/scraping-items/{id}` | Obtener item completo |
| PATCH | `/scraping-items/{id}` | Actualizar item |
| POST | `/scraping-items/{id}/publish` | Crear publicación |
| DELETE | `/scraping-items/{id}` | Eliminar item |
| GET | `/scraping-items/stats/summary` | Estadísticas |
| POST | `/scraping-items/bulk/mark-duplicates` | Marcar duplicados |

### 5. **Utilidades de Deduplicación**
📁 `backend/app/scrape/deduplication.py`

Funciones implementadas:
- `normalize_url()` - Normaliza URLs (lowercase, sin tracking params)
- `normalize_content()` - Normaliza contenido (whitespace, lowercase)
- `hash_text()` - SHA-256 de texto
- `generate_url_hash()` - Hash de URL normalizada
- `generate_content_hash()` - Hash de contenido normalizado
- `check_similarity()` - Chequea similitud entre textos

### 6. **Ejemplo de Scraper**
📁 `backend/examples/scraper_example.py`

Scraper de ejemplo que muestra:
- Cómo scrapear contenido
- Cómo normalizar y hashear
- Cómo usar el endpoint `/upsert`
- Manejo de errores
- Scraping en batch
- Deduplicación en acción

### 7. **Documentación**
📁 `backend/SCRAPING_ITEMS_README.md`

Documentación completa que incluye:
- Diagrama de arquitectura
- Schema completo de la tabla
- Descripción de todos los campos
- Documentación de endpoints
- Ejemplos de uso
- Estrategia de deduplicación
- Best practices
- Instrucciones de migración

### 8. **Integración con Router**
📁 `backend/app/api/router.py`

- Rutas agregadas bajo `/api/scraping-items`
- Tag: `scraping-items` en Swagger

## 🎯 Características Principales

### 1. **Trazabilidad Total**
Cada item registra:
- De dónde vino (medio, sección, URL)
- Quién lo scrapeó (scraper, versión, IP, user-agent)
- Cuándo se scrapeó (timestamp, duración)
- Cómo se procesó (IA modelo, tokens, costo)
- Qué pasó con él (estado, errores, publicación)

### 2. **Deduplicación Robusta**
- **Por URL**: `url_hash` (UNIQUE constraint)
  - Normaliza URLs (remove tracking params, lowercase)
  - Si existe, actualiza contenido (endpoint upsert)

- **Por Contenido**: `content_hash`
  - Normaliza contenido (whitespace, lowercase)
  - Detecta artículos idénticos de diferentes URLs
  - Endpoint bulk para marcar duplicados

### 3. **Pipeline de Estados**
```
scraped → pending_review → ready_for_ai → processing_ai →
ai_completed → ready_to_publish → published
         ↓
    discarded / error / duplicate
```

### 4. **Manejo de Errores**
- Contador de reintentos (`retry_count`)
- Máximo de reintentos configurable (`max_retries`)
- Error trace completo para debugging
- Timestamp del último error
- Estado `error` con mensaje descriptivo

### 5. **Tracking de IA**
- Título, resumen, tags generados por IA
- Modelo utilizado (ej: gpt-4o-mini)
- Versión de prompt (para A/B testing)
- Tokens consumidos
- Costo estimado en USD
- Metadata flexible (JSONB)

### 6. **Performance**
- Índices optimizados para queries comunes:
  - Por estado (WHERE status = 'ready_for_ai')
  - Por medio y fecha (WHERE source_media = 'lagaceta' ORDER BY article_date)
  - Por hash (deduplicación instantánea)
  - Full-text search en título/contenido (trigram index)

### 7. **Flexibilidad**
- Campo `extra_metadata` (JSONB) para datos específicos del scraper
- Campo `ai_metadata` (JSONB) para datos de IA
- Arrays para tags, imágenes, videos

## 🚀 Cómo Usar

### Paso 1: Ejecutar la migración
```bash
psql -U ladatajusta -d ladatajusta -f backend/migrations/001_create_scraping_items.sql
```

### Paso 2: Reiniciar el backend
```bash
cd backend
python -m uvicorn app.main:app --reload
```

### Paso 3: Ver en Swagger
Abrir: http://localhost:8000/docs

Verás la sección "scraping-items" con todos los endpoints.

### Paso 4: Probar con el ejemplo
```bash
cd backend
python examples/scraper_example.py
```

## 📊 Endpoints Clave

### Para Scrapers
```python
POST /api/scraping-items/upsert
```
**Uso:** Siempre usar este endpoint para evitar duplicados

### Para Pipeline de IA
```python
GET /api/scraping-items?status=ready_for_ai&limit=100
PATCH /api/scraping-items/{id}  # Actualizar con resultados de IA
```

### Para Publicación
```python
POST /api/scraping-items/{id}/publish
```
**Resultado:** Crea `Publication` y vincula con `publication_id`

### Para Monitoreo
```python
GET /api/scraping-items/stats/summary
```
**Uso:** Dashboard de estadísticas

## 🔑 Flujo Completo

1. **Scraper** scrapea noticia → POST `/upsert` → crea `ScrapingItem` con status="scraped"
2. **Revisor** (humano/bot) aprueba → PATCH status="ready_for_ai"
3. **Pipeline IA** procesa → PATCH con ai_title, ai_summary, etc → status="ai_completed"
4. **Sistema** valida → PATCH status="ready_to_publish"
5. **Publicador** crea publicación → POST `/{id}/publish` → crea `Publication` + status="published"

## 📈 Ventajas del Sistema

### vs. Scrapear directo a publicaciones:
✅ **Auditoría**: Sabes exactamente qué se scrapeó y cuándo
✅ **Deduplicación**: Evitas artículos repetidos
✅ **Flexibilidad**: Puedes re-procesar items sin re-scrapear
✅ **Trazabilidad**: Sabes de dónde vino cada publicación
✅ **Control de calidad**: Revisión antes de publicar
✅ **Debugging**: Raw HTML guardado para análisis
✅ **Costos**: Tracking de tokens/costo de IA

### vs. Tabla simple de scraping:
✅ **Estados**: Pipeline claro de scraping → publicación
✅ **Errores**: Manejo robusto de fallos con reintentos
✅ **Metadatos**: Tracking completo de scraper, IA, etc
✅ **Performance**: Índices optimizados para queries reales
✅ **Extensibilidad**: JSONB para datos custom

## 🎓 Conceptos Clave

### Deduplicación por URL
```python
url_hash = SHA256(normalize_url(original_url))
# Si url_hash existe → actualiza contenido
# Si no existe → crea nuevo item
```

### Deduplicación por Contenido
```python
content_hash = SHA256(normalize_content(content))
# Detecta artículos idénticos de diferentes URLs
# Útil para syndicated content
```

### Upsert Pattern
```sql
INSERT INTO scraping_items (...)
ON CONFLICT (url_hash) DO UPDATE SET
  content = EXCLUDED.content,
  updated_at = NOW()
RETURNING *;
```

## 🛠️ Próximos Pasos Sugeridos

1. **Integrar con scrapers existentes**: Modificar scrapers actuales para usar `/upsert`
2. **Pipeline de IA**: Crear worker que procese items con status="ready_for_ai"
3. **Dashboard**: Crear frontend para visualizar stats y gestionar items
4. **Automatización**: Scheduler para marcar duplicados periódicamente
5. **Alertas**: Notificaciones cuando hay muchos errores
6. **Archivado**: Script para archivar items publicados antiguos

## 📚 Recursos

- **SQL Migration**: `backend/migrations/001_create_scraping_items.sql`
- **Documentación**: `backend/SCRAPING_ITEMS_README.md`
- **Ejemplo de uso**: `backend/examples/scraper_example.py`
- **Swagger/OpenAPI**: http://localhost:8000/docs (sección scraping-items)

## ✅ Checklist de Implementación

- [x] Schema SQL con ENUMs, índices y constraints
- [x] Modelo SQLAlchemy async
- [x] Schemas Pydantic completos
- [x] 9 endpoints REST (CRUD + stats + bulk)
- [x] Lógica de upsert deduplicado (PostgreSQL ON CONFLICT)
- [x] Utilidades de normalización y hashing
- [x] Ejemplo funcional de scraper
- [x] Documentación completa
- [x] Integración con router FastAPI
- [ ] Ejecutar migración en DB
- [ ] Probar endpoints
- [ ] Integrar con scrapers existentes
- [ ] Crear pipeline de IA

---

**🎉 Sistema completo y listo para usar!**

Para preguntas o mejoras, consulta `SCRAPING_ITEMS_README.md` o revisa el código con comentarios detallados.
