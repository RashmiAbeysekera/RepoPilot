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
from typing import Any

from app.core.config import GEMINI_API_KEY, GEMINI_MODEL

logger = logging.getLogger("repopilot.gemini")


def get_gemini_client():
    """
    Initialize and return a google.genai.Client instance using GEMINI_API_KEY.

    Raises:
        ValueError: If GEMINI_API_KEY is missing or unconfigured.
    """
    if not GEMINI_API_KEY or not GEMINI_API_KEY.strip():
        logger.error("Gemini API call failed: GEMINI_API_KEY is not set.")
        raise ValueError(
            "Gemini API key is not configured. Please set GEMINI_API_KEY in the backend .env file."
        )

    try:
        from google import genai
        return genai.Client(api_key=GEMINI_API_KEY.strip())
    except Exception as error:
        logger.error("Failed to initialize Google GenAI client: %s", error)
        raise ValueError(f"Failed to initialize Gemini client: {error}") from error


def generate_rag_answer(
    system_instruction: str,
    user_prompt: str,
    model_name: str | None = None,
) -> str:
    """
    Send a structured generation request to Gemini for RAG answer generation.

    Args:
        system_instruction: High-priority system instructions guiding Gemini persona and constraints.
        user_prompt: Structured prompt containing retrieved code context and user question.
        model_name: Optional override for Gemini model. Defaults to config GEMINI_MODEL.

    Returns:
        Generated answer text string.

    Raises:
        ValueError: If API key is missing or request fails due to API error.
    """
    target_model = model_name or GEMINI_MODEL

    client = get_gemini_client()

    logger.info("Sending RAG generation request to Gemini model '%s'...", target_model)

    try:
        from google.genai import types

        config = types.GenerateContentConfig(
            system_instruction=system_instruction,
            temperature=0.2,  # Low temperature for precise, code-grounded answers
        )

        response = client.models.generate_content(
            model=target_model,
            contents=user_prompt,
            config=config,
        )

        if not response or not response.text:
            logger.warning("Gemini API returned empty response for model '%s'.", target_model)
            raise ValueError("Gemini API returned an empty answer.")

        answer_text = response.text.strip()
        logger.info(
            "Successfully generated answer from Gemini model '%s' (%d characters).",
            target_model,
            len(answer_text),
        )
        return answer_text

    except ValueError:
        raise
    except Exception as error:
        err_msg = str(error)
        logger.error("Gemini API call to model '%s' failed: %s", target_model, err_msg)
        raise ValueError(f"Gemini API generation failed: {err_msg}") from error
