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

import logging
from datetime import datetime, timezone
from typing import Any
import uuid

from sqlalchemy.orm import Session

from app.models.repository import Repository
from app.models.repository_file import RepositoryFile
from app.services import github_service

logger = logging.getLogger("repopilot.ingestion")

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

        items = github_service.fetch_repository_contents(owner, repo, current_path)

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

    Stale file deletion happens ONLY if discovery completes successfully without truncation.
    If GitHub API requests fail (e.g. rate limit / network error / timeout), the process
    aborts, raising ValueError, marks repository sync_status as 'failed', and existing
    database records remain untouched.
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
    was_truncated = False

    def _traverse(current_path: str, current_depth: int):
        nonlocal total_discovered, files_skipped, was_truncated

        if current_depth > MAX_DEPTH_LIMIT:
            was_truncated = True
            return

        if discovered_counter[0] >= max_files:
            was_truncated = True
            return

        # Fetch contents from GitHub.
        # Do NOT catch ValueError here — let rate limits, timeouts, and API errors
        # propagate up to abort the transaction and keep DB records safe.
        items = github_service.fetch_repository_contents(owner, repo, current_path)

        if not isinstance(items, list):
            items = [items]

        for item in items:
            if discovered_counter[0] >= max_files:
                was_truncated = True
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

                # Fetch text content. If an API/network/rate-limit error occurs,
                # fetch_file_content raises ValueError, which aborts traversal
                # immediately, protecting existing database files from deletion.
                content = github_service.fetch_file_content(owner, repo, item_path)
                if content is None and size > 0:
                    # Content could not be decoded or fetched for a file with size > 0.
                    # A failed file fetch must never be treated as a deleted file.
                    raise ValueError(f"Failed to fetch or decode content for file '{item_path}'.")

                file_category = get_file_category(ext)
                discovered_files.append({
                    "path": item_path,
                    "name": item_name,
                    "extension": ext,
                    "size": size,
                    "file_type": file_category,
                    "content": content or "",
                })

    try:
        # Step 0: Set repository status to syncing
        repository.sync_status = "syncing"
        repository.sync_error = None
        db.commit()

        # Step 1: Run GitHub Discovery
        _traverse("", 0)

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

        # Step 2: Remove stale files ONLY because discovery completed completely without truncation
        if not was_truncated:
            for record in existing_records:
                if record.path not in discovered_paths:
                    db.delete(record)
        else:
            logger.warning(
                "Discovery for repo '%s' was truncated (depth or max_files); skipping stale file deletion.",
                repository.full_name,
            )

        # Step 3: Update sync status to synced
        repository.sync_status = "synced"
        repository.last_synced_at = datetime.now(timezone.utc)
        repository.sync_error = None
        db.commit()

    except Exception as error:
        try:
            db.rollback()
            repository.sync_status = "failed"
            repository.sync_error = str(error)
            db.commit()
        except Exception as db_err:
            logger.error("Failed to update repository sync status on failure: %s", db_err)
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


