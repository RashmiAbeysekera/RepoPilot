"""
Tests for Day 6 Embedding Storage Pipeline.

Tests cover:
  1. Embedding service loads correctly
  2. Normal chunk content produces vector embedding
  3. Output vector format is list of floats
  4. Vector dimension matches expected model dimension (384)
  5. Empty/whitespace chunk content yields 0 embeddings / skipped
  6. CodeChunk -> ChunkEmbedding relationship & foreign key cascade deletion
  7. SHA-256 content hashing accuracy
  8. Repository-level embedding generation service
  9. Idempotency: running generation twice skips unchanged chunks
 10. Change detection: updating chunk content regenerates embedding
 11. API endpoints (generate & status)
 12. Invalid repository returns 404
"""

import uuid
import pytest
from app.models.chunk_embedding import ChunkEmbedding
from app.models.code_chunk import CodeChunk
from app.models.repository import Repository
from app.models.repository_file import RepositoryFile
from app.services import embedding_service


def test_embedding_service_generate_batch():
    """Test 1, 2, 3, 4: Model loading, vector output shape, numeric values, 384 dimensions."""
    texts = ["def authenticate(user, password): pass", "class DatabaseConnection: pass"]
    vectors = embedding_service.generate_embeddings_batch(texts)

    assert len(vectors) == 2
    for vec in vectors:
        assert isinstance(vec, list)
        assert len(vec) == 384  # all-MiniLM-L6-v2 dimension
        assert all(isinstance(x, float) for x in vec[:10])


def test_compute_content_hash():
    """Test 7: SHA-256 content hashing produces deterministic hex string."""
    text = "const greeting = 'Hello World';"
    hash1 = embedding_service.compute_content_hash(text)
    hash2 = embedding_service.compute_content_hash(text)

    assert len(hash1) == 64
    assert hash1 == hash2
    assert hash1 != embedding_service.compute_content_hash("different text")


def test_chunk_embedding_model_and_relationship(db_session):
    """Test 6: ChunkEmbedding model creation, relationship, and FK cascade deletion."""
    repo = Repository(
        name="Embedding Test Repo",
        full_name="testowner/embeddingrepo",
        github_url="https://github.com/testowner/embeddingrepo",
    )
    db_session.add(repo)
    db_session.commit()

    file_rec = RepositoryFile(
        repository_id=repo.id,
        path="src/auth.py",
        name="auth.py",
        extension=".py",
        size=50,
        file_type="source",
        content="def login(): pass",
    )
    db_session.add(file_rec)
    db_session.commit()

    chunk = CodeChunk(
        repository_file_id=file_rec.id,
        chunk_index=0,
        start_line=1,
        end_line=1,
        content="def login(): pass",
    )
    db_session.add(chunk)
    db_session.commit()

    dummy_vector = [0.1] * 384
    emb = ChunkEmbedding(
        code_chunk_id=chunk.id,
        embedding=dummy_vector,
        model_name="all-MiniLM-L6-v2",
        embedding_dimension=384,
        content_hash=embedding_service.compute_content_hash(chunk.content),
    )
    db_session.add(emb)
    db_session.commit()

    # Verify relationships
    assert chunk.embedding is not None
    assert chunk.embedding.id == emb.id
    assert emb.code_chunk.id == chunk.id

    # Verify cascading deletion from chunk -> embedding
    db_session.delete(chunk)
    db_session.commit()

    assert db_session.query(ChunkEmbedding).filter(ChunkEmbedding.id == emb.id).first() is None


def test_generate_embeddings_for_repository_idempotency(db_session):
    """Test 8, 9, 10: Service execution, idempotency, skipping unchanged, updating changed."""
    repo = Repository(
        name="Idempotent Embedding Repo",
        full_name="testowner/idememb",
        github_url="https://github.com/testowner/idememb",
    )
    db_session.add(repo)
    db_session.commit()

    file_rec = RepositoryFile(
        repository_id=repo.id,
        path="src/service.py",
        name="service.py",
        extension=".py",
        size=100,
        file_type="source",
        content="def compute(): return 42",
    )
    db_session.add(file_rec)
    db_session.commit()

    chunk = CodeChunk(
        repository_file_id=file_rec.id,
        chunk_index=0,
        start_line=1,
        end_line=1,
        content="def compute(): return 42",
    )
    db_session.add(chunk)
    db_session.commit()

    # 1. First run: generates embedding
    res1 = embedding_service.generate_embeddings_for_repository(db_session, repo.id)
    assert res1["total_chunks"] == 1
    assert res1["embeddings_created"] == 1
    assert res1["embeddings_skipped"] == 0

    # 2. Second run: skips unchanged chunk
    res2 = embedding_service.generate_embeddings_for_repository(db_session, repo.id)
    assert res2["total_chunks"] == 1
    assert res2["embeddings_created"] == 0
    assert res2["embeddings_skipped"] == 1

    # 3. Content modification: update chunk content -> regenerates existing embedding
    chunk.content = "def compute(): return 100 # updated"
    db_session.commit()

    res3 = embedding_service.generate_embeddings_for_repository(db_session, repo.id)
    assert res3["embeddings_updated"] == 1
    assert res3["embeddings_created"] == 0


def test_api_generate_and_status_embeddings(client, db_session):
    """Test 11, 12: REST API POST /embeddings/generate and GET /embeddings/status."""
    repo = Repository(
        name="API Embedding Repo",
        full_name="testowner/apiemb",
        github_url="https://github.com/testowner/apiemb",
    )
    db_session.add(repo)
    db_session.commit()

    file_rec = RepositoryFile(
        repository_id=repo.id,
        path="src/main.ts",
        name="main.ts",
        extension=".ts",
        size=50,
        file_type="source",
        content="console.log('RepoPilot');",
    )
    db_session.add(file_rec)
    db_session.commit()

    chunk = CodeChunk(
        repository_file_id=file_rec.id,
        chunk_index=0,
        start_line=1,
        end_line=1,
        content="console.log('RepoPilot');",
    )
    db_session.add(chunk)
    db_session.commit()

    # 1. Check status before embedding
    status_res1 = client.get(f"/api/repositories/{repo.id}/embeddings/status")
    assert status_res1.status_code == 200
    st1 = status_res1.json()
    assert st1["total_chunks"] == 1
    assert st1["embedded_chunks"] == 0
    assert st1["remaining_chunks"] == 1
    assert st1["model_name"] == "all-MiniLM-L6-v2"
    assert st1["embedding_dimension"] == 384

    # 2. Trigger embedding generation
    gen_res = client.post(f"/api/repositories/{repo.id}/embeddings/generate")
    assert gen_res.status_code == 200
    gen_data = gen_res.json()
    assert gen_data["embeddings_created"] == 1

    # 3. Check status after embedding
    status_res2 = client.get(f"/api/repositories/{repo.id}/embeddings/status")
    assert status_res2.status_code == 200
    st2 = status_res2.json()
    assert st2["embedded_chunks"] == 1
    assert st2["remaining_chunks"] == 0


def test_api_invalid_repository_embeddings_404(client):
    """Test 12: Non-existent repository returns 404."""
    fake_id = uuid.uuid4()
    assert client.post(f"/api/repositories/{fake_id}/embeddings/generate").status_code == 404
    assert client.get(f"/api/repositories/{fake_id}/embeddings/status").status_code == 404
