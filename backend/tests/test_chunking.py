"""
Tests for Day 5 Code Chunking feature.

Tests cover:
  1. CodeChunk model creation
  2. RepositoryFile -> CodeChunk relationship
  3. Foreign key cascading deletion
  4. Small file creates one chunk
  5. Large file creates multiple chunks
  6. Chunk overlap is correct
  7. start_line accuracy
  8. end_line accuracy
  9. Empty file creates zero chunks
 10. Re-running generation is idempotent (no duplicate chunks)
 11. Repository-level chunk generation API works
 12. Invalid repository returns 404
 13. Invalid file/repository combination returns 404
 14. Chunk retrieval endpoints work (list & detail)
 15. Single-file chunk generation endpoint works
"""

import uuid
import pytest
from app.models.code_chunk import CodeChunk
from app.models.repository import Repository
from app.models.repository_file import RepositoryFile
from app.services import chunking_service


def test_split_text_into_chunks_empty():
    """Test 9 & 10: Empty or None file content yields 0 chunks."""
    assert chunking_service.split_text_into_chunks(None) == []
    assert chunking_service.split_text_into_chunks("") == []
    assert chunking_service.split_text_into_chunks("\n\n") == []


def test_split_text_into_chunks_small():
    """Test 4, 7, 8: Small file (<= 100 lines) creates exactly 1 chunk covering lines 1 to N."""
    lines = [f"line {i}" for i in range(1, 45)]
    content = "\n".join(lines)
    chunks = chunking_service.split_text_into_chunks(content, chunk_size=100, chunk_overlap=10)

    assert len(chunks) == 1
    assert chunks[0]["chunk_index"] == 0
    assert chunks[0]["start_line"] == 1
    assert chunks[0]["end_line"] == 44
    assert chunks[0]["content"] == content


def test_split_text_into_chunks_large():
    """Test 5, 6, 7, 8: Large file (e.g. 250 lines) creates multiple chunks with 10-line overlap."""
    lines = [f"line {i}" for i in range(1, 251)]
    content = "\n".join(lines)

    chunks = chunking_service.split_text_into_chunks(content, chunk_size=100, chunk_overlap=10)

    # 250 lines, size 100, overlap 10 -> step 90
    # Chunk 0: lines 1..100 (start_idx 0)
    # Chunk 1: lines 91..190 (start_idx 90)
    # Chunk 2: lines 181..250 (start_idx 180)
    assert len(chunks) == 3

    assert chunks[0]["chunk_index"] == 0
    assert chunks[0]["start_line"] == 1
    assert chunks[0]["end_line"] == 100

    assert chunks[1]["chunk_index"] == 1
    assert chunks[1]["start_line"] == 91
    assert chunks[1]["end_line"] == 190

    assert chunks[2]["chunk_index"] == 2
    assert chunks[2]["start_line"] == 181
    assert chunks[2]["end_line"] == 250


def test_code_chunk_model_and_relationship(db_session):
    """Test 1, 2, 3: Model creation, relationships, and foreign key cascade deletion."""
    repo = Repository(
        name="Test Repo",
        full_name="testowner/testrepo",
        github_url="https://github.com/testowner/testrepo",
    )
    db_session.add(repo)
    db_session.commit()

    file_rec = RepositoryFile(
        repository_id=repo.id,
        path="src/index.js",
        name="index.js",
        extension=".js",
        size=120,
        file_type="source",
        content="console.log('hello');",
    )
    db_session.add(file_rec)
    db_session.commit()

    chunk = CodeChunk(
        repository_file_id=file_rec.id,
        chunk_index=0,
        start_line=1,
        end_line=1,
        content="console.log('hello');",
    )
    db_session.add(chunk)
    db_session.commit()

    # Relationship verification
    assert chunk in file_rec.chunks
    assert chunk.repository_file.path == "src/index.js"

    # Cascading deletion verification
    db_session.delete(file_rec)
    db_session.commit()

    assert db_session.query(CodeChunk).filter(CodeChunk.id == chunk.id).first() is None


def test_idempotent_chunk_generation(db_session):
    """Test 10: Re-running chunk generation replaces existing chunks without creating duplicates."""
    repo = Repository(
        name="Idempotency Repo",
        full_name="testowner/idempotent",
        github_url="https://github.com/testowner/idempotent",
    )
    db_session.add(repo)
    db_session.commit()

    content = "\n".join([f"line {i}" for i in range(1, 150)])
    file_rec = RepositoryFile(
        repository_id=repo.id,
        path="src/App.tsx",
        name="App.tsx",
        extension=".tsx",
        size=len(content),
        file_type="source",
        content=content,
    )
    db_session.add(file_rec)
    db_session.commit()

    # First run
    res1 = chunking_service.generate_chunks_for_file(db_session, file_rec)
    first_count = len(res1)
    assert first_count == 2  # 150 lines -> 2 chunks

    # Second run
    res2 = chunking_service.generate_chunks_for_file(db_session, file_rec)
    assert len(res2) == 2

    # Total in DB should still be 2
    total_db_chunks = db_session.query(CodeChunk).filter(CodeChunk.repository_file_id == file_rec.id).count()
    assert total_db_chunks == 2


