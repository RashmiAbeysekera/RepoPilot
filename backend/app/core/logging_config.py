"""
Structured application logging and security filters for RepoPilot.

RESPONSIBILITIES:
  - Structured key-value logging for operational auditability
  - Secret scrubbing filter ensuring credentials never leak to stdout/logs
  - Request timing and latency reporting
"""

import json
import logging
import re
from typing import Any

# Sensitive keys and patterns to scrub
SENSITIVE_KEY_NAMES = {
    "gemini_api_key",
    "google_api_key",
    "github_token",
    "github_webhook_secret",
    "database_url",
    "password",
    "secret",
    "token",
    "authorization",
    "api_key",
}

# Regex for common token shapes (e.g. AI Studio keys, GitHub personal tokens)
TOKEN_PATTERNS = [
    re.compile(r"AIza[0-9A-Za-z-_]{35}"),
    re.compile(r"ghp_[0-9A-Za-z]{36}"),
    re.compile(r"ghs_[0-9A-Za-z]{36}"),
    re.compile(r"postgres://[^@]+@"),
    re.compile(r"postgresql://[^@]+@"),
]


class SecretScrubbingFilter(logging.Filter):
    """
    Logging filter that intercepts log records and scrubs any sensitive credentials.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = self.scrub_text(record.msg)
        if record.args:
            if isinstance(record.args, dict):
                record.args = {k: self.scrub_value(k, v) for k, v in record.args.items()}
            elif isinstance(record.args, tuple):
                record.args = tuple(self.scrub_text(str(a)) if isinstance(a, str) else a for a in record.args)
        return True

    @classmethod
    def scrub_text(cls, text: str) -> str:
        for pattern in TOKEN_PATTERNS:
            text = pattern.sub("[REDACTED_CREDENTIAL]", text)
        return text

    @classmethod
    def scrub_value(cls, key: str, value: Any) -> Any:
        if any(sens in key.lower() for sens in SENSITIVE_KEY_NAMES):
            return "[REDACTED]"
        if isinstance(value, str):
            return cls.scrub_text(value)
        return value


def log_event(logger_instance: logging.Logger, event: str, level: int = logging.INFO, **kwargs: Any) -> None:
    """
    Log a structured event in readable key=value format while scrubbing secrets.

    Example output:
      INFO [event=retrieval_completed] repository_id=4e353f65 results=5 top_similarity=0.78 duration_ms=142
    """
    safe_kwargs = {}
    for k, v in kwargs.items():
        if any(sens in k.lower() for sens in SENSITIVE_KEY_NAMES):
            safe_kwargs[k] = "[REDACTED]"
        elif isinstance(v, str):
            safe_kwargs[k] = SecretScrubbingFilter.scrub_text(v)
        else:
            safe_kwargs[k] = v

    kv_parts = [f"{k}={v}" for k, v in safe_kwargs.items()]
    kv_str = " ".join(kv_parts) if kv_parts else ""
    msg = f"[event={event}] {kv_str}".strip()
    logger_instance.log(level, msg)
