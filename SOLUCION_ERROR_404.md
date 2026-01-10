# 🔧 Solución al Error 404 en Scraping Items

## ❌ Error Actual

```
GET http://localhost:8000/api/scraping-items/stats/summary 404 (Not Found)
```

## ✅ Causa del Problema

El backend está corriendo con código antiguo (antes de agregar las rutas de scraping). Necesita **reiniciarse** para cargar las nuevas rutas.

## 🚀 Solución Paso a Paso

### Paso 1: Detener el Backend

Si tienes el backend corriendo en una terminal, presiona `Ctrl + C` para detenerlo.

### Paso 2: Verificar que la Tabla Existe

La tabla `scraping_items` ya fue creada correctamente. Puedes verificarlo con:

```powershell
docker exec ladatajusta-db-1 psql -U ladatajusta -d ladatajusta -c "\dt scraping_items"
```

Deberías ver:
```
           List of relations
 Schema |      Name       | Type  |   Owner
--------+-----------------+-------+------------
 public | scraping_items  | table | ladatajusta
```

### Paso 3: Reiniciar el Backend

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Deberías ver en la salida:
```
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
INFO:     Started reloader process [xxxxx] using StatReload
INFO:     Started server process [xxxxx]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
```

### Paso 4: Verificar que las Rutas Están Cargadas

Abrir en el navegador:
```
http://localhost:8000/docs
```

Buscar la sección **"scraping-items"** - deberías ver:
- `POST /api/scraping-items`
- `POST /api/scraping-items/upsert`
- `GET /api/scraping-items`
- `GET /api/scraping-items/{item_id}`
- `PATCH /api/scraping-items/{item_id}`
- `DELETE /api/scraping-items/{item_id}`
- `POST /api/scraping-items/{item_id}/publish`
- `GET /api/scraping-items/stats/summary`
- `POST /api/scraping-items/bulk/mark-duplicates`

### Paso 5: Probar el Endpoint Manualmente

En una nueva terminal PowerShell:

```powershell
curl http://localhost:8000/api/scraping-items/stats/summary
```

Deberías obtener una respuesta JSON (aunque esté vacía porque no hay datos aún):

```json
{
  "total_items": 0,
  "by_status": {},
  "by_source_media": {},
  "avg_ai_tokens": null,
  "total_ai_cost_usd": null,
  "items_with_errors": 0,
  "items_ready_for_ai": 0,
  "items_pending_publish": 0
}
```

### Paso 6: Crear Datos de Prueba

Ahora que el backend está corriendo correctamente:

```powershell
cd backend
python -m scripts.seed_scraping_items
```

Deberías ver:
```
============================================================
  Seed Script - Crear Items de Prueba
============================================================

Creando 30 items de prueba...

  [1/30] Creando item... ✅ Gobierno anuncia nuevas medidas...
  ...
  [30/30] Creando item... ✅ Innovación tecnológica...

============================================================
  ✅ Creados: 30
  ❌ Fallidos: 0
============================================================
```

### Paso 7: Recargar la Página de Admin

1. Ir a: http://localhost:4321/admin/scraping
2. Presionar `F5` para recargar
3. Ahora deberías ver:
   - ✅ Stats cargadas (tarjetas con números)
   - ✅ Tabla con 20 items
   - ✅ Todo funcionando

## 🐛 Si Aún No Funciona

### Verificación 1: Backend está en el puerto correcto

```powershell
curl http://localhost:8000/health
```

Debe retornar: `{"ok":true}`

### Verificación 2: Frontend está usando la URL correcta

Abrir consola del navegador (F12) y verificar que las peticiones van a:
```
http://localhost:8000/api/scraping-items/...
```

### Verificación 3: Usuario está autenticado

En http://localhost:4321/admin/scraping, verificar que:
- Tienes sesión iniciada como admin
- No te redirige al login

### Verificación 4: No hay errores en el backend

En la terminal donde corre el backend, no debería haber errores tipo:
```
ERROR: ...
```

Si ves errores, cópialos y revisa.

## ✅ Checklist Final

Después de reiniciar el backend:

- [ ] Backend corriendo en puerto 8000
- [ ] Swagger muestra sección "scraping-items" con 9 endpoints
- [ ] `curl http://localhost:8000/api/scraping-items/stats/summary` retorna JSON
- [ ] Tabla `scraping_items` existe en DB
- [ ] Script seed crea 30 items exitosamente
- [ ] Página http://localhost:4321/admin/scraping carga sin errores
- [ ] Stats se muestran correctamente
- [ ] Tabla muestra items

## 🎯 Resumen

**El problema:** El backend no tenía cargadas las nuevas rutas de scraping-items.

**La solución:** Reiniciar el backend con `uvicorn`.

**Verificación:** Abrir http://localhost:8000/docs y buscar "scraping-items".

---

**Si sigues estos pasos, todo debería funcionar correctamente.** 🚀
