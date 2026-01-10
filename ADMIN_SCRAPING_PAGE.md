# 🎨 Página de Admin para Scraping Items

## ✅ Implementación Completa

Se ha creado una página de administración profesional para gestionar los items scrapeados antes de su publicación.

### 📄 Archivo Creado

**`frontend/src/pages/admin/scraping/index.astro`**
- 900+ líneas de código
- Interfaz completa y funcional
- Integración con API de scraping-items

### 🔗 URL de Acceso

```
http://localhost:4321/admin/scraping
```

## 🎯 Características Implementadas

### 1. **Dashboard con Estadísticas** 📊

4 tarjetas de stats en tiempo real:
- ✅ **Scrapeados** - Total de items scrapeados
- ✅ **Listos para IA** - Items pendientes de procesamiento
- ✅ **Publicados** - Items ya convertidos en publicaciones
- ✅ **Con errores** - Items que fallaron

### 2. **Filtros Avanzados** 🔍

Barra de filtros con:
- **Estado**: Todos los estados del pipeline
  - Scrapeado
  - Pendiente revisión
  - Listo para IA
  - Procesando IA
  - IA completado
  - Listo para publicar
  - Publicado
  - Descartado
  - Error
  - Duplicado

- **Medio**: Filtrar por fuente
  - La Gaceta
  - Clarín
  - Infobae
  - La Nación
  - Página 12
  - Perfil
  - Otros

- **Búsqueda de texto**: Buscar en título o contenido

### 3. **Tabla de Items** 📋

Muestra para cada item:
- **Estado** con badge de color
- **Medio** de origen
- **Título** (original o generado por IA)
- **Sección** (si existe)
- **Fecha** de scraping (relativa: "Hace 2h", "Ayer", etc.)
- **Acciones** según el estado

### 4. **Acciones Rápidas** ⚡

Botones de acción contextuales:

**Si está "Scrapeado":**
- ✅ **Aprobar** - Marca como "ready_for_ai"

**Si tiene "Error":**
- 🔄 **Reintentar** - Marca como "ready_for_ai" para re-procesar

**Si no está publicado/descartado:**
- ❌ **Descartar** - Marca como descartado

### 5. **Modal de Detalles** 🔍

Al hacer click en el ícono de ojo (👁️):

**Información General:**
- ID del item
- Estado actual
- Medio y sección
- Autor
- Fecha de scraping

**Contenido Original:**
- Título
- Subtítulo (si existe)
- Resumen
- Contenido completo (preview de 500 chars)
- URL original (clickeable)
- Tags

**Contenido IA** (si existe):
- Título generado por IA
- Resumen generado por IA
- Categoría sugerida
- Modelo utilizado

**Errores** (si existen):
- Mensaje de error
- Contador de intentos

### 6. **Paginación** 📄

- 20 items por página
- Botones Anterior/Siguiente
- Indicador: "1-20 de 145"

### 7. **Actualización en Tiempo Real** 🔄

- Botón "Actualizar" para refrescar
- Auto-refresh de stats después de cada acción
- Loading states mientras carga

## 🎨 Diseño

### Tema Claro
- Fondo blanco
- Texto oscuro
- Bordes sutiles
- Cards con sombras suaves

### Badges de Estado con Colores

- 🟣 **Scrapeado** - Púrpura
- 🟠 **Pendiente revisión** - Naranja
- 🔵 **Listo para IA** - Azul
- 🔷 **Procesando IA** - Azul claro
- 🟢 **IA completado** - Verde claro
- ✅ **Listo para publicar** - Verde
- ✅ **Publicado** - Verde
- ⚫ **Descartado** - Gris
- 🔴 **Error** - Rojo
- ⚫ **Duplicado** - Gris

### Responsive
- Tabla adaptable en mobile
- Filtros en columna en pantallas pequeñas
- Modal full-screen en mobile

## 🔌 Integración con API

Endpoints utilizados:

```typescript
// Obtener estadísticas
GET /api/scraping-items/stats/summary

// Listar items con filtros
GET /api/scraping-items?status=...&source_media=...&search_text=...&limit=20&offset=0

// Obtener detalles de un item
GET /api/scraping-items/{id}

// Actualizar estado
PATCH /api/scraping-items/{id}
```

