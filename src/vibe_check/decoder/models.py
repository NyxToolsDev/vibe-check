"""Data models for the decode command."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass
class FunctionInfo:
    """Extracted information about a single function or method."""

    name: str
    start_line: int
    end_line: int
    line_count: int
    signature: str
    decorators: list[str] = field(default_factory=list)
    docstring: str | None = None
    calls: list[str] = field(default_factory=list)
    description: str = ""


@dataclass
class ClassInfo:
    """Extracted information about a single class."""

    name: str
    start_line: int
    end_line: int
    bases: list[str] = field(default_factory=list)
    methods: list[FunctionInfo] = field(default_factory=list)
    docstring: str | None = None
    description: str = ""


@dataclass
class FileAnalysis:
    """Complete analysis of a single source file."""

    path: str
    language: str
    line_count: int
    summary: str = ""
    imports: list[str] = field(default_factory=list)
    functions: list[FunctionInfo] = field(default_factory=list)
    classes: list[ClassInfo] = field(default_factory=list)
    env_vars: list[str] = field(default_factory=list)
    called_by: list[str] = field(default_factory=list)
    calls_into: list[str] = field(default_factory=list)
    entry_point: bool = False


@dataclass
class ArchitectureMap:
    """High-level architecture overview of the project."""

    entry_points: list[str] = field(default_factory=list)
    dependency_graph: dict[str, list[str]] = field(default_factory=dict)
    external_deps: list[str] = field(default_factory=list)
    config_files: list[str] = field(default_factory=list)
    env_vars: list[str] = field(default_factory=list)


@dataclass
class DecodeReport:
    """Complete decode report for a project."""

    project_path: str
    decoded_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    version: str = "0.2.0"
    ai_backend: str = "none"
    total_files: int = 0
    files_by_language: dict[str, int] = field(default_factory=dict)
    files: list[FileAnalysis] = field(default_factory=list)
    architecture: ArchitectureMap = field(default_factory=ArchitectureMap)
    ai_enhanced: bool = False
    decode_time_ms: float = 0.0
