"""Data models for vibe-check scan results."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Literal

Severity = Literal["info", "warn", "fail"]
Category = Literal[
    "security", "testing", "code_quality", "architecture", "dependencies", "hipaa"
]
Grade = Literal["A", "B", "C", "D", "F"]


@dataclass
class Finding:
    """A single issue discovered by a scanner."""

    rule_id: str
    category: Category
    severity: Severity
    message: str
    file_path: str = ""
    line_number: int = 0
    suggestion: str = ""
    snippet: str = ""


@dataclass
class CategoryResult:
    """Aggregated results for one scan category."""

    category: Category
    findings: list[Finding]
    score: int
    grade: Grade
    scan_time_ms: float


@dataclass
class ScanReport:
    """Complete scan report for a project."""

    project_path: str
    scanned_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    total_files: int = 0
    files_by_language: dict[str, int] = field(default_factory=dict)
    categories: list[CategoryResult] = field(default_factory=list)
    overall_score: int = 100
    overall_grade: Grade = "A"
    total_scan_time_ms: float = 0.0
    version: str = "0.1.0"
    licensed: bool = False
