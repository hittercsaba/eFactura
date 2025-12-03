"""Increase access_token and refresh_token column size

Revision ID: 651555801aed
Revises: a9c4d3e2f1b5
Create Date: 2025-12-03 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '651555801aed'
down_revision = 'a9c4d3e2f1b5'
branch_labels = None
depends_on = None


def upgrade():
    # Increase access_token column size from 500 to 2000
    # JWT tokens from ANAF can be 1500+ characters long
    op.alter_column('anaf_tokens', 'access_token',
                    existing_type=sa.String(length=500),
                    type_=sa.String(length=2000),
                    existing_nullable=False)
    
    # Increase refresh_token column size from 500 to 2000
    op.alter_column('anaf_tokens', 'refresh_token',
                    existing_type=sa.String(length=500),
                    type_=sa.String(length=2000),
                    existing_nullable=True)


def downgrade():
    # Revert to 500 characters (may cause data loss if tokens are longer)
    op.alter_column('anaf_tokens', 'access_token',
                    existing_type=sa.String(length=2000),
                    type_=sa.String(length=500),
                    existing_nullable=False)
    
    op.alter_column('anaf_tokens', 'refresh_token',
                    existing_type=sa.String(length=2000),
                    type_=sa.String(length=500),
                    existing_nullable=True)
