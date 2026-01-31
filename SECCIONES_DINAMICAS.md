# Sistema de Secciones Dinámicas

## Resumen

Sistema completo para gestionar el menú de navegación del sitio con secciones dinámicas que agrupan publicaciones por categorías.

## Características Implementadas

### 1. Base de Datos

**Migración:** [`backend/migrations/005_create_sections.sql`](backend/migrations/005_create_sections.sql)

#### Tabla `sections`
Almacena las secciones del menú de navegación:
- `id`: UUID (PK)
- `name`: Nombre de la sección (ej: "Política", "Economía")
- `slug`: URL-friendly (ej: "politica", "economia")
- `description`: Descripción de la sección
- `icon`: Nombre del icono para la UI
- `display_order`: Orden de aparición en el menú (menor = primero)
- `is_active`: Si la sección está visible o no
- `created_at`, `updated_at`: Timestamps

#### Tabla `category_section_mapping`
Mapea categorías de publicaciones a secciones (many-to-many):
- `id`: UUID (PK)
- `section_id`: FK a `sections`
- `category_name`: Nombre de la categoría
- `created_at`: Timestamp

**Índices:**
- `idx_sections_order` en (display_order, is_active)
- `idx_category_section_mapping_section` en section_id
- `idx_category_section_mapping_category` en category_name

#### Secciones Predefinidas
Se crean 10 secciones por defecto:
1. Últimas Noticias
2. Política
3. Economía
4. Sociedad
5. Mundo
6. Deportes
7. Tecnología
8. Salud
9. Cultura
10. Medio Ambiente

### 2. Backend API

**Archivo:** [`backend/app/api/routes/sections.py`](backend/app/api/routes/sections.py)

#### Endpoints Públicos

##### `GET /api/sections`
Obtiene todas las secciones con conteo de publicaciones.

**Query params:**
- `include_inactive` (bool): Incluir secciones inactivas (default: false)

**Respuesta:**
```json
{
  "sections": [
    {
      "id": "uuid",
      "name": "Política",
      "slug": "politica",
      "description": "Noticias de política nacional e internacional",
      "icon": "landmark",
      "display_order": 2,
      "is_active": true,
      "publication_count": 3
    }
  ],
  "total": 10
}
```

##### `GET /api/sections/{slug}/publications`
Obtiene publicaciones de una sección específica.

**Query params:**
- `limit` (int): Número de publicaciones (default: 20, max: 100)
- `offset` (int): Offset para paginación (default: 0)

**Respuesta:**
```json
{
  "section": {
    "id": "uuid",
    "name": "Salud",
    "slug": "salud",
    "description": "Salud y bienestar",
    "icon": "heart"
  },
  "publications": [
    {
      "id": "uuid",
      "title": "Título de la publicación",
      "slug": "titulo-de-la-publicacion",
      "summary": "Resumen...",
      "category": "Salud",
      "tags": ["salud", "medicina"],
      "published_at": "2025-12-23T15:01:35.874100+00:00"
    }
  ],
  "total": 4,
  "limit": 20,
  "offset": 0
}
```

#### Endpoints de Administración (Requieren autenticación admin)

##### `POST /api/sections`
Crea una nueva sección.

**Body:**
```json
{
  "name": "Deportes",
  "slug": "deportes",
  "description": "Actualidad deportiva",
  "icon": "target",
  "display_order": 6,
  "is_active": true
}
```

##### `GET /api/sections/{section_id}/detail`
Obtiene detalles de una sección incluyendo sus categorías asignadas.

##### `PUT /api/sections/{section_id}`
Actualiza una sección.

**Body (todos los campos son opcionales):**
```json
{
  "name": "Nuevo nombre",
  "slug": "nuevo-slug",
  "description": "Nueva descripción",
  "icon": "nuevo-icono",
  "display_order": 5,
  "is_active": false
}
```

##### `DELETE /api/sections/{section_id}`
Elimina una sección y todas sus asignaciones de categorías (CASCADE).

##### `POST /api/sections/{section_id}/categories`
Agrega una categoría a una sección.

**Body:**
```json
{
  "category_name": "Salud"
}
```

##### `DELETE /api/sections/{section_id}/categories/{category_name}`
Elimina una categoría de una sección.

##### `GET /api/sections/admin/available-categories`
Obtiene todas las categorías disponibles de publicaciones publicadas.

**Respuesta:**
```json
[
  "Economía",
  "Política",
  "Salud",
  "Tecnología"
]
```

### 3. Modelos SQLAlchemy

**Archivo:** [`backend/app/db/models.py`](backend/app/db/models.py:159-199)

