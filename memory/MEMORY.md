# Mapa 3D Asturias — Estado del Proyecto

## Resumen
Mapa 3D interactivo de los 78 concejos de Asturias usando Three.js + FastAPI.
Servidor dev: `http://localhost:8555/asturias`

## COMPLETADO: Mapping marker-polígono corregido

### Problema
Los markers (m0-m77, orden alfabético) estaban mapeados por índice a polígonos (obj_c000-c081, orden SVG), causando etiquetas y markers en posiciones incorrectas.

### Solución
- **Hungarian algorithm** (`scipy.optimize.linear_sum_assignment`) para matching óptimo por proximidad GPS→centroide
- Función `build_marker_polygon_mapping()` en `scripts/build_asturias_scene.py`
- 78 markers matched a 82 polígonos (4 polígonos sin marker)
- Distancia media: 0.1273

### Verificación visual
- Costa oeste: Castropol, Tapia, El Franco, Navia → izquierda-arriba OK
- Costa este: Llanes, Ribadedeva, Cabrales → derecha OK
- Centro: Oviedo, Siero, Gijón → zona central OK
- Sur: Lena, Aller, Caso → zona inferior OK
- Suroeste: Ibias, Degaña, Cangas del Narcea → izquierda-abajo OK

---

## Archivos clave

| Archivo | Descripción |
|---------|-------------|
| `scripts/build_asturias_scene.py` | Build script con Hungarian matching (source→output) |
| `asturias_project/scene.js` | Fuente original (78 markers, 82 polígonos) |
| `app/static/js/asturias-scene.js` | Output generado (198,535 bytes) |
| `app/static/vendor/three/CSS2DRenderer.js` | Renderer de etiquetas 2D |
| `app/static/css/asturias.css` | Estilos `.label-3d` |
| `app/static/images/Mapa-de-Asturias.png` | Mapa de referencia |

---

## Notas técnicas

- **Coordenadas**: `pts_x → X_3d`, `pts_y → -Z_3d`, `depth → Y_3d` (rotateX(-PI/2))
- **SVG espejado**: izquierda=este, derecha=oeste. El código niega X para corregir
- **Polígonos**: c000-c081 (82 total), **Markers**: m0-m77 (78 total, orden alfabético)
- **Build script** (`build_asturias_scene.py`): 7 pasos — imports, bgcolor, colors, polygon extraction, marker repositioning, raycaster fix, CSS2D labels

## Lecciones aprendidas

- **Greedy matching insuficiente** para asignación bipartita geográfica → usar Hungarian algorithm
- **SVG projections no-lineales**: normalizar por rango falla. Rank-based (percentiles) elimina distorsión
- **Playwright + WebGL headless**: `CONTEXT_LOST_WEBGL` impide tests de raycaster. Screenshots sí funcionan
- **Fuentes woff2** causan timeout en screenshots Playwright → workaround: override font-family

## Estado actual
- Servidor corriendo en `http://localhost:8555/asturias` (HTTP 200)
- 78/78 concejos correctamente posicionados y verificados
- Sin tareas pendientes
