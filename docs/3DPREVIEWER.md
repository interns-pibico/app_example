# 3D Previewer — Documentación de Herramienta

> **Versión:** 1.0 · **Fecha:** 2026-03-23
> **URL:** `https://cris.pibico.es/3dpreviewer` · **Ruta local:** `GET /3dpreviewer`
> **Propósito:** Herramienta de desarrollo interna para previsualizar, manipular y exportar modelos 3D que luego se integran en el mapa de Asturias.

---

## Tabla de Contenidos

1. [Descripción General](#1-descripción-general)
2. [Interfaz — Layout de 3 Paneles](#2-interfaz--layout-de-3-paneles)
3. [Panel Izquierdo — Herramientas](#3-panel-izquierdo--herramientas)
4. [Viewport — Canvas 3D Central](#4-viewport--canvas-3d-central)
5. [Panel Derecho — Exportar y Código](#5-panel-derecho--exportar-y-código)
6. [Flujos de Trabajo Típicos](#6-flujos-de-trabajo-típicos)
7. [Referencia Técnica](#7-referencia-técnica)

---

## 1. Descripción General

El **3D Previewer** es un editor 3D ligero integrado en el proyecto `app_example`. Está diseñado para:

- **Previsualizar** modelos GLB/GLTF y archivos SVG en 3D antes de integrarlos en el mapa de Asturias
- **Ajustar** posición, rotación, escala y materiales de los modelos
- **Generar** automáticamente el código Three.js equivalente listo para pegar en los JSONs de edificios
- **Convertir** imágenes bitmap (PNG/JPG/WebP) en SVG vectoriales extruibles en 3D
- **Componer** escenas con primitivas y elementos arquitectónicos
- **Ejecutar** código Three.js directamente en la escena sin recargar la página

### Tecnologías usadas (todas locales, sin CDN)

| Librería | Versión | Función |
|----------|---------|---------|
| Three.js | r172 | Motor 3D (core + module) |
| OrbitControls | r172 | Navegación cámara (orbit, zoom, pan) |
| GLTFLoader | r172 | Importar modelos GLB/GLTF |
| GLTFExporter | r172 | Exportar escena a GLB |
| SVGLoader | r172 | Importar y extruir SVG en 3D |
| TransformControls | r172 | Gizmos de transformación interactivos |
| ImageTracer | — | Vectorización bitmap → SVG |

---

## 2. Interfaz — Layout de 3 Paneles

```
┌─────────────────────────────────────────────────────────────────────┐
│  HEADER: logo · estado · selector de fondo · botón Limpiar          │
├──────────────────┬──────────────────────────┬───────────────────────┤
│  PANEL IZQUIERDO │   VIEWPORT (canvas 3D)   │   PANEL DERECHO       │
│  270px           │   flexible (1fr)         │   260px               │
│                  │                          │                        │
│  Importar        │   [Canvas Three.js]      │   Exportar            │
│  ────────        │                          │   ─────────           │
│  Toolbar (8      │   OrbitControls          │   ↓ GLB               │
│  herramientas)   │   Grid / Wireframe       │   ↓ Three.js          │
│                  │   Info overlay           │   ↓ JSON              │
│  Panel activo    │                          │                        │
│  (varía según    │   Drop zone overlay      │   Transformar sel.    │
│  herramienta)    │   Loading overlay        │                        │
│                  │                          │   Visor código        │
│                  │                          │   (Three.js/JSON/Info)│
└──────────────────┴──────────────────────────┴───────────────────────┘
```

### Header

| Elemento | Función |
|----------|---------|
| `← Volver` | Navega a `/` (mapa principal) |
| Dot pulsante verde | Indica estado de Three.js (animado = activo) |
| Texto de estado | Muestra el último evento (carga, error, exportación...) |
| Swatches de fondo | 8 colores presets + picker personalizado para el fondo del viewport |
| `⊘ Limpiar` | Elimina todos los objetos de la escena |

**Fondos predefinidos:**

| Color | Hex | Uso típico |
|-------|-----|-----------|
| Negro | `#05050c` | Contraste máximo (default) |
| Azul noche | `#1a1a2e` | Revisión nocturna |
| Gris oscuro | `#2d2d2d` | Neutral |
| Slate | `#557a8a` | Semejante al océano del mapa |
| Azul cielo (Asturias) | `#a7d1f1` | Contexto del mapa real |
| Gris claro | `#d0d0d0` | Contraste con modelos oscuros |
| Hueso | `#f0ede8` | Revisión de colores claros |
| Blanco | `#ffffff` | Presentación |

---

## 3. Panel Izquierdo — Herramientas

### 3.1 Zona de Importación (siempre visible)

#### Drag & Drop / Clic para subir

Acepta dos tipos de archivo:

| Formato | Badge | Procesado por |
|---------|-------|---------------|
| `.glb` / `.gltf` | GLB (azul) | `GLTFLoader` de Three.js |
| `.svg` | SVG (verde) | `SVGLoader` → ExtrudeGeometry |

También se puede cargar un GLB por URL (campo de texto + botón `↓`).

---

### 3.2 Toolbar de Herramientas (8 modos)

```
[ ⬚ Sel ] [ 🔍 Insp ] [ 🎨 Mat ] [ ⬛ Prim ] [ ⬡ Path ] [ 🖼 Img→SVG ] [ 🏗 Build ] [ ⟨/⟩ Código ]
```

El botón activo se resalta en verde. Cada modo abre su panel específico debajo.

---

### 3.3 Modo Sel — Lista de objetos en escena

Lista todos los objetos raíz cargados en la escena:

| Icono | Tipo |
|-------|------|
| 🔵 (azul) | Objeto GLB/GLTF |
| 🟢 (verde) | Objeto SVG extruido |

Acciones por objeto:
- **Clic en nombre** → selecciona el objeto (lo resalta en el viewport)
- **`×`** (papelera) → elimina el objeto de la escena

---

### 3.4 Modo Insp — Inspector jerárquico de meshes

Muestra el árbol completo de nodos del objeto seleccionado (Group → Mesh → ...).

#### Barra de TransformControls

Aparece cuando hay un mesh seleccionado:

| Botón | Modo | Atajo visual |
|-------|------|--------------|
| `⟷ Mover` | translate | Flechas XYZ en viewport |
| `↻ Rotar` | rotate | Arcos de rotación |
| `⤢ Escalar` | scale | Cubos de escala |
| `✕ Off` | ninguno | Desactiva gizmos |

#### Panel de transformación numérica (`#xfPanel`)

Inputs numéricos de precisión para el mesh seleccionado:

| Campo | Unidad | Step |
|-------|--------|------|
| Pos X/Y/Z | unidades Three.js | 0.01 |
| Rot X/Y/Z | grados (°) | 1° |
| Esc X/Y/Z | factor multiplicador | 0.01 |

#### Barra de acciones del Inspector

| Botón | Acción |
|-------|--------|
| `＋⬛` | Añadir caja como hijo del GLB seleccionado |
| `＋⚪` | Añadir esfera como hijo |
| `＋🔵` | Añadir cilindro como hijo |
| `＋ GLB` | Fusionar otro GLB dentro del GLB activo (merge) |

---

### 3.5 Modo Mat — Editor de materiales

#### Sub-panel: Material del mesh (GLB / primitiva)

Disponible cuando hay un mesh seleccionado en el Inspector.

**Tipos de material:**

| Tipo | Descripción | Cuándo usar |
|------|-------------|-------------|
| Lambert | Difuso plano, bajo coste | Low-poly, estilo cartoon |
| Phong | Brillos especulares suaves | Materiales semi-brillantes |
| Standard (PBR) | Físicamente correcto | Metales, plásticos realistas |
| Basic | Sin iluminación | Debug, pantallas, UI |
| Wireframe | Solo aristas | Debug de geometría |

**Controles:**
- **Color**: picker visual + input hex manual (`#rrggbb`)
- **Opacidad**: slider 0.00–1.00
- **Roughness** / **Metalness**: sliders (solo en modo Standard/PBR)
- **Profundidad Z**: slider para meshes extruidos no-SVG
- **Aplicar** → aplica al mesh/objeto seleccionado
- **A todos** → aplica el material a toda la escena

#### Sub-panel: SVG → 3D (global)

Controles globales para los SVG cargados:

| Control | Rango | Descripción |
|---------|-------|-------------|
| Profundidad | 0.01–2.0 | Profundidad de extrusión 3D |
| Escala | 0.1–5.0 | Escala global del SVG |
| Material | (lista) | Lambert / Phong / Standard / Wireframe |
| Color | picker | Color uniforme |
| Color SVG | toggle | Usar los colores originales del SVG |
| Doble cara | toggle | `DoubleSide` (evita caras negras al girar) |
| Flat shading | toggle | Normales planas (estilo low-poly) |

---

### 3.6 Modo Prim — Añadir primitivas

Añade geometrías básicas a la escena:

| Botón | Geometría Three.js |
|-------|-------------------|
| ⬛ Caja | `BoxGeometry` |
| ⚪ Esfera | `SphereGeometry` |
| 🔵 Cilindro | `CylinderGeometry` |
| ▭ Plano | `PlaneGeometry` |
| ⭕ Toro | `TorusGeometry` |
| △ Cono | `ConeGeometry` |

**Parámetros configurables:**
- **Tamaño**: radio/dimensión base (default: 1)
- **Segmentos**: resolución de la malla (3–64, default: 16)
- **Color**: picker de color (default: verde `#00f5a0`)

---

### 3.7 Modo Path — Control individual de paths SVG

Cuando hay un SVG cargado, lista cada path/subpath por separado con control individual:

| Control | Descripción |
|---------|-------------|
| 👁 (ojo) | Mostrar/ocultar el path |
| Color | Picker de color individual por path |
| Profundidad | Input numérico de profundidad Z por path |
| `×` | Eliminar el path de la escena |
| `＋ SVG` | Fusionar un segundo SVG sobre el actual |
| `↺ Reset` | Restaurar todos los paths al estado original |

---

### 3.8 Modo Img→SVG — Vectorización de imágenes

Convierte imágenes bitmap en SVG vectoriales usando **ImageTracer.js**.

**Flujo:**
1. Cargar imagen (drag/clic) → PNG, JPG, WebP
2. Ajustar parámetros
3. Clic **↻ Convertir a SVG**
4. El SVG generado se carga automáticamente como objeto 3D extruido
5. Opcional: **↓ Guardar SVG** para exportar el archivo `.svg`

**Parámetros de vectorización:**

| Parámetro | Rango | Descripción |
|-----------|-------|-------------|
| Colores | 2–32 | Número de colores en la paleta reducida |
| Blur | 0–5 | Suavizado previo a la traza (reduce ruido) |
| Escala de grises | toggle | Convierte a grises antes de trazar |

> **Consejo**: para siluetas de edificios, usar 2–4 colores con blur 1–2 da mejores resultados. Para logos con muchos colores, subir a 16–32.

---

### 3.9 Modo Build — Constructor arquitectónico

Herramienta para construir estructuras con imagen de referencia superpuesta.

#### Referencia visual

Permite cargar una imagen (JPG/PNG/WebP) que se superpone semitransparente sobre el viewport para usar como guía de modelado:

- **Opacidad**: 0–100% (default: 50%)
- **Mostrar/Ocultar**: toggle la imagen sin descargarla

#### Vistas de cámara presets

| Botón | Posición cámara | Útil para |
|-------|----------------|-----------|
| ⬛ Frente | Ortogonal frontal | Fachada principal |
| ◧ Lateral | Ortogonal lateral | Perfil, profundidades |
| ⊡ Top | Cenital | Planta, footprint |
| ◈ ISO | Isométrica | Vista general 3D |

#### Elementos arquitectónicos

Configuración de dimensiones (W × H × D en unidades Three.js) + color:

| Botón | Tipo | Geometría |
|-------|------|-----------|
| 🧱 Muro | Pared vertical | Box estirado en Y |
| ▬ Piso | Suelo plano | Box plano en Y |
| 🟦 Techo | Cubierta plana | Box plano en Y |
| 🔺 Tejado ∧ | Tejado a dos aguas | PrismGeometry |
| ◆ Tejado ◆ | Tejado a cuatro aguas | PyramidGeometry |

---

### 3.10 Modo Código — Ejecutar Three.js en escena

Permite escribir o cargar código Three.js arbitrario y ejecutarlo directamente sobre la escena activa.

**Variables disponibles en el contexto de ejecución:**

```javascript
scene   // THREE.Scene activa
THREE   // Namespace Three.js completo
```

**Ejemplo de uso:**
```javascript
const geo = new THREE.BoxGeometry(1, 1, 1);
const mat = new THREE.MeshStandardMaterial({ color: 0x00f5a0 });
scene.add(new THREE.Mesh(geo, mat));
```

**Cargar desde archivo:** acepta `.js` y `.html` — extrae y ejecuta el bloque de código.

**Botón "Descargar HTML actualizado"**: genera un HTML standalone con la escena actual embebida (aparece después de ejecutar código).

Los errores de ejecución se muestran en rojo debajo del textarea.

---

## 4. Viewport — Canvas 3D Central

### 4.1 Controles de cámara (OrbitControls)

| Acción | Interacción |
|--------|-------------|
| Orbitar (rotar) | Clic izquierdo + arrastrar |
| Zoom | Rueda del ratón |
| Pan (desplazar) | Clic derecho + arrastrar |

También se muestra en el overlay inferior-izquierdo del viewport: _"Orbit: drag · Zoom: scroll · Pan: right-drag"_

### 4.2 Botones del viewport

| Botón | Función |
|-------|---------|
| `⊙ Reset` | Resetea la cámara a la posición inicial |
| `⊞ Grid` | Activa/desactiva la cuadrícula de referencia |
| `◈ Wire` | Activa/desactiva el modo wireframe global |

### 4.3 Drop zone

Al arrastrar un archivo sobre el viewport aparece un overlay verde con el texto **"SOLTAR ARCHIVO"**. Suelta para cargar directamente.

### 4.4 Loading overlay

Durante la carga de modelos pesados aparece un spinner con mensaje de progreso (`#lmsg`). El viewport queda bloqueado hasta que la carga finaliza.

---

## 5. Panel Derecho — Exportar y Código

### 5.1 Exportación

| Formato | Botón | Descripción |
|---------|-------|-------------|
| `.GLB` | ↓ Exportar .GLB (verde) | Exporta toda la escena como binario GLTF. Ideal para integrar como `type: "glb"` en el mapa |
| Código Three.js | ↓ Código Three.js (morado) | Genera el código JS que reproduce la escena |
| JSON geometría | ↓ JSON geometría (ámbar) | Estructura de datos serializada de la geometría |

El nombre del archivo de exportación es configurable en el campo **Nombre del archivo** (default: `export`).

### 5.2 Panel de transformación de la selección (`#trp`)

Aparece cuando hay un objeto seleccionado. Permite ajuste numérico preciso en tres ejes:

| Dimensión | Ejes | Unidades |
|-----------|------|---------|
| Posición | X (rojo) / Y (verde) / Z (azul) | unidades Three.js, step 0.1 |
| Rotación | X / Y / Z | grados (°), step 5° |
| Escala | X / Y / Z | factor, step 0.1 |

### 5.3 Visor de código (panel inferior)

Tres pestañas:

| Pestaña | Contenido |
|---------|-----------|
| **Three.js** | Código JavaScript generado de la escena (con sintaxis coloreada) |
| **JSON** | Estructura de datos de la geometría en JSON |
| **Info** | Información del modelo (número de vértices, triángulos, texturas...) |

Botón `⎘ Copiar` → copia el contenido de la pestaña activa al portapapeles.

**Coloreado de sintaxis:**

| Token | Color |
|-------|-------|
| Keywords (`const`, `new`, `function`...) | Morado `#c084fc` |
| Funciones | Azul `#60a5fa` |
| Números | Ámbar `#f59e0b` |
| Strings | Verde claro `#86efac` |
| Comentarios | Gris itálico |

---

## 6. Flujos de Trabajo Típicos

### 6.1 Previsualizar un GLB antes de integrarlo en el mapa

```
1. Arrastra el archivo .glb al drop zone (izquierda o viewport)
2. El modelo aparece en el viewport con cámara isométrica
3. Usa OrbitControls para inspeccionar
4. Cambia el fondo (swatch azul cielo → simula el contexto del mapa)
5. Compara visualmente con otros edificios
```

### 6.2 Ajustar posición/escala de un edificio y exportar el código

```
1. Cargar GLB
2. Ir a Insp → clic en el mesh raíz
3. En Panel Derecho, ajustar Posición y Escala numéricamente
4. Activar modo Mover (⟷) en TransformControls para ajuste visual
5. Panel Derecho → pestaña Three.js → copiar el código generado
6. Pegar los valores de offsetX/offsetZ/scale en el JSON del edificio
```

### 6.3 Convertir un SVG de silueta a objeto 3D para el mapa

```
1. Herramienta SVGLoader: arrastra el .svg
2. En Mat → SVG → ajustar Profundidad (0.01–0.5 para edificios low-poly)
3. Ajustar Escala para que encaje en las dimensiones del mapa
4. Activar "Color SVG" si el SVG tiene colores propios
5. En Paths: ocultar paths no deseados (fondos, decoraciones)
6. Exportar → Código Three.js → extraer los valores de ExtrudeGeometry
```

### 6.4 Crear un edificio composite con primitivas

```
1. Herramienta Prim → añadir la base (Caja)
2. En Inspector → ajustar dimensiones con inputs numéricos
3. Añadir más primitivas (muros, tejado)
4. En Mat → asignar color por primitiva
5. Exportar → JSON geometría → estructura lista para el JSON de composite
```

### 6.5 Construir con imagen de referencia

```
1. Ir a Build → cargar imagen de referencia (foto o plano del edificio)
2. Ajustar opacidad al 40–60%
3. Seleccionar vista de cámara: Frente para empezar
4. Añadir elementos: muro, piso, tejado ajustando W/H/D
5. Cambiar a vista ISO para verificar la composición 3D
6. Exportar .GLB cuando la estructura es satisfactoria
```

### 6.6 Vectorizar una imagen de referencia para crear silueta extruida

```
1. Img→SVG → cargar PNG/JPG de la silueta del edificio
2. Ajustar Colores a 2–4 (solo blanco/negro para silueta)
3. Blur 1–2 para suavizar bordes
4. Clic Convertir a SVG
5. El SVG se carga automáticamente en 3D
6. Ajustar en Mat → SVG → profundidad y escala
7. Guardar SVG para uso futuro
```

### 6.7 Ejecutar código Three.js personalizado

```
1. Código → pegar o cargar un .js con geometría Three.js
2. Variables disponibles: `scene`, `THREE`
3. Clic ▶ Ejecutar en escena
4. El resultado aparece inmediatamente en el viewport
5. Si hay error, se muestra en rojo debajo del textarea
6. Descargar HTML actualizado para tener el resultado como standalone
```

---

## 7. Referencia Técnica

### 7.1 Librerías y rutas

```javascript
// Imports internos del previewer
import * as THREE from '/static/vendor/three/three.module.js';
// three.module.js re-exporta desde three.core.js (r172, arquitectura split)

import { OrbitControls }    from '/static/vendor/three/OrbitControls.js';
import { GLTFLoader }       from '/static/vendor/three/GLTFLoader.js';
import { GLTFExporter }     from '/static/vendor/three/GLTFExporter.js';
import { SVGLoader }        from '/static/vendor/three/SVGLoader.js';
import { TransformControls } from '/static/vendor/three/TransformControls.js';
// ImageTracer: script clásico, disponible como window.ImageTracer
```

### 7.2 Ruta FastAPI

```python
# app/routers/pages.py
@router.get('/3dpreviewer')
async def previewer(request: Request):
    return _render(request, 'pages/3dpreviewer.html')
```

La ruta **no requiere autenticación** y sirve el HTML completo con todos los vendors embebidos vía Jinja2.

### 7.3 Variables CSS principales

```css
:root {
  --bg:     #0a0a0f;   /* Fondo del UI (panel izquierdo/derecho) */
  --panel:  #111118;   /* Panel principal */
  --panel2: #16161f;   /* Panel secundario, inputs */
  --border: #2a2a3a;   /* Bordes */
  --accent: #00f5a0;   /* Verde neón — selección, activo, accent */
  --accent2:#7c3aed;   /* Morado — botón exportar código */
  --accent3:#f59e0b;   /* Ámbar — botón exportar JSON, warnings */
  --text:   #e2e8f0;   /* Texto principal */
  --muted:  #64748b;   /* Texto secundario */
  --danger: #ef4444;   /* Rojo — errores, delete */
  --code:   #0d0d15;   /* Fondo del visor de código */
}
```

### 7.4 Layout grid

```css
.ws {
  display: grid;
  grid-template-columns: 270px 1fr 260px;
  height: calc(100vh - 46px); /* header 46px */
}
```

Panel izquierdo: 270px fijo · Viewport: flexible · Panel derecho: 260px fijo.

### 7.5 Iluminación de la escena Three.js

El previewer monta una escena con:

- `AmbientLight` — iluminación base
- `DirectionalLight` — desde arriba-derecha para sombras sutiles
- `HemisphereLight` — cielo/suelo para iluminación suave

No se expone la configuración de luces en la UI — son valores fijos pensados para revisión visual de modelos.

### 7.6 Notas de compatibilidad

| Situación | Comportamiento |
|-----------|----------------|
| **GLB con texturas** | Se cargan correctamente. Materiales originales del GLB se preservan |
| **GLB sin materiales** | Se asigna material Lambert gris neutro por defecto |
| **SVG complejo** | SVGs con paths muy complejos pueden tardar 1–3 s en extruir |
| **Imágenes grandes** | ImageTracer trabaja bien hasta ~2000×2000px; superiores pueden ser lentas |
| **Playwright headless** | El contexto WebGL puede perderse; recargar la página restaura la escena |
| **Caché del navegador** | La URL `/3dpreviewer` no tiene parámetros de cache-bust. Usar `Ctrl+Shift+R` si los cambios de código no se reflejan |

### 7.7 Vendors necesarios para el 3D Previewer

Si se regeneran los vendors con `download_three_vendors.sh`, estos archivos son **requeridos** específicamente por el previewer (además de los usados por `asturias-scene.js`):

```
app/static/vendor/three/
  ├── GLTFLoader.js        ← importar GLB/GLTF
  ├── GLTFExporter.js      ← exportar a GLB
  ├── SVGLoader.js         ← importar SVG → 3D
  └── TransformControls.js ← gizmos de transformación

app/static/vendor/imagetracer/
  └── imagetracer.js       ← vectorización bitmap → SVG
```

> **Importante**: `three.core.js` y `three.module.js` son ambos necesarios. `three.module.js` importa internamente desde `three.core.js` (arquitectura split de Three.js r172+). Si se borra `three.core.js`, el previewer deja de funcionar completamente.