```python
class Section(Base):
    """Navigation sections that group multiple categories"""
    __tablename__ = "sections"

    id: Mapped[uuid.UUID]
    name: Mapped[str]
    slug: Mapped[str]
    description: Mapped[str | None]
    icon: Mapped[str | None]
    display_order: Mapped[int]
    is_active: Mapped[bool]
    created_at: Mapped[datetime]
    updated_at: Mapped[datetime]

    category_mappings: Mapped[list["CategorySectionMapping"]]

class CategorySectionMapping(Base):
    """Maps publication categories to navigation sections (many-to-many)"""
    __tablename__ = "category_section_mapping"

    id: Mapped[uuid.UUID]
    section_id: Mapped[uuid.UUID]
    category_name: Mapped[str]
    created_at: Mapped[datetime]

    section: Mapped["Section"]
```

### 4. Frontend - Navegación Dinámica

**Archivo:** [`frontend/src/layouts/Layout.astro`](frontend/src/layouts/Layout.astro)

El layout principal del sitio obtiene las secciones del API y las muestra en el menú de navegación:

```astro
---
// Fetch sections from API
let sections: any[] = [];
try {
  const apiUrl = import.meta.env.PUBLIC_API_BASE_URL || 'http://localhost:8000';
  const response = await fetch(`${apiUrl}/api/sections`);
  if (response.ok) {
    const data = await response.json();
    sections = data.sections || [];
  }
} catch (error) {
  console.error('Failed to fetch sections:', error);
}
---

<nav class="nav" id="nav-menu">
  <a href="/" class="nav-link active">Inicio</a>
  {sections
    .filter(section => section.is_active && section.publication_count > 0)
    .slice(0, 6)
    .map(section => (
      <a href={`/seccion/${section.slug}`} class="nav-link">
        {section.name}
        {section.publication_count > 0 && (
          <span class="nav-count">{section.publication_count}</span>
        )}
      </a>
    ))
  }
</nav>
```

**Características:**
- Muestra solo secciones activas con publicaciones
- Limita a 6 secciones en el menú
- Muestra badge con contador de publicaciones
- Responsive (se adapta a móvil)

### 5. Frontend - Página de Sección

**Archivo:** [`frontend/src/pages/seccion/[slug].astro`](frontend/src/pages/seccion/[slug].astro)

Página dinámica que muestra todas las publicaciones de una sección:

**URL:** `/seccion/{slug}` (ej: `/seccion/salud`, `/seccion/politica`)

**Características:**
- Header con icono, nombre, descripción y contador
- Grid responsivo de tarjetas de publicaciones
- Muestra: título, resumen, categoría, fecha, tags
- Enlaces a publicaciones individuales
- Diseño adaptativo para móvil/tablet/desktop

### 6. Panel de Administración

**Archivo:** [`frontend/src/pages/admin/secciones/index.astro`](frontend/src/pages/admin/secciones/index.astro)

**URL:** `http://localhost:4321/admin/secciones`

Interfaz completa para administrar secciones:

#### Funcionalidades:

1. **Lista de Secciones**
   - Muestra todas las secciones (activas e inactivas)
   - Orden visual por `display_order`
   - Contador de publicaciones por sección
   - Indicador de estado (activa/inactiva)

2. **Crear/Editar Sección**
   - Modal con formulario
   - Campos: nombre, slug, descripción, icono, orden, activa
   - Validación de slug único
   - Auto-generación de slug sugerido

3. **Gestión de Categorías**
   - Modal dedicado para cada sección
   - Ver categorías asignadas
   - Agregar categorías desde dropdown
   - Remover categorías con un clic
   - Lista de categorías disponibles desde publicaciones

4. **Eliminar Sección**
   - Confirmación antes de eliminar
   - Elimina en cascada las asignaciones de categorías

#### Menú Lateral Actualizado
El `AdminLayout` ahora incluye enlace a "Secciones" en el menú de navegación admin.

## Flujo de Trabajo

### Cómo se relacionan las secciones con las publicaciones:

```
1. Publicación tiene category = "Salud"
   ↓
2. CategorySectionMapping vincula "Salud" → Section "Salud"
   ↓
3. Section "Salud" aparece en el menú con contador = 4
   ↓
4. Usuario hace clic en "Salud"
   ↓
5. Se muestra /seccion/salud con todas las publicaciones de categoría "Salud"
```

### Agregar una nueva categoría a una sección:

```bash
# Via API
POST /api/sections/{section_id}/categories
{
  "category_name": "Investigación"
}

# O via UI admin:
1. Ir a http://localhost:4321/admin/secciones
2. Clic en "Categorías" de la sección deseada
3. Seleccionar categoría del dropdown
4. Clic en "Agregar"
```

