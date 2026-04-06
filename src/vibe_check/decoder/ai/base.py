"""Abstract base class for AI backends."""

from __future__ import annotations

from abc import ABC, abstractmethod

from vibe_check.decoder.models import FileAnalysis, FunctionInfo


class BaseAIBackend(ABC):
    """Base class for AI-enhanced code explanation backends."""

    name: str = "unknown"

    @abstractmethod
    def explain_file(self, file_analysis: FileAnalysis, source: str) -> str:
        """Generate a plain-English explanation of what a file does.

        Args:
            file_analysis: Static analysis results for the file.
            source: Full source code of the file.

        Returns:
            A 2-3 sentence explanation, or empty string on failure.
        """

    @abstractmethod
    def explain_function(
        self, func: FunctionInfo, source: str, file_context: str,
    ) -> str:
        """Generate a plain-English explanation of what a function does.

        Args:
            func: Static analysis results for the function.
            source: Full source code of the file containing the function.
            file_context: Summary of the file for context.

        Returns:
            A 1-2 sentence explanation, or empty string on failure.
        """
