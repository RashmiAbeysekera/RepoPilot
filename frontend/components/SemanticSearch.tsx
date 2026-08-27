"use client";

import { useState } from "react";
import { searchRepository, type SearchResponse, type SearchResultItem } from "@/lib/api";

interface SemanticSearchProps {
  repositoryId: string;
  repositoryName: string;
}

const EXAMPLE_QUERIES = [
  "Where is user authentication implemented?",
  "How does the application connect to the database?",
  "Where are API requests handled?",
  "Which file manages chunking?",
  "Where is error handling implemented?",
];

export function SemanticSearch({ repositoryId, repositoryName }: SemanticSearchProps) {
  const [query, setQuery] = useState("");
  const [topK, setTopK] = useState(5);
  const [isSearching, setIsSearching] = useState(false);
  const [searchResult, setSearchResult] = useState<SearchResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [expandedChunkId, setExpandedChunkId] = useState<string | null>(null);

  async function handleSearch(e?: React.FormEvent) {
    if (e) e.preventDefault();
    if (!query.trim()) {
      setError("Please enter a natural-language search query.");
      return;
    }

    setIsSearching(true);
    setError(null);
    setSearchResult(null);

    const res = await searchRepository(repositoryId, query.trim(), topK);
    setIsSearching(false);

    if (res.ok) {
      setSearchResult(res.data);
      // Automatically expand first result if available
      if (res.data.results.length > 0) {
        setExpandedChunkId(res.data.results[0].chunk_id);
      }
    } else {
      setError(res.error);
    }
  }

  function toggleChunkExpand(chunkId: string) {
    setExpandedChunkId((prev) => (prev === chunkId ? null : chunkId));
  }

  function handleQueryPreset(preset: string) {
    setQuery(preset);
  }

  return (
    <div
      style={{
        background: "rgba(15, 23, 42, 0.75)",
        backdropFilter: "blur(12px)",
        border: "1px solid rgba(255, 255, 255, 0.1)",
        borderRadius: "12px",
        padding: "20px",
        color: "#f8fafc",
      }}
    >
      <div style={{ marginBottom: "16px" }}>
        <h3 style={{ margin: "0 0 4px 0", fontSize: "1.1rem", fontWeight: 600 }}>
          Repository Semantic Search
        </h3>
        <p style={{ margin: 0, fontSize: "0.85rem", color: "#94a3b8" }}>
          Ask natural language questions about <strong>{repositoryName}</strong> to find semantically relevant code chunks via pgvector.
        </p>
      </div>

      {/* Search Input Form */}
      <form onSubmit={handleSearch} style={{ display: "flex", gap: "10px", flexWrap: "wrap" }}>
        <div style={{ flex: 1, minWidth: "260px" }}>
          <input
            id="semantic-search-input"
            type="text"
            placeholder="e.g. Where is user authentication handled?"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            disabled={isSearching}
            className="input-field"
            style={{
              width: "100%",
              padding: "10px 14px",
              background: "rgba(30, 41, 59, 0.9)",
              border: "1px solid rgba(255, 255, 255, 0.15)",
              borderRadius: "8px",
              color: "#fff",
              fontSize: "0.9rem",
            }}
          />
        </div>

        <div style={{ width: "110px" }}>
          <select
            id="semantic-search-topk"
            value={topK}
            onChange={(e) => setTopK(Number(e.target.value))}
            disabled={isSearching}
            className="input-field"
            style={{
              width: "100%",
              padding: "10px 8px",
              background: "rgba(30, 41, 59, 0.9)",
              border: "1px solid rgba(255, 255, 255, 0.15)",
              borderRadius: "8px",
              color: "#fff",
              fontSize: "0.9rem",
              cursor: "pointer",
            }}
          >
            <option value={3}>Top 3</option>
            <option value={5}>Top 5</option>
            <option value={10}>Top 10</option>
            <option value={15}>Top 15</option>
            <option value={20}>Top 20</option>
          </select>
        </div>

        <button
          id="semantic-search-submit"
          type="submit"
          disabled={isSearching || !query.trim()}
          className="btn-primary"
          style={{
            padding: "10px 20px",
            fontWeight: 600,
            fontSize: "0.9rem",
            display: "flex",
            alignItems: "center",
            gap: "8px",
            opacity: isSearching || !query.trim() ? 0.6 : 1,
            cursor: isSearching || !query.trim() ? "not-allowed" : "pointer",
          }}
        >
          {isSearching ? "Searching..." : "🔍 Search"}
        </button>
      </form>

      {/* Suggested Query Presets */}
      <div style={{ marginTop: "12px", display: "flex", gap: "6px", flexWrap: "wrap", alignItems: "center" }}>
        <span style={{ fontSize: "0.75rem", color: "#64748b" }}>Try asking:</span>
        {EXAMPLE_QUERIES.map((preset, idx) => (
          <button
            key={idx}
            type="button"
            onClick={() => handleQueryPreset(preset)}
            style={{
              background: "rgba(255, 255, 255, 0.05)",
              border: "1px solid rgba(255, 255, 255, 0.1)",
              borderRadius: "4px",
              padding: "2px 8px",
              fontSize: "0.75rem",
              color: "#cbd5e1",
              cursor: "pointer",
              transition: "all 0.2s",
            }}
          >
            {preset}
          </button>
        ))}
      </div>

      {/* Error Banner */}
      {error && (
        <div
          style={{
            marginTop: "16px",
            padding: "12px 16px",
            background: "rgba(239, 68, 68, 0.15)",
            borderLeft: "4px solid #ef4444",
            borderRadius: "6px",
            color: "#fca5a5",
            fontSize: "0.85rem",
          }}
          role="alert"
        >
          <strong>Search Error:</strong> {error}
        </div>
      )}

      {/* Loading Skeleton Indicator */}
      {isSearching && (
        <div style={{ marginTop: "20px", textAlign: "center", padding: "30px 0" }}>
          <div
            style={{
              display: "inline-block",
              width: "28px",
              height: "28px",
              border: "3px solid rgba(255,255,255,0.1)",
              borderTopColor: "#3b82f6",
              borderRadius: "50%",
              animation: "spin 1s linear infinite",
            }}
          />
          <p style={{ margin: "10px 0 0 0", fontSize: "0.85rem", color: "#94a3b8" }}>
            Encoding query & retrieving nearest vectors...
          </p>
        </div>
      )}

      {/* Results List */}
      {!isSearching && searchResult && (
        <div style={{ marginTop: "20px" }}>
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              marginBottom: "12px",
              paddingBottom: "8px",
              borderBottom: "1px solid rgba(255, 255, 255, 0.1)",
            }}
          >
            <span style={{ fontSize: "0.85rem", color: "#94a3b8" }}>
              Results for: <em>"{searchResult.query}"</em>
            </span>
            <span
              style={{
                fontSize: "0.75rem",
                background: "rgba(59, 130, 246, 0.2)",
                color: "#93c5fd",
                padding: "3px 10px",
                borderRadius: "12px",
                fontWeight: 600,
              }}
            >
              {searchResult.total_results} {searchResult.total_results === 1 ? "match" : "matches"}
            </span>
          </div>

          {searchResult.results.length === 0 ? (
            <p style={{ fontSize: "0.85rem", color: "#94a3b8", textAlign: "center", padding: "20px 0" }}>
              No relevant code chunks found for this query.
            </p>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
              {searchResult.results.map((result: SearchResultItem, index: number) => {
                const isExpanded = expandedChunkId === result.chunk_id;
                const pctScore = (result.score * 100).toFixed(1);

                return (
                  <div
                    key={result.chunk_id}
                    style={{
                      background: "rgba(30, 41, 59, 0.6)",
                      border: "1px solid rgba(255, 255, 255, 0.08)",
                      borderRadius: "8px",
                      overflow: "hidden",
                      transition: "border-color 0.2s",
                    }}
                  >
                    {/* Header Row */}
                    <div
                      style={{
                        padding: "12px 16px",
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "center",
                        flexWrap: "wrap",
                        gap: "8px",
                        background: isExpanded ? "rgba(255, 255, 255, 0.03)" : "transparent",
                      }}
                    >
                      <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                        <span
                          style={{
                            display: "inline-flex",
                            alignItems: "center",
                            justifyContent: "center",
                            width: "24px",
                            height: "24px",
                            borderRadius: "50%",
                            background: "#3b82f6",
                            color: "#fff",
                            fontSize: "0.75rem",
                            fontWeight: 700,
                          }}
                        >
                          {index + 1}
                        </span>
                        <div>
                          <code
                            style={{
                              fontSize: "0.88rem",
                              color: "#60a5fa",
                              fontWeight: 600,
                            }}
                          >
                            {result.file_path}
                          </code>
                          <span
                            style={{
                              marginLeft: "10px",
                              fontSize: "0.75rem",
                              color: "#94a3b8",
                              background: "rgba(255, 255, 255, 0.06)",
                              padding: "2px 8px",
                              borderRadius: "4px",
                            }}
                          >
                            Lines {result.start_line}–{result.end_line}
                          </span>
                        </div>
                      </div>

                      <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
                        <span
                          style={{
                            fontSize: "0.8rem",
                            fontWeight: 600,
                            color: result.score > 0.7 ? "#34d399" : result.score > 0.5 ? "#facc15" : "#94a3b8",
                            background:
                              result.score > 0.7
                                ? "rgba(52, 211, 153, 0.12)"
                                : result.score > 0.5
                                ? "rgba(250, 204, 21, 0.12)"
                                : "rgba(255, 255, 255, 0.08)",
                            padding: "4px 10px",
                            borderRadius: "6px",
                          }}
                        >
                          Relevance: {result.score.toFixed(4)} ({pctScore}%)
                        </span>
                        <button
                          onClick={() => toggleChunkExpand(result.chunk_id)}
                          className="btn-secondary"
                          style={{
                            padding: "4px 12px",
                            fontSize: "0.78rem",
                            cursor: "pointer",
                          }}
                        >
                          {isExpanded ? "Hide Code ▲" : "Show Code ▼"}
                        </button>
                      </div>
                    </div>

                    {/* Expandable Chunk Content Viewer */}
                    {isExpanded && (
                      <div
                        style={{
                          borderTop: "1px solid rgba(255, 255, 255, 0.08)",
                          background: "#090d16",
                          padding: "14px 16px",
                        }}
                      >
                        <div
                          style={{
                            display: "flex",
                            justifyContent: "space-between",
                            alignItems: "center",
                            marginBottom: "8px",
                          }}
                        >
                          <span style={{ fontSize: "0.75rem", color: "#64748b" }}>
                            File: <code>{result.file_path}</code> (Lines {result.start_line}–{result.end_line})
                          </span>
                          <span style={{ fontSize: "0.75rem", color: "#64748b" }}>
                            Chunk Index: {result.chunk_index}
                          </span>
                        </div>

                        <pre
                          style={{
                            margin: 0,
                            padding: "12px",
                            background: "#020617",
                            border: "1px solid rgba(255, 255, 255, 0.1)",
                            borderRadius: "6px",
                            color: "#e2e8f0",
                            fontFamily: "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace",
                            fontSize: "0.82rem",
                            lineHeight: "1.45",
                            overflowX: "auto",
                            whiteSpace: "pre-wrap",
                            wordBreak: "break-word",
                          }}
                        >
                          <code>{result.content}</code>
                        </pre>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
