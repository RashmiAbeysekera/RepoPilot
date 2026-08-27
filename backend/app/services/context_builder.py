"""
Context Builder Service — Transforms retrieved code chunks into structured prompt context.

RESPONSIBILITIES:
  - Format individual code chunks with clear source metadata header (file path, line range, score)
  - Separate untrusted repository data from system instructions
  - Enforce deterministic context character/token limits to prevent prompt blowup
  - Preserve source traceability for downstream display
"""

import logging
from typing import Any

logger = logging.getLogger("repopilot.context_builder")

# Reasonable maximum character limit for constructed repository context (~3,000 tokens)
DEFAULT_MAX_CONTEXT_CHARS = 12000


def build_rag_context(
    chunks: list[dict[str, Any]],
    max_context_chars: int = DEFAULT_MAX_CONTEXT_CHARS,
) -> str:
    """
    Build a single formatted repository context string from a list of retrieved chunk dictionaries.

    Args:
        chunks: List of chunk dicts returned by search_service.search_repository_chunks.
                Each dict contains: file_path, start_line, end_line, score, content, chunk_index.
        max_context_chars: Upper character bound for total context section.

    Returns:
        Structured context string ready for inclusion in the RAG prompt.
    """
    if not chunks:
        return "No relevant repository code context available."

    formatted_sources: list[str] = []
    current_char_count = 0

    for idx, chunk in enumerate(chunks, start=1):
        file_path = chunk.get("file_path", "unknown")
        start_line = chunk.get("start_line", 1)
        end_line = chunk.get("end_line", 1)
        score = chunk.get("score", 0.0)
        content = chunk.get("content", "").strip()

        source_block = (
            f"--- Source {idx} ---\n"
            f"File: {file_path}\n"
            f"Lines: {start_line}-{end_line}\n"
            f"Relevance Score: {score:.4f}\n\n"
            f"```\n"
            f"{content}\n"
            f"```"
        )

        block_len = len(source_block)

        # Check if adding this block exceeds character limit
        if current_char_count + block_len > max_context_chars:
            logger.warning(
                "Context limit (%d chars) reached at source %d of %d. Truncating context.",
                max_context_chars,
                idx,
                len(chunks),
            )
            # If it's the very first source and it exceeds limit, truncate content deterministically
            if not formatted_sources:
                truncated_content = content[: max_context_chars - 200]
                truncated_block = (
                    f"--- Source {idx} (Truncated) ---\n"
                    f"File: {file_path}\n"
                    f"Lines: {start_line}-{end_line}\n"
                    f"Relevance Score: {score:.4f}\n\n"
                    f"```\n"
                    f"{truncated_content}\n"
                    f"... [Content truncated due to context limits]\n"
                    f"```"
                )
                formatted_sources.append(truncated_block)
            break

        formatted_sources.append(source_block)
        current_char_count += block_len + 2  # plus separator newlines

    return "\n\n".join(formatted_sources)
