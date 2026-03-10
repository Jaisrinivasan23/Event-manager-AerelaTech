"""Add user authentication and enhanced resource fields

Revision ID: 0002_auth_and_resource_enhancements
Revises: 0001_add_category
Create Date: 2026-03-10

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0002_auth_and_resource_enhancements'
down_revision = '0001_add_category'
branch_labels = None
depends_on = None


def upgrade():
    # Create users table
    op.create_table('users',
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('username', sa.String(length=80), nullable=False),
        sa.Column('email', sa.String(length=120), nullable=False),
        sa.Column('password_hash', sa.String(length=255), nullable=False),
        sa.Column('role', sa.String(length=20), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('user_id'),
        sa.UniqueConstraint('email'),
        sa.UniqueConstraint('username')
    )
    
    # Add new columns to resources table
    with op.batch_alter_table('resources', schema=None) as batch_op:
        batch_op.add_column(sa.Column('capacity', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('quantity', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('max_hours_per_day', sa.Float(), nullable=True))
    
    # Add new columns to events table
    with op.batch_alter_table('events', schema=None) as batch_op:
        batch_op.add_column(sa.Column('timezone', sa.String(length=50), nullable=True))
        batch_op.add_column(sa.Column('expected_attendees', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('created_by', sa.Integer(), nullable=True))
        batch_op.create_foreign_key('fk_events_created_by', 'users', ['created_by'], ['user_id'])
    
    # Add new columns to event_resource_allocations table
    with op.batch_alter_table('event_resource_allocations', schema=None) as batch_op:
        batch_op.add_column(sa.Column('reserved_quantity', sa.Integer(), nullable=True))
        batch_op.create_index('idx_event_resource', ['event_id', 'resource_id'], unique=False)


def downgrade():
    # Remove columns from event_resource_allocations
    with op.batch_alter_table('event_resource_allocations', schema=None) as batch_op:
        batch_op.drop_index('idx_event_resource')
        batch_op.drop_column('reserved_quantity')
    
    # Remove columns from events
    with op.batch_alter_table('events', schema=None) as batch_op:
        batch_op.drop_constraint('fk_events_created_by', type_='foreignkey')
        batch_op.drop_column('created_by')
        batch_op.drop_column('expected_attendees')
        batch_op.drop_column('timezone')
    
    # Remove columns from resources
    with op.batch_alter_table('resources', schema=None) as batch_op:
        batch_op.drop_column('max_hours_per_day')
        batch_op.drop_column('quantity')
        batch_op.drop_column('capacity')
    
    # Drop users table
    op.drop_table('users')
