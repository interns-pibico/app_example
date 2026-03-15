# app_example

Web application for exploring the municipalities of Asturias, built as a reference implementation and learning project by the pibiCo interns team.

## Overview

`app_example` is a full-stack FastAPI application that serves an interactive map and 3D scene explorer for Asturian points of interest. It acts as the main catch-all frontend on the pibiCo server and doubles as a scaffold demonstrating pibiCo's standard project structure.

## Features

- Interactive map of Asturias with points of interest (places)
- 3D isometric scenes built with Three.js
- JWT authentication and user management
- i18n support (Spanish, English, and more via Babel)
- Mercado (market) data model integration
- SVG/geometry processing with CairoSVG and Shapely
- OSM data import scripts

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | FastAPI, SQLAlchemy, Alembic |
| Database | PostgreSQL + GeoAlchemy2 |
| Frontend | Jinja2, Three.js, Vanilla JS |
| Auth | JWT (python-jose, passlib/bcrypt) |
| i18n | Babel |
| Server | Gunicorn + Uvicorn, Nginx |

## Project Structure

```
app/
├── core/          # Config, logging, exceptions, security
├── db/            # SQLAlchemy session and base
├── middleware/    # i18n, request context
├── models/        # SQLModel ORM models (places, user, mercado)
├── routers/       # FastAPI routes (pages, asturias_api, auth, users)
├── schemas/       # Pydantic schemas
├── services/      # Business logic
├── static/        # JS, CSS, fonts, 3D assets
└── templates/     # Jinja2 HTML templates
scripts/           # Data import and geometry scripts
migrations/        # Alembic migrations
```

## Setup

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your DATABASE_URL, SECRET_KEY, etc.

# Run migrations
alembic upgrade head

# Start development server
uvicorn app.main:app --reload
```

## Environment Variables

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | PostgreSQL connection string |
| `SECRET_KEY` | JWT signing secret |
| `DEBUG` | Enable debug mode (`True`/`False`) |
| `DEFAULT_LANGUAGE` | Default locale (`es`) |

## License

MIT — see [LICENSE](LICENSE)
