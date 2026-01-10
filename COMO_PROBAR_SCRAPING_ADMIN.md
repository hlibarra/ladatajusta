# 🚀 Cómo Probar la Página de Admin de Scraping

Guía paso a paso para probar la nueva página de administración de items scrapeados.

---

## ✅ Paso 1: Ejecutar la Migración SQL

Si aún NO ejecutaste la migración de la tabla `scraping_items`:

```powershell
# Conectar a PostgreSQL
docker exec -i ladatajusta-db-1 psql -U ladatajusta -d ladatajusta < backend/migrations/001_create_scraping_items.sql
```

Verificar que se creó:
```powershell
docker exec -it ladatajusta-db-1 psql -U ladatajusta -d ladatajusta -c "\dt scraping_items"
```

Deberías ver la tabla `scraping_items` en la lista.

---

## ✅ Paso 2: Reiniciar el Backend

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Verificar que está corriendo:
- Abrir: http://localhost:8000/docs
- Buscar sección "scraping-items"
- Deberías ver 9 endpoints

---

## ✅ Paso 3: Reiniciar el Frontend

```powershell
cd frontend
npm run dev
```

Verificar que está corriendo:
- Abrir: http://localhost:4321

---

## ✅ Paso 4: Crear Datos de Prueba

Ejecutar el script que crea 30 items de ejemplo:

```powershell
cd backend
python -m scripts.seed_scraping_items
```

Deberías ver algo así:
```
============================================================
  Seed Script - Crear Items de Prueba
============================================================

Creando 30 items de prueba...

  [1/30] Creando item... ✅ Gobierno anuncia nuevas medidas... (Estado: scraped)
  [2/30] Creando item... ✅ Histórica victoria del equipo... (Estado: error)
  [3/30] Creando item... ✅ Científicos descubren nueva... (Estado: ai_completed)
  ...
  [30/30] Creando item... ✅ Innovación tecnológica... (Estado: published)

============================================================
  ✅ Creados: 30
  ❌ Fallidos: 0
============================================================

🎉 ¡Datos de prueba creados!
```

---

## ✅ Paso 5: Acceder al Admin

### 5.1. Iniciar Sesión

1. Abrir: http://localhost:4321/admin/login

2. Ingresar credenciales:
   - **Email**: `admin@local.com`
   - **Password**: `admin123`

   > Si no tienes usuario admin, créalo:
   > ```powershell
   > cd backend
   > python -m scripts.create_admin
   > ```

3. Click en "Iniciar sesión"

### 5.2. Ir a la Página de Scraping

1. En el sidebar (izquierda), verás un nuevo enlace: **"Scraping"**

2. Click en "Scraping"

3. Deberías ver:
   - ✅ 4 tarjetas con estadísticas en la parte superior
   - ✅ Barra de filtros (Estado, Medio, Buscar)
   - ✅ Tabla con 20 items (paginados)
   - ✅ Botones de acción en cada item

---

## 🎮 Paso 6: Probar Funcionalidades

### 6.1. Ver Estadísticas

En la parte superior deberías ver algo como:
- **Scrapeados**: 10
- **Listos para IA**: 6
- **Publicados**: 8
- **Con errores**: 6

### 6.2. Filtrar por Estado

1. Click en el dropdown "Estado"
2. Seleccionar "Scrapeado"
3. Click en "Filtrar"
4. Ahora solo verás items con estado "Scrapeado"

### 6.3. Filtrar por Medio

1. Click en el dropdown "Medio"
2. Seleccionar "La Gaceta"
3. Click en "Filtrar"
4. Ahora solo verás items de La Gaceta

### 6.4. Buscar Texto

1. En el campo "Buscar", escribir: "gobierno"
2. Click en "Filtrar"
3. Verás items que contienen "gobierno" en título o contenido

### 6.5. Limpiar Filtros

1. Click en "Limpiar"
2. Todos los filtros se resetean

### 6.6. Ver Detalles de un Item

1. En cualquier fila de la tabla, click en el ícono de **ojo** 👁️
2. Se abrirá un modal con:
   - Información general
   - Contenido original
   - Contenido generado por IA (si existe)
   - Errores (si existen)
3. Click en "Cerrar" o la X para cerrar el modal

### 6.7. Aprobar un Item

1. Buscar un item con estado "Scrapeado"
2. Click en el botón verde ✅ (Aprobar)
3. Confirmar en el diálogo
4. El item cambia a estado "Listo para IA" (ready_for_ai)
5. Las stats se actualizan automáticamente

### 6.8. Reintentar un Item con Error

1. Filtrar por Estado: "Error"
2. Click en el botón naranja 🔄 (Reintentar)
3. Confirmar
4. El item cambia a "Listo para IA"

### 6.9. Descartar un Item

1. En cualquier item que NO esté publicado
2. Click en el botón rojo ❌ (Descartar)
3. Confirmar
4. El item cambia a estado "Descartado"

