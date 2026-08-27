"""
Repository Ingestion Service — File discovery, extension filtering, size limits, and persistent storage.

RESPONSIBILITIES:
  - Recursively traverse repository directory structures via GitHub API
  - Filter out ignored directories (.git, node_modules, build, etc.)
  - Filter out binary/media files (.png, .zip, .pdf, etc.)
  - Classify files into source, documentation, and configuration categories
  - Enforce maximum file size limits (500 KB) and repository item caps
  - Persist discovered files as RepositoryFile rows in PostgreSQL
  - Perform idempotent upserts (insert new, update modified, delete stale ONLY on successful discovery)
"""

from typing import Any
import uuid

from sqlalchemy.orm import Session

from app.models.repository import Repository
from app.models.repository_file import RepositoryFile
from app.services import github_service

IGNORED_DIRECTORIES = {
    ".git",
    "node_modules",
    "dist",
    "build",
    "__pycache__",
    ".next",
    "coverage",
    "vendor",
    ".venv",
    "venv",
    ".idea",
    ".vscode",
}

IGNORED_EXTENSIONS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".mp4",
    ".mp3",
    ".pdf",
    ".zip",
    ".exe",
    ".ico",
    ".woff",
    ".woff2",
    ".ttf",
    ".eot",
    ".tar",
    ".gz",
    ".pyc",
}

SUPPORTED_EXTENSIONS = {
    ".py",
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".java",
    ".c",
    ".cpp",
    ".h",
    ".hpp",
    ".html",
    ".css",
    ".json",
    ".yaml",
    ".yml",
    ".md",
    ".sql",
    ".xml",
    ".sh",
    ".toml",
}

DOCUMENTATION_EXTENSIONS = {".md", ".txt", ".rst"}
CONFIGURATION_EXTENSIONS = {".json", ".yaml", ".yml", ".xml", ".toml"}

MAX_FILES_LIMIT = 200
MAX_DEPTH_LIMIT = 5
MAX_FILE_SIZE_BYTES = 500_000  # 500 KB limit per file to prevent DB bloat


def is_ignored_directory(dir_name: str) -> bool:
    """Return True if the directory should be skipped during ingestion."""
    return dir_name.lower() in IGNORED_DIRECTORIES or dir_name.startswith(".")


def get_file_extension(file_path: str) -> str:
    """Extract lowercase file extension from path."""
    if "." not in file_path:
        return ""
    return f".{file_path.split('.')[-1].lower()}"


def classify_file(file_path: str) -> str:
    """
    Classify a file as 'source' or 'ignored'.
    """
    ext = get_file_extension(file_path)
    if ext in IGNORED_EXTENSIONS:
        return "ignored"
    elif ext in SUPPORTED_EXTENSIONS:
        return "source"
    else:
        return "ignored"


def get_file_category(extension: str) -> str:
    """Determine file_type category based on extension."""
    ext = extension.lower()
    if ext in DOCUMENTATION_EXTENSIONS:
        return "documentation"
    elif ext in CONFIGURATION_EXTENSIONS:
        return "configuration"
    return "source"


def ingest_repository_contents(
    owner: str,
    repo: str,
    path: str = "",
    depth: int = 0,
    discovered_counter: list[int] | None = None,
) -> dict[str, Any]:
    """
    In-memory discovery for legacy compatibility and lightweight discovery testing.
    """
    if discovered_counter is None:
        discovered_counter = [0]

    source_files: list[str] = []
    ignored_count = 0
    total_discovered = 0

    def _traverse(current_path: str, current_depth: int):
        nonlocal ignored_count, total_discovered

        if current_depth > MAX_DEPTH_LIMIT:
            return
        if discovered_counter[0] >= MAX_FILES_LIMIT:
            return

        try:
            items = github_service.fetch_repository_contents(owner, repo, current_path)
        except ValueError:
            return

        if not isinstance(items, list):
            items = [items]

        for item in items:
            if discovered_counter[0] >= MAX_FILES_LIMIT:
                break

            item_type = item.get("type")
            item_name = item.get("name", "")
            item_path = item.get("path", "")

            if item_type == "dir":
                if not is_ignored_directory(item_name):
                    _traverse(item_path, current_depth + 1)
                else:
                    ignored_count += 1
            elif item_type == "file":
                discovered_counter[0] += 1
                total_discovered += 1

                classification = classify_file(item_name)
                if classification == "source":
                    source_files.append(item_path)
                else:
                    ignored_count += 1

    _traverse(path, depth)

    return {
        "repository": f"{owner}/{repo}",
        "files_discovered": total_discovered,
        "source_files": len(source_files),
        "ignored_files": ignored_count,
        "file_paths": source_files[:20],
    }


