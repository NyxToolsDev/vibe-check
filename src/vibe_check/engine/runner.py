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
    """Run a full scan on the given project directory."""
    total_start = time.perf_counter()

    files = list(walk_files(project_path))
    python_asts = _parse_python_asts(files)

    all_scanners = get_all_scanners()
    active_categories = categories or list(all_scanners.keys())
    hipaa_active = licensed and "hipaa" in active_categories

    category_results = _run_all_scanners(
        all_scanners, active_categories, files, python_asts, project_path, licensed,
    )

    overall_score, overall_grade = calculate_overall(category_results, hipaa_active)
    total_elapsed_ms = (time.perf_counter() - total_start) * 1000

    return ScanReport(
        project_path=str(project_path.resolve()),
        total_files=len(files),
        files_by_language=_count_languages(files),
        categories=category_results,
        overall_score=overall_score,
        overall_grade=overall_grade,
        total_scan_time_ms=round(total_elapsed_ms, 2),
        licensed=licensed,
    )


def _parse_python_asts(files: list[FileInfo]) -> dict:
    """Parse all Python files into ASTs."""
    asts = {}
    for fi in files:
        if fi.language == "python":
            tree = parse_file(fi.path)
            if tree is not None:
                asts[fi.path] = tree
    return asts


def _run_all_scanners(
    all_scanners: dict,
    active_categories: list[str],
    files: list[FileInfo],
    python_asts: dict,
    project_path: Path,
    licensed: bool,
) -> list[CategoryResult]:
    """Execute each scanner and collect results."""
    results: list[CategoryResult] = []
    for cat_name in active_categories:
        scanner_cls = all_scanners.get(cat_name)
        if scanner_cls is None:
            continue
        result = _run_single_scanner(
            scanner_cls, cat_name, files, python_asts, project_path, licensed,
        )
        results.append(result)
    return results


def _run_single_scanner(
    scanner_cls: type,
    cat_name: str,
    files: list[FileInfo],
    python_asts: dict,
    project_path: Path,
    licensed: bool,
) -> CategoryResult:
    """Run one scanner and return its scored result."""
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
    return CategoryResult(
        category=cat_name,
        findings=findings,
        score=cat_score,
        grade=cat_grade,
        scan_time_ms=round(cat_elapsed_ms, 2),
    )


def _count_languages(files: list[FileInfo]) -> dict[str, int]:
    """Count files per language."""
    counts: dict[str, int] = {}
    for fi in files:
        counts[fi.language] = counts.get(fi.language, 0) + 1
    return dict(sorted(counts.items(), key=lambda x: -x[1]))
