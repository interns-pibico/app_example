import requests
import psycopg2
import json
import os
import time
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

DB_PARAMS = {
    "dbname": os.getenv("DB_NAME"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASS"),
    "host": os.getenv("DB_HOST"),
    "port": os.getenv("DB_PORT", "5432")
}

def obtener_bbox_municipio(nombre):
    """Obtiene el BBox oficial de un municipio usando Nominatim"""
    url = f"https://nominatim.openstreetmap.org/search?city={nombre}&state=Asturias&country=Spain&format=json"
    headers = {'User-Agent': 'AppAsturias_Update_Bot/1.0'}
    try:
        response = requests.get(url, headers=headers, timeout=10)
        data = response.json()
        if data:
            b = data[0]['boundingbox']
            # Reordenar de [lat_min, lat_max, lon_min, lon_max] a "lat_min, lon_min, lat_max, lon_max"
            return f"{b[0]}, {b[2]}, {b[1]}, {b[3]}"
    except Exception as e:
        print(f"⚠️ No se pudo obtener coordenadas para {nombre}: {e}")
    return None

def descargar_datos_overpass(bbox):
    """Descarga los puntos de interés dentro de un BBox"""
    url = "https://overpass-api.de/api/interpreter"
    query = f"""
    [out:json][timeout:90];
    (
      node["amenity"~"restaurant|cafe|pub|bar|theatre|arts_centre|cinema"]({bbox});
      node["shop"~"bakery|confectionery|deli|cheese|wine"]({bbox});
      node["tourism"~"viewpoint|museum"]({bbox});
      node["historic"~"monument|memorial|castle"]({bbox});
    );
    out body;
    """
    try:
        response = requests.post(url, data={'data': query}, timeout=100)
        response.raise_for_status()
        return response.json().get('elements', [])
    except Exception:
        return []

def actualizar_toda_asturias():
    conn = psycopg2.connect(**DB_PARAMS)
    cur = conn.cursor()
    
    # 1. Obtener la lista de todos los municipios importados
    cur.execute("SELECT nombre FROM municipios ORDER BY nombre ASC")
    municipios = [fila[0] for fila in cur.fetchall()]
    
    ahora = datetime.now()
    print(f"🚀 Iniciando actualización de {len(municipios)} municipios...")

    for nombre in municipios:
        print(f"\n--- Procesando: {nombre} ---")
        
        bbox = obtener_bbox_municipio(nombre)
        if not bbox:
            continue
            
        elementos = descargar_datos_overpass(bbox)
        print(f"📥 Recibidos {len(elementos)} elementos.")

        for el in elementos:
            tags = el.get('tags', {})
            tipo = tags.get('amenity') or tags.get('shop') or tags.get('tourism') or tags.get('historic') or 'punto'
            nombre_sitio = tags.get('name') or tipo.replace('_', ' ').capitalize()

            cur.execute("""
                INSERT INTO puntos_interes (osm_id, nombre, tipo, tags, geom, ultima_actualizacion)
                VALUES (%s, %s, %s, %s, ST_SetSRID(ST_MakePoint(%s, %s), 4326), %s)
                ON CONFLICT (osm_id) DO UPDATE SET 
                    nombre = EXCLUDED.nombre, tipo = EXCLUDED.tipo, tags = EXCLUDED.tags,
                    geom = EXCLUDED.geom, ultima_actualizacion = EXCLUDED.ultima_actualizacion;
            """, (el['id'], nombre_sitio, tipo, json.dumps(tags), el['lon'], el['lat'], ahora))
        
        conn.commit()
        print(f"✅ {nombre} guardado.")
        
        # Pausa de cortesía para no saturar las APIs (Muy importante)
        time.sleep(12) 

    cur.close()
    conn.close()
    print(f"\n[{ahora}] ✨ ACTUALIZACIÓN COMPLETA DE ASTURIAS.")

if __name__ == "__main__":
    actualizar_toda_asturias()