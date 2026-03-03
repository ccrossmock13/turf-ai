"""Add organizations and org_id columns for multi-tenancy.

Creates:
  - organizations table (org info)
  - org_members table (user-to-org membership with roles)
  - Adds org_id column to all feature data tables
  - Adds is_superadmin column to users

Revision ID: a1b2c3d4e5f6
Revises: e564d496ec1c
Create Date: 2026-03-03

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = 'e564d496ec1c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Tables that need org_id added
FEATURE_TABLES = [
    'equipment', 'equipment_hours', 'maintenance_schedules', 'equipment_calibration',
    'irrigation_zones', 'irrigation_runs', 'moisture_readings', 'et_data',
    'water_usage', 'crew_members', 'work_orders', 'daily_assignments',
    'time_entries', 'budgets', 'budget_line_items', 'expenses', 'purchase_orders',
    'calendar_events', 'scouting_reports', 'scouting_photos',
    'soil_tests', 'soil_amendments', 'water_tests',
    'spray_applications', 'spray_templates', 'custom_products',
    'user_inventory', 'inventory_quantities', 'sprayers',
    'community_posts', 'community_comments', 'community_alerts',
    'community_programs', 'community_benchmarks',
    'renovation_projects', 'notifications', 'notification_preferences',
    'notification_rules', 'saved_reports', 'compliance_records',
    'map_zones', 'map_pins', 'map_layers',
]


def upgrade() -> None:
    # Create organizations table
    op.create_table(
        'organizations',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('name', sa.Text(), nullable=False),
        sa.Column('slug', sa.Text(), nullable=False, unique=True),
        sa.Column('course_name', sa.Text()),
        sa.Column('address', sa.Text()),
        sa.Column('city', sa.Text()),
        sa.Column('state', sa.Text()),
        sa.Column('created_at', sa.Text(), server_default=sa.text("(datetime('now'))")),
        sa.Column('is_active', sa.Integer(), server_default='1'),
    )

    # Create org_members join table
    op.create_table(
        'org_members',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('org_id', sa.Integer(), sa.ForeignKey('organizations.id'), nullable=False),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('role', sa.Text(), server_default='member'),
        sa.Column('joined_at', sa.Text(), server_default=sa.text("(datetime('now'))")),
        sa.UniqueConstraint('org_id', 'user_id', name='uq_org_user'),
    )

    # Add is_superadmin to users
    with op.batch_alter_table('users') as batch_op:
        batch_op.add_column(sa.Column('is_superadmin', sa.Integer(), server_default='0'))

    # Add org_id to all feature tables
    for table_name in FEATURE_TABLES:
        try:
            with op.batch_alter_table(table_name) as batch_op:
                batch_op.add_column(sa.Column('org_id', sa.Integer(), nullable=True))
        except Exception:
            # Table may not exist yet — feature tables are created dynamically
            pass


def downgrade() -> None:
    # Remove org_id from feature tables
    for table_name in reversed(FEATURE_TABLES):
        try:
            with op.batch_alter_table(table_name) as batch_op:
                batch_op.drop_column('org_id')
        except Exception:
            pass

    # Remove is_superadmin from users
    with op.batch_alter_table('users') as batch_op:
        batch_op.drop_column('is_superadmin')

    op.drop_table('org_members')
    op.drop_table('organizations')
