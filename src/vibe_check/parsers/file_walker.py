"""File discovery with .gitignore support."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

import pathspec

SKIP_DIRS: set[str] = {
    "node_modules",
    "venv",
    ".venv",
    ".git",
    "__pycache__",
    "dist",
    "build",
    ".egg-info",
    ".eggs",
    ".tox",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
}

LANGUAGE_EXTENSIONS: dict[str, str] = {
    ".py": "python",
    ".js": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".jsx": "javascript",
    ".go": "go",
    ".java": "java",
    ".rb": "ruby",
    ".rs": "rust",
}

MAX_FILE_SIZE = 1_048_576  # 1 MB


@dataclass
class FileInfo:
    """Discovered source file with lazy content loading."""

    path: Path
    language: str
    _content: str | None = field(default=None, repr=False)

    @property
    def content(self) -> str:
        """Lazily read file content, capped at 1 MB."""
        if self._content is None:
            try:
                size = self.path.stat().st_size
                if size > MAX_FILE_SIZE:
                    self._content = ""
                else:
                    self._content = self.path.read_text(
                        encoding="utf-8", errors="ignore"
                    )
            except OSError:
                self._content = ""
        return self._content


def _load_gitignore(project_path: Path) -> pathspec.PathSpec | None:
    """Load .gitignore patterns from the project root."""
    gitignore = project_path / ".gitignore"
    if gitignore.is_file():
        try:
            text = gitignore.read_text(encoding="utf-8", errors="ignore")
            return pathspec.PathSpec.from_lines("gitwildmatch", text.splitlines())
        except OSError:
            pass
    return None


def _should_skip_dir(name: str) -> bool:
    """Check if a directory name should be skipped."""
    if name in SKIP_DIRS:
        return True
    if name.endswith(".egg-info"):
        return True
    return False


def walk_files(project_path: Path) -> Iterator[FileInfo]:
    """Walk a project directory yielding source files.

    Respects .gitignore, skips common non-source directories,
    and only yields files with recognized language extensions.
    """
    gitignore_spec = _load_gitignore(project_path)

    for root, dirs, files in os.walk(project_path):
        root_path = Path(root)

        # Filter out directories we want to skip (in-place mutation)
        dirs[:] = [
            d
            for d in dirs
            if not _should_skip_dir(d)
        ]

        for filename in files:
            file_path = root_path / filename
            ext = file_path.suffix.lower()
            language = LANGUAGE_EXTENSIONS.get(ext)
            if language is None:
                continue

            # Check gitignore
            if gitignore_spec is not None:
                try:
                    rel = file_path.relative_to(project_path).as_posix()
                    if gitignore_spec.match_file(rel):
                        continue
                except ValueError:
                    pass

            yield FileInfo(path=file_path, language=language)