def sync_repository_changes(
    db: Session,
    repository: Repository,
    added_paths: list[str],
    modified_paths: list[str],
    deleted_paths: list[str],
    commit_sha: str | None = None,
) -> dict[str, Any]:
    """
    Incrementally synchronize repository changes (added, modified, deleted files).

    This function processes deletions first, then modifications, then additions.
    It fetches content from GitHub for additions/modifications using github_service.
    If GitHub API requests fail, the operation aborts, preserving existing indexed data.
    """
    from datetime import datetime, timezone
    import logging
    from app.services import chunking_service, embedding_service

    logger = logging.getLogger("repopilot.sync")
    repo_name_log = repository.full_name
    logger.info(
        "Starting incremental sync for repo %s (owner/repo: %s). Additions: %d, Modifications: %d, Deletions: %d",
        repository.id, repo_name_log, len(added_paths), len(modified_paths), len(deleted_paths)
    )

    owner, repo = github_service.parse_github_url(repository.github_url)

    files_added_successfully: list[str] = []
    files_modified_successfully: list[str] = []
    files_deleted_successfully: list[str] = []
    files_skipped: list[str] = []

    # Make copies of the input lists so we can modify them if needed
    added_paths_copy = list(added_paths)
    modified_paths_copy = list(modified_paths)
    deleted_paths_copy = list(deleted_paths)

    try:
        # Step 1: Update repository status to 'syncing'
        repository.sync_status = "syncing"
        repository.sync_error = None
        db.commit()

        # Wrap files updates in a savepoint to support atomic rollback of changes on error
        with db.begin_nested():
            # Step 2: Process deletions
            for path in deleted_paths_copy:
                path_clean = path.strip("/")
                file_rec = (
                    db.query(RepositoryFile)
                    .filter(
                        RepositoryFile.repository_id == repository.id,
                        RepositoryFile.path == path_clean,
                    )
                    .first()
                )
                if file_rec:
                    db.delete(file_rec)
                    files_deleted_successfully.append(path_clean)
                    logger.info("Deleted indexed file record: %s", path_clean)
                else:
                    files_skipped.append(path_clean)
                    logger.warning("File requested for deletion not found in index: %s", path_clean)

            # Step 3: Process modifications
            for path in modified_paths_copy:
                path_clean = path.strip("/")
                file_rec = (
                    db.query(RepositoryFile)
                    .filter(
                        RepositoryFile.repository_id == repository.id,
                        RepositoryFile.path == path_clean,
                    )
                    .first()
                )

                # If not found in database, we treat it as an addition
                if not file_rec:
                    if path_clean not in added_paths_copy:
                        added_paths_copy.append(path_clean)
                    continue

                # Check extension
                ext = get_file_extension(path_clean)
                if ext not in SUPPORTED_EXTENSIONS:
                    db.delete(file_rec)
                    files_deleted_successfully.append(path_clean)
                    files_skipped.append(path_clean)
                    logger.info("Removed previously indexed file %s because its extension is now unsupported", path_clean)
                    continue

                # Fetch content
                content = github_service.fetch_file_content(owner, repo, path_clean)
                if content is None:
                    db.delete(file_rec)
                    files_deleted_successfully.append(path_clean)
                    files_skipped.append(path_clean)
                    logger.warning("Failed to fetch modified file content or file binary: %s. Removed index.", path_clean)
                    continue

                size = len(content.encode("utf-8"))
                if size > MAX_FILE_SIZE_BYTES:
                    db.delete(file_rec)
                    files_deleted_successfully.append(path_clean)
                    files_skipped.append(path_clean)
                    logger.warning("Modified file %s is oversized (%d bytes). Removed index.", path_clean, size)
                    continue

                # Update file record
                file_rec.size = size
                file_rec.content = content
                file_rec.file_type = get_file_category(ext)
                db.flush()

                # Re-generate chunks
                chunking_service.generate_chunks_for_file(db, file_rec)

                # Re-generate embeddings
                embedding_service.generate_embeddings_for_file(db, file_rec)

                files_modified_successfully.append(path_clean)
                logger.info("Successfully synchronized modified file: %s", path_clean)

            # Step 4: Process additions
            for path in added_paths_copy:
                path_clean = path.strip("/")
                
                file_rec = (
                    db.query(RepositoryFile)
                    .filter(
                        RepositoryFile.repository_id == repository.id,
                        RepositoryFile.path == path_clean,
                    )
                    .first()
                )

                # Check extension
                ext = get_file_extension(path_clean)
                if ext not in SUPPORTED_EXTENSIONS:
                    files_skipped.append(path_clean)
                    logger.info("Skipped added file %s due to unsupported extension", path_clean)
                    continue

                # Fetch content
                content = github_service.fetch_file_content(owner, repo, path_clean)
                if content is None:
                    files_skipped.append(path_clean)
                    logger.warning("Skipped added file %s because content fetch failed or file is binary", path_clean)
                    continue

                size = len(content.encode("utf-8"))
                if size > MAX_FILE_SIZE_BYTES:
                    files_skipped.append(path_clean)
                    logger.warning("Skipped added file %s because it is oversized (%d bytes)", path_clean, size)
                    continue

                if file_rec:
                    # Update existing record
                    file_rec.size = size
                    file_rec.content = content
                    file_rec.file_type = get_file_category(ext)
                    db.flush()
                    chunking_service.generate_chunks_for_file(db, file_rec)
                    embedding_service.generate_embeddings_for_file(db, file_rec)
                    files_modified_successfully.append(path_clean)
                    logger.info("Treated added file %s as modification because record already exists", path_clean)
                else:
                    # Create new record
                    file_rec = RepositoryFile(
                        repository_id=repository.id,
                        path=path_clean,
                        name=path_clean.split("/")[-1],
                        extension=ext,
                        size=size,
                        file_type=get_file_category(ext),
                        content=content,
                    )
                    db.add(file_rec)
                    db.flush()
                    
                    # Generate chunks
                    chunking_service.generate_chunks_for_file(db, file_rec)
                    
                    # Generate embeddings
                    embedding_service.generate_embeddings_for_file(db, file_rec)
                    
                    files_added_successfully.append(path_clean)
                    logger.info("Successfully synchronized added file: %s", path_clean)

        # Step 5: Update sync status to successful
        repository.sync_status = "synced"
        repository.last_synced_at = datetime.now(timezone.utc)
        if commit_sha:
            repository.last_commit_sha = commit_sha
        repository.sync_error = None
        db.commit()

        logger.info("Successfully completed incremental sync for repo %s", repo_name_log)

    except Exception as error:
        # Ensure we set status to failed and store the error message
        try:
            db.query(Repository).filter(Repository.id == repository.id).update({
                "sync_status": "failed",
                "sync_error": str(error)
            })
            db.commit()
        except Exception as db_err:
            logger.error("Failed to write sync error status to database: %s", db_err)
        
        logger.error("Incremental sync failed for repo %s: %s", repo_name_log, error)
        raise

    return {
        "repository_id": repository.id,
        "repository": repository.full_name,
        "sync_status": repository.sync_status,
        "files_added": files_added_successfully,
        "files_modified": files_modified_successfully,
        "files_deleted": files_deleted_successfully,
        "files_skipped": files_skipped,
    }

