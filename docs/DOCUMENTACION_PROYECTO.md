# Documentación Técnica — app_example

> **Versión:** 1.0 · **Fecha:** 2026-03-23 · **Rol:** Senior Technical Writer / Arquitecto de Software
> **Formato:** Optimizado para presentación / exportable a Notion o Word

---

## Tabla de Contenidos

1. [Información General y Contexto](#1-información-general-y-contexto)
2. [Arquitectura y Flujo del Sistema](#2-arquitectura-y-flujo-del-sistema)
3. [Escena 3D — Mapa Interactivo de Asturias](#3-escena-3d--mapa-interactivo-de-asturias)
4. [Edificios 3D y Waypoints](#4-edificios-3d-y-waypoints)
5. [Obtención y Gestión de Datos](#5-obtención-y-gestión-de-datos)
6. [Guía de Estilo y Diseño UI/UX](#6-guía-de-estilo-y-diseño-uiux)
7. [Documentación de la API](#7-documentación-de-la-api)
8. [Configuración y Despliegue](#8-configuración-y-despliegue)
9. [Mantenimiento y Escalabilidad](#9-mantenimiento-y-escalabilidad)

---

## 1. Información General y Contexto

### 1.1 Elevator Pitch

**app_example** es una aplicación web interactiva para explorar el Principado de Asturias y sus **78 municipios (concejos)** a través de un **mapa 3D isométrico cenital** construido con Three.js. El usuario ve Asturias desde el aire; al hacer clic en un municipio (o buscarlo por nombre), la plataforma del concejo se eleva y gira revelando una **mini-escena 3D** con edificios emblemáticos, un personaje asturiano animado y puntos de interés navegables.

La experiencia integra datos reales de **OpenStreetMap** (restaurantes, bares, museos, miradores, tiendas) y un **mercado de compras** con 6 rutas gastronómicas y culturales de Gijón, todo servido desde la misma API FastAPI sin dependencias de CDNs externos.

### 1.2 Objetivo y Alcance

| Dimensión | Descripción |
|-----------|-------------|
| **Objetivo principal** | Visualización lúdica e inmersiva del territorio asturiano para turistas y residentes |
| **Usuarios objetivo** | Turistas, residentes curiosos, exploradores digitales del patrimonio asturiano |
| **Alcance geográfico** | 78 municipios de Asturias (Principado de Asturias, España) |
| **Acceso** | Web app responsive; sin autenticación de usuario final |
| **Fuentes de datos** | OpenStreetMap (POIs), Drupal API de Gijón (comercios por rutas), PostgreSQL/PostGIS (geometrías) |

### 1.3 Stack Tecnológico Completo

#### Backend

| Componente | Tecnología | Versión |
|------------|-----------|---------|
| Framework web | FastAPI | 0.128.5 |
| Runtime Python | Python | 3.13 |
| Servidor ASGI (dev) | Uvicorn | 0.40.0 |
| Servidor ASGI (prod) | Gunicorn + UvicornWorker | 25.0.3 |
| ORM / queries | SQLAlchemy 2.0 async | 2.0.46 |
| Driver PostgreSQL | asyncpg | 0.31.0 |
| Extensión geo | GeoAlchemy2 | 0.18.1 |
| HTTP cliente async | httpx | 0.28.1 |
| Templates | Jinja2 + i18n (Babel) | 3.1.6 |
| Auth | JWT (python-jose) + passlib bcrypt | — |
| Logging | structlog | 25.5.0 |

#### Base de Datos

| Componente | Detalle |
|------------|---------|
| Motor | PostgreSQL + PostGIS |
| Base de datos | `asturiasmap` (compartida con `app_asturiasMobile`) |
| Usuario BD | `asturiasuser` con acceso completo de escritura |
| Tipos geoespaciales | MultiPolygon (municipios), Point (POIs) — SRID 4326 |
| Driver async | asyncpg vía SQLAlchemy async engine |

#### Frontend (todo local, sin CDN externos)

| Biblioteca | Versión | Ubicación |
|------------|---------|-----------|
| Three.js core | r172 | `static/vendor/three/three.core.js` |
| Three.js module | r172 | `static/vendor/three/three.module.js` |
| OrbitControls | r172 | `static/vendor/three/OrbitControls.js` |
| CSS2DRenderer | r172 | `static/vendor/three/CSS2DRenderer.js` |
| GLTFLoader | r172 | `static/vendor/three/GLTFLoader.js` |
| SVGLoader | r172 | `static/vendor/three/SVGLoader.js` |
| GLTFExporter | r172 | `static/vendor/three/GLTFExporter.js` |
| TransformControls | r172 | `static/vendor/three/TransformControls.js` |
| ImageTracer | — | `static/vendor/imagetracer/imagetracer.js` |
| Fuente Inter | WOFF2 | `static/vendor/fonts/` |

> **Sin CDN externos:** todos los assets frontend están autocontenidos en `app/static/vendor/`. Nunca hay llamadas a redes externas desde el navegador para cargar librerías.

#### Infraestructura

| Componente | Detalle |
|------------|---------|
| Process manager | Supervisor (`autorestart=true`) |
| Reverse proxy | Nginx + SSL (Let's Encrypt) |
| Puerto local | 8000 (Gunicorn/Uvicorn) |
| Dominio producción | `cris.pibico.es` (ruta raíz `/`) |
| Logs app | `logs/app_example.log` (rotación 10 MB × 5 backups) |
| Logs nginx | `/var/log/nginx/app_example_access.log` |

---

## 2. Arquitectura y Flujo del Sistema

### 2.1 Diagrama de Arquitectura (ASCII)

```
┌─────────────────────────────────────────────────────────────────────┐
│                         CLIENTE (Browser)                            │
│  asturias-scene.js (ES module, Three.js r172)                       │
│    ├─ Mapa 3D cenital — 78 polígonos extruidos                      │
│    ├─ Personaje asturiano animado (plaza por municipio)             │
│    ├─ Edificios 3D Gijón (composite, GLB, extruded)                 │
│    ├─ Modal datos: GET /api/restaurantes|ocio|tiendas|mercado       │
│    └─ Buscador de concejo (search-municipio)                        │
└──────────────────────┬──────────────────────────────────────────────┘
                       │ HTTPS  /
┌──────────────────────▼──────────────────────────────────────────────┐
│                         NGINX (cris.pibico.es)                       │
│  / → proxy_pass 127.0.0.1:8000                                      │
│  /static/ → alias app/static/ (cache 30d vendors, 7d css/js)       │
│  /market/ → proxy_pass app_markets_backend                          │
│  SSL: TLSv1.2+TLSv1.3, HSTS, CSP headers                          │
└──────────────────────┬──────────────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────────────┐
│                    SUPERVISOR                                         │
│  [program:app_example]  autorestart=true                             │
│  gunicorn app.main:app -c deploy/scripts/gunicorn_conf.py           │
│                  bind 127.0.0.1:8000                                │
└──────────────────────┬──────────────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────────────┐
│                    FASTAPI APP                                        │
│  routers/pages.py      → GET /   · GET /3dpreviewer                 │
│  routers/asturias_api  → /api/restaurantes · /api/ocio · ...        │
│  routers/v1/           → /api/v1/health · /api/v1/auth · ...        │
└──────────────────────┬──────────────────────────────────────────────┘
                       │ asyncpg / SQLAlchemy async
┌──────────────────────▼──────────────────────────────────────────────┐
│              PostgreSQL + PostGIS  (BD: asturiasmap)                 │
│  municipios · puntos_interes · municipio_comercios                   │
│  rutas_ciclismo · rutas_senderismo · rutas_sendas_verdes ...        │
└─────────────────────────────────────────────────────────────────────┘

        ┌──────────────────────────────────────┐
        │  SERVICIOS EXTERNOS (ETL / scripts)  │
        │  Overpass API   → update_osm         │
        │  Drupal Gijón API → scrape_compras   │
        └──────────────────────────────────────┘

        ┌──────────────────────────────────────┐
        │  Build Pipeline (offline)            │
        │  build_asturias_scene.py             │
        │  asturias-scene.template.js → .js    │
        └──────────────────────────────────────┘
```

### 2.2 Flujo de Usuario (User Flow)

```
Usuario abre https://cris.pibico.es/
        │
        ▼
[VISTA CENITAL] Mapa 3D de Asturias (cámara drone, sin rotación)
  78 polígonos extruidos coloreados por comarca
  Balizas rojas en cada concejo
  Océano Cantábrico alineado con el litoral real
        │
        ├─ Clic en baliza / búsqueda en navbar
        ▼
[PLATAFORMA ELEVADA] El municipio sube y escala
  Mini-escena 3D: edificios, árboles, personaje asturiano
  Plaza con carteles de categorías (restaurantes, ocio, tiendas, mercado)
  Botón X (top-center) para colapsar
        │
        ├─ Clic en cartel de categoría
        ▼
[MODAL LATERAL] Panel deslizante derecho
  Lista de POIs / rutas con botón "Ver"
  Subpanel place-card con mapa OSM tiles + pin
        │
        └─ Clic X modal → monigote vuelve al centro
           Clic X plataforma → municipio colapsa
```

### 2.3 Estructura de Archivos Clave

```
app_example/
├── app/
│   ├── main.py                         ← create_app() factory, lifespan, middlewares
│   ├── __version__.py                  ← Fuente única de versión semver
│   ├── core/
│   │   ├── config.py                   ← Pydantic Settings (@lru_cache)
│   │   ├── security.py                 ← JWT, bcrypt
│   │   ├── exceptions.py               ← AppException jerarquía → JSON automático
│   │   └── logging.py                  ← structlog (console dev / JSON prod)
│   ├── db/
│   │   ├── base.py                     ← DeclarativeBase (id, created_at, updated_at)
│   │   └── session.py                  ← async engine + get_db_session dependency
│   ├── models/
│   │   ├── user.py                     ← Modelo User (auth)
│   │   ├── places.py                   ← PuntoInteres (PostGIS Point, osm_id)
│   │   └── mercado.py                  ← MunicipioComercio (rutas comerciales Gijón)
│   ├── routers/
│   │   ├── pages.py                    ← GET / → asturias.html · GET /3dpreviewer
│   │   ├── asturias_api.py             ← /api/restaurantes|ocio|tiendas|mercado
│   │   └── v1/
│   │       ├── health.py               ← GET /api/v1/health/live|ready
│   │       ├── auth.py                 ← POST /api/v1/auth/login|register|refresh
│   │       └── users.py                ← CRUD /api/v1/users
│   ├── services/
│   │   ├── auth.py                     ← JWT logic + get_current_user dependency
│   │   └── user.py                     ← UserService CRUD
│   ├── middleware/
│   │   ├── i18n.py                     ← Detección idioma (query → cookie → header)
│   │   └── request_context.py          ← X-Request-ID, X-App-Version, structlog
│   ├── static/
│   │   ├── css/
│   │   │   ├── style.css               ← Layout base (navbar, footer, fuentes)
│   │   │   ├── asturias.css            ← Canvas fullscreen, modal, info-card, labels
│   │   │   ├── ocio.css                ← Filtros ocio, badges, spinners
│   │   │   └── chef_hat.css            ← Estilos plaza/personaje (activos)
│   │   ├── js/
│   │   │   ├── asturias-scene.js       ← Escena Three.js compilada (BUILD OUTPUT)
│   │   │   ├── asturias-scene.template.js ← FUENTE CANÓNICA del build pipeline
│   │   │   ├── elogio.js               ← Módulo 3D Elogio del Horizonte
│   │   │   └── gijon/
│   │   │       ├── index.js            ← Auto-generado por build script
│   │   │       ├── acuario.json        ← Acuario de Gijón (composite 62 partes)
│   │   │       ├── laLaboral.json      ← La Laboral (composite 57 partes)
│   │   │       ├── elogioTotem.json    ← Elogio Totem (GLB wrapper)
│   │   │       ├── elogio_espanha.json ← Escultura España (extruded)
│   │   │       ├── mercado.json        ← Config mercado (module_import)
│   │   │       ├── mercado-market.js   ← Módulo 3D mercado (5 puestos en semicírculo)
│   │   │       └── tree_0*.json        ← Árboles procedurales
│   │   └── vendor/
│   │       ├── three/                  ← Three.js r172 completo (local)
│   │       ├── fonts/                  ← Inter WOFF2 (latin + latin-ext)
│   │       └── imagetracer/            ← ImageTracer (3D previewer)
│   └── templates/
│       ├── base.html                   ← Layout: navbar, footer, i18n, versión
│       ├── components/modal.html       ← Modal lateral con filtros ocio y paginación
│       └── pages/
│           ├── asturias.html           ← Página principal mapa 3D
│           └── 3dpreviewer.html        ← Herramienta dev vista 3D
├── scripts/
│   ├── build_asturias_scene.py         ← Build pipeline 14 pasos (PRINCIPAL)
│   ├── scrape_gijon_compras.py         ← Scraper Drupal → municipio_comercios
│   ├── actualizar_geom_municipios.py   ← ETL geometrías OSM → municipios
│   ├── importar_municipios.py          ← Import inicial 78 concejos
│   ├── update_osm_asturias.py          ← Actualización POIs Overpass API
│   ├── buildings/                      ← (vacío activo; configs en static/js/)
│   ├── archive/                        ← Scripts de uso único ya ejecutados
│   ├── nginx.conf                      ← Config nginx producción activa
│   └── supervisor.conf                 ← Config supervisor producción activa
├── migrations/                         ← Alembic migrations
├── deploy/                             ← Templates de despliegue (supervisor/nginx)
├── docs/
│   └── DOCUMENTACION_PROYECTO.md       ← Este archivo
├── tests/
│   ├── conftest.py                     ← SQLite in-memory, dependency override
│   └── test_health.py                  ← Tests health endpoints
├── .env                                ← Config real (no commitear)
├── .env.example                        ← Plantilla documentada
├── alembic.ini                         ← Config Alembic
├── requirements.txt                    ← Dependencias producción
├── requirements-dev.txt                ← Dependencias desarrollo
├── data_concejos_asturias.json         ← Datos estáticos 78 concejos (usado por build)
├── download_three_vendors.sh           ← Script para regenerar vendor Three.js
└── start_server.sh                     ← Arranque rápido dev (puerto 8555)
```

### 2.4 Lógica de Negocio — Capas

#### `routers/asturias_api.py` — función central de consulta espacial

```python
ejecutar_consulta_espacial(municipio, tipos, db)
```

| Paso | PostGIS usada | Descripción |
|------|--------------|-------------|
| JOIN geoespacial | `ST_Within(p.geom, m.geom)` | Filtra POIs físicamente dentro del polígono del municipio |
| Normalización | `unaccent(m.nombre) ILIKE unaccent(:m)` | Búsqueda sin acentos, case-insensitive |
| Extracción tags | `p.tags->>'cuisine'`, `p.tags->>'website'` | Campos extras del JSON de OSM |
| Tipo doble filtro | `TRIM(p.tipo) = ANY(:tipos) OR p.tags->>'amenity' = ANY(:tipos)` | Cubre variantes de clasificación OSM |

---

## 3. Escena 3D — Mapa Interactivo de Asturias

### 3.1 Build Pipeline (`build_asturias_scene.py`)

El archivo `asturias-scene.js` (~323 KB) es **generado**, no editado manualmente. El pipeline transforma `asturias-scene.template.js` en 14 pasos secuenciales:

```
asturias-scene.template.js  →  [14 pasos]  →  asturias-scene.js
```

| Paso | Función | Descripción |
|------|---------|-------------|
| 1–4 | Carga datos | `data_concejos_asturias.json` → polygon data (coordenadas, nombres, altitudes) |
| 5 | `inject_polygon_geometry` | Geometrías extruidas de los 78 polígonos municipales |
| 6 | `inject_markers` | Balizas rojas con userData (nombre, coords GPS, concejo ID) |
| 7 | `inject_platform_data` | Datos de plataforma para animación de elevación |
| 8 | `inject_mountain_terrain` | Terreno sur (montañas Cantábrica) |
| 9 | `inject_coast_alignment` | Alineación litoral norte con datos reales |
| 10 | `inject_color_palette` | Colores por comarca (8 comarcas, paleta fija) |
| 11 | `inject_info_card_data` | Datos tarjeta info (población, altitud, área, comarca) |
| 12 | `inject_municipality_index` | Índice para búsqueda rápida por nombre |
| 13 | `inject_buildings` | Edificios 3D (scope:all + municipio-específicos) |
| 14 | `inject_ocean_and_boats` | Geometría océano con COAST_POINTS dinámicos (183 puntos) |

**Ejecución:**
```bash
python3 scripts/build_asturias_scene.py
```

### 3.2 Sistema de Coordenadas 3D

| Parámetro | Valor | Descripción |
|-----------|-------|-------------|
| Proyección | Equirectangular local | `pts_x → X_3d`, `pts_y → -Z_3d` |
| Eje Y | Altitud / elevación | Plataforma eleva en Y |
| Espejo X | `X_3d = -pts_x` | SVG fuente espejado: izquierda=este, derecha=oeste |
| Cámara cenital | `(0, 12, -0.001)` | Drone view; Z negativo = norte arriba |
| Escala edificios | `PLAZA_SCALE = 0.016` | 1 unidad Three.js ≈ ~60m real |

### 3.3 Sistema de Plataforma y Animación

Cuando el usuario hace clic en un municipio, la función `animatePolygon(poly)` gestiona dos estados:

**Expandir:**
- `targetY` = altura proporcional a altitud real del concejo
- `targetScale` > 1.0 (amplía el polígono)
- Cámara anima a posición isométrica `(6, 6, -6)`
- Edificios emergen (`visible = true`, `rotation.x` normalizado)
- Balizas se bloquean (no clickables durante animación)

**Colapsar** (botón X `#btn-close-platform`):
- `targetY = 0`, `targetScale = 1.0`
- Cámara vuelve a cenital
- `cerrarModal()` + `_hideBuildingCard()` + `closeMarketCard()`
- `selectedPolygon = null`

### 3.4 Plaza del Personaje Asturiano

Cada municipio tiene una **plaza** con el personaje asturiano y 3 carteles navegables:

| Elemento | Descripción |
|----------|-------------|
| Plataforma | Disco radio `6*S`, adoquines procedurales (`addCobblestones`) |
| Carteles | Arco de `5.0*S`, canvas 400×140px, texto negro |
| Personaje | `_makePlazaCharacter()` — traje asturiano completo con Montera Picona |
| Burbujas | Esferas translúcidas sobre carteles, oscilan en Y (`5.8*S + sin(t)`) |
| Animación boca | CanvasTexture dinámica: modo `talk` al caminar, `smile` en idle |
| Velocidad walk | `8.0*S` normal, `28.0*S` al volver al centro |
| Partículas polvo | 16 partículas radio `0.35*S`, fade 2.2s |

**Categorías de cartel disponibles:**

| Cartel | API llamada | Descripción |
|--------|-------------|-------------|
| 🍴 Restaurantes | `GET /api/restaurantes/{municipio}` | Bars, cafés, restaurantes, pubs |
| 🎭 Ocio | `GET /api/ocio/{municipio}` | Museos, miradores, teatros, monumentos |
| 🛍️ Tiendas | `GET /api/tiendas/{municipio}` | Comercios, panaderías, delicatessen |

### 3.5 Océano y Costa

El océano Cantábrico se genera con `createCoastAlignedOceanGeo(128, 64)` usando **183 COAST_POINTS dinámicos** calculados por el build script:

- **Algoritmo**: ray-casting de aristas exteriores de polígonos costeros
- **Criterio**: aristas con componente norte `out_nz > 0.25` no tapadas por otros polígonos
- **Muestreo**: paso 0.05, ventana ±0.12
- **UV**: `v=0` = costa, `v=1` = norte (para shaders de gradiente)
- **Corrección oeste**: si `X > 4.0` y Z cae > 0.25 → truncar (evita polígonos sumergidos)
- **Z_OVERLAP = 0.04**: desplazamiento sur para ocultar franja de playa

---

## 4. Edificios 3D y Waypoints

### 4.1 Tipos de Edificio

| Tipo JSON | Descripción | Ejemplo |
|-----------|-------------|---------|
| `composite` | Group de sub-meshes definidos en JSON | La Laboral (57 partes), Acuario (62 partes) |
| `extrude` | ExtrudeGeometry desde silueta 2D | Elogio España |
| `extrudePath` | Curva 3D extruida | Trayectorias curvas |
| `module_import` | ES module externo async | Mercado 3D (`mercado-market.js`) |
| `glb` | GLTFLoader con wrapper Group | ElogioTotem GLB |

### 4.2 Edificios Activos en Gijón (c013)

| Edificio | Tipo | Escala | Archivo |
|----------|------|--------|---------|
| Acuario de Gijón | composite (62 partes) | SCALE=0.0012 | `gijon/acuario.json` |
| La Laboral | composite (57 partes) | SCALE=0.0025 | `gijon/laLaboral.json` |
| Elogio del Horizonte | composite (torus+boxes) | — | `elogio.js` |
| Elogio Totem | glb (wrapper Group) | innerScale=0.1 | `gijon/elogioTotem.json` |
| Elogio España | extrude | — | `gijon/elogio_espanha.json` |
| Mercado 3D | module_import | MS=0.007 | `gijon/mercado-market.js` |
| Árboles | composite (×5 variantes) | — | `gijon/tree_0*.json` |

### 4.3 Patrón de Offset (ejes → vista usuario)

| Eje offset JSON | Vista usuario |
|----------------|---------------|
| `+offsetX` | Derecha |
| `-offsetX` | Izquierda |
| `+offsetZ` | Abajo (sur) |
| `-offsetZ` | Arriba (norte) |

### 4.4 Waypoints de Edificios (Building Cards)

Los 3 edificios principales de Gijón tienen **discos de waypoint** en el suelo que el personaje puede alcanzar:

```javascript
WAYPOINT_BUILDINGS = [
  { nombre: 'La Laboral',       color: 0xFF8C00, offsetX, offsetZ, lat, lon, desc },
  { nombre: 'Acuario de Gijón', color: 0x00CED1, offsetX, offsetZ, lat, lon, desc },
  { nombre: 'Elogio del Horizonte', color: 0xFF69B4, ... }
]
```

Al llegar al waypoint → tarjeta `#building-card` con mapa OSM tiles + pan mouse/touch.

### 4.5 Mercado 3D (`mercado-market.js`)

- 5 puestos en semicírculo (`SR = 11*MS = 0.077`)
- Suelo con adoquines `addCobblestones()` en D-shape
- Disco naranja `0xFF6600` en origen local `(0, 0.62*MS, 0)` como target del personaje
- Al llegar → `_showMarketCard()` → modal con 6 rutas de compras Gijón
- **Crítico**: disco DEBE estar en `localX=0, localZ=0` para que `cfg.offsetX/offsetZ` coincida exactamente con el target

---

## 5. Obtención y Gestión de Datos

### 5.1 Tablas de Base de Datos

#### `municipios`

| Columna | Tipo | Descripción |
|---------|------|-------------|
| `id` | integer PK | Identificador concejo |
| `nombre` | varchar | Nombre oficial del concejo |
| `geom` | MultiPolygon (SRID 4326) | Geometría completa del municipio |
| `poblacion` | integer | Habitantes (fuente INE) |

#### `puntos_interes`

| Columna | Tipo | Descripción |
|---------|------|-------------|
| `osm_id` | bigint UNIQUE | ID OpenStreetMap |
| `nombre` | varchar(255) | Nombre del lugar |
| `tipo` | varchar(50) | Clasificación OSM (restaurant, museum, viewpoint...) |
| `tags` | json | Tags completas OSM (cuisine, website, description...) |
| `geom` | Point (SRID 4326) | Coordenadas geográficas |
| `id` | integer PK | ID interno |
| `created_at / updated_at` | timestamp | Auditoría |
| `ultima_actualizacion` | timestamp | Última sync OSM |

#### `municipio_comercios`

| Columna | Tipo | Descripción |
|---------|------|-------------|
| `municipio` | varchar(100) | Nombre del concejo |
| `ruta_id` | varchar(50) | Slug de la ruta (`gastro`, `dulzon`, `artesano`...) |
| `ruta_nombre` | varchar(200) | Nombre legible de la ruta |
| `nombre` | varchar(300) | Nombre del comercio |
| `descripcion` | text | Descripción |
| `direccion` | varchar(400) | Dirección postal |
| `lat / lon` | float | Coordenadas |
| `telefono` | varchar(100) | Teléfono |
| `web` | varchar(500) | URL web |
| `horario` | text | Horario de apertura |
| `slug` | varchar(300) | Slug Drupal del comercio |

**Restricción única**: `(municipio, slug, ruta_id)` — misma tienda puede estar en varias rutas.

### 5.2 Scripts ETL

| Script | Fuente | Destino | Uso |
|--------|--------|---------|-----|
| `scripts/update_osm_asturias.py` | Overpass API | `puntos_interes` | Actualización periódica POIs |
| `scripts/scrape_gijon_compras.py` | Drupal API `drupal.gijon.es` | `municipio_comercios` | Importación rutas comerciales |
| `scripts/actualizar_geom_municipios.py` | OSM Nominatim / geojson | `municipios` | Actualización geometrías |
| `scripts/importar_municipios.py` | Lista fija 78 concejos | `municipios` | Importación inicial |

**Ejecutar scraper de Gijón:**
```bash
python3 scripts/scrape_gijon_compras.py --municipio Gijón
# Importa ~86 tiendas en 6 rutas desde Drupal JSON API
```

**6 rutas del mercado de Gijón:**

| ruta_id | Label | Icono | Color |
|---------|-------|-------|-------|
| `gastro` | Gastro | 🍴 | #e07a5f |
| `dulzon` | Dulces | 🍬 | #f4a261 |
| `artesano` | Artesanía | 🎨 | #81b29a |
| `arte-cultura` | Arte y Cultura | 🎭 | #9b72cf |
| `historia` | Comercios con Historia | 🏛️ | #5c8a8a |
| `moda` | Diseño y Moda | 👗 | #d4a5c9 |

---

## 6. Guía de Estilo y Diseño UI/UX

### 6.1 Paleta de Colores

| Elemento | Color | Uso |
|----------|-------|-----|
| Navbar / Header / Footer | `#650E01` (burdeos) | Fondo principal UI |
| Texto sobre navbar | `rgba(255,255,255,0.9)` | Links y versión |
| Modal background | `#C4D8E8` (azul claro) | Restaurantes/ocio/tiendas |
| Modal mercado | `#C4D8E8` inline + clase `modal-mercado` | Override via JS (caché CSS) |
| Highlight búsqueda | `0x33ff66` (verde) | Esfera raycaster Three.js |
| Botón primario | `#650E01` | Cerrar, volver |
| Hover botón | `#8a1501` | Estados hover |
| Texto tarjetas | `#111111` | Carteles plaza |
| Building card | `#C4D8E8` | Tarjeta edificios |

### 6.2 Tipografía

| Fuente | Pesos | Uso |
|--------|-------|-----|
| Inter | Regular 400, Medium 500, Bold 700 | Todo el UI |
| Fuente local | WOFF2 latin + latin-ext | Sin Google Fonts |

### 6.3 Layout Principal

- **Canvas Three.js**: `position: fixed; top:0; left:0; width:100vw; height:100vh; z-index:0`
- **Header/navbar**: `position: relative; z-index: 50` (flota sobre canvas)
- **Footer**: `position: fixed; bottom: 0` (fijo sobre canvas)
- **Modal lateral**: `position: fixed; right: 10px; top: 60px; width: min(420px, 92vw)`
- **Botón X plataforma**: `position: fixed; left: 50%; top: 80px` (top-center)

### 6.4 Buscador de Concejo

El input `#search-municipio` en la navbar:
- Dropdown `#search-dropdown` con hasta 8 matches (nombre en negrita)
- Al seleccionar: expande plataforma + resalta baliza con esfera verde pulsante
- `window.closeInfoCard`: función global necesaria (ES module scope — inline onclick no puede acceder)

### 6.5 Modal de Datos (panel deslizante)

```
[modal-general] (display: flex cuando activo)
  ├── modal-header
  │   ├── close-button (×) → cerrarModal()
  │   ├── modal-titulo
  │   └── modal-municipio-tag
  ├── ocio-filters (solo en categoría ocio)
  ├── contenedor-items (cards + btn "Ver")
  └── modal-footer
      ├── btn-cargar-mas (paginación PAGE_SIZE items)
      └── btn-tripadvisor (TripAdvisor / web turismo oficial)
```

> **CRÍTICO CSS caching**: Starlette StaticFiles dev no envía `Cache-Control`. Los estilos críticos de z-index, display y background se aplican siempre **inline via JS** para evitar que el navegador sirva versiones cacheadas.

---

## 7. Documentación de la API

### 7.1 Endpoints de Datos Geoespaciales

#### `GET /api/restaurantes/{municipio}`

Devuelve restaurantes, bares, cafés y pubs dentro del municipio (búsqueda espacial `ST_Within`).

**Parámetros:**
| Parámetro | Tipo | Descripción |
|-----------|------|-------------|
| `municipio` | path | Nombre del concejo (acepta acentos, case-insensitive) |

**Respuesta:**
```json
{
  "municipio": "Gijón",
  "total": 300,
  "resultados": [
    {
      "id": 255174168,
      "nombre": "Casa Antidio",
      "tipo": "bar",
      "tipo_label": "Bar",
      "lat": 43.53,
      "lon": -5.66,
      "cuisine": null,
      "description": null
    }
  ]
}
```

---

#### `GET /api/ocio/{municipio}`

Devuelve puntos de ocio: museos, monumentos, miradores, teatros, castillos, memoriales.

**Tipos incluidos:** `viewpoint`, `museum`, `theatre`, `arts_centre`, `castle`, `monument`, `cinema`, `memorial`

**Respuesta:** igual a `/api/restaurantes` con campo `tipo_label` de `OCIO_LABELS`.

---

#### `GET /api/tiendas/{municipio}`

Devuelve comercios: panaderías, supermercados, ropa, delicatessen, vino, quesos, kioscos.

**Tipos incluidos:** `bakery`, `supermarket`, `clothes`, `fashion`, `kiosk`, `deli`, `cheese`, `wine`

---

#### `GET /api/mercado/{municipio}`

Devuelve las 6 rutas comerciales disponibles con conteo de tiendas.

**Respuesta:**
```json
[
  {
    "id": "gastro",
    "label": "Gastro",
    "icon": "🍴",
    "color": "#e07a5f",
    "count": 20
  }
]
```

---

#### `GET /api/mercado/{municipio}/{ruta_id}`

Devuelve las tiendas de una ruta concreta.

**Respuesta:**
```json
[
  {
    "nombre": "Sidrería El Gaitero",
    "descripcion": "...",
    "direccion": "Calle Mayor 5",
    "lat": 43.53,
    "lon": -5.66,
    "telefono": "+34 985...",
    "web": "https://...",
    "horario": "L-V 10:00-20:00"
  }
]
```

---

### 7.2 Endpoints de Sistema (API v1)

#### `GET /api/v1/health/live`

```json
{ "status": "ok", "version": "0.1.0" }
```

#### `GET /api/v1/health/ready`

```json
{ "status": "ok", "version": "0.1.0" }
```

---

### 7.3 Endpoints de Autenticación (API v1)

#### `POST /api/v1/auth/register`

```json
{ "email": "user@example.com", "username": "user", "password": "secret", "full_name": "Nombre" }
```

#### `POST /api/v1/auth/login`

Devuelve `access_token` (JWT, 30 min) + `refresh_token` (JWT, 7 días).

#### `POST /api/v1/auth/refresh`

Renueva el access token usando el refresh token.

---

### 7.4 Endpoints de Usuarios (API v1, requiere auth)

| Método | Ruta | Descripción |
|--------|------|-------------|
| `GET` | `/api/v1/users/` | Lista usuarios (autenticado) |
| `GET` | `/api/v1/users/me` | Perfil del usuario actual |
| `PATCH` | `/api/v1/users/me` | Actualizar perfil |

**Header requerido:** `Authorization: Bearer <access_token>`

---

### 7.5 Rutas de Página

| Ruta | Descripción |
|------|-------------|
| `GET /` | Mapa 3D Asturias (página principal) |
| `GET /3dpreviewer` | Herramienta 3D previewer (dev) |
| `GET /docs` | Swagger UI (solo `APP_ENV=development`) |
| `GET /redoc` | ReDoc (solo `APP_ENV=development`) |

---

## 8. Configuración y Despliegue

### 8.1 Variables de Entorno (`.env`)

| Variable | Valor dev | Descripción |
|----------|-----------|-------------|
| `APP_NAME` | `app_example` | Nombre de la app |
| `APP_ENV` | `development` | `development` o `production` |
| `APP_DEBUG` | `true` | Activa logs verbose y SQL echo |
| `APP_SECRET_KEY` | `change-me` | Secret para tokens de sesión |
| `JWT_SECRET_KEY` | `change-me-jwt` | Secret para JWT |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | `30` | Expiración access token |
| `JWT_REFRESH_TOKEN_EXPIRE_DAYS` | `7` | Expiración refresh token |
| `DATABASE_URL` | `postgresql+asyncpg://asturiasuser:asturiasuser@localhost:5432/asturiasmap` | Conexión BD |
| `DEFAULT_LOCALE` | `en` | Idioma por defecto |
| `SUPPORTED_LOCALES` | `["en","es"]` | Idiomas soportados |
| `LOG_LEVEL` | `INFO` | Nivel de logging |
| `LOG_FORMAT` | `console` | `console` (dev) o `json` (prod) |

> **CRÍTICO**: `APP_ENV` en Supervisor (`environment=APP_ENV="development"`) sobreescribe el `.env`. Activa `/docs` y `/redoc` en producción si no se cambia a `production`.

### 8.2 Inicio Rápido (Desarrollo)

```bash
cd /home/erpnext/.services/app_example
source venv/bin/activate

# Compilar traducciones
pybabel compile -d app/i18n/locales -D messages

# Regenerar escena 3D (tras cambiar edificios o datos)
python3 scripts/build_asturias_scene.py

# Arrancar servidor con hot reload
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# O usar el script de arranque rápido (puerto 8555)
./start_server.sh
```

### 8.3 Supervisor (Producción)

**Config activa:** `/etc/supervisor/conf.d/app_example.conf`

```ini
[program:app_example]
command=/home/erpnext/.services/app_example/venv/bin/gunicorn app.main:app \
        -c /home/erpnext/.services/app_example/deploy/scripts/gunicorn_conf.py
directory=/home/erpnext/.services/app_example
user=erpnext
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/home/erpnext/.services/app_example/logs/app_example.log
stdout_logfile_maxbytes=10MB
stdout_logfile_backups=5
environment=PATH="/home/erpnext/.services/app_example/venv/bin",APP_ENV="development"
```

**Comandos:**
```bash
sudo supervisorctl status app_example
sudo supervisorctl restart app_example
sudo supervisorctl tail -f app_example
```

### 8.4 Nginx (Producción)

**Config activa:** `/etc/nginx/conf.d/app_example.conf` (basada en `scripts/nginx.conf`)

Características:
- SSL TLS 1.2+1.3 con certificado Let's Encrypt (`cris.pibico.es`)
- Redirect HTTP → HTTPS (301)
- HSTS, CSP, X-Frame-Options, X-Content-Type-Options
- Gzip para JS/CSS/JSON/SVG (nivel 6)
- Caché tiered: vendors 365d (immutable), CSS/JS 7d (must-revalidate), imágenes 30d
- Proxy `/market/` → `app_markets_backend` (app separada en mismo servidor)

```bash
sudo nginx -t               # Verificar config
sudo systemctl reload nginx # Aplicar cambios
```

### 8.5 Regenerar Three.js Vendors

Si se necesita actualizar Three.js:

```bash
# Descarga todos los loaders (r172)
chmod +x download_three_vendors.sh
./download_three_vendors.sh

# CRÍTICO: ajustar imports en OrbitControls.js y otros addons
# Cambiar: from 'three' → from '/static/vendor/three/three.module.js'
```

> **Importante**: `three.module.js` importa internamente desde `three.core.js`. Ambos archivos son necesarios — `three.core.js` es la librería principal y `three.module.js` es el re-exportador de la arquitectura split de r172+.

---

## 9. Mantenimiento y Escalabilidad

### 9.1 Añadir un Nuevo Edificio 3D

1. Crear el JSON de configuración en `app/static/js/{municipio}/nombre.json`
2. Definir el tipo (`composite`, `extrude`, `module_import`, `glb`)
3. Ajustar `offsetX`, `offsetZ`, `heightOffset`, `rotateY`
4. Ejecutar el build: `python3 scripts/build_asturias_scene.py`
5. Verificar en navegador (sin caché: `Ctrl+Shift+R`)

**Regla de orientación:**
```
SIEMPRE: rotateX = -Math.PI/2 (aplana el modelo al suelo)
         rotateY = ajuste manual para orientación horizontal
```

### 9.2 Añadir un Nuevo Municipio con Datos

1. Asegurar que el municipio tiene geometría en `municipios` (PostGIS)
2. Importar POIs desde OSM: `python3 scripts/update_osm_asturias.py`
3. El buscador de concejo lo detecta automáticamente (datos en BD)
4. Para mercado de compras: `python3 scripts/scrape_gijon_compras.py --municipio NombreMunicipio`

### 9.3 Migraciones de Base de Datos

```bash
# Crear migración tras modificar modelos
alembic revision --autogenerate -m "descripción"

# Aplicar
alembic upgrade head

# Ver estado
alembic current && alembic history
```

> **Importante**: todos los modelos deben re-exportarse en `app/models/__init__.py` para que Alembic los detecte.

### 9.4 Internacionalización (i18n)

El middleware `I18nMiddleware` detecta el idioma por prioridad: `?lang=` → cookie → `Accept-Language` → `DEFAULT_LOCALE`.

```bash
# Extraer strings nuevos
pybabel extract -F app/i18n/babel.cfg -o app/i18n/locales/messages.pot app/

# Actualizar catálogos existentes
pybabel update -i app/i18n/locales/messages.pot -d app/i18n/locales

# Compilar (necesario para que funcione)
pybabel compile -d app/i18n/locales -D messages
```

### 9.5 Tests

```bash
# Ejecutar todos los tests
pytest tests/ -v

# Con coverage
pytest tests/ --cov=app --cov-report=html
```

Los tests usan SQLite en memoria (`aiosqlite`). Los errores de DB en tests de health son esperados en entorno sin PostgreSQL local — los 2 tests de lógica pasan correctamente.

### 9.6 Checklist de Deploy

- [ ] `.env` actualizado (`APP_ENV=production`, `LOG_FORMAT=json`, secrets reales)
- [ ] `APP_ENV="production"` en la línea `environment=` del conf de Supervisor
- [ ] `pybabel compile` ejecutado
- [ ] `python3 scripts/build_asturias_scene.py` ejecutado
- [ ] `alembic upgrade head` aplicado
- [ ] `sudo supervisorctl restart app_example`
- [ ] `sudo nginx -t && sudo systemctl reload nginx`
- [ ] Verificar: `curl https://cris.pibico.es/api/v1/health/live`

### 9.7 Puntos de Atención / Gotchas Conocidos

| Situación | Síntoma | Solución |
|-----------|---------|----------|
| `three.core.js` borrado | Error 404 fatal, escena no carga | Restaurar con `download_three_vendors.sh` |
| CSS cacheado indefinidamente | Estilos no se actualizan en browser | Aplicar estilos críticos inline via JS; forzar `Ctrl+Shift+R` |
| `APP_ENV` en Supervisor sobreescribe `.env` | `/docs` activo en prod | Cambiar `APP_ENV="production"` en `environment=` del conf |
| `window.closeInfoCard` no definido | Error onclick inline | Asignar a `window.closeInfoCard` (ES module scope aislado) |
| Playwright headless sin WebGL | Raycaster 3D no funciona | Tests de UI deben ejecutarse en browser con GPU o usar `evaluate()` para llamar funciones JS directamente |
| Monigote tiembla al llegar | Bounce Y contamina distancia | `dir.y = 0` antes de `dist = dir.length()` para distancia XZ pura |
