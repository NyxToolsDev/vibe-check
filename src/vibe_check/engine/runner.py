"""Scan orchestrator — coordinates file discovery, parsing, and scanning."""

from __future__ import annotations

import time
from pathlib import Path

import vibe_check.scanners  # noqa: F401 — trigger scanner registration
from vibe_check.engine.models import CategoryResult, ScanReport
from vibe_check.engine.registry import get_all_scanners
from vibe_check.engine.scoring import calculate_overall, score_category
from vibe_check.parsers.file_walker import FileInfo, walk_files
from vibe_check.parsers.python_parser import parse_file


def run_scan(
    project_path: Path,
    categories: list[str] | None = None,
    licensed: bool = False,
) -> ScanReport:
    """Run a full scan on the given project directory.

    Args:
        project_path: Root directory of the project to scan.
        categories: Specific categories to scan, or None for all.
        licensed: Whether the user has a Pro license (enables HIPAA).

    Returns:
        Complete ScanReport with all findings and grades.
    """
    total_start = time.perf_counter()

    # Discover files
    files = list(walk_files(project_path))
    files_by_language = _count_languages(files)

    # Parse Python ASTs
    python_asts = {}
    for fi in files:
        if fi.language == "python":
            tree = parse_file(fi.path)
            if tree is not None:
                python_asts[fi.path] = tree

    # Run scanners
    all_scanners = get_all_scanners()
    active_categories = categories or list(all_scanners.keys())

    category_results: list[CategoryResult] = []
    hipaa_active = licensed and "hipaa" in active_categories

    for cat_name in active_categories:
        scanner_cls = all_scanners.get(cat_name)
        if scanner_cls is None:
            continue

        scanner = scanner_cls()
        cat_start = time.perf_counter()

        try:
            if cat_name == "hipaa":
                findings = scanner.scan(files, python_asts, project_path, licensed=licensed)
            else:
                findings = scanner.scan(files, python_asts, project_path)
        except Exception:
            findings = []

        cat_elapsed_ms = (time.perf_counter() - cat_start) * 1000
        cat_score, cat_grade = score_category(findings)

        category_results.append(CategoryResult(
            category=cat_name,
            findings=findings,
            score=cat_score,
            grade=cat_grade,
            scan_time_ms=round(cat_elapsed_ms, 2),
        ))

    # Calculate overall
    overall_score, overall_grade = calculate_overall(category_results, hipaa_active)
    total_elapsed_ms = (time.perf_counter() - total_start) * 1000

    return ScanReport(
        project_path=str(project_path.resolve()),
        total_files=len(files),
        files_by_language=files_by_language,
        categories=category_results,
        overall_score=overall_score,
        overall_grade=overall_grade,
        total_scan_time_ms=round(total_elapsed_ms, 2),
        licensed=licensed,
    )


def _count_languages(files: list[FileInfo]) -> dict[str, int]:
    """Count files per language."""
    counts: dict[str, int] = {}
    for fi in files:
        counts[fi.language] = counts.get(fi.language, 0) + 1
    return dict(sorted(counts.items(), key=lambda x: -x[1]))
