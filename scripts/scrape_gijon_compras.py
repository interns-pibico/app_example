#!/usr/bin/env python3
"""
Scraper para las rutas de compras de Gijón/Xixón.
Fuente: Drupal JSON API en drupal.gijon.es/_format=json
Robots.txt de gijon.es: Disallow vacío → permitido.
Ley 37/2007 de reutilización de datos públicos (proyecto POC).

Uso:
    python3 scripts/scrape_gijon_compras.py [--municipio Gijón]
"""
import argparse
import html as html_module
import re
import sys
import time
import os

import httpx
from bs4 import BeautifulSoup
import psycopg2
from psycopg2.extras import execute_values
from dotenv import load_dotenv

load_dotenv()

RUTAS_GIJON = {
    'gastro':       ('ruta-gijonxixon-compra-gastro',         'Ruta Gijón/Xixón Compra Gastro'),
    'dulzon':       ('ruta-gijonxixon-dulzon',                'Ruta Dulzón'),
    'artesano':     ('ruta-gijonxixon-artesano',              'Ruta Artesano'),
    'arte-cultura': ('ruta-gijonxixon-arte-y-cultura',        'Arte y Cultura'),
    'historia':     ('ruta-gijonxixon-comercios-con-historia', 'Comercios con Historia'),
    'moda':         ('ruta-gijonxixon-diseno-y-moda',         'Diseño y Moda'),
}

DRUPAL_BASE = 'https://drupal.gijon.es'
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (compatible; AsturiasMapBot/1.0)',
    'Accept': 'application/json',
}


def get_db_conn():
    db_url = os.environ.get('DATABASE_URL', '')
    db_url = db_url.replace('postgresql+asyncpg://', 'postgresql://')
    return psycopg2.connect(db_url)


def strip_html(html: str) -> str:
    """Remove HTML tags, return plain text."""
    if not html:
        return ''
    return BeautifulSoup(html, 'html.parser').get_text(separator=' ').strip()


def fetch_json(client: httpx.Client, url: str) -> dict | None:
    try:
        r = client.get(url, headers=HEADERS, timeout=20, follow_redirects=True)
        if r.status_code == 200:
            return r.json()
        print(f'  [HTTP {r.status_code}] {url}')
        return None
    except Exception as e:
        print(f'  [ERROR] {url}: {e}')
        return None


def get_field(data: dict, field: str, key: str = 'value', default=None):
    """Safely extract first item from a Drupal field array."""
    arr = data.get(field, [])
    if arr and isinstance(arr, list):
        return arr[0].get(key, default)
    return default


def scrape_ruta_node_ids(client: httpx.Client, ruta_slug: str) -> list[int]:
    url = f'{DRUPAL_BASE}/es/{ruta_slug}/?_format=json'
    data = fetch_json(client, url)
    if not data:
        return []
    refs = data.get('field_contenidos_relacionados', [])
    ids = [r['target_id'] for r in refs if 'target_id' in r]
    print(f'  → {len(ids)} tiendas en {ruta_slug}')
    return ids


