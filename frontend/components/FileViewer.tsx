"use client";

import type { RepositoryFileDetail } from "@/lib/api";

interface FileViewerProps {
  file: RepositoryFileDetail | null;
  isLoading: boolean;
  error: string | null;
  onClose: () => void;
}

export default function FileViewer({ file, isLoading, error, onClose }: FileViewerProps) {
  if (!file && !isLoading && !error) {
    return (
      <div
        style={{
          background: "rgba(15, 23, 42, 0.4)",
          borderRadius: "8px",
          border: "1px dashed rgba(255, 255, 255, 0.15)",
          padding: "32px",
          textAlign: "center",
          color: "#9ca3af",
          fontSize: "0.9rem",
          height: "100%",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        Select a file from the explorer to view its contents.
      </div>
    );
  }

  function formatBytes(bytes: number): string {
    if (bytes === 0) return "0 B";
    const k = 1024;
    const sizes = ["B", "KB", "MB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + " " + sizes[i];
  }

  return (
    <div
      style={{
        background: "rgba(15, 23, 42, 0.8)",
        borderRadius: "8px",
        border: "1px solid rgba(255, 255, 255, 0.1)",
        padding: "16px",
        height: "100%",
        display: "flex",
        flexDirection: "column",
      }}
    >
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          paddingBottom: "12px",
          borderBottom: "1px solid rgba(255, 255, 255, 0.1)",
          marginBottom: "12px",
        }}
      >
        <div>
          <h4 style={{ margin: 0, fontSize: "0.95rem", fontFamily: "monospace", color: "#60a5fa" }}>
            {file?.path ?? "Loading..."}
          </h4>
          {file && (
            <div style={{ display: "flex", gap: "12px", marginTop: "4px", fontSize: "0.75rem", color: "#9ca3af" }}>
              <span>Size: <code>{formatBytes(file.size)}</code></span>
              <span>Extension: <code>{file.extension || "none"}</code></span>
              <span>Type: <code>{file.file_type}</code></span>
            </div>
          )}
        </div>
        <button
          onClick={onClose}
          className="btn-secondary"
          style={{ padding: "4px 8px", fontSize: "0.8rem" }}
        >
          Close ✕
        </button>
      </div>

      {isLoading && (
        <p style={{ color: "#9ca3af", fontSize: "0.85rem", padding: "16px" }}>
          Fetching file content...
        </p>
      )}

      {error && (
        <p style={{ color: "#ef4444", fontSize: "0.85rem", padding: "16px" }}>
          {error}
        </p>
      )}

      {!isLoading && !error && file && (
        <div
          style={{
            flex: 1,
            overflow: "auto",
            background: "rgba(0, 0, 0, 0.4)",
            borderRadius: "6px",
            padding: "14px",
            border: "1px solid rgba(255, 255, 255, 0.05)",
            maxHeight: "450px",
          }}
        >
          {file.content ? (
            <pre
              style={{
                margin: 0,
                fontFamily: "Consolas, Monaco, 'Andale Mono', 'Ubuntu Mono', monospace",
                fontSize: "0.82rem",
                color: "#e2e8f0",
                lineHeight: 1.5,
                whiteSpace: "pre-wrap",
                wordBreak: "break-word",
              }}
            >
              {file.content}
            </pre>
          ) : (
            <p style={{ color: "#6b7280", fontStyle: "italic", fontSize: "0.85rem", margin: 0 }}>
              No text content available for this file (empty or binary file).
            </p>
          )}
        </div>
      )}
    </div>
  );
}
