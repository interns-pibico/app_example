# app/models/mapas.py
from sqlalchemy import String, BigInteger, JSON
from sqlalchemy.orm import Mapped, mapped_column
from geoalchemy2 import Geometry
from geoalchemy2.shape import to_shape
from app.db.base import Base  # Importas TU clase Base con los campos de tiempo

class PuntoInteres(Base):
    __tablename__ = "puntos_interes"

    
    osm_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    nombre: Mapped[str] = mapped_column(String(255))
    tipo: Mapped[str] = mapped_column(String(50)) 
    tags: Mapped[dict | None] = mapped_column(JSON)
    
    geom: Mapped[Geometry] = mapped_column(
        Geometry(geometry_type='POINT', srid=4326)
    )

    @property
    def lat(self):
        return to_shape(self.geom).y if self.geom else None

    @property
    def lon(self):
        return to_shape(self.geom).x if self.geom else None