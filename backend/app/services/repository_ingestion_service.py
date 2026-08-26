"""
Repository Ingestion Service — File discovery, extension filtering, and content ingestion logic.

RESPONSIBILITIES:
  - Recursively traverse repository directory structures
  - Filter out ignored directories (.git, node_modules, build, etc.)
  - Filter out binary/media files (.png, .zip, .pdf, etc.)
  - Identify supported source code and documentation files
  - Enforce safety thresholds (max file limits, depth limits)
  - Generate structured ingestion metrics (files_discovered, source_files, ignored_files)

This service operates in-memory and does NOT persist giant code blobs into PostgreSQL.
"""

from typing import Any
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
}

MAX_FILES_LIMIT = 200
MAX_DEPTH_LIMIT = 5


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
    Classify a file as 'source', 'ignored', or 'other'.
    """
    ext = get_file_extension(file_path)

    if ext in IGNORED_EXTENSIONS:
        return "ignored"
    elif ext in SUPPORTED_EXTENSIONS:
        return "source"
    else:
        return "ignored"


def ingest_repository_contents(
    owner: str,
    repo: str,
    path: str = "",
    depth: int = 0,
    discovered_counter: list[int] | None = None,
) -> dict[str, Any]:
    """
    Recursively discover repository files up to MAX_FILES_LIMIT and MAX_DEPTH_LIMIT.

    Returns structured summary:
    {
        "repository": "owner/repo",
        "files_discovered": int,
        "source_files": int,
        "ignored_files": int,
        "file_paths": list[str]
    }
    """
    if discovered_counter is None:
        discovered_counter = [0]  # mutable counter shared across recursive calls

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
            # If path fails or is inaccessible, skip gracefully
            return

        if not isinstance(items, list):
            # Single file item
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
        "file_paths": source_files[:20],  # Return top 20 source file paths as sample
    }
