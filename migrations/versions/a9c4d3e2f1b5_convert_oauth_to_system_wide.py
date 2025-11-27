"""Convert OAuth config to system-wide (remove user_id, add created_by)

Revision ID: a9c4d3e2f1b5
Revises: f3a8b9c5d1e2
Create Date: 2025-11-27 10:45:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a9c4d3e2f1b5'
down_revision = 'f3a8b9c5d1e2'
branch_labels = None
depends_on = None


def upgrade():
    # Step 1: Add new columns (nullable first)
    op.add_column('anaf_oauth_configs', sa.Column('created_by', sa.Integer(), nullable=True))
    op.add_column('anaf_oauth_configs', sa.Column('updated_at', sa.DateTime(), nullable=True))
    
    # Step 2: Create foreign key for created_by
    op.create_foreign_key('fk_oauth_config_created_by', 'anaf_oauth_configs', 'users', ['created_by'], ['id'])
    
    # Step 3: Remove the unique constraint on user_id (if it exists)
    try:
        op.drop_constraint('anaf_oauth_configs_user_id_key', 'anaf_oauth_configs', type_='unique')
    except:
        pass  # Constraint might not exist
    
    # Step 4: Remove foreign key on user_id
    try:
        op.drop_constraint('anaf_oauth_configs_user_id_fkey', 'anaf_oauth_configs', type_='foreignkey')
    except:
        pass  # Might be named differently
    
    # Step 5: Set created_by to the user_id value for existing records
    op.execute("UPDATE anaf_oauth_configs SET created_by = user_id WHERE created_by IS NULL")
    
    # Step 6: Drop the user_id column
    op.drop_column('anaf_oauth_configs', 'user_id')
    
    # Step 7: Make created_by NOT NULL
    op.alter_column('anaf_oauth_configs', 'created_by', nullable=False)


def downgrade():
    # Reverse: Add user_id back
    op.add_column('anaf_oauth_configs', sa.Column('user_id', sa.Integer(), nullable=True))
    
    # Copy created_by to user_id
    op.execute("UPDATE anaf_oauth_configs SET user_id = created_by WHERE user_id IS NULL")
    
    # Make user_id NOT NULL
    op.alter_column('anaf_oauth_configs', 'user_id', nullable=False)
    
    # Recreate foreign key
    op.create_foreign_key('anaf_oauth_configs_user_id_fkey', 'anaf_oauth_configs', 'users', ['user_id'], ['id'])
    
    # Recreate unique constraint
    op.create_unique_constraint('anaf_oauth_configs_user_id_key', 'anaf_oauth_configs', ['user_id'])
    
    # Drop new columns
    op.drop_constraint('fk_oauth_config_created_by', 'anaf_oauth_configs', type_='foreignkey')
    op.drop_column('anaf_oauth_configs', 'updated_at')
    op.drop_column('anaf_oauth_configs', 'created_by')

