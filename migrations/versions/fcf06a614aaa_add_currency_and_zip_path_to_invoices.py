"""add_currency_and_zip_path_to_invoices

Revision ID: fcf06a614aaa
Revises: 23aca829d151
Create Date: 2025-01-16 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'fcf06a614aaa'
down_revision = '23aca829d151'
branch_labels = None
depends_on = None


def upgrade():
    # Add currency field for storing invoice currency code (EUR, RON, etc.)
    op.add_column('invoices', sa.Column('currency', sa.String(length=3), nullable=True))
    
    # Add zip_file_path field for storing relative path to saved ZIP file
    op.add_column('invoices', sa.Column('zip_file_path', sa.String(length=500), nullable=True))


def downgrade():
    # Remove zip_file_path column
    op.drop_column('invoices', 'zip_file_path')
    
    # Remove currency column
    op.drop_column('invoices', 'currency')
