"""create_chunk_embeddings_table

Revision ID: 4a5b6c7d8e9f
Revises: 3f8a9b1c2d4e
Create Date: 2026-08-27 23:05:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector


# revision identifiers, used by Alembic.
revision: str = '4a5b6c7d8e9f'
down_revision: Union[str, Sequence[str], None] = '3f8a9b1c2d4e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("CREATE EXTENSION IF NOT EXISTS vector;")

    op.create_table(
        'chunk_embeddings',
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('code_chunk_id', sa.UUID(), nullable=False),
        sa.Column('embedding', Vector(384), nullable=False),
        sa.Column('model_name', sa.String(length=100), nullable=False, server_default='all-MiniLM-L6-v2'),
        sa.Column('embedding_dimension', sa.Integer(), nullable=False, server_default='384'),
        sa.Column('content_hash', sa.String(length=64), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['code_chunk_id'], ['code_chunks.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('code_chunk_id', name='uq_chunk_embeddings_code_chunk_id')
    )
    op.create_index(op.f('ix_chunk_embeddings_code_chunk_id'), 'chunk_embeddings', ['code_chunk_id'], unique=True)
    op.create_index(op.f('ix_chunk_embeddings_content_hash'), 'chunk_embeddings', ['content_hash'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_chunk_embeddings_content_hash'), table_name='chunk_embeddings')
    op.drop_index(op.f('ix_chunk_embeddings_code_chunk_id'), table_name='chunk_embeddings')
    op.drop_table('chunk_embeddings')
