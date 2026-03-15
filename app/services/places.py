que me de los import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert
from app.models.places import PuntoInteres
from datetime import datetime

async def sincronizar_asturias_osm(db: AsyncSession):
    # Definimos el recuadro de Asturias (Sur, Oeste, Norte, Este)
    bbox = "42.8, -7.2, 43.7, -4.3"
    overpass_url = "https://overpass-api.de/api/interpreter"
    
    # Dividimos en categorías para evitar que el servidor de Overpass nos de error 504
    categorias = [
        'node["amenity"~"restaurant|cafe|bar|pub|cinema|theatre|arts_centre"]',
        'node["tourism"~"viewpoint|museum|hotel"]',
        'node["shop"~"bakery|cheese|wine|deli|confectionery"]',
        'node["historic"~"monument|memorial|castle"]'
    ]
    
    total_acumulado = 0
    now = datetime.now() # Fecha sin zona horaria para evitar errores de Postgres

    async with httpx.AsyncClient(timeout=90.0) as client:
        for cat in categorias:
            # Creamos la query específica para esta categoría
            query = f"""
            [out:json][timeout:90];
            ({cat}({bbox}););
            out body;
            """
            
            try:
                print(f"⏳ Descargando categoría: {cat}...")
                response = await client.post(overpass_url, data={"data": query})
                
                if response.status_code != 200:
                    print(f"⚠️ Error en categoría {cat}: Código {response.status_code}")
                    continue
                
                data = response.json()
                elementos = data.get("elements", [])
                print(f"✅ Encontrados {len(elementos)} elementos.")

                for el in elementos:
                    osm_id = el.get("id")
                    tags = el.get("tags", {})
                    nombre = tags.get("name", "Sin nombre")
                    
                    # Prioridad: amenity → tourism → shop → historic
                    tipo = tags.get("amenity") or tags.get("tourism") or tags.get("shop") or tags.get("historic") or "otros"
                    
                    lat = el.get("lat")
                    lon = el.get("lon")

                    if not lat or not lon:
                        continue

                    # Preparamos el INSERT con ON CONFLICT (UPSERT)
                    stmt = insert(PuntoInteres).values(
                        osm_id=osm_id,
                        nombre=nombre,
                        tipo=tipo,
                        tags=tags,
                        geom=f"SRID=4326;POINT({lon} {lat})",
                        created_at=now,
                        updated_at=now
                    ).on_conflict_do_update(
                        index_elements=['osm_id'],
                        set_={
                            "nombre": nombre,
                            "tipo": tipo,
                            "tags": tags,
                            "geom": f"SRID=4326;POINT({lon} {lat})",
                            "updated_at": now
                        }
                    )
                    await db.execute(stmt)
                
                total_acumulado += len(elementos)
                # Guardamos después de cada categoría para no perder progreso
                await db.commit()
                
            except Exception as e:
                print(f"❌ Error procesando {cat}: {str(e)}")
                continue
                
    return {"status": "success", "total_final": total_acumulado}