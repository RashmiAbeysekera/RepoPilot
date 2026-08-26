"use client";

import { useState, useEffect, useCallback } from "react";
import {
  listRepositories,
  deleteRepository,
  ingestRepository,
  type Repository,
  type IngestResult,
} from "@/lib/api";

interface RepositoryListProps {
  /**
   * Increment this counter to trigger a reload of the repository list.
   * The parent bumps it whenever a new repository is added.
   */
  refreshTrigger: number;
}

/**
 * Displays the list of saved repositories and allows deleting or analyzing them.
 */
export default function RepositoryList({ refreshTrigger }: RepositoryListProps) {
  const [repositories, setRepositories] = useState<Repository[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  // Ingestion Analysis state
  const [analyzingId, setAnalyzingId] = useState<string | null>(null);
  const [analysisResult, setAnalysisResult] = useState<IngestResult | null>(null);
  const [analysisError, setAnalysisError] = useState<string | null>(null);

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

  useEffect(() => {
    loadRepositories();
  }, [loadRepositories, refreshTrigger]);

  async function handleDelete(repo: Repository) {
    setDeletingId(repo.id);
    setDeleteError(null);
    const result = await deleteRepository(repo.id);
    setDeletingId(null);

    if (result.ok) {
      setRepositories((prev) => prev.filter((r) => r.id !== repo.id));
      if (analysisResult?.repository_id === repo.id) {
        setAnalysisResult(null);
      }
    } else {
      setDeleteError(result.error);
    }
  }

  async function handleAnalyze(repo: Repository) {
    setAnalyzingId(repo.id);
    setAnalysisError(null);
    setAnalysisResult(null);

    const result = await ingestRepository(repo.id);
    setAnalyzingId(null);

    if (result.ok) {
      setAnalysisResult(result.data);
    } else {
      setAnalysisError(result.error);
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

      {analysisError && (
        <p className="feedback-error" role="alert">{analysisError}</p>
      )}

      {!isLoading && !loadError && repositories.length === 0 && (
        <p className="list-empty-message">
          No repositories yet. Import one above to get started.
        </p>
      )}

      {repositories.length > 0 && (
        <ul className="repo-list">
          {repositories.map((repo) => (
            <li key={repo.id} className="repo-item">
              <div className="repo-info">
                <p className="repo-name">{repo.name}</p>
                <p className="repo-full-name">{repo.full_name}</p>
                {repo.description && (
                  <p className="repo-description">{repo.description}</p>
                )}
                <p className="repo-branch">Branch: <code>{repo.default_branch}</code></p>
              </div>

              <div className="repo-actions">
                <button
                  id={`analyze-repo-${repo.id}`}
                  onClick={() => handleAnalyze(repo)}
                  disabled={analyzingId === repo.id}
                  className="btn-primary"
                  style={{ marginRight: "8px" }}
                >
                  {analyzingId === repo.id ? "Analyzing..." : "Analyze Repository"}
                </button>
                <a
                  href={repo.github_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="btn-secondary"
                  id={`open-repo-${repo.id}`}
                  style={{ marginRight: "8px" }}
                >
                  GitHub ↗
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

      {analysisResult && (
        <div
          className="repopilot-card"
          style={{ marginTop: "20px", borderLeft: "4px solid #3b82f6" }}
        >
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <h3 style={{ margin: 0, fontSize: "1.1rem", fontWeight: 600 }}>
              Repository Analysis: {analysisResult.repository}
            </h3>
            <button
              onClick={() => setAnalysisResult(null)}
              className="btn-secondary"
              style={{ padding: "4px 8px", fontSize: "0.8rem" }}
            >
              Close ✕
            </button>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "12px", marginTop: "16px" }}>
            <div style={{ background: "rgba(255, 255, 255, 0.05)", padding: "12px", borderRadius: "8px", textAlign: "center" }}>
              <p style={{ margin: 0, fontSize: "0.8rem", color: "#9ca3af" }}>Discovered Files</p>
              <p style={{ margin: "4px 0 0 0", fontSize: "1.4rem", fontWeight: "bold" }}>{analysisResult.files_discovered}</p>
            </div>
            <div style={{ background: "rgba(16, 185, 129, 0.1)", padding: "12px", borderRadius: "8px", textAlign: "center" }}>
              <p style={{ margin: 0, fontSize: "0.8rem", color: "#34d399" }}>Source Files</p>
              <p style={{ margin: "4px 0 0 0", fontSize: "1.4rem", fontWeight: "bold", color: "#10b981" }}>{analysisResult.source_files}</p>
            </div>
            <div style={{ background: "rgba(239, 68, 68, 0.1)", padding: "12px", borderRadius: "8px", textAlign: "center" }}>
              <p style={{ margin: 0, fontSize: "0.8rem", color: "#f87171" }}>Ignored Files</p>
              <p style={{ margin: "4px 0 0 0", fontSize: "1.4rem", fontWeight: "bold", color: "#ef4444" }}>{analysisResult.ignored_files}</p>
            </div>
          </div>

          {analysisResult.file_paths.length > 0 && (
            <div style={{ marginTop: "16px" }}>
              <p style={{ fontSize: "0.85rem", fontWeight: 600, marginBottom: "6px" }}>Sample Discovered Source Files:</p>
              <div style={{ background: "rgba(0, 0, 0, 0.3)", padding: "10px", borderRadius: "6px", maxHeight: "150px", overflowY: "auto" }}>
                <ul style={{ margin: 0, paddingLeft: "18px", fontSize: "0.8rem", fontFamily: "monospace" }}>
                  {analysisResult.file_paths.map((filePath, idx) => (
                    <li key={idx} style={{ color: "#93c5fd" }}>{filePath}</li>
                  ))}
                </ul>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

