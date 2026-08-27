"use client";

import React, { useEffect, useState } from "react";
import {
  CodeChunkDetail,
  CodeChunkMetadata,
  generateRepositoryChunks,
  getChunkDetail,
  listRepositoryChunks,
} from "@/lib/api";

interface ChunkExplorerProps {
  repositoryId: string;
  repositoryName: string;
}

export function ChunkExplorer({ repositoryId, repositoryName }: ChunkExplorerProps) {
  const [chunks, setChunks] = useState<CodeChunkMetadata[]>([]);
  const [selectedChunk, setSelectedChunk] = useState<CodeChunkDetail | null>(null);
  const [loadingChunks, setLoadingChunks] = useState(false);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [generationResult, setGenerationResult] = useState<{
    files_processed: number;
    chunks_created: number;
  } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");

  const loadChunks = async () => {
    setLoadingChunks(true);
    setError(null);
    const result = await listRepositoryChunks(repositoryId);
    setLoadingChunks(false);

    if (result.ok) {
      setChunks(result.data.chunks);
    } else {
      setError(result.error);
    }
  };

  useEffect(() => {
    loadChunks();
    setSelectedChunk(null);
    setGenerationResult(null);
  }, [repositoryId]);

  const handleGenerate = async () => {
    setGenerating(true);
    setError(null);
    setGenerationResult(null);

    const result = await generateRepositoryChunks(repositoryId);
    setGenerating(false);

    if (result.ok) {
      setGenerationResult({
        files_processed: result.data.files_processed,
        chunks_created: result.data.chunks_created,
      });
      loadChunks();
    } else {
      setError(result.error);
    }
  };

  const handleSelectChunk = async (chunkId: string) => {
    setLoadingDetail(true);
    const result = await getChunkDetail(repositoryId, chunkId);
    setLoadingDetail(false);

    if (result.ok) {
      setSelectedChunk(result.data);
    } else {
      setError(result.error);
    }
  };

  // Filter chunks by search query
  const filteredChunks = chunks.filter(
    (c) =>
      c.file_path.toLowerCase().includes(searchQuery.toLowerCase()) ||
      c.file_name.toLowerCase().includes(searchQuery.toLowerCase())
  );

  // Group chunks by file path
  const groupedChunks = filteredChunks.reduce<Record<string, CodeChunkMetadata[]>>(
    (acc, chunk) => {
      if (!acc[chunk.file_path]) {
        acc[chunk.file_path] = [];
      }
      acc[chunk.file_path].push(chunk);
      return acc;
    },
    {}
  );

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden shadow-2xl">
      {/* Header Bar */}
      <div className="p-4 bg-slate-950/60 border-b border-slate-800 flex flex-wrap items-center justify-between gap-4">
        <div>
          <h2 className="text-lg font-semibold text-slate-100 flex items-center gap-2">
            <span className="text-cyan-400 font-mono">🧩</span> Code Chunk Explorer
          </h2>
          <p className="text-xs text-slate-400">
            {repositoryName} &bull; {chunks.length} total chunks generated
          </p>
        </div>

        <button
          onClick={handleGenerate}
          disabled={generating}
          className="px-4 py-2 bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-400 hover:to-blue-500 disabled:opacity-50 text-white text-xs font-semibold rounded-lg shadow-lg transition-all flex items-center gap-2"
        >
          {generating ? (
            <>
              <svg className="animate-spin h-3.5 w-3.5 text-white" viewBox="0 0 24 24" fill="none">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
              </svg>
              Generating Chunks...
            </>
          ) : (
            <>⚡ Generate Chunks</>
          )}
        </button>
      </div>

      {/* Generation Result Banner */}
      {generationResult && (
        <div className="mx-4 mt-4 p-3 bg-cyan-950/40 border border-cyan-500/30 rounded-lg text-xs text-cyan-200 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="text-emerald-400 font-bold">✓ Chunk generation completed.</span>
            <span>Files processed: <strong className="text-white">{generationResult.files_processed}</strong></span>
            <span>&bull;</span>
            <span>Chunks created: <strong className="text-white">{generationResult.chunks_created}</strong></span>
          </div>
          <button
            onClick={() => setGenerationResult(null)}
            className="text-slate-400 hover:text-white"
          >
            ✕
          </button>
        </div>
      )}

      {/* Error Alert */}
      {error && (
        <div className="mx-4 mt-4 p-3 bg-rose-950/40 border border-rose-500/30 rounded-lg text-xs text-rose-300 flex items-center justify-between">
          <span>⚠️ {error}</span>
          <button onClick={() => setError(null)} className="text-slate-400 hover:text-white">
            ✕
          </button>
        </div>
      )}

      {/* Main Split Layout */}
      <div className="grid grid-cols-1 md:grid-cols-12 min-h-[420px]">
        {/* Left Side: Chunk List grouped by file */}
        <div className="md:col-span-5 border-r border-slate-800 p-4 flex flex-col gap-3 max-h-[550px] overflow-y-auto">
          {/* Search bar */}
          <input
            type="text"
            placeholder="Search chunks by path..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full px-3 py-1.5 bg-slate-950 border border-slate-800 rounded-lg text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-cyan-500 transition-all"
          />

          {loadingChunks ? (
            <div className="py-12 text-center text-xs text-slate-400">Loading chunks...</div>
          ) : Object.keys(groupedChunks).length === 0 ? (
            <div className="py-12 text-center text-xs text-slate-500 flex flex-col items-center gap-2">
              <span>No chunks found.</span>
              <span className="text-[11px] text-slate-600">
                Click <strong>[Generate Chunks]</strong> above to create chunks from repository files.
              </span>
            </div>
          ) : (
            Object.entries(groupedChunks).map(([filePath, fileChunks]) => (
              <div key={filePath} className="flex flex-col gap-1">
                <div className="text-xs font-mono font-medium text-cyan-300 truncate py-1 border-b border-slate-800/60">
                  📁 {filePath}
                </div>
                <div className="pl-3 flex flex-col gap-1">
                  {fileChunks.map((c) => {
                    const isSelected = selectedChunk?.id === c.id;
                    return (
                      <button
                        key={c.id}
                        onClick={() => handleSelectChunk(c.id)}
                        className={`w-full text-left px-2.5 py-1.5 rounded text-xs transition-all flex items-center justify-between ${
                          isSelected
                            ? "bg-cyan-500/20 text-cyan-200 border border-cyan-500/40 font-medium"
                            : "hover:bg-slate-800/60 text-slate-300"
                        }`}
                      >
                        <span className="font-mono">Chunk {c.chunk_index}</span>
                        <span className="text-[11px] text-slate-400 font-mono">
                          L{c.start_line}–L{c.end_line}
                        </span>
                      </button>
                    );
                  })}
                </div>
              </div>
            ))
          )}
        </div>

        {/* Right Side: Chunk Content Viewer */}
        <div className="md:col-span-7 p-4 bg-slate-950/40 flex flex-col min-h-[420px]">
          {loadingDetail ? (
            <div className="m-auto text-xs text-slate-400">Loading chunk content...</div>
          ) : selectedChunk ? (
            <div className="flex flex-col h-full gap-3">
              <div className="p-3 bg-slate-900 border border-slate-800 rounded-lg flex items-center justify-between text-xs">
                <div>
                  <div className="text-slate-100 font-mono font-semibold">
                    File: <span className="text-cyan-400">{selectedChunk.file_path}</span>
                  </div>
                  <div className="text-slate-400 text-[11px] mt-0.5">
                    Chunk: <strong className="text-slate-200">{selectedChunk.chunk_index}</strong> &bull; Lines:{" "}
                    <strong className="text-slate-200">
                      {selectedChunk.start_line}–{selectedChunk.end_line}
                    </strong>
                  </div>
                </div>
                <button
                  onClick={() => navigator.clipboard.writeText(selectedChunk.content)}
                  className="px-2.5 py-1 bg-slate-800 hover:bg-slate-700 text-slate-300 text-[11px] rounded transition-all"
                  title="Copy chunk text"
                >
                  Copy Text
                </button>
              </div>

              <div className="flex-1 bg-slate-950 border border-slate-800/80 rounded-lg p-3 overflow-x-auto max-h-[450px]">
                <pre className="font-mono text-xs text-slate-200 leading-relaxed whitespace-pre font-normal">
                  {selectedChunk.content}
                </pre>
              </div>
            </div>
          ) : (
            <div className="m-auto text-center text-xs text-slate-500 flex flex-col items-center gap-2">
              <span className="text-2xl">📑</span>
              <span>Select a chunk from the list to view stored text content and line metadata.</span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
