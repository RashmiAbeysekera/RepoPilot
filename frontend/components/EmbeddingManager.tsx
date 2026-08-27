"use client";

import React, { useEffect, useState } from "react";
import {
  EmbeddingGenerationResponse,
  EmbeddingStatusResponse,
  generateRepositoryEmbeddings,
  getRepositoryEmbeddingStatus,
} from "@/lib/api";

interface EmbeddingManagerProps {
  repositoryId: string;
  repositoryName: string;
}

export function EmbeddingManager({ repositoryId, repositoryName }: EmbeddingManagerProps) {
  const [status, setStatus] = useState<EmbeddingStatusResponse | null>(null);
  const [loadingStatus, setLoadingStatus] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [generationResult, setGenerationResult] = useState<EmbeddingGenerationResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const fetchStatus = async () => {
    setLoadingStatus(true);
    setError(null);
    const result = await getRepositoryEmbeddingStatus(repositoryId);
    setLoadingStatus(false);

    if (result.ok) {
      setStatus(result.data);
    } else {
      setError(result.error);
    }
  };

  useEffect(() => {
    fetchStatus();
    setGenerationResult(null);
  }, [repositoryId]);

  const handleGenerate = async () => {
    setGenerating(true);
    setError(null);
    setGenerationResult(null);

    const result = await generateRepositoryEmbeddings(repositoryId);
    setGenerating(false);

    if (result.ok) {
      setGenerationResult(result.data);
      fetchStatus();
    } else {
      setError(result.error);
    }
  };

  const coveragePercent = status && status.total_chunks > 0
    ? Math.round((status.embedded_chunks / status.total_chunks) * 100)
    : 0;

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden shadow-2xl p-6 flex flex-col gap-6">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-800 pb-4">
        <div>
          <h2 className="text-lg font-semibold text-slate-100 flex items-center gap-2">
            <span className="text-purple-400 font-mono">⚡</span> Vector Embeddings (pgvector)
          </h2>
          <p className="text-xs text-slate-400">
            {repositoryName} &bull; Local SentenceTransformers Model
          </p>
        </div>

        <button
          onClick={handleGenerate}
          disabled={generating || loadingStatus}
          className="px-5 py-2.5 bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 disabled:opacity-50 text-white text-xs font-semibold rounded-lg shadow-lg transition-all flex items-center gap-2"
        >
          {generating ? (
            <>
              <svg className="animate-spin h-4 w-4 text-white" viewBox="0 0 24 24" fill="none">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
              </svg>
              Generating Embeddings...
            </>
          ) : (
            <>⚡ Generate Embeddings</>
          )}
        </button>
      </div>

      {/* Generation Result Banner */}
      {generationResult && (
        <div className="p-4 bg-purple-950/40 border border-purple-500/30 rounded-lg text-xs text-purple-200 flex items-center justify-between">
          <div className="flex flex-wrap items-center gap-3">
            <span className="text-emerald-400 font-bold">✓ Embedding generation completed.</span>
            <span>Created: <strong className="text-white">{generationResult.embeddings_created}</strong></span>
            <span>&bull;</span>
            <span>Updated: <strong className="text-white">{generationResult.embeddings_updated}</strong></span>
            <span>&bull;</span>
            <span>Skipped (Unchanged): <strong className="text-white">{generationResult.embeddings_skipped}</strong></span>
          </div>
          <button onClick={() => setGenerationResult(null)} className="text-slate-400 hover:text-white">
            ✕
          </button>
        </div>
      )}

      {/* Error Alert */}
      {error && (
        <div className="p-4 bg-rose-950/40 border border-rose-500/30 rounded-lg text-xs text-rose-300 flex items-center justify-between">
          <span>⚠️ {error}</span>
          <button onClick={() => setError(null)} className="text-slate-400 hover:text-white">
            ✕
          </button>
        </div>
      )}

      {/* Status Cards & Progress */}
      {loadingStatus && !status ? (
        <div className="py-12 text-center text-xs text-slate-400">Loading embedding status...</div>
      ) : status ? (
        <div className="flex flex-col gap-6">
          {/* Progress Bar */}
          <div className="flex flex-col gap-2 bg-slate-950 p-4 rounded-lg border border-slate-800/80">
            <div className="flex items-center justify-between text-xs">
              <span className="text-slate-300 font-medium">Vector Embedding Coverage</span>
              <span className="text-purple-400 font-mono font-semibold">
                {status.embedded_chunks} / {status.total_chunks} chunks ({coveragePercent}%)
              </span>
            </div>
            <div className="w-full bg-slate-800 rounded-full h-2.5 overflow-hidden">
              <div
                className="bg-gradient-to-r from-purple-500 to-indigo-500 h-2.5 rounded-full transition-all duration-500"
                style={{ width: `${coveragePercent}%` }}
              />
            </div>
          </div>

          {/* Metric Cards Grid */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="bg-slate-950 p-4 rounded-lg border border-slate-800/80 text-center">
              <p className="text-[11px] text-slate-400 uppercase tracking-wider font-semibold">Total Chunks</p>
              <p className="text-2xl font-bold text-slate-100 font-mono mt-1">{status.total_chunks}</p>
            </div>

            <div className="bg-purple-950/30 p-4 rounded-lg border border-purple-800/40 text-center">
              <p className="text-[11px] text-purple-300 uppercase tracking-wider font-semibold">Embedded Chunks</p>
              <p className="text-2xl font-bold text-purple-300 font-mono mt-1">{status.embedded_chunks}</p>
            </div>

            <div className="bg-slate-950 p-4 rounded-lg border border-slate-800/80 text-center">
              <p className="text-[11px] text-slate-400 uppercase tracking-wider font-semibold">Embedding Model</p>
              <p className="text-xs font-bold text-cyan-400 font-mono mt-2 truncate" title={status.model_name}>
                {status.model_name}
              </p>
            </div>

            <div className="bg-slate-950 p-4 rounded-lg border border-slate-800/80 text-center">
              <p className="text-[11px] text-slate-400 uppercase tracking-wider font-semibold font-mono">Vector Dimension</p>
              <p className="text-2xl font-bold text-emerald-400 font-mono mt-1">{status.embedding_dimension}</p>
            </div>
          </div>

          {/* Info Card */}
          <div className="p-4 bg-slate-950/60 border border-slate-800 rounded-lg text-xs text-slate-400 leading-relaxed flex items-start gap-3">
            <span className="text-base">💡</span>
            <div>
              <p className="text-slate-300 font-semibold mb-1">How vector embeddings work in RepoPilot:</p>
              <p>
                Each CodeChunk text segment is converted into a 384-dimensional dense numerical vector using the local model <strong>{status.model_name}</strong>.
                Vectors are stored in PostgreSQL using the <strong>pgvector</strong> extension for future semantic search and RAG context retrieval.
              </p>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
