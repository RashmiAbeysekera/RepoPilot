"""
GitHub Service — Communicates with the public GitHub REST API.

RESPONSIBILITIES:
  - Parse and validate public GitHub repository URLs
  - Retrieve repository metadata (name, full_name, description, default_branch)
  - Retrieve directory and file tree listings from GitHub's REST API

This service does NOT manage database persistence or HTTP routing.
It strictly encapsulates external communication with GitHub.
"""

from urllib.parse import urlparse
import httpx

GITHUB_API_BASE = "https://api.github.com"
DEFAULT_TIMEOUT = 10.0  # seconds


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
        raise ValueError(f"GitHub API request timed out for '{owner}/{repo}'.") from err
    except httpx.RequestError as err:
        raise ValueError(f"Could not connect to GitHub API: {err}") from err

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
        raise ValueError(f"GitHub repository '{owner}/{repo}' not found or is private.")
    elif response.status_code == 403:
        raise ValueError("GitHub API rate limit exceeded. Please try again later.")
    else:
        raise ValueError(f"GitHub API error (HTTP {response.status_code}).")


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
        raise ValueError(f"GitHub API request timed out fetching contents for path '{path}'.") from err
    except httpx.RequestError as err:
        raise ValueError(f"Could not connect to GitHub API: {err}") from err

    if response.status_code == 200:
        return response.json()
    elif response.status_code == 404:
        raise ValueError(f"Path '{path}' not found in repository '{owner}/{repo}'.")
    elif response.status_code == 403:
        raise ValueError("GitHub API rate limit exceeded.")
    else:
        raise ValueError(f"GitHub API returned HTTP {response.status_code} for path '{path}'.")