def test_api_generate_repository_chunks(client, db_session):
    """Test 11: POST /api/repositories/{id}/chunks/generate generates chunks for all repo files."""
    repo = Repository(
        name="API Repo",
        full_name="testowner/apirepo",
        github_url="https://github.com/testowner/apirepo",
    )
    db_session.add(repo)
    db_session.commit()

    file1 = RepositoryFile(
        repository_id=repo.id,
        path="README.md",
        name="README.md",
        extension=".md",
        size=50,
        file_type="documentation",
        content="# Hello World\nWelcome to RepoPilot.",
    )
    file2 = RepositoryFile(
        repository_id=repo.id,
        path="src/main.py",
        name="main.py",
        extension=".py",
        size=20,
        file_type="source",
        content="print('ok')",
    )
    db_session.add_all([file1, file2])
    db_session.commit()

    response = client.post(f"/api/repositories/{repo.id}/chunks/generate")
    assert response.status_code == 200
    data = response.json()
    assert data["repository_id"] == str(repo.id)
    assert data["files_processed"] == 2
    assert data["chunks_created"] == 2


def test_api_generate_single_file_chunks(client, db_session):
    """Test 15: POST /api/repositories/{id}/files/{file_id}/chunks/generate."""
    repo = Repository(
        name="Single File Repo",
        full_name="testowner/singlefilerepo",
        github_url="https://github.com/testowner/singlefilerepo",
    )
    db_session.add(repo)
    db_session.commit()

    file_rec = RepositoryFile(
        repository_id=repo.id,
        path="src/utils.py",
        name="utils.py",
        extension=".py",
        size=10,
        file_type="source",
        content="def add(a, b):\n    return a + b",
    )
    db_session.add(file_rec)
    db_session.commit()

    response = client.post(f"/api/repositories/{repo.id}/files/{file_rec.id}/chunks/generate")
    assert response.status_code == 200
    data = response.json()
    assert data["repository_id"] == str(repo.id)
    assert data["files_processed"] == 1
    assert data["chunks_created"] == 1


def test_api_chunk_retrieval(client, db_session):
    """Test 14: List chunks & get single chunk detail."""
    repo = Repository(
        name="Retrieval Repo",
        full_name="testowner/retrievalrepo",
        github_url="https://github.com/testowner/retrievalrepo",
    )
    db_session.add(repo)
    db_session.commit()

    file_rec = RepositoryFile(
        repository_id=repo.id,
        path="src/server.ts",
        name="server.ts",
        extension=".ts",
        size=100,
        file_type="source",
        content="import express from 'express';\nconst app = express();",
    )
    db_session.add(file_rec)
    db_session.commit()

    # Generate chunks first
    chunking_service.generate_chunks_for_file(db_session, file_rec)

    # 1. List chunks
    list_res = client.get(f"/api/repositories/{repo.id}/chunks")
    assert list_res.status_code == 200
    list_data = list_res.json()
    assert list_data["total_chunks"] == 1
    chunk_meta = list_data["chunks"][0]
    assert chunk_meta["file_path"] == "src/server.ts"
    assert chunk_meta["start_line"] == 1
    assert chunk_meta["end_line"] == 2
    assert "content" not in chunk_meta  # List view excludes content

    # 2. Get single chunk detail
    chunk_id = chunk_meta["id"]
    detail_res = client.get(f"/api/repositories/{repo.id}/chunks/{chunk_id}")
    assert detail_res.status_code == 200
    detail_data = detail_res.json()
    assert detail_data["id"] == chunk_id
    assert detail_data["content"] == "import express from 'express';\nconst app = express();"


def test_api_invalid_repository_404(client):
    """Test 12: Non-existent repository returns 404."""
    fake_id = uuid.uuid4()
    assert client.post(f"/api/repositories/{fake_id}/chunks/generate").status_code == 404
    assert client.get(f"/api/repositories/{fake_id}/chunks").status_code == 404
    assert client.get(f"/api/repositories/{fake_id}/chunks/{fake_id}").status_code == 404


def test_api_invalid_file_repository_mismatch_404(client, db_session):
    """Test 13: Mismatched file and repository IDs return 404."""
    repo1 = Repository(name="Repo 1", full_name="owner/repo1", github_url="https://github.com/owner/repo1")
    repo2 = Repository(name="Repo 2", full_name="owner/repo2", github_url="https://github.com/owner/repo2")
    db_session.add_all([repo1, repo2])
    db_session.commit()

    file_in_repo1 = RepositoryFile(
        repository_id=repo1.id,
        path="file1.txt",
        name="file1.txt",
        extension=".txt",
        size=10,
        file_type="documentation",
        content="hello",
    )
    db_session.add(file_in_repo1)
    db_session.commit()

    # Attempting to generate chunk for repo1's file using repo2's ID
    res = client.post(f"/api/repositories/{repo2.id}/files/{file_in_repo1.id}/chunks/generate")
    assert res.status_code == 404
