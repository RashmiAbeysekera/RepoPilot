"""add_sync_fields_to_repositories

Revision ID: 5b6c7d8e9f0a
Revises: 4a5b6c7d8e9f
Create Date: 2026-08-29 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5b6c7d8e9f0a'
down_revision: Union[str, Sequence[str], None] = '4a5b6c7d8e9f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'repositories',
        sa.Column('sync_status', sa.String(length=50), server_default='idle', nullable=False)
    )
    op.add_column(
        'repositories',
        sa.Column('last_synced_at', sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        'repositories',
        sa.Column('last_commit_sha', sa.String(length=40), nullable=True)
    )
    op.add_column(
        'repositories',
        sa.Column('sync_error', sa.Text(), nullable=True)
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('repositories', 'sync_error')
    op.drop_column('repositories', 'last_commit_sha')
    op.drop_column('repositories', 'last_synced_at')
    op.drop_column('repositories', 'sync_status')
