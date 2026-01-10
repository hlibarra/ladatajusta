# 🚀 Quick Start - Sistema de Scraping

Guía rápida para poner en marcha el sistema de scraping staging.

## ✅ Paso 1: Ejecutar la migración SQL

```bash
# Conectarse a PostgreSQL
psql -U ladatajusta -d ladatajusta

# Ejecutar la migración
\i backend/migrations/001_create_scraping_items.sql

# Verificar que la tabla se creó
\dt scraping_items

# Salir
\q
```

**Alternativa con Docker:**
```bash
docker exec -i ladatajusta-db-1 psql -U ladatajusta -d ladatajusta < backend/migrations/001_create_scraping_items.sql
```

## ✅ Paso 2: Reiniciar el backend

```bash
cd backend

# Activar entorno virtual
.\.venv\Scripts\Activate.ps1  # Windows
# o
source .venv/bin/activate      # Linux/Mac

# Reiniciar servidor
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## ✅ Paso 3: Verificar en Swagger

Abrir en el navegador:
```
http://localhost:8000/docs
```

Buscar la sección **"scraping-items"** - deberías ver 9 endpoints:

- POST `/api/scraping-items` - Crear item
- POST `/api/scraping-items/upsert` ⭐ **RECOMENDADO**
- GET `/api/scraping-items` - Listar items
- GET `/api/scraping-items/{id}` - Obtener item
- PATCH `/api/scraping-items/{id}` - Actualizar item
- DELETE `/api/scraping-items/{id}` - Eliminar item
- POST `/api/scraping-items/{id}/publish` - Publicar
- GET `/api/scraping-items/stats/summary` - Estadísticas
- POST `/api/scraping-items/bulk/mark-duplicates` - Marcar duplicados

## ✅ Paso 4: Probar con el ejemplo

```bash
cd backend
python examples/scraper_example.py
```

Deberías ver:
```
============================================================
  Example Scraper for La Data Justa
============================================================

📰 Example 1: Single URL scrape
Scraping: https://www.lagaceta.com.ar/nota/123456/politica/example-article
  ✓ Scraped: Example Article Title
  ✓ Saved to staging (ID: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx)
    Status: scraped
    URL hash: abc123...

...
```

## ✅ Paso 5: Probar en Swagger

### 5.1. Crear un item de scraping

En Swagger, expandir `POST /api/scraping-items/upsert` → **Try it out**

Copiar y pegar este JSON:

```json
{
  "source_media": "lagaceta",
  "source_section": "politica",
  "source_url": "https://www.lagaceta.com.ar/nota/999/test",
  "source_url_normalized": "https://lagaceta.com.ar/nota/999/test",
  "title": "Artículo de prueba",
  "content": "Contenido del artículo de prueba...",
  "content_hash": "1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
  "url_hash": "fedcba0987654321fedcba0987654321fedcba0987654321fedcba0987654321",
  "scraper_name": "manual_test",
  "scraper_version": "1.0.0",
  "tags": ["test", "politica"]
}
```

Click **Execute** → Deberías ver respuesta 200 con el item creado.

### 5.2. Listar items

Expandir `GET /api/scraping-items` → **Try it out** → **Execute**

Deberías ver tu item en la lista.

### 5.3. Ver estadísticas

Expandir `GET /api/scraping-items/stats/summary` → **Try it out** → **Execute**

Deberías ver:
```json
{
  "total_items": 1,
  "by_status": {
    "scraped": 1
  },
  "by_source_media": {
    "lagaceta": 1
  },
  ...
}
```

## 📊 Paso 6: Queries útiles en la base de datos

```sql
-- Ver todos los items
SELECT id, source_media, title, status, scraped_at
FROM scraping_items
ORDER BY scraped_at DESC
LIMIT 10;

-- Ver stats por estado
SELECT status, COUNT(*) as count
FROM scraping_items
GROUP BY status;

