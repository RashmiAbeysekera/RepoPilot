"use client";

import { useState } from "react";
import type { RepositoryFile } from "@/lib/api";

interface FileExplorerProps {
  files: RepositoryFile[];
  selectedFileId: string | null;
  onSelectFile: (file: RepositoryFile) => void;
  isLoading: boolean;
}

export default function FileExplorer({
  files,
  selectedFileId,
  onSelectFile,
  isLoading,
}: FileExplorerProps) {
  const [filterText, setFilterText] = useState("");

  const filteredFiles = files.filter((f) =>
    f.path.toLowerCase().includes(filterText.toLowerCase())
  );

  function formatBytes(bytes: number): string {
    if (bytes === 0) return "0 B";
    const k = 1024;
    const sizes = ["B", "KB", "MB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + " " + sizes[i];
  }

  function getBadgeColor(fileType: string): string {
    switch (fileType) {
      case "documentation":
        return "#3b82f6"; // blue
      case "configuration":
        return "#f59e0b"; // amber
      default:
        return "#10b981"; // green
    }
  }

  return (
    <div
      style={{
        background: "rgba(15, 23, 42, 0.6)",
        borderRadius: "8px",
        border: "1px solid rgba(255, 255, 255, 0.1)",
        padding: "16px",
        height: "100%",
        display: "flex",
        flexDirection: "column",
      }}
    >
      <div style={{ marginBottom: "12px", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h3 style={{ margin: 0, fontSize: "1rem", fontWeight: 600, color: "#f3f4f6" }}>
          Repository Files ({files.length})
        </h3>
      </div>

      <input
        type="text"
        placeholder="Filter by path..."
        value={filterText}
        onChange={(e) => setFilterText(e.target.value)}
        style={{
          width: "100%",
          padding: "8px 12px",
          background: "rgba(0, 0, 0, 0.3)",
          border: "1px solid rgba(255, 255, 255, 0.15)",
          borderRadius: "6px",
          color: "#fff",
          fontSize: "0.85rem",
          marginBottom: "12px",
        }}
      />

      {isLoading && (
        <p style={{ fontSize: "0.85rem", color: "#9ca3af", textAlign: "center" }}>
          Loading files...
        </p>
      )}

      {!isLoading && files.length === 0 && (
        <p style={{ fontSize: "0.85rem", color: "#9ca3af", textAlign: "center" }}>
          No files stored yet. Run ingestion to import repository files.
        </p>
      )}

      {!isLoading && files.length > 0 && (
        <div style={{ overflowY: "auto", flex: 1, maxHeight: "400px" }}>
          <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
            {filteredFiles.map((file) => {
              const isSelected = selectedFileId === file.id;
              return (
                <li
                  key={file.id}
                  onClick={() => onSelectFile(file)}
                  style={{
                    padding: "8px 10px",
                    borderRadius: "6px",
                    cursor: "pointer",
                    marginBottom: "4px",
                    background: isSelected ? "rgba(59, 130, 246, 0.25)" : "transparent",
                    border: isSelected ? "1px solid #3b82f6" : "1px solid transparent",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    transition: "background 0.15s ease",
                  }}
                  id={`file-item-${file.id}`}
                >
                  <div style={{ display: "flex", alignItems: "center", overflow: "hidden" }}>
                    <span style={{ marginRight: "8px", fontSize: "0.9rem" }}>📄</span>
                    <span
                      style={{
                        fontSize: "0.82rem",
                        fontFamily: "monospace",
                        color: isSelected ? "#93c5fd" : "#e5e7eb",
                        whiteSpace: "nowrap",
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                      }}
                      title={file.path}
                    >
                      {file.path}
                    </span>
                  </div>

                  <div style={{ display: "flex", alignItems: "center", gap: "8px", flexShrink: 0 }}>
                    <span
                      style={{
                        fontSize: "0.7rem",
                        padding: "2px 6px",
                        borderRadius: "4px",
                        background: getBadgeColor(file.file_type),
                        color: "#ffffff",
                        fontWeight: 500,
                        textTransform: "capitalize",
                      }}
                    >
                      {file.file_type}
                    </span>
                    <span style={{ fontSize: "0.75rem", color: "#9ca3af", fontFamily: "monospace" }}>
                      {formatBytes(file.size)}
                    </span>
                  </div>
                </li>
              );
            })}
          </ul>
        </div>
      )}
    </div>
  );
}
