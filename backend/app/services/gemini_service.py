"""
Gemini LLM Service — Integration layer for Google Gemini API.

RESPONSIBILITIES:
  - Read configuration (GEMINI_API_KEY, GEMINI_MODEL) from central config
  - Initialize official Google GenAI client (google-genai SDK)
  - Receive system instructions and user prompt
  - Execute generation request
  - Return generated answer text
  - Handle API errors (missing key, quota exceeded, invalid model, network failures)
  - Never expose API credentials in logs or client-facing responses
"""

import logging
import time
from collections.abc import Callable
from typing import Any

from app.core.config import get_gemini_api_key, get_gemini_max_retries, get_gemini_model

logger = logging.getLogger("repopilot.gemini")


def get_gemini_client():
    """
    Initialize and return a google.genai.Client instance using GEMINI_API_KEY.

    Raises:
        ValueError: If GEMINI_API_KEY is missing or unconfigured.
    """
    api_key = get_gemini_api_key()
    if not api_key:
        logger.error("Gemini API call failed: GEMINI_API_KEY is not set.")
        raise ValueError(
            "Gemini API key is not configured. Please set GEMINI_API_KEY in the backend .env file."
        )

    try:
        from google import genai
        return genai.Client(api_key=api_key)
    except Exception as error:
        logger.error("Failed to initialize Google GenAI client: %s", error)
        raise ValueError(f"Failed to initialize Gemini client: {error}") from error


def check_gemini_health() -> str:
    """
    Check if Gemini AI integration is configured.

    Returns:
        'healthy' if API key is present and configured,
        'not-configured' if API key is missing.
    """
    api_key = get_gemini_api_key()
    return "healthy" if api_key else "not-configured"


def is_transient_gemini_error(error: Exception) -> bool:
    """
    Determine if a Gemini API error is transient and safe to retry.

    Transient errors include:
      - HTTP 503 / UNAVAILABLE / model capacity / high demand
      - HTTP 429 / RESOURCE_EXHAUSTED / temporary rate-limiting spikes
    Non-transient errors (invalid keys, auth failures, invalid arguments) fail immediately.
    """
    err_str = str(error).lower()
    transient_indicators = [
        "503",
        "unavailable",
        "high demand",
        "resource_exhausted",
        "429",
        "deadline_exceeded",
        "timeout",
    ]
    return any(indicator in err_str for indicator in transient_indicators)


def classify_gemini_error(error: Exception) -> str:
    """
    Format user-friendly, non-leaking diagnostic message for Gemini failures.
    Always prefixed with 'Gemini API generation failed: ' for consistent error trapping.
    """
    err_str = str(error).lower()
    if "503" in err_str or "unavailable" in err_str or "high demand" in err_str:
        return (
            "Gemini API generation failed: Gemini service temporarily unavailable (503). "
            "The model is experiencing high demand. Please try again in a moment."
        )
    if "429" in err_str or "resource_exhausted" in err_str:
        return (
            "Gemini API generation failed: Rate limit or quota exceeded (429). "
            "Please try again in a moment."
        )
    if "401" in err_str or "403" in err_str or "api_key_invalid" in err_str or "permission_denied" in err_str:
        return (
            "Gemini API generation failed: Authentication failed. "
            "Please verify GEMINI_API_KEY in backend/.env."
        )
    return f"Gemini API generation failed: {error}"


def call_gemini_with_retry(
    call_fn: Callable[[], Any],
    max_retries: int | None = None,
    initial_delay: float = 1.0,
    backoff_factor: float = 2.0,
    max_delay: float = 8.0,
) -> Any:
    """
    Execute a callable Gemini operation with bounded exponential backoff for transient errors.

    Args:
        call_fn: Zero-argument callable executing the Gemini API call.
        max_retries: Maximum number of retries (defaults to GEMINI_MAX_RETRIES from config).
        initial_delay: Initial sleep duration in seconds.
        backoff_factor: Exponential multiplier.
        max_delay: Maximum sleep duration cap in seconds.

    Returns:
        Result of call_fn().

    Raises:
        ValueError: When retries are exhausted or a non-transient error occurs.
    """
    retries = max_retries if max_retries is not None else get_gemini_max_retries()
    delay = initial_delay

    for attempt in range(1, retries + 2):
        try:
            return call_fn()
        except Exception as error:
            # Check if this error is transient and we have retries remaining
            if attempt <= retries and is_transient_gemini_error(error):
                current_delay = delay
                err_lower = str(error).lower()
                # For 429 rate limit or quota exceeded, back off with higher delay
                if "429" in err_lower or "resource_exhausted" in err_lower:
                    current_delay = max(delay, 2.5)

                logger.warning(
                    "Gemini API transient error on attempt %d/%d (%s). Retrying in %.2fs...",
                    attempt,
                    retries + 1,
                    error,
                    current_delay,
                )
                time.sleep(current_delay)
                delay = min(max_delay, current_delay * backoff_factor)
            else:
                formatted_msg = classify_gemini_error(error)
                logger.error("Gemini API call failed permanently (attempt %d): %s", attempt, formatted_msg)
                raise ValueError(formatted_msg) from error


def generate_rag_answer(
    system_instruction: str,
    user_prompt: str,
    model_name: str | None = None,
) -> str:
    """
    Send a structured generation request to Gemini for RAG answer generation
    with bounded retry on transient capacity/rate errors.

    Args:
        system_instruction: High-priority system instructions guiding Gemini persona and constraints.
        user_prompt: Structured prompt containing retrieved code context and user question.
        model_name: Optional override for Gemini model. Defaults to config GEMINI_MODEL.

    Returns:
        Generated answer text string.

    Raises:
        ValueError: If API key is missing or request fails due to API error.
    """
    target_model = model_name or get_gemini_model()
    client = get_gemini_client()

    logger.info("Sending RAG generation request to Gemini model '%s'...", target_model)

    from google.genai import types

    config = types.GenerateContentConfig(
        system_instruction=system_instruction,
        temperature=0.2,  # Low temperature for precise, code-grounded answers
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
    )

    def _execute():
        resp = client.models.generate_content(
            model=target_model,
            contents=user_prompt,
            config=config,
        )
        if not resp or not resp.text:
            logger.warning("Gemini API returned empty response for model '%s'.", target_model)
            raise ValueError("Gemini API returned an empty answer.")
        return resp.text.strip()

    answer_text = call_gemini_with_retry(_execute)
    logger.info(
        "Successfully generated answer from Gemini model '%s' (%d characters).",
        target_model,
        len(answer_text),
    )
    return answer_text

