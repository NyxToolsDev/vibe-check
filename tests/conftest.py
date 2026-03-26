"""Shared test fixtures for vibe-check."""

from __future__ import annotations

import ast
import textwrap
from pathlib import Path

import pytest

from vibe_check.parsers.file_walker import FileInfo


@pytest.fixture()
def tmp_project(tmp_path: Path) -> Path:
    """Create a minimal project directory for scanning."""
    return tmp_path


def make_file(
    tmp_path: Path,
    name: str,
    content: str,
    language: str = "python",
) -> FileInfo:
    """Helper to create a FileInfo with given content."""
    p = tmp_path / name
    p.parent.mkdir(parents=True, exist_ok=True)
    dedented = textwrap.dedent(content)
    p.write_text(dedented, encoding="utf-8")
    return FileInfo(path=p, language=language, _content=dedented)


def parse_python(content: str) -> ast.Module:
    """Parse a Python string into an AST."""
    return ast.parse(textwrap.dedent(content))
