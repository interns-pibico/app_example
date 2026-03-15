"""add_municipio_comercios

Revision ID: c07a0d6b819b
Revises: aae43ff21c50
Create Date: 2026-02-27 10:46:19.145790

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'c07a0d6b819b'
down_revision: Union[str, None] = 'aae43ff21c50'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('municipio_comercios',
    sa.Column('municipio', sa.String(length=100), nullable=False),
    sa.Column('ruta_id', sa.String(length=50), nullable=False),
    sa.Column('ruta_nombre', sa.String(length=200), nullable=False),
    sa.Column('nombre', sa.String(length=300), nullable=False),
    sa.Column('descripcion', sa.Text(), nullable=True),
    sa.Column('direccion', sa.String(length=400), nullable=True),
    sa.Column('lat', sa.Float(), nullable=True),
    sa.Column('lon', sa.Float(), nullable=True),
    sa.Column('telefono', sa.String(length=100), nullable=True),
    sa.Column('web', sa.String(length=500), nullable=True),
    sa.Column('horario', sa.Text(), nullable=True),
    sa.Column('slug', sa.String(length=300), nullable=False),
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('municipio', 'slug', 'ruta_id', name='uq_municipio_slug_ruta')
    )
    op.create_index(op.f('ix_municipio_comercios_municipio'), 'municipio_comercios', ['municipio'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_municipio_comercios_municipio'), table_name='municipio_comercios')
    op.drop_table('municipio_comercios')
