"""Increase api_keys key_hash column size

Revision ID: eb59af9858d8
Revises: 0dceccd3d798
Create Date: 2025-01-20 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'eb59af9858d8'
down_revision = '0dceccd3d798'
branch_labels = None
depends_on = None


def upgrade():
    # Increase key_hash column size from 128 to 255 to accommodate longer password hashes
    op.alter_column('api_keys', 'key_hash',
                   existing_type=sa.VARCHAR(length=128),
                   type_=sa.String(length=255),
                   existing_nullable=False)


def downgrade():
    # Revert key_hash column size back to 128
    op.alter_column('api_keys', 'key_hash',
                   existing_type=sa.String(length=255),
                   type_=sa.VARCHAR(length=128),
                   existing_nullable=False)

