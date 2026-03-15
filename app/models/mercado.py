from typing import Optional
from sqlalchemy import String, Float, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base


class MunicipioComercio(Base):
    __tablename__ = 'municipio_comercios'
    __table_args__ = (
        UniqueConstraint('municipio', 'slug', 'ruta_id', name='uq_municipio_slug_ruta'),
    )

    municipio: Mapped[str] = mapped_column(String(100), index=True)
    ruta_id: Mapped[str] = mapped_column(String(50))
    ruta_nombre: Mapped[str] = mapped_column(String(200))
    nombre: Mapped[str] = mapped_column(String(300))
    descripcion: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    direccion: Mapped[Optional[str]] = mapped_column(String(400), nullable=True)
    lat: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    lon: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    telefono: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    web: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    horario: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    slug: Mapped[str] = mapped_column(String(300))
