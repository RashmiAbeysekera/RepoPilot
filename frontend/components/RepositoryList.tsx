"use client";

import { useState, useEffect, useCallback } from "react";
import { listRepositories, deleteRepository, type Repository } from "@/lib/api";

interface RepositoryListProps {
  /**
   * Increment this counter to trigger a reload of the repository list.
   * The parent bumps it whenever a new repository is added.
   */
  refreshTrigger: number;
}

/**
 * Displays the list of saved repositories and allows deleting them.
 *
 * Uses a refreshTrigger prop instead of managing its own "add" state —
 * keeping concerns separated: this component is only responsible for
 * displaying and deleting, not creating.
 */
export default function RepositoryList({ refreshTrigger }: RepositoryListProps) {
  const [repositories, setRepositories] = useState<Repository[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  const loadRepositories = useCallback(async () => {
    setIsLoading(true);
    setLoadError(null);
    const result = await listRepositories();
    setIsLoading(false);

    if (result.ok) {
      setRepositories(result.data);
    } else {
      setLoadError(result.error);
    }
  }, []);

  // Reload whenever the parent signals that a new repository was added
  useEffect(() => {
    loadRepositories();
  }, [loadRepositories, refreshTrigger]);

  async function handleDelete(repo: Repository) {
    setDeletingId(repo.id);
    setDeleteError(null);
    const result = await deleteRepository(repo.id);
    setDeletingId(null);

    if (result.ok) {
      // Optimistically remove from local state — no need to refetch
      setRepositories((prev) => prev.filter((r) => r.id !== repo.id));
    } else {
      setDeleteError(result.error);
    }
  }

  return (
    <div className="repopilot-card">
      <h2 className="card-title">Repositories</h2>

      {isLoading && (
        <p className="list-empty-message">Loading repositories...</p>
      )}

      {loadError && (
        <p className="feedback-error" role="alert">{loadError}</p>
      )}

      {deleteError && (
        <p className="feedback-error" role="alert">{deleteError}</p>
      )}

      {!isLoading && !loadError && repositories.length === 0 && (
        <p className="list-empty-message">
          No repositories yet. Add one above to get started.
        </p>
      )}

      {repositories.length > 0 && (
        <ul className="repo-list">
          {repositories.map((repo) => (
            <li key={repo.id} className="repo-item">
              <div className="repo-info">
                <p className="repo-name">{repo.name}</p>
                <p className="repo-full-name">
                  {/* Extract "owner/repo" for display */}
                  {repo.full_name}
                </p>
                {repo.description && (
                  <p className="repo-description">{repo.description}</p>
                )}
              </div>

              <div className="repo-actions">
                <a
                  href={repo.github_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="btn-secondary"
                  id={`open-repo-${repo.id}`}
                >
                  Open ↗
                </a>
                <button
                  id={`delete-repo-${repo.id}`}
                  onClick={() => handleDelete(repo)}
                  disabled={deletingId === repo.id}
                  className="btn-danger"
                >
                  {deletingId === repo.id ? "Deleting..." : "Delete"}
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
