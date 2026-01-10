# Sistema de Auditoría de Publicaciones

## Resumen

Se ha implementado un sistema completo de auditoría que registra **quién publicó cada noticia** y **qué agente editorial la firmó**.

## Cambios Implementados

### 1. Base de Datos

**Migración:** [`backend/migrations/004_add_published_by_user_id.sql`](backend/migrations/004_add_published_by_user_id.sql)

```sql
ALTER TABLE publications
  ADD COLUMN published_by_user_id UUID REFERENCES users(id) ON DELETE SET NULL;

CREATE INDEX idx_publications_published_by_user ON publications(published_by_user_id);
```

### 2. Modelo SQLAlchemy

**Archivo:** [`backend/app/db/models.py`](backend/app/db/models.py:77-79)

```python
published_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
    UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"),
    nullable=True, index=True
)
```

**Relación agregada:**
```python
published_by_user: Mapped[Optional["User"]] = relationship(foreign_keys=[published_by_user_id])
```

### 3. Endpoint de Publicación

**Archivo:** [`backend/app/api/routes/scraping_items.py`](backend/app/api/routes/scraping_items.py:267-287)

**Cambios:**
- ✅ **Requiere autenticación de admin** (`CurrentAdmin`)
- ✅ **Registra automáticamente** el usuario que publicó
- ✅ **Mantiene la selección manual** del agente editorial

**Firma actualizada:**
```python
@router.post("/{item_id}/publish", response_model=dict)
async def publish_scraping_item(
    item_id: uuid.UUID,
    publish_req: ScrapingItemPublishRequest,
    current_user: CurrentAdmin,  # ← NUEVO: requiere admin
    db: AsyncSession = Depends(get_db),
) -> Any:
```

**Creación de publicación:**
```python
publication = Publication(
    scraped_article_id=None,
    scraping_item_id=item_id,
    agent_id=publish_req.agent_id,          # ← Agente editorial (manual)
    published_by_user_id=current_user.id,    # ← Usuario admin (automático)
    state="published",
    title=title,
    # ... resto de campos
)
```

## Conceptos Clave

### Agent vs User

| Concepto | Propósito | Visible para | Cómo se asigna |
|----------|-----------|--------------|----------------|
| **Agent** (Agente Editorial) | Personalidad que "firma" la noticia públicamente | Lectores del sitio | **Manual** - El admin lo selecciona al publicar |
| **User** (Usuario Admin) | Persona real que operó el sistema | Solo auditoría interna | **Automático** - Se registra del token JWT |

**Ejemplos de Agentes:**
- Ana Datos (Política y Transparencia)
- Diego Ambiente (Medio Ambiente)
- Carmen Economía (Economía)
- María Salud (Salud)
- Roberto Investigador (Investigación)

### Flujo de Publicación

```
1. Admin hace login → Recibe token JWT
2. Admin abre scraping item → Modal de publicación
3. Admin selecciona agente → (Opcional, puede ser null)
4. Admin hace clic en "Publicar"
   ↓
5. Backend valida token → Extrae user_id
6. Backend crea publicación:
   - agent_id = selección del admin (o null)
   - published_by_user_id = user_id del token
   - published_at = timestamp actual
```

## Datos Registrados al Publicar

| Campo | Valor | Tipo |
|-------|-------|------|
| `published_at` | Fecha/hora UTC de publicación | Timestamp automático |
| `published_by_user_id` | ID del usuario admin que publicó | **NUEVO** - Automático del JWT |
| `agent_id` | ID del agente editorial que firma | Manual/Opcional |
| `scraping_item_id` | Vínculo al item scrapeado | Automático |
| `state` | "published" | Automático |
| `created_at` | Fecha/hora de creación del registro | Timestamp automático |

## Seguridad

### Antes ❌
```python
# Cualquiera podía publicar sin autenticación
@router.post("/{item_id}/publish")
async def publish_scraping_item(
    item_id: uuid.UUID,
    publish_req: ScrapingItemPublishRequest,
    db: AsyncSession = Depends(get_db),
):
```

### Ahora ✅
```python
# Solo admins autenticados pueden publicar
@router.post("/{item_id}/publish")
async def publish_scraping_item(
    item_id: uuid.UUID,
    publish_req: ScrapingItemPublishRequest,
    current_user: CurrentAdmin,  # ← Requiere JWT de admin
    db: AsyncSession = Depends(get_db),
):
```

## Consultas de Auditoría

### Ver quién publicó cada noticia

```sql
SELECT
    p.id,
    p.title,
    p.published_at,
    u.email as published_by,
    a.name as signed_by_agent
FROM publications p
LEFT JOIN users u ON p.published_by_user_id = u.id
LEFT JOIN agents a ON p.agent_id = a.id
WHERE p.state = 'published'
ORDER BY p.published_at DESC;
```

### Publicaciones por usuario

```sql
SELECT
    u.email,
    COUNT(p.id) as total_publicaciones
FROM users u
LEFT JOIN publications p ON p.published_by_user_id = u.id
WHERE u.is_admin = true
GROUP BY u.id, u.email
ORDER BY total_publicaciones DESC;
```

### Publicaciones por agente

```sql
SELECT
    a.name as agente,
    a.specialization,
    COUNT(p.id) as total_publicaciones
FROM agents a
LEFT JOIN publications p ON p.agent_id = a.id
WHERE p.state = 'published'
GROUP BY a.id, a.name, a.specialization
ORDER BY total_publicaciones DESC;
```

## Retrocompatibilidad

✅ **Publicaciones antiguas siguen funcionando**
- El campo `published_by_user_id` es **nullable**
- Publicaciones creadas antes tienen `published_by_user_id = NULL`
- No hay pérdida de datos

## Próximos Pasos (Opcionales)

1. **Dashboard de auditoría** - Crear vista admin con:
   - Publicaciones por usuario
   - Publicaciones por agente
   - Gráficos de actividad

2. **Logs de cambios** - Registrar modificaciones:
   - Quién cambió el estado (draft → published)
   - Quién modificó el contenido
   - Historial de ediciones

3. **Permisos granulares** - Diferentes niveles:
   - Editor: puede publicar
   - Revisor: solo puede aprobar
   - Admin: control total

## Resumen Técnico

✅ **Completado:**
- Migración de base de datos aplicada
- Modelo actualizado con campo `published_by_user_id`
- Endpoint requiere autenticación de admin
- Usuario se registra automáticamente al publicar
- Backend reiniciado y funcionando

✅ **Frontend ya compatible:**
- `authFetch` envía token JWT automáticamente
- No requiere cambios en la interfaz

✅ **Listo para usar:**
- Al publicar desde http://localhost:4321/admin/scraping
- El sistema registrará automáticamente quién publicó
