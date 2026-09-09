"""
FastAPI router for public webhooks (e.g. GitHub integrations).
"""

import hmac
import hashlib
import logging
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.config import get_github_webhook_secret
from app.core.database import get_db
from app.models.repository import Repository
from app.services import repository_ingestion_service

logger = logging.getLogger("repopilot.webhooks")
router = APIRouter(prefix="/api/webhooks", tags=["Webhooks"])


async def verify_signature(request: Request) -> bytes:
    """
    Validate the GitHub signature header x-hub-signature-256.
    Raises HTTP 401 if validation fails.
    """
    secret = get_github_webhook_secret()
    # If GITHUB_WEBHOOK_SECRET is not set, we skip signature check in local dev.
    # But if it is set, we strictly enforce it.
    if not secret:
        logger.warning("GITHUB_WEBHOOK_SECRET is not configured. Webhook signature verification is skipped.")
        return await request.body()

    signature = request.headers.get("x-hub-signature-256")
    if not signature:
        logger.error("Missing x-hub-signature-256 header")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing GitHub signature header.",
        )

    if not signature.startswith("sha256="):
        logger.error("Signature header does not start with sha256=")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid signature header format.",
        )

    raw_body = await request.body()
    expected_hash = signature.split("sha256=")[-1]
    
    computed_hash = hmac.new(
        secret.encode("utf-8"),
        raw_body,
        hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(expected_hash, computed_hash):
        logger.error("Signature mismatch!")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Signature validation failed.",
        )

    return raw_body


@router.post(
    "/github",
    status_code=status.HTTP_200_OK,
    summary="GitHub repository webhook endpoint",
)
async def github_webhook(
    request: Request,
    raw_body: bytes = Depends(verify_signature),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Receive GitHub webhook push events, consolidate files changed across
    all commits, and run the incremental synchronization service.
    """
    # 1. Distinguish event type (we only support push event)
    github_event = request.headers.get("x-github-event")
    if github_event != "push":
        logger.info("Skipped unsupported GitHub event: %s", github_event)
        return {
            "status": "skipped",
            "message": f"Unsupported event '{github_event}'. Only 'push' is supported.",
        }

    try:
        payload = await request.json()
    except Exception as err:
        logger.error("Failed to parse JSON body: %s", err)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON payload.",
        ) from err

    # 2. Extract repository details
    repo_data = payload.get("repository", {})
    repo_full_name = repo_data.get("full_name")  # e.g. "facebook/react"
    
    if not repo_full_name:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Missing repository full_name in webhook payload.",
        )

    # 3. Map to database repository record
    repository = (
        db.query(Repository)
        .filter(Repository.full_name == repo_full_name)
        .first()
    )
    if not repository:
        logger.warning("Repository '%s' not found in database", repo_full_name)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository '{repo_full_name}' is not registered in RepoPilot.",
        )

    # 4. Verify branch ref matches default_branch
    ref = payload.get("ref", "")  # e.g. "refs/heads/main"
    expected_ref = f"refs/heads/{repository.default_branch}"
    if ref != expected_ref:
        logger.info("Skipped push ref '%s' since default branch is '%s'", ref, repository.default_branch)
        return {
            "status": "skipped",
            "message": f"Push event on ref '{ref}' does not match default branch '{repository.default_branch}'.",
        }

    # 5. Extract files from commits
    commits = payload.get("commits", [])
    added_files: set[str] = set()
    modified_files: set[str] = set()
    removed_files: set[str] = set()

    for commit in commits:
        added_files.update(commit.get("added", []))
        modified_files.update(commit.get("modified", []))
        removed_files.update(commit.get("removed", []))

    # Resolve overlapping changes:
    # - Deletions take precedence.
    # - If added and then modified, it's added.
    # - If modified and then removed, it's removed.
    resolved_removed = list(removed_files)
    resolved_added = list(added_files - removed_files)
    resolved_modified = list(modified_files - added_files - removed_files)

    commit_sha = payload.get("after")  # The head commit SHA after the push

    # 6. Execute sync
    try:
        result = repository_ingestion_service.sync_repository_changes(
            db=db,
            repository=repository,
            added_paths=resolved_added,
            modified_paths=resolved_modified,
            deleted_paths=resolved_removed,
            commit_sha=commit_sha,
        )
    except Exception as error:
        logger.exception("Synchronization error: %s", error)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Incremental sync failed: {error}",
        ) from error

    return result
