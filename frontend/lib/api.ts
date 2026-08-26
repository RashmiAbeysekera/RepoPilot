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

/** POST /api/repositories — add a new repository. */
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