def scrape_shop_node(client: httpx.Client, node_id: int) -> dict | None:
    url = f'{DRUPAL_BASE}/es/node/{node_id}/?_format=json'
    data = fetch_json(client, url)
    if not data:
        return None

    # Title
    nombre = html_module.unescape(get_field(data, 'title') or f'Tienda {node_id}').strip()

    # Description (body)
    body_html = get_field(data, 'body') or ''
    descripcion = strip_html(body_html)[:1000] if body_html else None

    # Address
    direccion = get_field(data, 'field_direccion')

    # Lat/Lon — validate range (lat: 35-45, lon: -10 to 5 for Spain)
    lat_str = get_field(data, 'field_latitud')
    lon_str = get_field(data, 'field_longitud')
    lat = float(lat_str) if lat_str else None
    lon = float(lon_str) if lon_str else None
    if lat is not None and not (35 <= lat <= 45):
        lat, lon = None, None  # swapped or garbage

    # Fallback: field_lo (map widget)
    if lat is None:
        lo = data.get('field_lo', [])
        if lo:
            try:
                _lat = float(lo[0].get('lat', 0))
                _lon = float(lo[0].get('lon', 0))
                if 35 <= _lat <= 45:
                    lat, lon = _lat or None, _lon or None
            except (ValueError, TypeError):
                pass

    # Phone
    tel_raw = get_field(data, 'field_telefono') or ''
    telefono = tel_raw.strip()[:100] if tel_raw else None

    # Web
    web_arr = data.get('field_web', [])
    web = web_arr[0].get('uri') if web_arr else None

    # Horario: strip HTML entities
    horario_raw = get_field(data, 'field_horario') or ''
    horario = strip_html(horario_raw.replace('&#13;', ' ').replace('\r', ' '))[:500] if horario_raw else None

    # Slug from path
    path_alias = get_field(data, 'path', 'alias') or f'/node/{node_id}'
    slug = path_alias.lstrip('/')

    return {
        'slug': slug,
        'nombre': nombre,
        'descripcion': descripcion,
        'direccion': direccion,
        'lat': lat,
        'lon': lon,
        'telefono': telefono,
        'web': web,
        'horario': horario,
    }


def upsert_comercios(conn, municipio: str, ruta_id: str, ruta_nombre: str, shops: list[dict]):
    if not shops:
        return
    with conn.cursor() as cur:
        rows = [
            (
                municipio, ruta_id, ruta_nombre,
                s['nombre'], s['descripcion'], s['direccion'],
                s['lat'], s['lon'], s['telefono'], s['web'], s['horario'],
                s['slug'],
            )
            for s in shops
        ]
        execute_values(cur, """
            INSERT INTO municipio_comercios
                (municipio, ruta_id, ruta_nombre, nombre, descripcion, direccion,
                 lat, lon, telefono, web, horario, slug)
            VALUES %s
            ON CONFLICT (municipio, slug, ruta_id) DO UPDATE SET
                ruta_nombre  = EXCLUDED.ruta_nombre,
                nombre       = EXCLUDED.nombre,
                descripcion  = EXCLUDED.descripcion,
                direccion    = EXCLUDED.direccion,
                lat          = EXCLUDED.lat,
                lon          = EXCLUDED.lon,
                telefono     = EXCLUDED.telefono,
                web          = EXCLUDED.web,
                horario      = EXCLUDED.horario,
                updated_at   = now()
        """, rows)
    conn.commit()


def main():
    parser = argparse.ArgumentParser(description='Scraper rutas de compras Gijón (Drupal JSON API)')
    parser.add_argument('--municipio', default='Gijón')
    parser.add_argument('--delay', type=float, default=0.5,
                        help='Pausa entre requests en segundos (default: 0.5)')
    args = parser.parse_args()

    if args.municipio != 'Gijón':
        print(f'[ERROR] Solo Gijón soportado en esta versión.')
        sys.exit(1)

    municipio = args.municipio
    print(f'=== Scraping rutas de compras de {municipio} (Drupal JSON API) ===')
    conn = get_db_conn()

    with httpx.Client() as client:
        for ruta_id, (ruta_slug, ruta_nombre) in RUTAS_GIJON.items():
            print(f'\n[Ruta] {ruta_id} → {ruta_nombre}')
            node_ids = scrape_ruta_node_ids(client, ruta_slug)
            if not node_ids:
                print('  (Sin tiendas, saltando)')
                continue
            time.sleep(args.delay)

            shops = []
            for i, nid in enumerate(node_ids, 1):
                shop = scrape_shop_node(client, nid)
                if shop:
                    shops.append(shop)
                    lat_str = f' lat={shop["lat"]:.4f}' if shop['lat'] else ' (sin coords)'
                    print(f'  [{i}/{len(node_ids)}] {shop["nombre"][:45]}{lat_str}')
                else:
                    print(f'  [{i}/{len(node_ids)}] node/{nid} → skip')
                time.sleep(args.delay)

            upsert_comercios(conn, municipio, ruta_id, ruta_nombre, shops)
            print(f'  ✓ {len(shops)} tiendas guardadas')

    conn.close()
    print('\n=== Scraping completado ===')


if __name__ == '__main__':
    main()
