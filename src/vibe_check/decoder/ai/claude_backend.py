"""Anthropic Claude API backend for AI-enhanced explanations."""

from __future__ import annotations

import logging

import httpx

from vibe_check.decoder.ai.base import BaseAIBackend
from vibe_check.decoder.models import FileAnalysis, FunctionInfo

logger = logging.getLogger(__name__)

_DEFAULT_MODEL = "claude-sonnet-4-20250514"
_API_URL = "https://api.anthropic.com/v1/messages"
_API_VERSION = "2023-06-01"
_TIMEOUT = 30.0
_MAX_SOURCE_CHARS = 8000


class ClaudeBackend(BaseAIBackend):
    """AI backend using the Anthropic Messages API via httpx."""

    name = "claude"

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
    ) -> None:
        self._api_key = api_key or ""
        self._model = model or _DEFAULT_MODEL

    def explain_file(self, file_analysis: FileAnalysis, source: str) -> str:
        truncated = source[:_MAX_SOURCE_CHARS]
        prompt = (
            f"You are a code documentation assistant. Given the following source file "
            f"and its metadata, write a 2-3 sentence plain-English explanation of what "
            f"this file does and why it exists.\n\n"
            f"File: {file_analysis.path}\n"
            f"Language: {file_analysis.language}\n"
            f"Imports: {', '.join(file_analysis.imports[:20])}\n"
            f"Functions: {', '.join(f.name for f in file_analysis.functions[:20])}\n"
            f"Classes: {', '.join(c.name for c in file_analysis.classes[:10])}\n\n"
            f"Source code:\n```\n{truncated}\n```"
        )
        return self._call(prompt)

    def explain_function(
        self, func: FunctionInfo, source: str, file_context: str,
    ) -> str:
        # Extract just the function source
        lines = source.splitlines()
        start = max(0, func.start_line - 1)
        end = min(len(lines), func.end_line)
        func_source = "\n".join(lines[start:end])[:4000]

        prompt = (
            f"You are a code documentation assistant. Write a 1-2 sentence "
            f"plain-English explanation of what this function does.\n\n"
            f"File context: {file_context}\n"
            f"Function: {func.signature}\n"
            f"Decorators: {', '.join(func.decorators) if func.decorators else 'none'}\n\n"
            f"Source:\n```\n{func_source}\n```"
        )
        return self._call(prompt)

    def _call(self, prompt: str) -> str:
        """Make an API call to the Anthropic Messages API."""
        try:
            response = httpx.post(
                _API_URL,
                headers={
                    "x-api-key": self._api_key,
                    "anthropic-version": _API_VERSION,
                    "content-type": "application/json",
                },
                json={
                    "model": self._model,
                    "max_tokens": 256,
                    "messages": [{"role": "user", "content": prompt}],
                },
                timeout=_TIMEOUT,
            )
            if response.status_code != 200:
                logger.warning("Claude API returned %d", response.status_code)
                return ""
            data = response.json()
            content = data.get("content", [])
            if content and content[0].get("type") == "text":
                return content[0]["text"].strip()
            return ""
        except (httpx.HTTPError, OSError, ValueError, KeyError) as exc:
            logger.warning("Claude API call failed: %s", exc)
            return ""
