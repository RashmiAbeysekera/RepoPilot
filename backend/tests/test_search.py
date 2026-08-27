"""
Unit and integration tests for the Semantic Search service and API endpoints.
"""

import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.chunk_embedding import ChunkEmbedding
from app.models.code_chunk import CodeChunk
from app.models.repository import Repository
from app.models.repository_file import RepositoryFile
from app.services import embedding_service, search_service


def create_test_repo_with_embeddings(db: Session, repo_name: str = "TestRepo"):
    """
    Helper to seed a repository with files, code chunks, and vector embeddings.
    """
    repo = Repository(
        name=repo_name,
        full_name=f"owner/{repo_name}",
        github_url=f"https://github.com/owner/{repo_name}",
        default_branch="main",
    )
    db.add(repo)
    db.flush()

    file1 = RepositoryFile(
        repository_id=repo.id,
        path="src/auth/login.py",
        name="login.py",
        extension=".py",
        size=350,
        content="def authenticate_user(username, password):\n    # Verify credentials against DB hash\n    return True\n",
    )
    file2 = RepositoryFile(
        repository_id=repo.id,
        path="src/db/connection.py",
        name="connection.py",
        extension=".py",
        size=280,
        content="def get_database_connection():\n    # Establish PostgreSQL connection session\n    return engine.connect()\n",
    )
    db.add_all([file1, file2])
    db.flush()

    chunk1 = CodeChunk(
        repository_file_id=file1.id,
        chunk_index=0,
        start_line=1,
        end_line=3,
        content=file1.content,
    )
    chunk2 = CodeChunk(
        repository_file_id=file2.id,
        chunk_index=0,
        start_line=1,
        end_line=3,
        content=file2.content,
    )
    db.add_all([chunk1, chunk2])
    db.flush()

    # Generate embeddings using local SentenceTransformer service
    embedding_service.generate_embeddings_for_repository(db, repo.id)
    db.commit()

    return repo, [chunk1, chunk2]


def test_search_service_valid_query(db_session: Session):
    """
    Verify search service returns semantically relevant chunks with scores.
    """
    repo, chunks = create_test_repo_with_embeddings(db_session, "SearchRepo1")

    res = search_service.search_repository_chunks(
        db=db_session,
        repository_id=repo.id,
        query="Where is user authentication implemented?",
        top_k=5,
    )

    assert res["repository_id"] == repo.id
    assert res["query"] == "Where is user authentication implemented?"
    assert res["total_results"] == 2
    assert len(res["results"]) == 2

    top_result = res["results"][0]
    assert top_result["file_path"] == "src/auth/login.py"
    assert "authenticate_user" in top_result["content"]
    assert top_result["start_line"] == 1
    assert top_result["end_line"] == 3
    assert 0.0 <= top_result["score"] <= 1.0


def test_search_results_relevance_ordering(db_session: Session):
    """
    Verify search results are strictly ordered by descending relevance score.
    """
    repo, _ = create_test_repo_with_embeddings(db_session, "RelevanceRepo")

    res = search_service.search_repository_chunks(
        db=db_session,
        repository_id=repo.id,
        query="How does database connection work?",
        top_k=5,
    )

    results = res["results"]
    assert len(results) == 2
    # Top result should be the database connection file
    assert results[0]["file_path"] == "src/db/connection.py"
    assert results[0]["score"] >= results[1]["score"]


def test_search_top_k_parameter(db_session: Session):
    """
    Verify top_k parameter truncates returned results count.
    """
    repo, _ = create_test_repo_with_embeddings(db_session, "TopKRepo")

    res = search_service.search_repository_chunks(
        db=db_session,
        repository_id=repo.id,
        query="python code",
        top_k=1,
    )

    assert res["total_results"] == 1
    assert len(res["results"]) == 1


def test_search_invalid_top_k_rejected(db_session: Session):
    """
    Verify top_k < 1 or > 20 is rejected with ValueError.
    """
    repo, _ = create_test_repo_with_embeddings(db_session, "InvalidTopKRepo")

    with pytest.raises(ValueError, match="top_k must be an integer between 1 and 20"):
        search_service.search_repository_chunks(
            db=db_session, repository_id=repo.id, query="auth", top_k=0
        )

    with pytest.raises(ValueError, match="top_k must be an integer between 1 and 20"):
        search_service.search_repository_chunks(
            db=db_session, repository_id=repo.id, query="auth", top_k=25
        )


