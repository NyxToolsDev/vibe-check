"""Factory for creating AI backend instances."""

from __future__ import annotations

from vibe_check.decoder.ai.base import BaseAIBackend


def create_backend(
    backend: str,
    url: str | None = None,
    key: str | None = None,
    model: str | None = None,
) -> BaseAIBackend | None:
    """Create an AI backend instance by name.

    Args:
        backend: Backend type — "none", "claude", or "openai-compat".
        url: Base URL for the API (required for openai-compat).
        key: API key for authentication.
        model: Model name to use.

    Returns:
        A BaseAIBackend instance, or None if backend is "none".
    """
    if backend == "none":
        return None

    if backend == "claude":
        from vibe_check.decoder.ai.claude_backend import ClaudeBackend

        return ClaudeBackend(api_key=key, model=model)

    if backend == "openai-compat":
        from vibe_check.decoder.ai.openai_compat_backend import OpenAICompatBackend

        return OpenAICompatBackend(base_url=url, api_key=key, model=model)

    return None
