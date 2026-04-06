"""Tests for AI backend factory and backends."""

from __future__ import annotations

from vibe_check.decoder.ai.base import BaseAIBackend
from vibe_check.decoder.ai.claude_backend import ClaudeBackend
from vibe_check.decoder.ai.factory import create_backend
from vibe_check.decoder.ai.openai_compat_backend import OpenAICompatBackend


class TestFactory:
    def test_create_none(self) -> None:
        result = create_backend("none")
        assert result is None

    def test_create_claude(self) -> None:
        result = create_backend("claude", key="test-key")
        assert isinstance(result, ClaudeBackend)
        assert isinstance(result, BaseAIBackend)

    def test_create_openai_compat(self) -> None:
        result = create_backend(
            "openai-compat",
            url="http://localhost:11434/v1",
            model="llama3",
        )
        assert isinstance(result, OpenAICompatBackend)
        assert isinstance(result, BaseAIBackend)

    def test_create_unknown(self) -> None:
        result = create_backend("unknown-backend")
        assert result is None


class TestClaudeBackend:
    def test_init_defaults(self) -> None:
        backend = ClaudeBackend()
        assert backend.name == "claude"

    def test_init_custom_model(self) -> None:
        backend = ClaudeBackend(api_key="key", model="claude-opus-4-20250514")
        assert backend._model == "claude-opus-4-20250514"

    def test_explain_file_no_api_returns_empty(self) -> None:
        backend = ClaudeBackend(api_key="invalid")
        from vibe_check.decoder.models import FileAnalysis

        fa = FileAnalysis(path="test.py", language="python", line_count=1)
        # Should not raise, just return empty string on failure
        result = backend.explain_file(fa, "x = 1")
        assert isinstance(result, str)


class TestOpenAICompatBackend:
    def test_init_defaults(self) -> None:
        backend = OpenAICompatBackend()
        assert backend.name == "openai-compat"
        assert "localhost" in backend._base_url

    def test_init_custom_url(self) -> None:
        backend = OpenAICompatBackend(
            base_url="http://192.168.1.100:8080/v1",
            model="openclaw",
        )
        assert "192.168.1.100" in backend._base_url
        assert backend._model == "openclaw"

    def test_explain_file_no_server_returns_empty(self) -> None:
        backend = OpenAICompatBackend(base_url="http://localhost:99999/v1")
        from vibe_check.decoder.models import FileAnalysis

        fa = FileAnalysis(path="test.py", language="python", line_count=1)
        result = backend.explain_file(fa, "x = 1")
        assert isinstance(result, str)