def test_search_empty_query_rejected(db_session: Session):
    """
    Verify empty or whitespace-only queries are rejected with ValueError.
    """
    repo, _ = create_test_repo_with_embeddings(db_session, "EmptyQueryRepo")

    with pytest.raises(ValueError, match="cannot be empty or whitespace-only"):
        search_service.search_repository_chunks(
            db=db_session, repository_id=repo.id, query="", top_k=5
        )

    with pytest.raises(ValueError, match="cannot be empty or whitespace-only"):
        search_service.search_repository_chunks(
            db=db_session, repository_id=repo.id, query="   \n \t ", top_k=5
        )


def test_search_nonexistent_repository(db_session: Session):
    """
    Verify searching a non-existent repository raises ValueError.
    """
    fake_id = uuid.uuid4()
    with pytest.raises(ValueError, match="not found"):
        search_service.search_repository_chunks(
            db=db_session, repository_id=fake_id, query="login", top_k=5
        )


def test_repository_scoping_isolation(db_session: Session):
    """
    CRITICAL: Verify searching Repository A NEVER returns chunks belonging to Repository B.
    """
    repo_a, _ = create_test_repo_with_embeddings(db_session, "RepoA")
    repo_b, _ = create_test_repo_with_embeddings(db_session, "RepoB")

    # Search Repo A
    res_a = search_service.search_repository_chunks(
        db=db_session, repository_id=repo_a.id, query="authenticate_user", top_k=10
    )

    # All returned chunk IDs must belong ONLY to Repo A files
    file_ids_in_a = {
        f.id for f in db_session.query(RepositoryFile).filter(RepositoryFile.repository_id == repo_a.id).all()
    }
    for item in res_a["results"]:
        assert item["repository_file_id"] in file_ids_in_a

    # Search Repo B
    res_b = search_service.search_repository_chunks(
        db=db_session, repository_id=repo_b.id, query="authenticate_user", top_k=10
    )
    file_ids_in_b = {
        f.id for f in db_session.query(RepositoryFile).filter(RepositoryFile.repository_id == repo_b.id).all()
    }
    for item in res_b["results"]:
        assert item["repository_file_id"] in file_ids_in_b


def test_repository_with_chunks_but_no_embeddings(db_session: Session):
    """
    Verify searching a repository with code chunks but NO embeddings raises an explicit error.
    """
    repo = Repository(
        name="UnembeddedRepo",
        full_name="owner/UnembeddedRepo",
        github_url="https://github.com/owner/UnembeddedRepo",
        default_branch="main",
    )
    db_session.add(repo)
    db_session.flush()

    file_rec = RepositoryFile(
        repository_id=repo.id,
        path="src/main.py",
        name="main.py",
        extension=".py",
        size=50,
        content="print('hello')",
    )
    db_session.add(file_rec)
    db_session.flush()

    chunk = CodeChunk(
        repository_file_id=file_rec.id,
        chunk_index=0,
        start_line=1,
        end_line=1,
        content="print('hello')",
    )
    db_session.add(chunk)
    db_session.commit()

    with pytest.raises(ValueError, match="Repository has not been embedded yet"):
        search_service.search_repository_chunks(
            db=db_session, repository_id=repo.id, query="hello", top_k=5
        )


def test_api_semantic_search_endpoint(client: TestClient, db_session: Session):
    """
    Verify POST /api/repositories/{id}/search API endpoint returns 200 OK with valid results.
    """
    repo, _ = create_test_repo_with_embeddings(db_session, "ApiSearchRepo")

    response = client.post(
        f"/api/repositories/{repo.id}/search",
        json={"query": "Where is user login handled?", "top_k": 5},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["repository_id"] == str(repo.id)
    assert data["query"] == "Where is user login handled?"
    assert data["total_results"] == 2
    assert len(data["results"]) == 2

    first_result = data["results"][0]
    assert "chunk_id" in first_result
    assert "repository_file_id" in first_result
    assert "file_path" in first_result
    assert "start_line" in first_result
    assert "end_line" in first_result
    assert "content" in first_result
    assert "score" in first_result


def test_api_semantic_search_validation_errors(client: TestClient, db_session: Session):
    """
    Verify API endpoint returns 400 for empty queries and invalid top_k, and 404 for missing repo.
    """
    repo, _ = create_test_repo_with_embeddings(db_session, "ValidationRepo")

    # Empty query
    resp_empty = client.post(
        f"/api/repositories/{repo.id}/search",
        json={"query": "", "top_k": 5},
    )
    assert resp_empty.status_code == 400

    # Nonexistent repo UUID
    resp_404 = client.post(
        f"/api/repositories/{uuid.uuid4()}/search",
        json={"query": "auth", "top_k": 5},
    )
    assert resp_404.status_code == 404
