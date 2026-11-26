"""Store source snapshots for text diffs.

Revision ID: 20261126snapshot
Revises: 74c13fac4328
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20261126snapshot"
down_revision: Union[str, Sequence[str], None] = "74c13fac4328"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("sources", sa.Column("last_content", sa.Text(), nullable=True))
    op.create_index("ix_sources_user_id", "sources", ["user_id"])
    op.create_index("ix_notifications_user_id", "notifications", ["user_id"])
    op.create_index("ix_notifications_item_id", "notifications", ["item_id"])


def downgrade() -> None:
    op.drop_index("ix_sources_user_id", table_name="sources")
    op.drop_index("ix_notifications_item_id", table_name="notifications")
    op.drop_index("ix_notifications_user_id", table_name="notifications")
    op.drop_column("sources", "last_content")
