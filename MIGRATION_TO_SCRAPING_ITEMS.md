# Migración del Sistema de Scraping

## Resumen

Se ha completado la migración del sistema antiguo de scraping (`scraped_articles`) al nuevo sistema robusto (`scraping_items`).

## Cambios Realizados

### 1. Base de Datos

**Migración:** [`backend/migrations/003_add_scraping_item_id_to_publications.sql`](backend/migrations/003_add_scraping_item_id_to_publications.sql)

- Agregado campo `scraping_item_id` a la tabla `publications`
- Agregado campo `scraping_item_id` a la tabla `ai_runs`
- Ambos campos son opcionales (`NULLABLE`) para compatibilidad con datos existentes

### 2. Modelos SQLAlchemy

**Archivo:** [`backend/app/db/models.py`](backend/app/db/models.py)

#### Publication (líneas 64-104)
- Agregado: `scraping_item_id` como foreign key a `scraping_items`
- Agregado: relación `scraping_item` para acceso al objeto completo
- Mantenido: `scraped_article_id` para compatibilidad con 31 publicaciones existentes

#### AIRun (líneas 107-117)
- Agregado: `scraping_item_id` como foreign key a `scraping_items`
- Modificado: `scraped_article_id` ahora es NULLABLE

### 3. Rutas de API

**Archivo:** [`backend/app/api/routes/scraping_items.py`](backend/app/api/routes/scraping_items.py)

#### Endpoint `/api/scraping-items/{item_id}/publish` (líneas 266-354)
- **Antes:** Creaba publicación con `scraped_article_id=None` y usaba solo `scraping_items.publication_id` para el vínculo
- **Ahora:** Crea publicación con `scraping_item_id=item_id` (vínculo bidireccional completo)
- **Beneficio:** Ahora las publicaciones están correctamente vinculadas al sistema nuevo

## Estado Actual del Sistema

### Tabla `scraping_items` (Sistema NUEVO)
- **Total de items:** 14
- **Características:**
  - Pipeline completo de estados (scraped → ready_for_ai → ai_completed → ready_to_publish → published)
  - Trazabilidad completa del scraping
  - Gestión de errores y reintentos
  - Procesamiento con IA
  - Metadatos extensibles
  - Deduplicación por hash
- **Interfaz Admin:** http://localhost:4321/admin/scraping

### Tabla `scraped_articles` (Sistema ANTIGUO - Deprecado)
- **Total de items:** 31
- **Publicaciones vinculadas:** 31 (todas las publicaciones actuales)
- **Estado:** DEPRECADO - Solo se mantiene para compatibilidad con datos históricos
- **Acciones:**
  - ✅ No se crearán más registros en esta tabla
  - ✅ Las publicaciones existentes siguen funcionando
  - ❌ No eliminar hasta migrar las 31 publicaciones existentes

## Sistema de Vinculación

### Publicaciones NUEVAS (desde scraping_items)
```
scraping_item --[publication_id]--> publication
publication --[scraping_item_id]--> scraping_item
```
**Vínculo bidireccional completo**

### Publicaciones ANTIGUAS (desde scraped_articles)
```
scraped_article --[publication]--> publication
publication --[scraped_article_id]--> scraped_article
```
**Mantenido por compatibilidad**

## Verificación

Para verificar que todo funciona correctamente:

```bash
# 1. Ver items de scraping
curl http://localhost:8000/api/scraping-items?limit=5

# 2. Ver estadísticas
curl http://localhost:8000/api/scraping-items/stats/summary

# 3. Publicar un item (requiere item en estado apropiado)
curl -X POST http://localhost:8000/api/scraping-items/{item_id}/publish \
  -H "Content-Type: application/json" \
  -d '{"agent_id": "agent-uuid-here"}'
```

## Próximos Pasos (Opcional)

Si deseas eliminar completamente el sistema antiguo:

1. **Migrar las 31 publicaciones existentes:**
   - Crear script que copie datos de `scraped_articles` a `scraping_items`
   - Actualizar `publications` para usar `scraping_item_id` en vez de `scraped_article_id`

2. **Eliminar tablas antiguas:**
   - DROP TABLE `scraped_articles`
   - Eliminar campo `scraped_article_id` de `publications`
   - Eliminar campo `scraped_article_id` de `ai_runs`

3. **Limpiar código:**
   - Eliminar modelo `ScrapedArticle` de `models.py`
   - Eliminar rutas relacionadas con scraping antiguo
   - Actualizar frontend para eliminar referencias

**Nota:** No es necesario hacer esto ahora. El sistema funciona perfectamente con ambos esquemas coexistiendo.

## Resumen Técnico

✅ **Completado:**
- Base de datos actualizada con nuevo campo `scraping_item_id`
- Modelos SQLAlchemy actualizados con relaciones correctas
- Endpoint de publicación ahora crea vínculos bidireccionales
- Backend reiniciado y funcionando correctamente

✅ **Sistema funcionando:**
- Nuevas publicaciones se crean desde `scraping_items` con vínculo completo
- Publicaciones antiguas siguen funcionando con `scraped_articles`
- Interfaz admin de scraping lista para usar en `/admin/scraping`

⚠️ **Pendiente (opcional):**
- Migrar 31 publicaciones antiguas al nuevo sistema
- Eliminar código relacionado con `scraped_articles` cuando ya no haya datos antiguos