-- Ver items pendientes de IA
SELECT id, title, scraped_at
FROM scraping_items
WHERE status = 'ready_for_ai'
ORDER BY scraped_at ASC;
```

## 🔄 Workflow completo de ejemplo

### 1. Scrapear un artículo

```python
import httpx
from app.scrape.deduplication import generate_content_hash, generate_url_hash

url = "https://www.lagaceta.com.ar/nota/12345/politica/ejemplo"
content = "Contenido del artículo..."

async with httpx.AsyncClient() as client:
    response = await client.post(
        "http://localhost:8000/api/scraping-items/upsert",
        json={
            "source_media": "lagaceta",
            "source_url": url,
            "source_url_normalized": url,
            "title": "Título del artículo",
            "content": content,
            "content_hash": generate_content_hash(content),
            "url_hash": generate_url_hash(url),
            "scraper_name": "mi_scraper",
        }
    )
    item = response.json()
    item_id = item["id"]
```

### 2. Marcar como listo para IA

```python
await client.patch(
    f"http://localhost:8000/api/scraping-items/{item_id}",
    json={"status": "ready_for_ai"}
)
```

### 3. Procesar con IA (simulado)

```python
# Tu pipeline de IA procesa el item...
ai_result = {
    "title": "Título mejorado por IA",
    "summary": "Resumen generado por IA",
    "tags": ["tag1", "tag2"],
    "category": "politica",
}

# Guardar resultados
await client.patch(
    f"http://localhost:8000/api/scraping-items/{item_id}",
    json={
        "status": "ai_completed",
        "ai_title": ai_result["title"],
        "ai_summary": ai_result["summary"],
        "ai_tags": ai_result["tags"],
        "ai_category": ai_result["category"],
        "ai_model": "gpt-4o-mini",
        "ai_tokens_used": 1500,
    }
)
```

### 4. Marcar como listo para publicar

```python
await client.patch(
    f"http://localhost:8000/api/scraping-items/{item_id}",
    json={"status": "ready_to_publish"}
)
```

### 5. Publicar

```python
response = await client.post(
    f"http://localhost:8000/api/scraping-items/{item_id}/publish",
    json={"agent_id": None}  # O UUID del agente
)

publication = response.json()
print(f"Publicado: {publication['publication_id']}")
print(f"Slug: {publication['slug']}")
```

## 🎯 Próximos pasos

1. **Integrar scrapers existentes**: Modificar tus scrapers para usar `/upsert`
2. **Crear pipeline de IA**: Worker que procese items con status `ready_for_ai`
3. **Dashboard**: Frontend para ver y gestionar items
4. **Automatización**: Cron jobs o workers para procesamiento automático

## 📚 Más información

- **Documentación completa**: `backend/SCRAPING_ITEMS_README.md`
- **Resumen ejecutivo**: `backend/SCRAPING_SYSTEM_SUMMARY.md`
- **Queries útiles**: `backend/migrations/002_scraping_items_useful_queries.sql`
- **Tests**: `backend/tests/test_scraping_items_api.py`

## ❓ Troubleshooting

### Error: "relation scraping_items does not exist"
→ No ejecutaste la migración. Ver Paso 1.

### Error: "column ... does not exist"
→ La migración no se completó correctamente. Revisar logs de PostgreSQL.

### Error: "duplicate key value violates unique constraint"
→ Ya existe un item con ese `url_hash`. Esto es esperado - usa `/upsert` en vez de POST.

### No veo los endpoints en Swagger
→ Reinicia el backend. Verifica que `scraping_items.py` esté en `app/api/routes/`.

## ✅ Checklist de verificación

- [ ] Tabla `scraping_items` creada en PostgreSQL
- [ ] Backend reiniciado
- [ ] Endpoints visibles en Swagger (http://localhost:8000/docs)
- [ ] Ejemplo ejecutado exitosamente
- [ ] Primer item creado manualmente en Swagger
- [ ] Stats endpoint retorna datos

---

**¡Listo! Sistema de scraping operativo.** 🎉
