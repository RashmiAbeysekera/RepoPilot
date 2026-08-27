"use client";

import { useState } from "react";
import {
  askRepositoryQuestion,
  type RAGAnswerResponse,
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
  const [isLoading, setIsLoading] = useState(false);
  const [ragResult, setRagResult] = useState<RAGAnswerResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [expandedSourceId, setExpandedSourceId] = useState<string | null>(null);

  async function handleAsk(e?: React.FormEvent) {
    if (e) e.preventDefault();
    if (!query.trim()) {
      setError("Please enter a question about the repository.");
      return;
    }

    setIsLoading(true);
    setError(null);
    setRagResult(null);

    const res = await askRepositoryQuestion(repositoryId, query.trim(), topK);
    setIsLoading(false);

    if (res.ok) {
      setRagResult(res.data);
      // Auto expand the first source reference if available
      if (res.data.sources && res.data.sources.length > 0) {
        setExpandedSourceId(res.data.sources[0].chunk_id);
      }
    } else {
      setError(res.error);
    }
  }

  function toggleSourceExpand(chunkId: string) {
    setExpandedSourceId((prev) => (prev === chunkId ? null : chunkId));
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
              background: "rgba(56, 189, 248, 0.15)",
              color: "#38bdf8",
              border: "1px solid rgba(56, 189, 248, 0.3)",
              fontWeight: 500,
            }}
          >
            RAG Pipeline
          </span>
        </div>
        <p style={{ margin: 0, fontSize: "0.85rem", color: "#94a3b8" }}>
          Ask natural language developer questions about <strong>{repositoryName}</strong>. RepoPilot retrieves code evidence via vector search and generates grounded answers using Gemini AI.
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
            {isLoading ? "Analyzing repository..." : "Ask"}
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
          <span style={{ display: "inline-block", animation: "pulse 1.5s infinite" }}>
            🔍 Retrieving relevant code context & generating grounded answer with Gemini...
          </span>
        </div>
      )}

      {/* Error State */}
      {error && (
        <div
          style={{
            marginTop: "16px",
            padding: "12px 16px",
            background: "rgba(239, 68, 68, 0.1)",
            border: "1px solid rgba(239, 68, 68, 0.3)",
            borderRadius: "8px",
            color: "#fca5a5",
            fontSize: "0.85rem",
          }}
        >
          <strong>Error:</strong> {error}
        </div>
      )}

      {/* RAG Answer Display */}
      {ragResult && (
        <div style={{ marginTop: "20px", display: "flex", flexDirection: "column", gap: "16px" }}>
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
              <span style={{ fontWeight: 600, color: "#f8fafc", fontSize: "0.95rem" }}>
                Grounded Answer
              </span>
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
                marginBottom: "8px",
              }}
            >
              <h4 style={{ margin: 0, fontSize: "0.9rem", fontWeight: 600, color: "#cbd5e1" }}>
                Source References ({ragResult.sources.length})
              </h4>
              <span style={{ fontSize: "0.75rem", color: "#64748b" }}>
                Code evidence retrieved via pgvector similarity search
              </span>
            </div>

            {ragResult.sources.length === 0 ? (
              <p style={{ margin: 0, fontSize: "0.85rem", color: "#64748b", italic: "true" }}>
                No relevant source code chunks found for this query.
              </p>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                {ragResult.sources.map((src: RAGSourceReference, idx: number) => {
                  const isExpanded = expandedSourceId === src.chunk_id;
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
                      {/* Source Header Row */}
                      <div
                        onClick={() => toggleSourceExpand(src.chunk_id)}
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
                        </div>

                        <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                          <span
                            style={{
                              fontSize: "0.75rem",
                              fontWeight: 600,
                              color: src.score >= 0.7 ? "#4ade80" : src.score >= 0.4 ? "#facc15" : "#94a3b8",
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

                      {/* Expandable Chunk Content */}
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
                              fontFamily: "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace",
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
