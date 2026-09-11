"use client";

import { useState } from "react";
import {
  askRepositoryQuestion,
  type AgentTraceStep,
  type RAGAnswerResponse,
  type RAGFileSource,
  type RAGSourceReference,
} from "@/lib/api";

interface AskRepoPilotProps {
  repositoryId: string;
  repositoryName: string;
}

const SAMPLE_QUESTIONS = [
  "Where is authentication implemented?",
  "How does the application connect to PostgreSQL?",
  "Where are API requests handled?",
  "How does user registration work?",
  "Where is error handling implemented?",
];

export function AskRepoPilot({ repositoryId, repositoryName }: AskRepoPilotProps) {
  const [query, setQuery] = useState("");
  const [topK, setTopK] = useState(5);
  const [useAgent, setUseAgent] = useState(true);
  const [isLoading, setIsLoading] = useState(false);
  const [ragResult, setRagResult] = useState<RAGAnswerResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<"files" | "chunks">("files");
  const [expandedFile, setExpandedFile] = useState<string | null>(null);
  const [expandedChunkId, setExpandedChunkId] = useState<string | null>(null);
  const [isTraceOpen, setIsTraceOpen] = useState(true);

  async function handleAsk(e?: React.FormEvent) {
    if (e) e.preventDefault();
    if (!query.trim()) {
      setError("Please enter a question about the repository.");
      return;
    }

    setIsLoading(true);
    setError(null);
    setRagResult(null);

    const res = await askRepositoryQuestion(repositoryId, query.trim(), topK, useAgent);
    setIsLoading(false);

    if (res.ok) {
      setRagResult(res.data);
      // Auto-expand first file source by default
      if (res.data.file_sources && res.data.file_sources.length > 0) {
        setExpandedFile(res.data.file_sources[0].file_path);
      } else if (res.data.sources && res.data.sources.length > 0) {
        setExpandedChunkId(res.data.sources[0].chunk_id);
      }
    } else {
      setError(res.error);
    }
  }

  function toggleFileExpand(filePath: string) {
    setExpandedFile((prev) => (prev === filePath ? null : filePath));
  }

  function toggleChunkExpand(chunkId: string) {
    setExpandedChunkId((prev) => (prev === chunkId ? null : chunkId));
  }

  function getToolBadge(toolName: string) {
    switch (toolName) {
      case "search_repository":
        return { label: "Semantic Search", icon: "🔍", color: "#38bdf8", bg: "rgba(56, 189, 248, 0.15)" };
      case "read_repository_file":
        return { label: "Read File", icon: "📄", color: "#4ade80", bg: "rgba(74, 222, 128, 0.15)" };
      case "find_repository_files":
        return { label: "Find Files", icon: "📁", color: "#c084fc", bg: "rgba(192, 132, 252, 0.15)" };
      case "get_repository_structure":
        return { label: "Structure Overview", icon: "🏗️", color: "#facc15", bg: "rgba(250, 204, 21, 0.15)" };
      default:
        return { label: toolName, icon: "⚙️", color: "#94a3b8", bg: "rgba(148, 163, 184, 0.15)" };
    }
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
        marginTop: "20px",
      }}
    >
      {/* Header */}
      <div style={{ marginBottom: "16px" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "4px" }}>
          <h3 style={{ margin: 0, fontSize: "1.15rem", fontWeight: 600, color: "#38bdf8" }}>
            🤖 Ask RepoPilot
          </h3>
          <span
            style={{
              fontSize: "0.72rem",
              padding: "2px 8px",
              borderRadius: "12px",
              background: useAgent ? "rgba(168, 85, 247, 0.15)" : "rgba(56, 189, 248, 0.15)",
              color: useAgent ? "#c084fc" : "#38bdf8",
              border: `1px solid ${useAgent ? "rgba(168, 85, 247, 0.3)" : "rgba(56, 189, 248, 0.3)"}`,
              fontWeight: 500,
            }}
          >
            {useAgent ? "Agentic Workflow" : "Direct RAG"}
          </span>
        </div>
        <p style={{ margin: 0, fontSize: "0.85rem", color: "#94a3b8" }}>
          Ask natural language developer questions about <strong>{repositoryName}</strong>. The intelligence agent formulates multi-step investigation plans using read-only tools to retrieve evidence and cite exact sources.
        </p>
      </div>

      {/* Preset Questions */}
      <div style={{ marginBottom: "16px" }}>
        <span style={{ fontSize: "0.75rem", color: "#64748b", display: "block", marginBottom: "6px" }}>
          Example Questions:
        </span>
        <div style={{ display: "flex", flexWrap: "wrap", gap: "6px" }}>
          {SAMPLE_QUESTIONS.map((sample, idx) => (
            <button
              key={idx}
              type="button"
              onClick={() => setQuery(sample)}
              style={{
                background: "rgba(255, 255, 255, 0.05)",
                border: "1px solid rgba(255, 255, 255, 0.1)",
                borderRadius: "16px",
                padding: "4px 10px",
                color: "#cbd5e1",
                fontSize: "0.75rem",
                cursor: "pointer",
                transition: "all 0.2s ease",
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.background = "rgba(56, 189, 248, 0.15)";
                e.currentTarget.style.borderColor = "rgba(56, 189, 248, 0.4)";
                e.currentTarget.style.color = "#38bdf8";
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = "rgba(255, 255, 255, 0.05)";
                e.currentTarget.style.borderColor = "rgba(255, 255, 255, 0.1)";
                e.currentTarget.style.color = "#cbd5e1";
              }}
            >
              {sample}
            </button>
          ))}
        </div>
      </div>

      {/* Query Form */}
      <form onSubmit={handleAsk} style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
        <div style={{ display: "flex", gap: "8px" }}>
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Ask a question about authentication, database, structure..."
            disabled={isLoading}
            style={{
              flex: 1,
              background: "rgba(15, 23, 42, 0.9)",
              border: "1px solid rgba(255, 255, 255, 0.15)",
              borderRadius: "8px",
              padding: "10px 14px",
              color: "#f8fafc",
              fontSize: "0.9rem",
              outline: "none",
            }}
          />

          <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
            <label style={{ fontSize: "0.75rem", color: "#94a3b8", whiteSpace: "nowrap" }}>
              Top-K:
            </label>
            <select
              value={topK}
              onChange={(e) => setTopK(Number(e.target.value))}
              disabled={isLoading}
              style={{
                background: "rgba(15, 23, 42, 0.9)",
                border: "1px solid rgba(255, 255, 255, 0.15)",
                borderRadius: "8px",
                padding: "10px 8px",
                color: "#f8fafc",
                fontSize: "0.85rem",
                outline: "none",
                cursor: "pointer",
              }}
            >
              {[3, 5, 7, 10].map((k) => (
                <option key={k} value={k} style={{ background: "#0f172a", color: "#f8fafc" }}>
                  {k} chunks
                </option>
              ))}
            </select>
          </div>

          {/* Agent Toggle */}
          <button
            type="button"
            onClick={() => setUseAgent((prev) => !prev)}
            style={{
              background: useAgent ? "rgba(168, 85, 247, 0.2)" : "rgba(255, 255, 255, 0.05)",
              color: useAgent ? "#c084fc" : "#94a3b8",
              border: `1px solid ${useAgent ? "rgba(168, 85, 247, 0.4)" : "rgba(255, 255, 255, 0.1)"}`,
              borderRadius: "8px",
              padding: "0 10px",
              fontSize: "0.78rem",
              fontWeight: 500,
              cursor: "pointer",
              whiteSpace: "nowrap",
            }}
            title={useAgent ? "Agentic Mode active: uses tools dynamically" : "Direct RAG: single-pass search"}
          >
            {useAgent ? "🧠 Agent Mode" : "⚡ Direct RAG"}
          </button>

          <button
            type="submit"
            disabled={isLoading || !query.trim()}
            style={{
              background: isLoading || !query.trim() ? "rgba(56, 189, 248, 0.3)" : "#0284c7",
              color: "#ffffff",
              border: "none",
              borderRadius: "8px",
              padding: "10px 18px",
              fontSize: "0.9rem",
              fontWeight: 600,
              cursor: isLoading || !query.trim() ? "not-allowed" : "pointer",
              transition: "background 0.2s ease",
              whiteSpace: "nowrap",
            }}
          >
            {isLoading ? "Investigating..." : "Ask"}
          </button>
        </div>
      </form>

      {/* Loading State */}
      {isLoading && (
        <div
          style={{
            marginTop: "16px",
            padding: "16px",
            background: "rgba(56, 189, 248, 0.05)",
            border: "1px dashed rgba(56, 189, 248, 0.3)",
            borderRadius: "8px",
            textAlign: "center",
            color: "#38bdf8",
            fontSize: "0.9rem",
          }}
        >
          <span style={{ display: "inline-block" }}>
            🧠 Agent investigating repository: formulating queries, inspecting code evidence & citing sources...
          </span>
        </div>
      )}

      {/* Error State */}
      {error && (
        <div
          style={{
            marginTop: "16px",
            padding: "12px 16px",
            background: error.toLowerCase().includes("rate limit") ? "rgba(234, 179, 8, 0.1)" : "rgba(239, 68, 68, 0.1)",
            border: `1px solid ${error.toLowerCase().includes("rate limit") ? "rgba(234, 179, 8, 0.3)" : "rgba(239, 68, 68, 0.3)"}`,
            borderRadius: "8px",
            color: error.toLowerCase().includes("rate limit") ? "#fde047" : "#fca5a5",
            fontSize: "0.85rem",
          }}
        >
          <strong>{error.toLowerCase().includes("rate limit") ? "⏳ Rate Limit:" : "Error:"}</strong> {error}
        </div>
      )}

      {/* RAG & Agent Answer Display */}
      {ragResult && (
        <div style={{ marginTop: "20px", display: "flex", flexDirection: "column", gap: "16px" }}>
          {/* Confidence / Threshold Warning */}
          {ragResult.confidence_warning && (
            <div
              style={{
                padding: "10px 14px",
                background: "rgba(234, 179, 8, 0.1)",
                border: "1px solid rgba(234, 179, 8, 0.3)",
                borderRadius: "8px",
                color: "#fde047",
                fontSize: "0.82rem",
                display: "flex",
                alignItems: "center",
                gap: "8px",
              }}
            >
              <span>⚠️</span>
              <span>{ragResult.confidence_warning}</span>
            </div>
          )}

          {/* Agent Activity Trace Section */}
          {ragResult.trace && ragResult.trace.length > 0 && (
            <div
              style={{
                background: "rgba(15, 23, 42, 0.9)",
                border: "1px solid rgba(168, 85, 247, 0.3)",
                borderRadius: "10px",
                overflow: "hidden",
              }}
            >
              <div
                onClick={() => setIsTraceOpen((prev) => !prev)}
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  padding: "10px 16px",
                  background: "rgba(168, 85, 247, 0.08)",
                  cursor: "pointer",
                  borderBottom: isTraceOpen ? "1px solid rgba(168, 85, 247, 0.2)" : "none",
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                  <span style={{ fontSize: "0.95rem" }}>🧭</span>
                  <span style={{ fontWeight: 600, color: "#c084fc", fontSize: "0.88rem" }}>
                    Investigation Activity ({ragResult.trace.length} action{ragResult.trace.length === 1 ? "" : "s"})
                  </span>
                </div>
                <span style={{ fontSize: "0.75rem", color: "#94a3b8" }}>
                  {isTraceOpen ? "▲ Hide Actions" : "▼ Show Actions"}
                </span>
              </div>

              {isTraceOpen && (
                <div style={{ padding: "12px 16px", display: "flex", flexDirection: "column", gap: "8px" }}>
                  {ragResult.trace.map((step: AgentTraceStep, sIdx: number) => {
                    const badge = getToolBadge(step.tool);
                    return (
                      <div
                        key={sIdx}
                        style={{
                          display: "flex",
                          alignItems: "flex-start",
                          gap: "10px",
                          fontSize: "0.82rem",
                          background: "rgba(255, 255, 255, 0.02)",
                          padding: "8px 12px",
                          borderRadius: "6px",
                          border: "1px solid rgba(255, 255, 255, 0.05)",
                        }}
                      >
                        <span
                          style={{
                            fontSize: "0.7rem",
                            color: badge.color,
                            background: badge.bg,
                            padding: "2px 6px",
                            borderRadius: "4px",
                            fontWeight: 600,
                            whiteSpace: "nowrap",
                            display: "flex",
                            alignItems: "center",
                            gap: "4px",
                          }}
                        >
                          <span>{badge.icon}</span>
                          <span>{badge.label}</span>
                        </span>
                        <div style={{ flex: 1, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                          <span style={{ color: "#e2e8f0" }}>
                            {step.status === "blocked" ? "🚫 " : "✓ "}
                            {step.result_summary}
                          </span>
                          {step.duration_ms !== undefined && step.duration_ms > 0 && (
                            <span style={{ fontSize: "0.72rem", color: "#64748b", fontFamily: "monospace" }}>
                              {step.duration_ms}ms
                            </span>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          )}

          {/* Answer Card */}
          <div
            style={{
              background: "rgba(30, 41, 59, 0.8)",
              border: "1px solid rgba(56, 189, 248, 0.3)",
              borderRadius: "10px",
              padding: "16px 20px",
            }}
          >
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                marginBottom: "12px",
                borderBottom: "1px solid rgba(255, 255, 255, 0.08)",
                paddingBottom: "8px",
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                <span style={{ fontWeight: 600, color: "#f8fafc", fontSize: "0.95rem" }}>
                  AI Answer
                </span>
                {ragResult.chunks_retrieved !== undefined && (
                  <span
                    style={{
                      fontSize: "0.72rem",
                      color: "#38bdf8",
                      background: "rgba(56, 189, 248, 0.1)",
                      padding: "1px 6px",
                      borderRadius: "4px",
                    }}
                  >
                    {ragResult.chunks_retrieved} source reference(s) grounded
                  </span>
                )}
                {ragResult.duration_ms !== undefined && ragResult.duration_ms !== null && (
                  <span
                    style={{
                      fontSize: "0.72rem",
                      color: "#94a3b8",
                      background: "rgba(255, 255, 255, 0.05)",
                      padding: "1px 6px",
                      borderRadius: "4px",
                    }}
                  >
                    ⏱️ {(ragResult.duration_ms / 1000).toFixed(2)}s
                  </span>
                )}
              </div>
              <span
                style={{
                  fontSize: "0.72rem",
                  color: "#94a3b8",
                  background: "rgba(255, 255, 255, 0.05)",
                  padding: "2px 8px",
                  borderRadius: "4px",
                  border: "1px solid rgba(255, 255, 255, 0.1)",
                }}
              >
                Model: {ragResult.model_name}
              </span>
            </div>

            <div
              style={{
                fontSize: "0.9rem",
                lineHeight: "1.6",
                color: "#e2e8f0",
                whiteSpace: "pre-wrap",
                fontFamily: "inherit",
              }}
            >
              {ragResult.answer}
            </div>
          </div>

          {/* Sources Section */}
          <div>
            <div
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                marginBottom: "10px",
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                <h4 style={{ margin: 0, fontSize: "0.9rem", fontWeight: 600, color: "#cbd5e1" }}>
                  Sources
                </h4>
                <span style={{ fontSize: "0.75rem", color: "#64748b" }}>
                  ({(ragResult.file_sources && ragResult.file_sources.length > 0)
                    ? `${ragResult.file_sources.length} unique file(s)`
                    : `${ragResult.sources.length} reference(s)`})
                </span>
              </div>

              {/* View Mode Toggle: Files vs Chunks */}
              {ragResult.sources.length > 0 && (
                <div
                  style={{
                    display: "flex",
                    background: "rgba(0, 0, 0, 0.3)",
                    borderRadius: "6px",
                    padding: "2px",
                    border: "1px solid rgba(255, 255, 255, 0.1)",
                  }}
                >
                  <button
                    type="button"
                    onClick={() => setViewMode("files")}
                    style={{
                      background: viewMode === "files" ? "rgba(56, 189, 248, 0.2)" : "transparent",
                      color: viewMode === "files" ? "#38bdf8" : "#94a3b8",
                      border: "none",
                      borderRadius: "4px",
                      padding: "3px 8px",
                      fontSize: "0.72rem",
                      cursor: "pointer",
                      fontWeight: viewMode === "files" ? 600 : 400,
                    }}
                  >
                    Deduplicated Files
                  </button>
                  <button
                    type="button"
                    onClick={() => setViewMode("chunks")}
                    style={{
                      background: viewMode === "chunks" ? "rgba(56, 189, 248, 0.2)" : "transparent",
                      color: viewMode === "chunks" ? "#38bdf8" : "#94a3b8",
                      border: "none",
                      borderRadius: "4px",
                      padding: "3px 8px",
                      fontSize: "0.72rem",
                      cursor: "pointer",
                      fontWeight: viewMode === "chunks" ? 600 : 400,
                    }}
                  >
                    All Chunks ({ragResult.sources.length})
                  </button>
                </div>
              )}
            </div>

            {ragResult.sources.length === 0 ? (
              <p style={{ margin: 0, fontSize: "0.85rem", color: "#64748b", fontStyle: "italic" }}>
                No relevant source code chunks found for this query.
              </p>
            ) : viewMode === "files" && ragResult.file_sources && ragResult.file_sources.length > 0 ? (
              /* Deduplicated File Cards View */
              <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                {ragResult.file_sources.map((fileSrc: RAGFileSource, idx: number) => {
                  const isExpanded = expandedFile === fileSrc.file_path;
                  const pct = (fileSrc.max_similarity * 100).toFixed(1);
                  const matchingChunks = ragResult.sources.filter(
                    (s) => s.file_path === fileSrc.file_path
                  );

                  return (
                    <div
                      key={fileSrc.file_path || idx}
                      style={{
                        background: "rgba(15, 23, 42, 0.8)",
                        border: "1px solid rgba(255, 255, 255, 0.08)",
                        borderRadius: "8px",
                        overflow: "hidden",
                      }}
                    >
                      {/* File Card Header */}
                      <div
                        onClick={() => toggleFileExpand(fileSrc.file_path)}
                        style={{
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "space-between",
                          padding: "10px 14px",
                          cursor: "pointer",
                          background: isExpanded
                            ? "rgba(56, 189, 248, 0.08)"
                            : "rgba(255, 255, 255, 0.02)",
                          transition: "background 0.2s ease",
                        }}
                      >
                        <div style={{ display: "flex", alignItems: "center", gap: "8px", flexWrap: "wrap" }}>
                          <span style={{ fontSize: "1rem" }}>📄</span>
                          <span
                            style={{
                              fontFamily: "monospace",
                              fontSize: "0.85rem",
                              fontWeight: 600,
                              color: "#38bdf8",
                            }}
                          >
                            {fileSrc.file_path}
                          </span>

                          {/* Line Ranges Badges */}
                          {fileSrc.line_ranges.length > 0 && (
                            <span
                              style={{
                                fontSize: "0.75rem",
                                color: "#94a3b8",
                                background: "rgba(255, 255, 255, 0.05)",
                                padding: "1px 6px",
                                borderRadius: "4px",
                              }}
                            >
                              Lines {fileSrc.line_ranges.join(", ")}
                            </span>
                          )}

                          {fileSrc.chunks_count > 1 && (
                            <span
                              style={{
                                fontSize: "0.7rem",
                                color: "#64748b",
                                background: "rgba(255, 255, 255, 0.03)",
                                padding: "1px 5px",
                                borderRadius: "4px",
                              }}
                            >
                              {fileSrc.chunks_count} references
                            </span>
                          )}
                        </div>

                        <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                          <span
                            style={{
                              fontSize: "0.75rem",
                              fontWeight: 600,
                              color:
                                fileSrc.max_similarity >= 0.7
                                  ? "#4ade80"
                                  : fileSrc.max_similarity >= 0.4
                                  ? "#facc15"
                                  : "#94a3b8",
                              background: "rgba(0, 0, 0, 0.3)",
                              padding: "2px 8px",
                              borderRadius: "12px",
                              border: "1px solid rgba(255, 255, 255, 0.1)",
                            }}
                          >
                            {pct}% match
                          </span>
                          <span style={{ fontSize: "0.75rem", color: "#64748b" }}>
                            {isExpanded ? "▲ Hide" : "▼ View Code"}
                          </span>
                        </div>
                      </div>

                      {/* Expanded Code Evidence */}
                      {isExpanded && (
                        <div
                          style={{
                            padding: "12px 14px",
                            borderTop: "1px solid rgba(255, 255, 255, 0.05)",
                            background: "#090d16",
                            display: "flex",
                            flexDirection: "column",
                            gap: "8px",
                          }}
                        >
                          {matchingChunks.map((chunk, cIdx) => (
                            <div key={chunk.chunk_id || cIdx}>
                              <div
                                style={{
                                  fontSize: "0.72rem",
                                  color: "#64748b",
                                  marginBottom: "4px",
                                }}
                              >
                                {chunk.start_line && chunk.end_line
                                  ? `Lines ${chunk.start_line}–${chunk.end_line}`
                                  : `Reference #${cIdx + 1}`}
                                {" · "}
                                <span style={{ color: "#94a3b8" }}>
                                  {(chunk.score * 100).toFixed(1)}% score
                                </span>
                              </div>
                              <pre
                                style={{
                                  margin: 0,
                                  fontFamily:
                                    "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace",
                                  fontSize: "0.8rem",
                                  lineHeight: "1.45",
                                  color: "#e2e8f0",
                                  overflowX: "auto",
                                  whiteSpace: "pre-wrap",
                                  wordBreak: "break-word",
                                  background: "rgba(15, 23, 42, 0.6)",
                                  padding: "8px 12px",
                                  borderRadius: "6px",
                                }}
                              >
                                <code>{chunk.content}</code>
                              </pre>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            ) : (
              /* All Chunks View */
              <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                {ragResult.sources.map((src: RAGSourceReference, idx: number) => {
                  const isExpanded = expandedChunkId === src.chunk_id;
                  const percentage = (src.score * 100).toFixed(1);

                  return (
                    <div
                      key={src.chunk_id || idx}
                      style={{
                        background: "rgba(15, 23, 42, 0.8)",
                        border: "1px solid rgba(255, 255, 255, 0.08)",
                        borderRadius: "8px",
                        overflow: "hidden",
                      }}
                    >
                      <div
                        onClick={() => toggleChunkExpand(src.chunk_id || `chunk-${idx}`)}
                        style={{
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "space-between",
                          padding: "10px 14px",
                          cursor: "pointer",
                          background: isExpanded
                            ? "rgba(56, 189, 248, 0.08)"
                            : "rgba(255, 255, 255, 0.02)",
                          transition: "background 0.2s ease",
                        }}
                      >
                        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                          <span style={{ fontSize: "1rem" }}>📄</span>
                          <span
                            style={{
                              fontFamily: "monospace",
                              fontSize: "0.85rem",
                              fontWeight: 600,
                              color: "#38bdf8",
                            }}
                          >
                            {src.file_path}
                          </span>
                          {src.start_line && src.end_line && (
                            <span
                              style={{
                                fontSize: "0.75rem",
                                color: "#94a3b8",
                                background: "rgba(255, 255, 255, 0.05)",
                                padding: "1px 6px",
                                borderRadius: "4px",
                              }}
                            >
                              Lines {src.start_line}–{src.end_line}
                            </span>
                          )}
                        </div>

                        <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                          <span
                            style={{
                              fontSize: "0.75rem",
                              fontWeight: 600,
                              color:
                                src.score >= 0.7
                                  ? "#4ade80"
                                  : src.score >= 0.4
                                  ? "#facc15"
                                  : "#94a3b8",
                              background: "rgba(0, 0, 0, 0.3)",
                              padding: "2px 8px",
                              borderRadius: "12px",
                              border: "1px solid rgba(255, 255, 255, 0.1)",
                            }}
                          >
                            {percentage}% score
                          </span>
                          <span style={{ fontSize: "0.75rem", color: "#64748b" }}>
                            {isExpanded ? "▲ Hide" : "▼ View Code"}
                          </span>
                        </div>
                      </div>

                      {isExpanded && (
                        <div
                          style={{
                            padding: "12px 14px",
                            borderTop: "1px solid rgba(255, 255, 255, 0.05)",
                            background: "#090d16",
                          }}
                        >
                          <pre
                            style={{
                              margin: 0,
                              fontFamily:
                                "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace",
                              fontSize: "0.8rem",
                              lineHeight: "1.45",
                              color: "#e2e8f0",
                              overflowX: "auto",
                              whiteSpace: "pre-wrap",
                              wordBreak: "break-word",
                            }}
                          >
                            <code>{src.content}</code>
                          </pre>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
