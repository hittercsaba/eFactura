"""Increase client_secret column size to accommodate encrypted data

Revision ID: f3a8b9c5d1e2
Revises: eb59af9858d8
Create Date: 2025-11-27 10:20:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f3a8b9c5d1e2'
down_revision = 'eb59af9858d8'
branch_labels = None
depends_on = None


def upgrade():
    # Increase client_secret column size from 255 to 500 to accommodate encrypted data
    op.alter_column('anaf_oauth_configs', 'client_secret',
                   existing_type=sa.VARCHAR(length=255),
                   type_=sa.String(length=500),
                   existing_nullable=False)


def downgrade():
    # Revert client_secret column size back to 255
    op.alter_column('anaf_oauth_configs', 'client_secret',
                   existing_type=sa.String(length=500),
                   type_=sa.VARCHAR(length=255),
                   existing_nullable=False)

