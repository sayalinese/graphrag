"""add user menu configs table

Revision ID: b1f4d2a9c8e1
Revises: 9f1c2b7e4a10
Create Date: 2026-03-21 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b1f4d2a9c8e1'
down_revision = '9f1c2b7e4a10'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'user_menu_configs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('menu_data', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id'),
    )
    with op.batch_alter_table('user_menu_configs', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_user_menu_configs_user_id'), ['user_id'], unique=True)


def downgrade():
    with op.batch_alter_table('user_menu_configs', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_user_menu_configs_user_id'))

    op.drop_table('user_menu_configs')