### Crear una nueva sección:

```bash
# Via API
POST /api/sections
{
  "name": "Ciencia",
  "slug": "ciencia",
  "description": "Descubrimientos científicos",
  "icon": "flask",
  "display_order": 11,
  "is_active": true
}

# O via UI admin:
1. Ir a http://localhost:4321/admin/secciones
2. Clic en "Nueva Sección"
3. Completar formulario
4. Clic en "Guardar"
```

## Mapeo Actual de Categorías

| Sección | Categorías Mapeadas |
|---------|-------------------|
| Política | Política |
| Economía | Economía |
| Sociedad | Sociedad, Educación |
| Deportes | Deportes |
| Tecnología | Tecnología, Ciencia, Investigación |
| Salud | Salud |
| Cultura | Cultura, Turismo |
| Medio Ambiente | Medio Ambiente |

## Estadísticas Actuales

- **Total secciones:** 10
- **Secciones con publicaciones:** 8
- **Categorías únicas:** 12
- **Publicaciones totales:** 34

**Distribución:**
- Tecnología: 8 publicaciones
- Economía: 6 publicaciones
- Salud: 4 publicaciones
- Política: 3 publicaciones
- Cultura: 3 publicaciones
- Medio Ambiente: 3 publicaciones
- Sociedad: 2 publicaciones
- Deportes: 1 publicación

## Ventajas del Sistema

1. **Dinámico:** El menú se actualiza automáticamente según las publicaciones
2. **Flexible:** Múltiples categorías pueden pertenecer a una sección
3. **Escalable:** Agregar nuevas secciones no requiere cambios de código
4. **Administrativo:** Todo se gestiona desde la UI admin
5. **Optimizado:** Consultas eficientes con índices y conteos
6. **Responsive:** Se adapta a cualquier tamaño de pantalla

## Próximos Pasos Opcionales

1. **Ordenar por drag-and-drop** - Interfaz para reordenar secciones arrastrando
2. **Iconos visuales** - Biblioteca de iconos integrada con preview
3. **Analytics por sección** - Estadísticas de vistas por sección
4. **Secciones destacadas** - Marcar secciones para mostrar en homepage
5. **Reglas de auto-asignación** - Reglas para mapear categorías automáticamente

## Archivos Modificados/Creados

### Backend
- ✅ `backend/migrations/005_create_sections.sql` - NUEVO
- ✅ `backend/app/db/models.py` - MODIFICADO (agregado Section, CategorySectionMapping)
- ✅ `backend/app/api/routes/sections.py` - NUEVO
- ✅ `backend/app/api/router.py` - MODIFICADO (registro de rutas)

### Frontend
- ✅ `frontend/src/layouts/Layout.astro` - MODIFICADO (navegación dinámica)
- ✅ `frontend/src/layouts/AdminLayout.astro` - MODIFICADO (link a secciones)
- ✅ `frontend/src/pages/seccion/[slug].astro` - NUEVO
- ✅ `frontend/src/pages/admin/secciones/index.astro` - NUEVO

### Documentación
- ✅ `SECCIONES_DINAMICAS.md` - NUEVO (este archivo)

## Comandos Útiles

```bash
# Consultar secciones desde terminal
curl http://localhost:8000/api/sections

# Consultar publicaciones de una sección
curl "http://localhost:8000/api/sections/salud/publications?limit=5"

# Ver categorías disponibles (requiere auth)
curl -H "Authorization: Bearer <token>" \
  http://localhost:8000/api/sections/admin/available-categories

# Verificar mapeos en la base de datos
docker exec -i ladatajusta-db-1 psql -U ladatajusta -d ladatajusta \
  -c "SELECT s.name, csm.category_name FROM sections s
      JOIN category_section_mapping csm ON s.id = csm.section_id
      ORDER BY s.display_order, csm.category_name;"
```

## Troubleshooting

### Las secciones no aparecen en el menú
- Verificar que `is_active = true`
- Verificar que `publication_count > 0`
- Verificar que hay categorías mapeadas
- Verificar que las categorías coinciden exactamente (case-sensitive)

### Error al agregar categoría
- Verificar que la categoría ya existe en alguna publicación
- Verificar que no esté ya asignada a esa sección (unique constraint)

### Backend no arranca después de migración
- Verificar que la migración se aplicó: `docker exec -i ladatajusta-db-1 psql -U ladatajusta -d ladatajusta -c "\dt sections"`
- Reconstruir imagen: `docker compose build backend --no-cache`