### 6.10. Paginación

1. En la parte inferior de la tabla verás: "1-20 de 30"
2. Click en "Siguiente"
3. Verás items 21-30
4. Click en "Anterior" para volver

### 6.11. Actualizar Manualmente

1. Click en el botón "Actualizar" (🔄 arriba a la derecha)
2. Se recargan los items y las stats

---

## 🎨 Elementos Visuales a Verificar

### Badges de Estado

Cada estado tiene un color diferente:
- 🟣 **Scrapeado** - Badge púrpura
- 🔵 **Listo para IA** - Badge azul
- 🟢 **IA completado** - Badge verde claro
- ✅ **Publicado** - Badge verde
- 🔴 **Error** - Badge rojo
- ⚫ **Descartado** - Badge gris

### Tarjetas de Stats

4 tarjetas con íconos:
- 📦 Scrapeados (púrpura)
- ⏱️ Listos para IA (azul)
- ✅ Publicados (verde)
- ❌ Con errores (rojo)

### Tabla Responsive

- En desktop: Tabla completa
- En mobile: Tabla adaptable o scroll horizontal

---

## 🐛 Verificar Funcionalidad

### Test Checklist

- [ ] Stats cargan correctamente
- [ ] Tabla muestra items
- [ ] Filtros funcionan (estado, medio, búsqueda)
- [ ] Paginación funciona (siguiente/anterior)
- [ ] Modal de detalles se abre y cierra
- [ ] Botón "Aprobar" cambia estado a ready_for_ai
- [ ] Botón "Reintentar" funciona en items con error
- [ ] Botón "Descartar" cambia estado a discarded
- [ ] Botón "Actualizar" recarga datos
- [ ] Loading states se muestran correctamente
- [ ] Empty state se muestra si no hay items

---

## 🎯 Flujo Completo de Prueba

### Escenario: Procesar un Item Scrapeado

1. **Ver item inicial**
   - Filtrar por estado "Scrapeado"
   - Identificar un item

2. **Ver detalles**
   - Click en ojo 👁️
   - Revisar contenido original
   - Cerrar modal

3. **Aprobar para IA**
   - Click en ✅ Aprobar
   - Confirmar
   - Verificar que cambió a "Listo para IA"

4. **Simular procesamiento IA**
   - En Swagger (http://localhost:8000/docs)
   - Buscar `PATCH /api/scraping-items/{id}`
   - Usar el ID del item
   - Actualizar con:
   ```json
   {
     "status": "ai_completed",
     "ai_title": "Título generado por IA",
     "ai_summary": "Resumen generado",
     "ai_model": "gpt-4o-mini"
   }
   ```

5. **Verificar cambios**
   - Volver al admin
   - Click en "Actualizar"
   - Ver que el item ahora está en "IA completado"
   - Abrir detalles y ver contenido IA

---

## 📸 Screenshots Esperados

### Vista Principal
```
┌────────────────────────────────────────────────────┐
│ 📦 Scrapeados: 10  ⏱️ Listos: 6  ✅ Pub: 8  ❌ Err: 6│
├────────────────────────────────────────────────────┤
│ Estado: [Todos▼] Medio: [Todos▼] Buscar: [______] │
│ [Filtrar] [Limpiar]                                │
├─────┬─────────┬───────────────────┬────────┬───────┤
│🟣   │lagaceta │Gobierno anuncia...│Hace 2h │👁️✅❌  │
│🔵   │clarin   │Histórica victoria.│Ayer    │👁️     │
│🔴   │infobae  │Científicos desc...│Hace 5h │👁️🔄❌  │
└─────┴─────────┴───────────────────┴────────┴───────┘
                  1-20 de 30
            [Anterior] [Siguiente]
```

---

## ✅ Checklist Final

Antes de dar por terminado, verificar:

- [ ] Backend corriendo en puerto 8000
- [ ] Frontend corriendo en puerto 4321
- [ ] Tabla `scraping_items` creada en DB
- [ ] 30 items de prueba creados
- [ ] Login admin funcionando
- [ ] Página `/admin/scraping` accesible
- [ ] Stats se muestran correctamente
- [ ] Filtros funcionan
- [ ] Acciones (aprobar, descartar, reintentar) funcionan
- [ ] Modal de detalles funciona
- [ ] Paginación funciona

---

## 🎉 ¡Listo!

Si todos los pasos funcionaron:
- ✅ Tienes una página completa de administración de scraping
- ✅ Puedes ver, filtrar y gestionar items scrapeados
- ✅ Puedes aprobar items para procesamiento IA
- ✅ Puedes ver detalles completos de cada item
- ✅ Tienes un workflow visual claro del pipeline

**Próximo paso sugerido**: Crear el pipeline de IA automático que procese items con estado `ready_for_ai`.
