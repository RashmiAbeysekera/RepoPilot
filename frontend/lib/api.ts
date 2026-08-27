/**
 * Thin wrapper around the browser's native fetch() for talking to the
 * FastAPI backend. Kept in its own module so components don't need to
 * know about URLs, timeouts, or error shapes directly.
 */

// NEXT_PUBLIC_ prefixed variables are the only environment variables
// Next.js exposes to browser (client-side) code. Anything without that
// prefix stays server-only. Our backend URL is not secret, so it's safe
// to expose here — but a database URL or API key never would be.
const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") ?? "http://localhost:8000";

// -------------------------------------------------------------------------
// Health check types and functions
// -------------------------------------------------------------------------

export type HealthStatus = "healthy" | "unavailable";

export interface HealthResponse {
  status: string;
  backend: HealthStatus;
  database: HealthStatus;
}

/**
 * Discriminated result type. Instead of throwing on failure, we return
 * a value the caller is forced to check — this makes network failure a
 * normal, handled case rather than an exceptional one.
 */
export type HealthCheckResult =
  | { ok: true; data: HealthResponse }
  | { ok: false; reason: "network" | "timeout" | "unexpected" };

/**
 * Calls GET /api/health on the FastAPI backend.
 *
 * Handles three distinct failure modes a real client has to deal with:
 *   - the server never responds in time (timeout)
 *   - the request fails outright, e.g. backend process is down (network)
 *   - the server responds, but not with the JSON shape we expect (unexpected)
 */
export async function checkBackendHealth(): Promise<HealthCheckResult> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 5000);

  try {
    const response = await fetch(`${API_BASE_URL}/api/health`, {
      method: "GET",
      signal: controller.signal,
    });

    if (!response.ok) {
      console.error(`Health check returned HTTP ${response.status}`);
      return { ok: false, reason: "unexpected" };
    }

    const data = (await response.json()) as HealthResponse;

    if (!data.backend || !data.database) {
      console.error("Health check response missing expected fields:", data);
      return { ok: false, reason: "unexpected" };
    }

    return { ok: true, data };
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      console.error("Health check timed out.");
      return { ok: false, reason: "timeout" };
    }

    // Typically a network-level failure: backend process not running,
    // wrong port, CORS misconfiguration, DNS failure, etc.
    console.error("Health check failed:", error);
    return { ok: false, reason: "network" };
  } finally {
    clearTimeout(timeoutId);
  }
}

// -------------------------------------------------------------------------
// Repository types and functions
// -------------------------------------------------------------------------

/** Shape of a repository object returned by the API. */
export interface Repository {
  id: string;
  name: string;
  full_name: string;
  github_url: string;
  description: string | null;
  default_branch: string;
  created_at: string;
  updated_at: string;
}

/** Shape of an API error response from FastAPI. */
interface ApiError {
  detail: string;
}

export type ApiResult<T> =
  | { ok: true; data: T }
  | { ok: false; error: string };

/** POST /api/repositories/import — import a public GitHub repository. */
export async function importRepository(
  githubUrl: string
): Promise<ApiResult<Repository>> {
  try {
    const response = await fetch(`${API_BASE_URL}/api/repositories/import`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ github_url: githubUrl }),
    });

    if (response.status === 201) {
      const data = (await response.json()) as Repository;
      return { ok: true, data };
    }

    const errorBody = (await response.json()) as ApiError;
    return {
      ok: false,
      error: errorBody.detail ?? `Import failed with status ${response.status}`,
    };
  } catch {
    return { ok: false, error: "Could not reach the backend. Is it running?" };
  }
}

export interface IngestResult {
  repository_id: string;
  repository: string;
  default_branch: string;
  files_discovered: number;
  files_stored: number;
  files_updated: number;
  files_skipped: number;
  skip_reasons: Record<string, number>;
  source_files: number;
  ignored_files: number;
  file_paths: string[];
}

/** POST /api/repositories/{id}/ingest — discover and analyze repository source files. */
export async function ingestRepository(
  id: string
): Promise<ApiResult<IngestResult>> {
  try {
    const response = await fetch(`${API_BASE_URL}/api/repositories/${id}/ingest`, {
      method: "POST",
    });

    if (response.ok) {
      const data = (await response.json()) as IngestResult;
      return { ok: true, data };
    }

    const errorBody = (await response.json()) as ApiError;
    return {
      ok: false,
      error: errorBody.detail ?? `Analysis failed with status ${response.status}`,
    };
  } catch {
    return { ok: false, error: "Could not reach the backend during analysis." };
  }
}

/** POST /api/repositories — add a new repository manually. */
export async function addRepository(
  githubUrl: string
): Promise<ApiResult<Repository>> {
  try {
    const response = await fetch(`${API_BASE_URL}/api/repositories`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ github_url: githubUrl }),
    });

    if (response.status === 201) {
      const data = (await response.json()) as Repository;
      return { ok: true, data };
    }

    // FastAPI sends error details in { detail: "..." }
    const errorBody = (await response.json()) as ApiError;
    return {
      ok: false,
      error: errorBody.detail ?? `Request failed with status ${response.status}`,
    };
  } catch {
    return { ok: false, error: "Could not reach the backend. Is it running?" };
  }
}


/** GET /api/repositories — list all saved repositories. */
export async function listRepositories(): Promise<ApiResult<Repository[]>> {
  try {
    const response = await fetch(`${API_BASE_URL}/api/repositories`);
    if (!response.ok) {
      return { ok: false, error: `Failed to load repositories (HTTP ${response.status})` };
    }
    const data = (await response.json()) as Repository[];
    return { ok: true, data };
  } catch {
    return { ok: false, error: "Could not reach the backend. Is it running?" };
  }
}

