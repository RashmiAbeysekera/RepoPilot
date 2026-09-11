"""
GitHub Service — Communicates with the public GitHub REST API.

RESPONSIBILITIES:
  - Parse and validate public GitHub repository URLs
  - Retrieve repository metadata (name, full_name, description, default_branch)
  - Retrieve directory and file tree listings from GitHub's REST API

This service does NOT manage database persistence or HTTP routing.
It strictly encapsulates external communication with GitHub.
"""

import base64
import time
from urllib.parse import urlparse
import httpx

GITHUB_API_BASE = "https://api.github.com"
DEFAULT_TIMEOUT = 10.0  # seconds

# In-memory cache for health probe to prevent excessive external requests
_github_health_cache: dict[str, float | str] = {"status": "healthy", "timestamp": 0.0}


class GitHubServiceError(ValueError):
    """Base exception for all GitHub service errors."""
    pass


class GitHubResourceNotFoundError(GitHubServiceError):
    """Raised when a repository, directory path, or file is not found (HTTP 404)."""
    pass


class GitHubAPIError(GitHubServiceError):
    """Raised when an external API, network, rate limit (HTTP 403), or timeout occurs."""
    pass


def parse_github_url(github_url: str) -> tuple[str, str]:
    """
    Extract (owner, repo) from a public GitHub URL.

    Supported examples:
        - "https://github.com/owner/repository"
        - "https://github.com/owner/repository.git"
        - "https://github.com/owner/repository/"

    Rejects:
        - Non-GitHub domains ("https://google.com", "https://youtube.com/example")
        - Plain strings without owner/repo ("hello")
        - Incomplete GitHub URLs ("https://github.com/owner")
    """
    url_str = str(github_url).strip()
    if not url_str.startswith(("http://", "https://")):
        url_str = f"https://{url_str}"

    parsed = urlparse(url_str)

    # Must be hosted on github.com
    hostname = (parsed.netloc or "").lower().split(":")[0]
    if hostname not in ("github.com", "www.github.com"):
        raise ValueError(f"URL must be a valid GitHub repository link. Got domain: '{hostname}'")

    # Clean path segments
    path = parsed.path.strip("/").removesuffix(".git")
    parts = [p for p in path.split("/") if p]

    if len(parts) < 2:
        raise ValueError(f"GitHub URL must contain both owner and repository name (e.g. 'https://github.com/owner/repo'). Got: '{github_url}'")

    owner = parts[0]
    repo = parts[1]

    return owner, repo


def fetch_repository_metadata(owner: str, repo: str) -> dict:
    """
    Fetch metadata for a public repository from GitHub REST API.

    GET https://api.github.com/repos/{owner}/{repo}

    Raises:
        ValueError: On 404 (not found), 403 (rate limit/forbidden), or network/timeout failures.
    """
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "RepoPilot-AI",
    }
    url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}"

    try:
        with httpx.Client(timeout=DEFAULT_TIMEOUT) as client:
            response = client.get(url, headers=headers)
    except httpx.TimeoutException as err:
        raise GitHubAPIError(f"GitHub API request timed out for '{owner}/{repo}'.") from err
    except httpx.RequestError as err:
        raise GitHubAPIError(f"Could not connect to GitHub API: {err}") from err

    if response.status_code == 200:
        data = response.json()
        return {
            "name": data.get("name", repo),
            "full_name": data.get("full_name", f"{owner}/{repo}"),
            "github_url": data.get("html_url", f"https://github.com/{owner}/{repo}"),
            "description": data.get("description"),
            "default_branch": data.get("default_branch", "main"),
        }
    elif response.status_code == 404:
        raise GitHubResourceNotFoundError(f"GitHub repository '{owner}/{repo}' not found or is private.")
    elif response.status_code == 403:
        raise GitHubAPIError("GitHub API rate limit exceeded. Please try again later.")
    else:
        raise GitHubAPIError(f"GitHub API error (HTTP {response.status_code}).")


