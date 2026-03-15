from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.db.session import get_db_session

router = APIRouter()

SHOP_LABELS = {
    'bakery': 'Panadería', 'supermarket': 'Supermercado',
    'clothes': 'Tienda de ropa', 'deli': 'Delicatessen',
    'cheese': 'Quesería', 'wine': 'Vinoteca', 'kiosk': 'Kiosco',
    'fashion': 'Moda',
}
OCIO_LABELS = {
    'museum': 'Museo', 'monument': 'Monumento', 'castle': 'Castillo',
    'viewpoint': 'Mirador', 'theatre': 'Teatro', 'arts_centre': 'Centro de arte',
    'cinema': 'Cine', 'memorial': 'Memorial',
}
TIPO_LABELS = {
    'restaurant': 'Restaurante', 'bar': 'Bar', 'cafe': 'Cafetería', 'pub': 'Pub',
}


async def ejecutar_consulta_espacial(municipio: str, tipos: list, db: AsyncSession):
    # Esta query es mucho más potente:
    # 1. Busca el municipio en la tabla 'municipios' (usando unaccent)
    # 2. Busca todos los puntos que estén DENTRO de ese municipio geográficamente
    query = text("""
        SELECT p.osm_id, p.nombre, TRIM(p.tipo) as tipo,
               ST_X(p.geom) as lon, ST_Y(p.geom) as lat,
               p.tags->>'cuisine' as cuisine,
               p.tags->>'description' as description,
               p.tags->>'shop' as shop_type,
               p.tags->>'website' as website
        FROM puntos_interes p
        JOIN municipios m ON ST_Within(p.geom, m.geom)
        WHERE unaccent(m.nombre) ILIKE unaccent(:m)
        AND (
            TRIM(p.tipo) = ANY(:tipos)
            OR p.tags->>'amenity' = ANY(:tipos)
            OR p.tags->>'shop' = ANY(:tipos)
            OR p.tags->>'tourism' = ANY(:tipos)
            OR p.tags->>'historic' = ANY(:tipos)
        )
        AND p.nombre IS NOT NULL
        LIMIT 300
    """)

    result = await db.execute(query, {"m": municipio, "tipos": tipos})
    return result.fetchall()


@router.get("/api/restaurantes/{municipio}")
async def get_restaurantes(municipio: str, db: AsyncSession = Depends(get_db_session)):
    tipos = ['restaurant', 'pub', 'cafe', 'bar']
    filas = await ejecutar_consulta_espacial(municipio, tipos, db)
    return {
        "municipio": municipio.capitalize(),
        "total": len(filas),
        "resultados": [
            {
                "id": f.osm_id,
                "nombre": f.nombre,
                "tipo": f.tipo,
                "tipo_label": TIPO_LABELS.get(f.tipo, f.tipo or ''),
                "lat": f.lat,
                "lon": f.lon,
                "cuisine": f.cuisine,
                "description": f.description,
            }
            for f in filas
        ],
    }


@router.get("/api/ocio/{municipio}")
async def get_ocio(municipio: str, db: AsyncSession = Depends(get_db_session)):
    tipos = ['viewpoint', 'museum', 'theatre', 'arts_centre', 'castle', 'monument', 'cinema', 'memorial']
    filas = await ejecutar_consulta_espacial(municipio, tipos, db)
    return {
        "municipio": municipio.capitalize(),
        "total": len(filas),
        "resultados": [
            {
                "id": f.osm_id,
                "nombre": f.nombre,
                "tipo": f.tipo,
                "tipo_label": OCIO_LABELS.get(f.tipo, f.tipo or ''),
                "lat": f.lat,
                "lon": f.lon,
                "description": f.description,
            }
            for f in filas
        ],
    }


MERCADO_RUTAS_META = {
    'gastro':       {'label': 'Gastro',                  'icon': '🍴', 'color': '#e07a5f'},
    'dulzon':       {'label': 'Dulces',                  'icon': '🍬', 'color': '#f4a261'},
    'artesano':     {'label': 'Artesanía',               'icon': '🎨', 'color': '#81b29a'},
    'arte-cultura': {'label': 'Arte y Cultura',          'icon': '🎭', 'color': '#9b72cf'},
    'historia':     {'label': 'Comercios con Historia',  'icon': '🏛️', 'color': '#5c8a8a'},
    'moda':         {'label': 'Diseño y Moda',           'icon': '👗', 'color': '#d4a5c9'},
}


@router.get("/api/mercado/{municipio}")
async def get_mercado_rutas(municipio: str, db: AsyncSession = Depends(get_db_session)):
    """Devuelve las rutas de compras disponibles con conteo de tiendas."""
    q = text("""
        SELECT ruta_id, COUNT(*) as cnt
        FROM municipio_comercios
        WHERE unaccent(municipio) ILIKE unaccent(:m)
        GROUP BY ruta_id
        ORDER BY ruta_id
    """)
    result = await db.execute(q, {"m": municipio})
    rows = {r.ruta_id: r.cnt for r in result.fetchall()}

    rutas = []
    for ruta_id, meta in MERCADO_RUTAS_META.items():
        rutas.append({
            "id":     ruta_id,
            "label":  meta['label'],
            "icon":   meta['icon'],
            "color":  meta['color'],
            "count":  rows.get(ruta_id, 0),
        })
    return rutas


@router.get("/api/mercado/{municipio}/{ruta_id}")
async def get_mercado_tiendas(municipio: str, ruta_id: str, db: AsyncSession = Depends(get_db_session)):
    """Devuelve las tiendas de una ruta concreta."""
    q = text("""
        SELECT nombre, descripcion, direccion, lat, lon, telefono, web, horario
        FROM municipio_comercios
        WHERE unaccent(municipio) ILIKE unaccent(:m)
          AND ruta_id = :r
        ORDER BY nombre
    """)
    result = await db.execute(q, {"m": municipio, "r": ruta_id})
    rows = result.fetchall()
    return [
        {
            "nombre":      r.nombre,
            "descripcion": r.descripcion,
            "direccion":   r.direccion,
            "lat":         r.lat,
            "lon":         r.lon,
            "telefono":    r.telefono,
            "web":         r.web,
            "horario":     r.horario,
        }
        for r in rows
    ]


@router.get("/api/tiendas/{municipio}")
async def get_tiendas(municipio: str, db: AsyncSession = Depends(get_db_session)):
    tipos = ['bakery', 'supermarket', 'clothes', 'fashion', 'kiosk', 'deli', 'cheese', 'wine']
    filas = await ejecutar_consulta_espacial(municipio, tipos, db)
    return {
        "municipio": municipio.capitalize(),
        "total": len(filas),
        "resultados": [
            {
                "id": f.osm_id,
                "nombre": f.nombre,
                "tipo": f.tipo,
                "tipo_label": SHOP_LABELS.get(f.tipo or f.shop_type or '', f.tipo or ''),
                "lat": f.lat,
                "lon": f.lon,
                "description": f.description,
            }
            for f in filas
        ],
    }
