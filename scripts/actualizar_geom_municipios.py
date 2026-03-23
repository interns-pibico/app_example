import requests
import psycopg2
import json
import os
import time
from dotenv import load_dotenv

load_dotenv()

def actualizar_geometrias():
    conn = psycopg2.connect(
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASS"),
        host=os.getenv("DB_HOST")
    )
    cur = conn.cursor()

    cur.execute("SELECT nombre FROM municipios WHERE geom IS NOT NULL")
    ya_tienen = [f[0] for f in cur.fetchall()]

    cur.execute("SELECT nombre FROM municipios WHERE geom IS NULL")
    municipios = [f[0] for f in cur.fetchall()]

    print(f"🌍 {len(ya_tienen)} municipios ya tienen geometría. Faltan {len(municipios)}.")

    headers = {'User-Agent': 'AppAsturias_Geom_Fix/2.0'}
    for nombre in municipios:
        print(f"🔍 Buscando límites reales para {nombre}...")

        try:
            geojson = _buscar_poligono_nominatim(nombre, headers)
            if geojson:
                geojson_str = json.dumps(geojson)
                # ST_Multi() convierte Polygon → MultiPolygon si es necesario
                cur.execute("""
                    UPDATE municipios
                    SET geom = ST_Multi(ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326))
                    WHERE nombre = %s
                """, (geojson_str, nombre))
                conn.commit()

                # Verificar cuántos vértices tiene el polígono obtenido
                cur.execute("""
                    SELECT ST_NPoints(geom), ST_GeometryType(geom)
                    FROM municipios WHERE nombre = %s
                """, (nombre,))
                row = cur.fetchone()
                print(f"✅ {nombre}: {row[1]}, {row[0]} vértices")
            else:
                print(f"⚠️ No se encontró polígono real para {nombre}")

            # Pausa de cortesía para Nominatim
            time.sleep(1.2)

        except Exception as e:
            conn.rollback()
            print(f"❌ Error en {nombre}: {e}")

    cur.close()
    conn.close()
    print("✨ Proceso de geometrías finalizado.")


def _buscar_poligono_nominatim(nombre, headers):
    """Busca el polígono real de un municipio en Nominatim.
    Devuelve el GeoJSON dict o None si no se encuentra un polígono.
    """
    url = (
        f"https://nominatim.openstreetmap.org/search"
        f"?city={nombre}&state=Asturias&country=Spain"
        f"&format=json&polygon_geojson=1&limit=5"
    )
    res = requests.get(url, headers=headers, timeout=15)
    data = res.json()
    # Preferir resultados cuyo GeoJSON NO sea un punto
    for item in data:
        geojson = item.get('geojson', {})
        gtype = geojson.get('type', '')
        if gtype in ('Polygon', 'MultiPolygon'):
            return geojson
    return None


def actualizar_todas_geometrias():
    """Fuerza la actualización de TODOS los municipios (incluidos los que ya tienen geom)."""
    conn = psycopg2.connect(
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASS"),
        host=os.getenv("DB_HOST")
    )
    cur = conn.cursor()

    cur.execute("SELECT nombre FROM municipios ORDER BY nombre ASC")
    municipios = [f[0] for f in cur.fetchall()]

    print(f"🌍 Actualizando polígonos reales para {len(municipios)} municipios...")

    headers = {'User-Agent': 'AppAsturias_Geom_Fix/2.0'}
    ok = 0
    fail = 0
    for nombre in municipios:
        print(f"🔍 {nombre}...")

        try:
            geojson = _buscar_poligono_nominatim(nombre, headers)
            if geojson:
                geojson_str = json.dumps(geojson)
                # ST_Multi() convierte Polygon → MultiPolygon si es necesario
                cur.execute("""
                    UPDATE municipios
                    SET geom = ST_Multi(ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326))
                    WHERE nombre = %s
                """, (geojson_str, nombre))
                conn.commit()

                cur.execute("""
                    SELECT ST_NPoints(geom), ST_GeometryType(geom)
                    FROM municipios WHERE nombre = %s
                """, (nombre,))
                row = cur.fetchone()
                print(f"  ✅ {row[1]}, {row[0]} vértices")
                ok += 1
            else:
                print(f"  ⚠️ Sin polígono GeoJSON en Nominatim")
                fail += 1

            time.sleep(1.2)

        except Exception as e:
            conn.rollback()
            print(f"  ❌ Error: {e}")
            fail += 1

    cur.close()
    conn.close()
    print(f"\n✨ Finalizado: {ok} OK, {fail} fallidos.")


if __name__ == "__main__":
    import sys
    if "--todos" in sys.argv:
        actualizar_todas_geometrias()
    else:
        actualizar_geometrias()