/** DELETE /api/repositories/{id} — remove a saved repository. */
export async function deleteRepository(id: string): Promise<ApiResult<null>> {
  try {
    const response = await fetch(`${API_BASE_URL}/api/repositories/${id}`, {
      method: "DELETE",
    });
    if (response.status === 204) {
      return { ok: true, data: null };
    }
    const errorBody = (await response.json()) as ApiError;
    return {
      ok: false,
      error: errorBody.detail ?? `Delete failed with status ${response.status}`,
    };
  } catch {
    return { ok: false, error: "Could not reach the backend. Is it running?" };
  }
}

// -------------------------------------------------------------------------
// Repository Files types and functions
// -------------------------------------------------------------------------

export interface RepositoryFile {
  id: string;
  repository_id: string;
  path: string;
  name: string;
  extension: string;
  size: number;
  file_type: string;
  created_at: string;
  updated_at: string;
}

export interface RepositoryFileDetail extends RepositoryFile {
  content: string | null;
}

export interface RepositoryFileList {
  repository_id: string;
  total_files: number;
  files: RepositoryFile[];
}

/** GET /api/repositories/{id}/files — list all stored files for a repository. */
export async function listRepositoryFiles(
  repositoryId: string
): Promise<ApiResult<RepositoryFileList>> {
  try {
    const response = await fetch(`${API_BASE_URL}/api/repositories/${repositoryId}/files`);
    if (!response.ok) {
      const errorBody = (await response.json()) as ApiError;
      return { ok: false, error: errorBody.detail ?? `Failed to list files (HTTP ${response.status})` };
    }
    const data = (await response.json()) as RepositoryFileList;
    return { ok: true, data };
  } catch {
    return { ok: false, error: "Could not reach backend when listing repository files." };
  }
}

/** GET /api/repositories/{id}/files/{fileId} — retrieve single file with content. */
export async function getRepositoryFile(
  repositoryId: string,
  fileId: string
): Promise<ApiResult<RepositoryFileDetail>> {
  try {
    const response = await fetch(
      `${API_BASE_URL}/api/repositories/${repositoryId}/files/${fileId}`
    );
    if (!response.ok) {
      const errorBody = (await response.json()) as ApiError;
      return { ok: false, error: errorBody.detail ?? `Failed to fetch file (HTTP ${response.status})` };
    }
    const data = (await response.json()) as RepositoryFileDetail;
    return { ok: true, data };
  } catch {
    return { ok: false, error: "Could not reach backend when fetching file detail." };
  }
}

// -------------------------------------------------------------------------
// Code Chunking types and functions
// -------------------------------------------------------------------------

export interface CodeChunkMetadata {
  id: string;
  repository_file_id: string;
  file_path: string;
  file_name: string;
  chunk_index: number;
  start_line: number;
  end_line: number;
  created_at: string;
}

export interface CodeChunkDetail extends CodeChunkMetadata {
  content: string;
}

export interface CodeChunkListResponse {
  repository_id: string;
  total_chunks: number;
  chunks: CodeChunkMetadata[];
}

export interface ChunkGenerationResponse {
  repository_id: string;
  files_processed: number;
  chunks_created: number;
}

/** POST /api/repositories/{id}/chunks/generate — generate chunks for repository files. */
export async function generateRepositoryChunks(
  repositoryId: string
): Promise<ApiResult<ChunkGenerationResponse>> {
  try {
    const response = await fetch(
      `${API_BASE_URL}/api/repositories/${repositoryId}/chunks/generate`,
      { method: "POST" }
    );
    if (!response.ok) {
      const errorBody = (await response.json()) as ApiError;
      return { ok: false, error: errorBody.detail ?? `Chunk generation failed (HTTP ${response.status})` };
    }
    const data = (await response.json()) as ChunkGenerationResponse;
    return { ok: true, data };
  } catch {
    return { ok: false, error: "Could not reach backend during chunk generation." };
  }
}

/** GET /api/repositories/{id}/chunks — list chunk metadata for repository. */
export async function listRepositoryChunks(
  repositoryId: string
): Promise<ApiResult<CodeChunkListResponse>> {
  try {
    const response = await fetch(`${API_BASE_URL}/api/repositories/${repositoryId}/chunks`);
    if (!response.ok) {
      const errorBody = (await response.json()) as ApiError;
      return { ok: false, error: errorBody.detail ?? `Failed to list chunks (HTTP ${response.status})` };
    }
    const data = (await response.json()) as CodeChunkListResponse;
    return { ok: true, data };
  } catch {
    return { ok: false, error: "Could not reach backend when listing chunks." };
  }
}

/** GET /api/repositories/{id}/chunks/{chunkId} — get single chunk full detail. */
export async function getChunkDetail(
  repositoryId: string,
  chunkId: string
): Promise<ApiResult<CodeChunkDetail>> {
  try {
    const response = await fetch(
      `${API_BASE_URL}/api/repositories/${repositoryId}/chunks/${chunkId}`
    );
    if (!response.ok) {
      const errorBody = (await response.json()) as ApiError;
      return { ok: false, error: errorBody.detail ?? `Failed to fetch chunk (HTTP ${response.status})` };
    }
    const data = (await response.json()) as CodeChunkDetail;
    return { ok: true, data };
  } catch {
    return { ok: false, error: "Could not reach backend when fetching chunk detail." };
  }
}