def fetch_repository_contents(owner: str, repo: str, path: str = "") -> list[dict] | dict:
    """
    Fetch content listing for a path inside a public GitHub repository.

    GET https://api.github.com/repos/{owner}/{repo}/contents/{path}

    Returns a list of item dictionaries for directory listings,
    or a single item dictionary for a file.
    """
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "RepoPilot-AI",
    }
    clean_path = path.strip("/")
    url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/contents/{clean_path}" if clean_path else f"{GITHUB_API_BASE}/repos/{owner}/{repo}/contents"

    try:
        with httpx.Client(timeout=DEFAULT_TIMEOUT) as client:
            response = client.get(url, headers=headers)
    except httpx.TimeoutException as err:
        raise GitHubAPIError(f"GitHub API request timed out fetching contents for path '{path}'.") from err
    except httpx.RequestError as err:
        raise GitHubAPIError(f"Could not connect to GitHub API: {err}") from err

    if response.status_code == 200:
        return response.json()
    elif response.status_code == 404:
        # Check if this 404 is because the repository genuinely has 0 files/commits
        try:
            error_data = response.json()
            msg = str(error_data.get("message", "")).lower()
            if "empty" in msg and not clean_path:
                return []
        except Exception:
            pass
        raise GitHubResourceNotFoundError(f"Path '{path}' not found in repository '{owner}/{repo}'.")
    elif response.status_code == 403:
        raise GitHubAPIError("GitHub API rate limit exceeded.")
    else:
        raise GitHubAPIError(f"GitHub API returned HTTP {response.status_code} for path '{path}'.")


def fetch_file_content(owner: str, repo: str, path: str) -> str | None:
    """
    Fetch and decode text content for a file from GitHub REST API.
    Decodes base64 content if returned, or falls back to download_url.

    Returns:
        Decoded text string if successfully fetched, or None if the file
        cannot be decoded (binary/non-UTF-8).

    Raises:
        GitHubResourceNotFoundError: If the file does not exist on GitHub (HTTP 404).
        GitHubAPIError: If an external API, network, rate limit (403), or timeout error occurs.
    """
    try:
        data = fetch_repository_contents(owner, repo, path)
    except GitHubResourceNotFoundError:
        raise
    except ValueError as err:
        err_msg = str(err).lower()
        if "not found" in err_msg or "404" in err_msg:
            raise GitHubResourceNotFoundError(f"File '{path}' not found in repository '{owner}/{repo}'.") from err
        raise GitHubAPIError(str(err)) from err

    if not isinstance(data, dict):
        return None

    encoding = data.get("encoding")
    content_raw = data.get("content")

    if encoding == "base64" and content_raw is not None:
        try:
            decoded_bytes = base64.b64decode(content_raw)
            return decoded_bytes.decode("utf-8")
        except (ValueError, UnicodeDecodeError):
            # Non-decodable / binary file
            return None

    download_url = data.get("download_url")
    if download_url:
        try:
            with httpx.Client(timeout=DEFAULT_TIMEOUT) as client:
                res = client.get(download_url)
                if res.status_code == 200:
                    return res.text
                elif res.status_code == 404:
                    raise GitHubResourceNotFoundError(f"File '{path}' download not found.")
                elif res.status_code == 403:
                    raise GitHubAPIError("GitHub API rate limit exceeded.")
                else:
                    raise GitHubAPIError(f"GitHub API returned HTTP {res.status_code} downloading '{path}'.")
        except httpx.TimeoutException as err:
            raise GitHubAPIError(f"GitHub API request timed out downloading file '{path}'.") from err
        except httpx.RequestError as err:
            raise GitHubAPIError(f"Could not connect to GitHub API downloading file '{path}': {err}") from err

    return None


def check_github_health(cache_ttl: float = 0.0) -> str:
    """
    Check connectivity to the public GitHub REST API.
    Optionally uses an in-memory TTL cache when cache_ttl > 0 to avoid excessive outbound requests.

    Returns:
        'healthy' if GitHub API is reachable,
        'unavailable' if network or timeout failure occurs.
    """
    now = time.time()
    last_ts = float(_github_health_cache.get("timestamp", 0.0))
    if cache_ttl > 0.0 and (now - last_ts < cache_ttl) and _github_health_cache.get("status"):
        return str(_github_health_cache["status"])

    headers = {
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "RepoPilot-AI",
    }
    status_result = "unavailable"
    try:
        with httpx.Client(timeout=4.0) as client:
            resp = client.get(f"{GITHUB_API_BASE}/zen", headers=headers)
            # 200 or 403 (rate limited) both confirm the GitHub API is reachable
            if resp.status_code in (200, 403):
                status_result = "healthy"
    except Exception:
        status_result = "unavailable"

    _github_health_cache["status"] = status_result
    _github_health_cache["timestamp"] = now
    return status_result

