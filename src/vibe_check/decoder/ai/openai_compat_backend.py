"""OpenAI-compatible API backend for local models (Ollama, LM Studio, etc.)."""

from __future__ import annotations

import logging

import httpx

from vibe_check.decoder.ai.base import BaseAIBackend
from vibe_check.decoder.models import FileAnalysis, FunctionInfo

logger = logging.getLogger(__name__)

_DEFAULT_MODEL = "llama3"
_DEFAULT_URL = "http://localhost:11434/v1"
_TIMEOUT = 60.0  # Local models can be slower
_MAX_SOURCE_CHARS = 6000


class OpenAICompatBackend(BaseAIBackend):
    """AI backend using OpenAI-compatible chat completions API.

    Works with Ollama, LM Studio, vLLM, or any server exposing
    POST /v1/chat/completions in the OpenAI format.
    """

    name = "openai-compat"

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
    ) -> None:
        self._base_url = (base_url or _DEFAULT_URL).rstrip("/")
        self._api_key = api_key or "not-needed"
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
        lines = source.splitlines()
        start = max(0, func.start_line - 1)
        end = min(len(lines), func.end_line)
        func_source = "\n".join(lines[start:end])[:4000]

        prompt = (
            f"You are a code documentation assistant. Write a 1-2 sentence "
            f"plain-English explanation of what this function does.\n\n"
            f"File context: {file_context}\n"
            f"Function: {func.signature}\n\n"
            f"Source:\n```\n{func_source}\n```"
        )
        return self._call(prompt)

    def _call(self, prompt: str) -> str:
        """Make a call to the OpenAI-compatible chat completions endpoint."""
        url = f"{self._base_url}/chat/completions"
        try:
            response = httpx.post(
                url,
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self._model,
                    "max_tokens": 256,
                    "messages": [
                        {
                            "role": "system",
                            "content": "You are a concise code documentation assistant. "
                            "Explain code in plain English.",
                        },
                        {"role": "user", "content": prompt},
                    ],
                },
                timeout=_TIMEOUT,
            )
            if response.status_code != 200:
                logger.warning(
                    "OpenAI-compat API at %s returned %d", url, response.status_code,
                )
                return ""
            data = response.json()
            choices = data.get("choices", [])
            if choices:
                return choices[0].get("message", {}).get("content", "").strip()
            return ""
        except (httpx.HTTPError, OSError, ValueError, KeyError) as exc:
            logger.warning("OpenAI-compat API call failed: %s", exc)
            return ""
