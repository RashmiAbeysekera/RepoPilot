"""create_code_chunks_table

Revision ID: 3f8a9b1c2d4e
Revises: 0829ba4c3f1b
Create Date: 2026-08-27 19:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3f8a9b1c2d4e'
down_revision: Union[str, Sequence[str], None] = '0829ba4c3f1b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'code_chunks',
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('repository_file_id', sa.UUID(), nullable=False),
        sa.Column('chunk_index', sa.Integer(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('start_line', sa.Integer(), nullable=False),
        sa.Column('end_line', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['repository_file_id'], ['repository_files.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('repository_file_id', 'chunk_index', name='uq_code_chunks_file_id_chunk_index')
    )
    op.create_index(op.f('ix_code_chunks_repository_file_id'), 'code_chunks', ['repository_file_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_code_chunks_repository_file_id'), table_name='code_chunks')
    op.drop_table('code_chunks')