## 🚀 Uso

### Acceder a la Página

1. Ir a http://localhost:4321/admin/login
2. Login con credenciales de admin
3. En el sidebar, click en "**Scraping**"

### Workflow Típico

**1. Ver items recién scrapeados:**
- Filtrar por Estado: "Scrapeado"
- Ver la lista de nuevos items

**2. Aprobar para procesamiento IA:**
- Click en botón ✅ (Aprobar)
- El item pasa a estado "ready_for_ai"

**3. Ver items con error:**
- Filtrar por Estado: "Error"
- Ver detalles del error (ícono ojo)
- Click en 🔄 (Reintentar) para re-procesar

**4. Buscar un item específico:**
- Usar el campo de búsqueda
- Busca en título y contenido

**5. Ver detalles completos:**
- Click en ícono ojo 👁️
- Ver toda la información
- Revisar contenido original vs IA

**6. Descartar items no relevantes:**
- Click en ❌ (Descartar)
- El item se marca como descartado

## 📊 Estados del Pipeline

```
┌──────────────┐
│  Scrapeado   │  ← Recién importado
└──────┬───────┘
       │ (Acción: Aprobar ✅)
       ▼
┌──────────────┐
│Ready for IA  │  ← Listo para procesar
└──────┬───────┘
       │ (Pipeline de IA)
       ▼
┌──────────────┐
│IA Completed  │  ← IA terminó
└──────┬───────┘
       │ (Auto o manual)
       ▼
┌──────────────┐
│Ready to Pub  │  ← Listo para publicar
└──────┬───────┘
       │ (Publicación)
       ▼
┌──────────────┐
│  Published   │  ← Convertido en publicación
└──────────────┘

Estados alternativos:
- Error → Reintentar → Ready for IA
- Descartado (final)
- Duplicado (final)
```

## 🎯 Próximos Pasos Sugeridos

1. **Probar la página**
   - Navegar a http://localhost:4321/admin/scraping
   - Verificar que carga correctamente

2. **Insertar datos de prueba**
   - Usar Swagger para crear items de prueba
   - O ejecutar `python examples/scraper_example.py`

3. **Probar filtros**
   - Filtrar por diferentes estados
   - Buscar texto
   - Verificar paginación

4. **Probar acciones**
   - Aprobar un item
   - Descartar un item
   - Ver detalles en el modal

## 🐛 Troubleshooting

### No veo items en la tabla
- ✅ Verificar que la tabla `scraping_items` existe en la DB
- ✅ Verificar que hay items en la DB (SQL: `SELECT COUNT(*) FROM scraping_items`)
- ✅ Verificar que el backend está corriendo
- ✅ Abrir consola del navegador (F12) para ver errores

### Los botones no funcionan
- ✅ Verificar que estás autenticado como admin
- ✅ Verificar endpoints en Swagger funcionan
- ✅ Revisar consola del navegador

### El modal no se abre
- ✅ Verificar que el item existe
- ✅ Revisar consola del navegador
- ✅ Verificar endpoint GET `/api/scraping-items/{id}`

## 📝 Código Importante

### Cambiar página con filtros:
```typescript
currentFilters = {
  status: 'ready_for_ai',
  source_media: 'lagaceta',
  search_text: 'política'
};
loadItems();
```

### Actualizar estado de un item:
```typescript
await authFetch(`/api/scraping-items/${itemId}`, {
  method: 'PATCH',
  body: JSON.stringify({ status: 'ready_for_ai' })
});
```

---

## ✨ Resumen

✅ **Página completa creada**: `/admin/scraping`
✅ **Link agregado al sidebar**: Visible en el menú de admin
✅ **Stats en tiempo real**: 4 tarjetas con métricas
✅ **Filtros avanzados**: Estado, medio, búsqueda
✅ **Tabla con paginación**: 20 items por página
✅ **Acciones contextuales**: Aprobar, reintentar, descartar
✅ **Modal de detalles**: Vista completa del item
✅ **Diseño responsive**: Funciona en mobile
✅ **Tema claro**: Consistente con el resto del admin

**¡Todo listo para gestionar items scrapeados!** 🎉
