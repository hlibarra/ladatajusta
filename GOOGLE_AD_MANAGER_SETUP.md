# Configuración de Google Ad Manager (GAM) - Site Skin Ads

Esta guía te ayudará a configurar los anuncios de tipo "Site Skin / Page Skin" usando Google Ad Manager (GAM) y Google Publisher Tag (GPT).

## 📋 Resumen de la Implementación

Se ha implementado un sistema completo de Site Skin Ads que:

- ✅ Muestra anuncios laterales (izquierda y derecha) solo en pantallas >= 1700px
- ✅ Oculta automáticamente los ads en resoluciones menores
- ✅ Usa Google Publisher Tag (GPT) con buenas prácticas
- ✅ Implementa fallback automático (oculta contenedores si GAM no llena)
- ✅ Maneja resize del viewport con recarga/destrucción de slots
- ✅ Logs detallados en consola para debugging

## 🔧 Configuración Requerida

### Paso 1: Obtener tu Network Code

1. Ingresa a tu cuenta de [Google Ad Manager](https://admanager.google.com/)
2. Ve a **Admin → Global settings**
3. Copia tu **Network code** (ej: `123456789`)

### Paso 2: Crear Ad Units en GAM

Crea dos ad units para los skin ads:

#### Ad Unit 1: Skin Left (Izquierdo)
- **Nombre**: `skin_left`
- **Tamaños**:
  - 300x600 (Half Page)
  - 160x600 (Wide Skyscraper)
- **Código**: Copiar el Ad Unit Path completo (ej: `/123456789/ladatajusta/skin_left`)

#### Ad Unit 2: Skin Right (Derecho)
- **Nombre**: `skin_right`
- **Tamaños**:
  - 300x600 (Half Page)
  - 160x600 (Wide Skyscraper)
- **Código**: Copiar el Ad Unit Path completo (ej: `/123456789/ladatajusta/skin_right`)

### Paso 3: Configurar en el Código

Abre el archivo: `frontend/src/layouts/Layout.astro`

Busca la sección **GAM_CONFIG** (línea ~140) y reemplaza los valores:

```javascript
var GAM_CONFIG = {
  networkCode: '123456789', // ⬅️ REEMPLAZAR: Tu Network Code de GAM
  adUnits: {
    skinLeft: '/123456789/ladatajusta/skin_left',   // ⬅️ REEMPLAZAR: Tu Ad Unit Path completo
    skinRight: '/123456789/ladatajusta/skin_right'  // ⬅️ REEMPLAZAR: Tu Ad Unit Path completo
  },
  sizes: {
    skinLeft: [[300, 600], [160, 600]],   // Tamaños permitidos
    skinRight: [[300, 600], [160, 600]]
  },
  breakpoint: 1700 // Mostrar skin ads solo en pantallas >= 1700px
};
```

**Ejemplo con valores reales:**

```javascript
var GAM_CONFIG = {
  networkCode: '987654321',
  adUnits: {
    skinLeft: '/987654321/ladatajusta/skin_left',
    skinRight: '/987654321/ladatajusta/skin_right'
  },
  sizes: {
    skinLeft: [[300, 600], [160, 600]],
    skinRight: [[300, 600], [160, 600]]
  },
  breakpoint: 1700
};
```

### Paso 4: Crear Line Items y Creatividades

En Google Ad Manager:

1. **Crear Order**: Ve a **Delivery → Orders → New Order**
2. **Crear Line Items**:
   - Uno para `skin_left`
   - Uno para `skin_right`
3. **Subir Creatividades**: Sube imágenes en los tamaños soportados (300x600 o 160x600)
4. **Targeting**: Asigna los Line Items a los Ad Units correspondientes

## 🧪 Testing y Debugging

### Probar en Local

1. **Abrir consola del navegador** (F12)
2. **Buscar logs de GAM**:
   ```
   [GAM] DOM listo - Viewport width: 1920
   [GAM] Inicializando Skin Ads...
   [GAM] Slot izquierdo definido: /123456789/ladatajusta/skin_left
   [GAM] Slot derecho definido: /123456789/ladatajusta/skin_right
   [GAM] Servicios habilitados
   [GAM] Display ejecutado para skin ads
   [GAM] Slot renderizado: div-gpt-ad-skin-left isEmpty: false
   [GAM] Contenedor visible: skin-ad-left-container
   ```

### Verificar que funciona:

1. **Viewport ancho (>= 1700px)**: Deben aparecer los contenedores laterales
2. **Viewport estrecho (< 1700px)**: Los contenedores deben ocultarse
3. **Resize**: Al cambiar tamaño de ventana, los ads deben cargarse/destruirse automáticamente
4. **Fallback**: Si GAM no tiene ads para mostrar, los contenedores se ocultan automáticamente

### Usar Google Publisher Console

Para debugging avanzado:

1. Abre la consola de Chrome (F12)
2. Escribe: `googletag.openConsole()`
3. Se abrirá la **Google Publisher Console** con información detallada de todos los slots

## 🎨 Personalización

### Cambiar el breakpoint

Si quieres que los skin ads aparezcan en resoluciones diferentes:

```javascript
breakpoint: 1920 // Cambiar a 1280, 1440, 1600, 1920, etc.
```

### Modificar tamaños de ads

Si quieres soportar otros tamaños de anuncios:

```javascript
sizes: {
  skinLeft: [[300, 600], [160, 600], [120, 600]],  // Agregar más tamaños
  skinRight: [[300, 600], [160, 600], [120, 600]]
}
```

**Tamaños IAB estándar para skins:**
- 160x600 - Wide Skyscraper
- 300x600 - Half Page
- 120x600 - Skyscraper

### Personalizar estilos

Los contenedores de skin ads tienen estas clases CSS:

```css
.skin-ad              /* Contenedor principal */
.skin-ad-left         /* Skin izquierdo */
.skin-ad-right        /* Skin derecho */
.skin-ad-content      /* Contenido interno */
#div-gpt-ad-skin-left   /* Slot GAM izquierdo */
#div-gpt-ad-skin-right  /* Slot GAM derecho */
```

Modificar en: `frontend/src/layouts/Layout.astro` (sección `<style>`)

## 🚀 Optimizaciones Implementadas

1. **Single Request**: Todos los ads se cargan en una sola petición HTTP
2. **Collapse Empty Divs**: Si no hay ad, el contenedor se colapsa automáticamente
3. **Lazy Loading**: Los ads solo se cargan si el viewport cumple el breakpoint
4. **Resize con Debounce**: Evita llamadas excesivas al hacer resize (300ms debounce)
5. **Destroy on Breakpoint**: Los slots se destruyen automáticamente en viewports pequeños

## ⚠️ Notas Importantes

1. **Testeo sin Line Items**: Si no tienes Line Items activos en GAM, los slots aparecerán vacíos y se ocultarán automáticamente
2. **Modo Test**: GAM permite usar "Google Publisher Console" para forzar creatividades de test
3. **HTTPS Required**: GPT requiere que tu sitio esté en HTTPS en producción
4. **AdBlockers**: Los ad blockers bloquearán estos ads, es comportamiento esperado

## 📚 Referencias

- [Google Publisher Tag Developer Guide](https://developers.google.com/publisher-tag/guides/get-started)
- [GPT Reference](https://developers.google.com/publisher-tag/reference)
- [GAM Implementation Guide](https://support.google.com/admanager/answer/1638622)

## 🆘 Troubleshooting

### Los ads no aparecen

1. ✅ Verifica que el Network Code sea correcto
2. ✅ Verifica que los Ad Unit Paths sean correctos
3. ✅ Asegúrate de tener Line Items activos en GAM
4. ✅ Revisa la consola del navegador por errores
5. ✅ Usa `googletag.openConsole()` para ver detalles

### Los contenedores aparecen vacíos

- Esto es normal si no hay Line Items activos
- El sistema automáticamente oculta los contenedores vacíos
- Crea Line Items y Creatividades en GAM

### Los ads no se destruyen al hacer resize

- Verifica que el breakpoint esté configurado correctamente
- Revisa los logs en consola durante el resize
- El debounce de 300ms es intencional (puedes ajustarlo)

---

**¿Necesitas ayuda?** Abre un issue en el repositorio o consulta la documentación de Google Ad Manager.
