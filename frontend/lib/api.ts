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
