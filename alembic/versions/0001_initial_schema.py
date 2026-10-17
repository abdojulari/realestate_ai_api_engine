"""Create application tables from the SQLAlchemy models.

Revision ID: 0001_initial
Revises:
Create Date: 2026-10-17
"""

from alembic import op
import sqlalchemy as sa

from db_models import Base

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"'))
    Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    Base.metadata.drop_all(bind=op.get_bind())