def ingest_and_persist_repository(
    db: Session,
    repository: Repository,
    max_files: int = MAX_FILES_LIMIT,
    max_file_size: int = MAX_FILE_SIZE_BYTES,
) -> dict[str, Any]:
    """
    Traverse repository on GitHub, fetch contents of supported text files,
    and persist/upsert RepositoryFile records cleanly into PostgreSQL.

    Stale file deletion happens ONLY if discovery completes successfully.
    If GitHub API requests fail (e.g. rate limit / network error), the process
    aborts, raising ValueError, and database records remain untouched.
    """
    owner, repo = github_service.parse_github_url(repository.github_url)

    discovered_files: list[dict[str, Any]] = []
    total_discovered = 0
    files_skipped = 0
    skip_reasons: dict[str, int] = {
        "ignored_directory": 0,
        "unsupported_extension": 0,
        "oversized": 0,
        "fetch_failed": 0,
    }

    discovered_counter = [0]
    discovery_success = False

    def _traverse(current_path: str, current_depth: int):
        nonlocal total_discovered, files_skipped

        if current_depth > MAX_DEPTH_LIMIT or discovered_counter[0] >= max_files:
            return

        # Fetch contents from GitHub.
        # Do NOT catch ValueError here — let rate limits, timeouts, and API errors
        # propagate up to abort the transaction and keep DB records safe.
        items = github_service.fetch_repository_contents(owner, repo, current_path)

        if not isinstance(items, list):
            items = [items]

        for item in items:
            if discovered_counter[0] >= max_files:
                break

            item_type = item.get("type")
            item_name = item.get("name", "")
            item_path = item.get("path", "")

            if item_type == "dir":
                if not is_ignored_directory(item_name):
                    _traverse(item_path, current_depth + 1)
                else:
                    skip_reasons["ignored_directory"] += 1
            elif item_type == "file":
                discovered_counter[0] += 1
                total_discovered += 1

                ext = get_file_extension(item_name)
                if ext not in SUPPORTED_EXTENSIONS:
                    files_skipped += 1
                    skip_reasons["unsupported_extension"] += 1
                    continue

                size = item.get("size", 0)
                if size > max_file_size:
                    files_skipped += 1
                    skip_reasons["oversized"] += 1
                    continue

                # Fetch text content
                content = github_service.fetch_file_content(owner, repo, item_path)
                if content is None and size > 0:
                    files_skipped += 1
                    skip_reasons["fetch_failed"] += 1
                    continue

                file_category = get_file_category(ext)
                discovered_files.append({
                    "path": item_path,
                    "name": item_name,
                    "extension": ext,
                    "size": size,
                    "file_type": file_category,
                    "content": content or "",
                })

    # Step 1: Run GitHub Discovery
    _traverse("", 0)
    discovery_success = True

    # Step 2: Update Database ONLY if discovery completed successfully
    if not discovery_success:
        raise ValueError("GitHub repository discovery did not complete successfully.")

    existing_records = (
        db.query(RepositoryFile)
        .filter(RepositoryFile.repository_id == repository.id)
        .all()
    )
    existing_map = {f.path: f for f in existing_records}

    stored_count = 0
    updated_count = 0
    discovered_paths: set[str] = set()

    for item in discovered_files:
        path = item["path"]
        discovered_paths.add(path)

        if path in existing_map:
            record = existing_map[path]
            record.name = item["name"]
            record.extension = item["extension"]
            record.size = item["size"]
            record.file_type = item["file_type"]
            record.content = item["content"]
            updated_count += 1
        else:
            record = RepositoryFile(
                repository_id=repository.id,
                path=item["path"],
                name=item["name"],
                extension=item["extension"],
                size=item["size"],
                file_type=item["file_type"],
                content=item["content"],
            )
            db.add(record)
            stored_count += 1

    # Remove stale files ONLY because discovery succeeded completely
    for record in existing_records:
        if record.path not in discovered_paths:
            db.delete(record)

    try:
        db.commit()
    except Exception:
        db.rollback()
        raise

    return {
        "repository_id": repository.id,
        "repository": repository.full_name,
        "default_branch": repository.default_branch,
        "files_discovered": total_discovered,
        "files_stored": stored_count,
        "files_updated": updated_count,
        "files_skipped": files_skipped,
        "skip_reasons": skip_reasons,
        "source_files": stored_count + updated_count,
        "ignored_files": files_skipped + skip_reasons["ignored_directory"],
        "file_paths": [item["path"] for item in discovered_files[:20]],
    }
