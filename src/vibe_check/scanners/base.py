"""Abstract base class for all scanners."""

from __future__ import annotations

import ast
from abc import ABC, abstractmethod
from pathlib import Path

from vibe_check.engine.models import Category, Finding
from vibe_check.parsers.file_walker import FileInfo


class BaseScanner(ABC):
    """Base class that all scanners must implement."""

    @property
    @abstractmethod
    def category(self) -> Category:
        """The category this scanner belongs to."""

    @abstractmethod
    def scan(
        self,
        files: list[FileInfo],
        python_asts: dict[Path, ast.Module],
        project_path: Path,
    ) -> list[Finding]:
        """Run the scanner and return findings.

        Args:
            files: Discovered source files.
            python_asts: Pre-parsed Python ASTs keyed by path.
            project_path: Root of the project being scanned.

        Returns:
            List of findings (issues) discovered.
        """
