"""add source_hash price_per_m2 title

Revision ID: a1b2c3d4e5f6
Revises: 57b13657ea66
Create Date: 2026-07-07 05:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '57b13657ea66'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add source_hash, price_per_m2, and title columns."""
    op.add_column('listings', sa.Column('source_hash', sa.String(length=64), nullable=True))
    op.add_column('listings', sa.Column('price_per_m2', sa.Numeric(precision=15, scale=2), nullable=True))
    op.add_column('listings', sa.Column('title', sa.String(length=500), nullable=True))
    op.create_index(op.f('ix_listings_source_hash'), 'listings', ['source_hash'], unique=False)


def downgrade() -> None:
    """Remove source_hash, price_per_m2, and title columns."""
    op.drop_index(op.f('ix_listings_source_hash'), table_name='listings')
    op.drop_column('listings', 'title')
    op.drop_column('listings', 'price_per_m2')
    op.drop_column('listings', 'source_hash')
