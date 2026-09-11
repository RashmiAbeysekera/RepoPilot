"""
Process-local in-memory rate limiter for protecting expensive AI endpoints.

DESIGN:
  - Thread-safe sliding-window counter using threading.Lock
  - Zero external infrastructure dependency (no Redis required for single-process local dev)
  - Configurable via environment variables (RATE_LIMIT_ENABLED, AI_RATE_LIMIT_PER_MINUTE)
  - Automatically purges expired timestamps to prevent unbounded memory growth

LIMITATIONS:
  - Process-local: State is stored in memory. In multi-worker or multi-process deployments,
    each worker maintains its own window counter. For horizontal scaling across instances,
    a distributed store such as Redis would be used.
"""

import logging
import threading
import time
from collections import defaultdict
from typing import Dict, List

from app.core.config import get_ai_rate_limit_per_minute, get_rate_limit_enabled
from app.core.errors import RateLimitExceededError

logger = logging.getLogger("repopilot.ratelimit")

_lock = threading.Lock()
# Maps bucket key (e.g. client IP or endpoint name) to list of request timestamps
_request_windows: Dict[str, List[float]] = defaultdict(list)


class InMemoryRateLimiter:
    """
    Sliding window rate limiter with microsecond timestamp tracking.
    """

    @classmethod
    def check_rate_limit(
        cls,
        key: str,
        max_requests: int | None = None,
        window_seconds: int = 60,
    ) -> None:
        """
        Record a request against the rate limit bucket.
        Raises RateLimitExceededError if the limit is exceeded.
        """
        if not get_rate_limit_enabled():
            return

        limit = max_requests if max_requests is not None else get_ai_rate_limit_per_minute()
        now = time.time()
        window_start = now - window_seconds

        with _lock:
            history = _request_windows[key]
            # Prune timestamps outside current sliding window
            valid_history = [ts for ts in history if ts > window_start]
            _request_windows[key] = valid_history

            if len(valid_history) >= limit:
                # Calculate how many seconds until the oldest request falls off
                oldest_in_window = valid_history[0]
                retry_after = max(1, int(oldest_in_window + window_seconds - now))
                logger.warning(
                    "Rate limit exceeded for key '%s' (%d/%d in %ds). Retry-After: %ds",
                    key,
                    len(valid_history),
                    limit,
                    window_seconds,
                    retry_after,
                )
                raise RateLimitExceededError(
                    message=f"Rate limit exceeded for AI operations ({limit} requests/minute). Please wait {retry_after}s.",
                    retry_after=retry_after,
                )

            # Record this request
            _request_windows[key].append(now)

    @classmethod
    def reset(cls) -> None:
        """Clear all rate limit buckets (useful for unit tests)."""
        with _lock:
            _request_windows.clear()
