"use client";

import { useState, useEffect, useCallback } from "react";
import {
  listRepositories,
  deleteRepository,
  ingestRepository,
  listRepositoryFiles,
  getRepositoryFile,
  type Repository,
  type IngestResult,
  type RepositoryFile,
  type RepositoryFileDetail,
} from "@/lib/api";
import FileExplorer from "./FileExplorer";
import FileViewer from "./FileViewer";
import { ChunkExplorer } from "./ChunkExplorer";
import { EmbeddingManager } from "./EmbeddingManager";
import { SemanticSearch } from "./SemanticSearch";

interface RepositoryListProps {
  refreshTrigger: number;
}

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

  // File, Chunk, Embedding, and Search Explorer state
  const [activeRepoId, setActiveRepoId] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<"files" | "chunks" | "embeddings" | "search">("files");
  const [fileList, setFileList] = useState<RepositoryFile[]>([]);
  const [isFilesLoading, setIsFilesLoading] = useState(false);
  const [selectedFileDetail, setSelectedFileDetail] = useState<RepositoryFileDetail | null>(null);
  const [isFileLoading, setIsFileLoading] = useState(false);
  const [fileError, setFileError] = useState<string | null>(null);

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

  async function loadFiles(repoId: string) {
    setActiveRepoId(repoId);
    setActiveTab("files");
    setIsFilesLoading(true);
    setSelectedFileDetail(null);
    setFileError(null);

    const res = await listRepositoryFiles(repoId);
    setIsFilesLoading(false);
    if (res.ok) {
      setFileList(res.data.files);
    } else {
      setFileError(res.error);
    }
  }

  function openChunks(repoId: string) {
    setActiveRepoId(repoId);
    setActiveTab("chunks");
  }

  function openEmbeddings(repoId: string) {
    setActiveRepoId(repoId);
    setActiveTab("embeddings");
  }

  function openSearch(repoId: string) {
    setActiveRepoId(repoId);
    setActiveTab("search");
  }

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
      if (activeRepoId === repo.id) {
        setActiveRepoId(null);
        setFileList([]);
        setSelectedFileDetail(null);
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
      // Automatically load updated files into file explorer
      loadFiles(repo.id);
    } else {
      setAnalysisError(result.error);
    }
  }

  async function handleSelectFile(file: RepositoryFile) {
    if (!activeRepoId) return;
    setIsFileLoading(true);
    setFileError(null);

    const res = await getRepositoryFile(activeRepoId, file.id);
    setIsFileLoading(false);
    if (res.ok) {
      setSelectedFileDetail(res.data);
    } else {
      setFileError(res.error);
    }
  }

  return (
    <div className="repopilot-card">
      <h2 className="card-title">Repositories</h2>

      {isLoading && <p className="list-empty-message">Loading repositories...</p>}
      {loadError && <p className="feedback-error" role="alert">{loadError}</p>}
      {deleteError && <p className="feedback-error" role="alert">{deleteError}</p>}
      {analysisError && <p className="feedback-error" role="alert">{analysisError}</p>}

      {!isLoading && !loadError && repositories.length === 0 && (
        <p className="list-empty-message">
          No repositories yet. Import one above to get started.
        </p>
      )}

      {repositories.length > 0 && (
        <ul className="repo-list">
          {repositories.map((repo) => (
            <li key={repo.id} className="repo-item" style={{ flexDirection: "column", alignItems: "stretch", padding: "18px 0" }}>
              {/* Top Repository Info Bar */}
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: "12px", marginBottom: "14px" }}>
                <div className="repo-info">
                  <div style={{ display: "flex", alignItems: "center", gap: "10px", flexWrap: "wrap" }}>
                    <h3 style={{ margin: 0, fontSize: "1.1rem", fontWeight: 700, color: "#f8fafc" }}>{repo.name}</h3>
                    <span style={{ fontSize: "0.78rem", background: "rgba(255, 255, 255, 0.08)", color: "#cbd5e1", padding: "2px 8px", borderRadius: "4px", fontWeight: 500 }}>
                      {repo.full_name}
                    </span>
                    <span style={{ fontSize: "0.75rem", background: "rgba(59, 130, 246, 0.15)", color: "#93c5fd", padding: "2px 8px", borderRadius: "4px" }}>
                      Branch: <code>{repo.default_branch}</code>
                    </span>
                  </div>
                  {repo.description && <p className="repo-description" style={{ marginTop: "6px" }}>{repo.description}</p>}
                </div>

                <a
                  href={repo.github_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="btn-secondary"
                  id={`open-repo-${repo.id}`}
                  style={{ fontSize: "0.8rem", padding: "4px 10px" }}
                >
                  GitHub ↗
                </a>
              </div>

              {/* Action Toolbar Row — wraps naturally without overflowing */}
              <div className="repo-actions" style={{ display: "flex", flexWrap: "wrap", gap: "8px", alignItems: "center" }}>
                <button
                  id={`analyze-repo-${repo.id}`}
                  onClick={() => handleAnalyze(repo)}
                  disabled={analyzingId === repo.id}
                  className="btn-primary"
                  style={{ width: "auto", padding: "6px 14px", fontSize: "0.8125rem", marginTop: 0 }}
                >
                  {analyzingId === repo.id ? "Ingesting..." : "Ingest Repository"}
                </button>
                <button
                  id={`view-files-${repo.id}`}
                  onClick={() => loadFiles(repo.id)}
                  className="btn-secondary"
                >
                  {activeRepoId === repo.id && activeTab === "files" ? "Refreshing Files..." : "📁 View Files"}
                </button>
                <button
                  id={`view-chunks-${repo.id}`}
                  onClick={() => openChunks(repo.id)}
                  className="btn-secondary"
                >
                  🧩 Chunk Explorer
                </button>
                <button
                  id={`view-embeddings-${repo.id}`}
                  onClick={() => openEmbeddings(repo.id)}
                  className="btn-secondary"
                >
                  ⚡ Vector Embeddings
                </button>
                <button
                  id={`view-search-${repo.id}`}
                  onClick={() => openSearch(repo.id)}
                  className="btn-secondary"
                >
                  🔍 Semantic Search
                </button>
                <button
                  id={`delete-repo-${repo.id}`}
                  onClick={() => handleDelete(repo)}
                  disabled={deletingId === repo.id}
                  className="btn-danger"
                  style={{ marginLeft: "auto" }}
                >
                  {deletingId === repo.id ? "Deleting..." : "Delete"}
                </button>
              </div>

              {/* Ingestion Analysis Summary Card */}
              {analysisResult && analysisResult.repository_id === repo.id && (
                <div
                  style={{
                    marginTop: "16px",
                    padding: "16px",
                    background: "rgba(30, 41, 59, 0.7)",
                    borderRadius: "8px",
                    borderLeft: "4px solid #3b82f6",
                  }}
                >
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                    <h3 style={{ margin: 0, fontSize: "1rem", fontWeight: 600 }}>
                      Ingestion Summary: {analysisResult.repository}
                    </h3>
                    <button
                      onClick={() => setAnalysisResult(null)}
                      className="btn-secondary"
                      style={{ padding: "2px 6px", fontSize: "0.75rem" }}
                    >
                      Close ✕
                    </button>
                  </div>

                  <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: "10px", marginTop: "12px" }}>
                    <div style={{ background: "rgba(255, 255, 255, 0.05)", padding: "10px", borderRadius: "6px", textAlign: "center" }}>
                      <p style={{ margin: 0, fontSize: "0.75rem", color: "#9ca3af" }}>Discovered</p>
                      <p style={{ margin: "2px 0 0 0", fontSize: "1.2rem", fontWeight: "bold" }}>{analysisResult.files_discovered}</p>
                    </div>
                    <div style={{ background: "rgba(16, 185, 129, 0.1)", padding: "10px", borderRadius: "6px", textAlign: "center" }}>
                      <p style={{ margin: 0, fontSize: "0.75rem", color: "#34d399" }}>Stored (New)</p>
                      <p style={{ margin: "2px 0 0 0", fontSize: "1.2rem", fontWeight: "bold", color: "#10b981" }}>{analysisResult.files_stored ?? analysisResult.source_files}</p>
                    </div>
                    <div style={{ background: "rgba(59, 130, 246, 0.1)", padding: "10px", borderRadius: "6px", textAlign: "center" }}>
                      <p style={{ margin: 0, fontSize: "0.75rem", color: "#93c5fd" }}>Updated</p>
                      <p style={{ margin: "2px 0 0 0", fontSize: "1.2rem", fontWeight: "bold", color: "#60a5fa" }}>{analysisResult.files_updated ?? 0}</p>
                    </div>
                    <div style={{ background: "rgba(239, 68, 68, 0.1)", padding: "10px", borderRadius: "6px", textAlign: "center" }}>
                      <p style={{ margin: 0, fontSize: "0.75rem", color: "#f87171" }}>Skipped</p>
                      <p style={{ margin: "2px 0 0 0", fontSize: "1.2rem", fontWeight: "bold", color: "#ef4444" }}>{analysisResult.files_skipped ?? analysisResult.ignored_files}</p>
                    </div>
                  </div>
                </div>
              )}

              {/* Active Repository Explorer Area */}
              {activeRepoId === repo.id && (
                <div style={{ marginTop: "20px" }}>
                  {/* View Mode Tabs */}
                  <div style={{ display: "flex", gap: "8px", marginBottom: "12px" }}>
                    <button
                      onClick={() => {
                        setActiveTab("files");
                        if (fileList.length === 0) loadFiles(repo.id);
                      }}
                      className={activeTab === "files" ? "btn-primary" : "btn-secondary"}
                      style={{ fontSize: "0.8rem", padding: "6px 12px" }}
                    >
                      📁 Repository Files
                    </button>
                    <button
                      onClick={() => setActiveTab("chunks")}
                      className={activeTab === "chunks" ? "btn-primary" : "btn-secondary"}
                      style={{ fontSize: "0.8rem", padding: "6px 12px" }}
                    >
                      🧩 Code Chunks
                    </button>
                    <button
                      onClick={() => setActiveTab("embeddings")}
                      className={activeTab === "embeddings" ? "btn-primary" : "btn-secondary"}
                      style={{ fontSize: "0.8rem", padding: "6px 12px" }}
                    >
                      ⚡ Vector Embeddings
                    </button>
                    <button
                      onClick={() => setActiveTab("search")}
                      className={activeTab === "search" ? "btn-primary" : "btn-secondary"}
                      style={{ fontSize: "0.8rem", padding: "6px 12px" }}
                    >
                      🔍 Semantic Search
                    </button>
                  </div>

                  {/* Tab Content */}
                  {activeTab === "files" ? (
                    <div
                      style={{
                        display: "grid",
                        gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))",
                        gap: "16px",
                        minHeight: "350px",
                      }}
                    >
                      <FileExplorer
                        files={fileList}
                        selectedFileId={selectedFileDetail?.id ?? null}
                        onSelectFile={handleSelectFile}
                        isLoading={isFilesLoading}
                      />
                      <FileViewer
                        file={selectedFileDetail}
                        isLoading={isFileLoading}
                        error={fileError}
                        onClose={() => setSelectedFileDetail(null)}
                      />
                    </div>
                  ) : activeTab === "chunks" ? (
                    <ChunkExplorer repositoryId={repo.id} repositoryName={repo.full_name} />
                  ) : activeTab === "embeddings" ? (
                    <EmbeddingManager repositoryId={repo.id} repositoryName={repo.full_name} />
                  ) : (
                    <SemanticSearch repositoryId={repo.id} repositoryName={repo.full_name} />
                  )}
                </div>
              )}

            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
