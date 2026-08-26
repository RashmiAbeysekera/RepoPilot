"""
Repository service — business logic for creating, reading, and deleting repositories.

WHY A SERVICE LAYER?
  The router (api/repositories.py) handles HTTP: parsing requests, setting
  status codes, returning responses. It should not contain database queries
  or business rules — that's what this service is for.

  Separating the two means:
    - The router stays thin and readable
    - The service can be tested without HTTP at all
    - Logic can be reused across multiple endpoints or future CLI tools

TRANSACTION PATTERN:
  Every function that writes to the database follows this pattern:
    1. db.add(...)      — stages the object for insertion
    2. db.commit()      — writes it to the database permanently
    3. db.refresh(...)  — re-reads the row to get server-generated values
                          (like the UUID and timestamps set by the DB)

  If db.commit() raises an exception, SQLAlchemy automatically marks the
  session as invalid — the caller's get_db() dependency closes it cleanly.
"""

import uuid

from sqlalchemy.orm import Session

from app.models.repository import Repository
from app.schemas.repository import RepositoryCreate
from app.services import github_service


def import_repository_from_github(db: Session, github_url: str) -> Repository:
    """
    Import a public repository from GitHub.

    1. Parse owner and repo from URL.
    2. Fetch live metadata from GitHub REST API.
    3. Check for duplicates in PostgreSQL database.
    4. Save and return the populated repository.
    """
    owner, repo = github_service.parse_github_url(github_url)
    metadata = github_service.fetch_repository_metadata(owner, repo)

    # Check for existing full_name or github_url
    existing = (
        db.query(Repository)
        .filter(
            (Repository.full_name == metadata["full_name"])
            | (Repository.github_url == metadata["github_url"])
        )
        .first()
    )
    if existing:
        raise ValueError(f"Repository '{metadata['full_name']}' is already imported.")

    repository = Repository(
        name=metadata["name"],
        full_name=metadata["full_name"],
        github_url=metadata["github_url"],
        description=metadata["description"],
        default_branch=metadata["default_branch"],
    )

    db.add(repository)
    db.commit()
    db.refresh(repository)

    return repository


def _parse_github_url(github_url: str) -> tuple[str, str]:

    """
    Extract (name, full_name) from a GitHub URL.

    Example:
        "https://github.com/owner/my-repo" → ("my-repo", "owner/my-repo")

    We strip trailing slashes and .git suffixes to normalize the URL.
    """
    url = str(github_url).rstrip("/").removesuffix(".git")
    # Split by '/' and take the last two segments: owner and repo name
    parts = url.rstrip("/").split("/")
    if len(parts) < 2:
        raise ValueError(f"Cannot parse owner/repo from URL: {github_url}")
    name = parts[-1]
    full_name = f"{parts[-2]}/{parts[-1]}"
    return name, full_name


def create_repository(db: Session, data: RepositoryCreate) -> Repository:
    """
    Insert a new repository row into the database.

    Raises:
        ValueError: if a repository with the same github_url or full_name
                    already exists. The router translates this into a 400.
    """
    # Normalize the URL to a plain string (Pydantic wraps it in a URL object)
    github_url_str = str(data.github_url).rstrip("/")

    # Check for duplicates BEFORE attempting an insert.
    # This gives us a clean, readable error rather than relying on catching
    # a database IntegrityError (which is harder to interpret).
    existing = (
        db.query(Repository)
        .filter(Repository.github_url == github_url_str)
        .first()
    )
    if existing:
        raise ValueError(f"Repository '{github_url_str}' already exists.")

    name, full_name = _parse_github_url(github_url_str)

    # Also check full_name uniqueness (handles edge cases like trailing slashes)
    existing_full = (
        db.query(Repository)
        .filter(Repository.full_name == full_name)
        .first()
    )
    if existing_full:
        raise ValueError(f"Repository '{full_name}' already exists.")

    repository = Repository(
        name=name,
        full_name=full_name,
        github_url=github_url_str,
        description=data.description,
        default_branch=data.default_branch,
    )

    db.add(repository)      # Stage for insertion (not written yet)
    db.commit()             # Write to the database
    db.refresh(repository)  # Re-read to populate server-generated fields (id, timestamps)

    return repository


def list_repositories(db: Session) -> list[Repository]:
    """
    Return all repositories, ordered by creation date (newest first).
    """
    return (
        db.query(Repository)
        .order_by(Repository.created_at.desc())
        .all()
    )


def get_repository_by_id(db: Session, repository_id: uuid.UUID) -> Repository | None:
    """
    Return a single repository by its UUID primary key, or None if not found.
    """
    return db.query(Repository).filter(Repository.id == repository_id).first()


def delete_repository(db: Session, repository: Repository) -> None:
    """
    Delete a repository from the database.

    The caller is responsible for fetching the repository first
    (and returning a 404 if it doesn't exist).
    """
    db.delete(repository)
    db.commit()
