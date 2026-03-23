# app_example

Web application for exploring the municipalities of Asturias, built as a reference implementation and learning project by the pibiCo interns team.

## Overview

`app_example` is a full-stack FastAPI application that serves an interactive 3D map of Asturias. Users can explore all 78 municipalities, discover points of interest (restaurants, leisure, tourism), visit a 3D market in Gijón, and interact with an animated character guide. It also includes a standalone **3D Previewer** tool for editing and exporting Three.js geometries.

## Features

- Interactive isometric 3D map of Asturias (all 78 municipalities) built with Three.js
- Animated character guide (monigote in traditional Asturian costume) with walkable plaza
- Points of interest per municipality: restaurants, leisure, tourism
- 3D market scene for Gijón with shop data from the Gijón open data portal
- 3D Previewer tool at `/3dpreviewer` — load GLB models, edit materials, export Three.js code
- JWT authentication and user management
- i18n support (Spanish and English via Babel/gettext)
- OSM data import scripts
- Build pipeline: `scripts/build_asturias_scene.py` generates the final scene JS from a template

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | FastAPI 0.128, SQLAlchemy 2.0 async, Alembic |
| Database | PostgreSQL + PostGIS + GeoAlchemy2 |
| Frontend | Jinja2, Three.js r172 (local), Vanilla JS (ES modules) |
| Auth | JWT (python-jose, passlib/bcrypt) |
| i18n | Babel + gettext (.po/.mo) |
| Server | Gunicorn + Uvicorn workers, Nginx reverse proxy |
| Process Manager | Supervisor |

## Project Structure

```
app/
├── core/           # Config (Pydantic Settings), logging, exceptions, security
├── db/             # SQLAlchemy async engine and session
├── middleware/     # i18n detection, request context (X-Request-ID)
├── models/         # ORM models: User, PuntoInteres, MunicipioComercio
├── routers/        # FastAPI routes: pages, asturias_api, v1/ (auth, users, health)
├── schemas/        # Pydantic schemas for request/response validation
├── services/       # Business logic: user, auth
├── static/
│   ├── css/        # App styles (asturias.css, chef_hat.css, ocio.css, style.css)
│   ├── js/         # Scene JS, gijon/ and oviedo/ building configs
│   └── vendor/     # Local Three.js r172 + addons, fonts (Inter), ImageTracer
└── templates/
    ├── base.html
    └── pages/      # asturias.html (main map), 3dpreviewer.html
scripts/
├── build_asturias_scene.py   # Main build pipeline (template → asturias-scene.js)
├── scrape_gijon_compras.py   # Scraper for Gijón market data
├── update_osm_asturias.py    # OSM POI importer
└── archive/                  # One-off generation scripts (kept for reference)
migrations/                   # Alembic migrations
docs/                         # Extended documentation
```

---

## Clone and Run on a New Machine

### Prerequisites

- Python 3.11+
- PostgreSQL 14+ with **PostGIS** extension
- Git

### 1. Clone the repository

```bash
git clone https://github.com/interns-pibico/app_example.git
cd app_example
```

### 2. Create virtual environment and install dependencies

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Create the PostgreSQL database

```bash
# Connect to PostgreSQL as superuser
psql -U postgres

# Inside psql:
CREATE DATABASE app_example;
CREATE USER asturiasuser WITH PASSWORD 'asturiasuser';
GRANT ALL PRIVILEGES ON DATABASE app_example TO asturiasuser;
\c app_example
CREATE EXTENSION postgis;
\q
```

### 4. Configure environment variables

```bash
cp .env.example .env
```

Edit `.env` and set at minimum:

```ini
DATABASE_URL=postgresql+asyncpg://asturiasuser:asturiasuser@localhost:5432/app_example
APP_SECRET_KEY=<generate with: openssl rand -hex 32>
JWT_SECRET_KEY=<generate with: openssl rand -hex 32>
APP_ENV=development
```

### 5. Run database migrations

```bash
alembic upgrade head
```

This creates three tables: `users`, `puntos_interes` (POIs with PostGIS geometry), and `municipio_comercios` (Gijón market shops).

### 6. Compile translations

```bash
pybabel compile -d app/i18n/locales -D messages
```

### 7. (Optional) Import data

```bash
# Import Asturias municipalities and POIs from OpenStreetMap
python3 scripts/importar_municipios.py
python3 scripts/update_osm_asturias.py

# Import Gijón market shop data
python3 scripts/scrape_gijon_compras.py --municipio Gijón
```

### 8. Start the development server

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Open http://localhost:8000 in your browser.

### Verify it works

| URL | Expected |
|-----|----------|
| `http://localhost:8000/` | Interactive 3D map of Asturias |
| `http://localhost:8000/3dpreviewer` | 3D model editor |
| `http://localhost:8000/api/v1/health/live` | `{"status":"ok"}` |
| `http://localhost:8000/docs` | Swagger UI (dev only) |

---

## Build Pipeline

The 3D scene is generated from a template — never edit `asturias-scene.js` directly:

```bash
python3 scripts/build_asturias_scene.py
```

This reads `app/static/js/asturias-scene.template.js`, injects building configs from `app/static/js/*/` subdirectories, computes coastline geometry from PostGIS polygon data, and writes `app/static/js/asturias-scene.js`.

---

## Production Deployment

See `docs/DOCUMENTACION_PROYECTO.md` → Section 8 (Despliegue) for the full Nginx + Supervisor setup.

Quick summary:
```bash
# Supervisor
sudo cp deploy/supervisor/app.conf /etc/supervisor/conf.d/app_example.conf
sudo supervisorctl reread && sudo supervisorctl update

# Nginx
sudo cp deploy/nginx/app.conf /etc/nginx/conf.d/app_example.conf
sudo nginx -t && sudo systemctl reload nginx
```

---

## Documentation

| File | Contents |
|------|----------|
| `docs/DOCUMENTACION_PROYECTO.md` | Full technical documentation (architecture, DB schema, API endpoints, deploy) |
| `docs/3DPREVIEWER.md` | 3D Previewer tool documentation (modes, workflows, exports) |
| `CLAUDE.md` | Development guidelines for Claude Code |

## License

MIT — see [LICENSE](LICENSE)
