"""Decode orchestrator — coordinates file discovery, analysis, and reporting."""

from __future__ import annotations

import time
from pathlib import Path

from vibe_check.decoder.analyzers.cross_ref import (
    build_architecture_map,
    build_cross_references,
)
from vibe_check.decoder.analyzers.generic_analyzer import analyze_generic_file
from vibe_check.decoder.analyzers.python_analyzer import analyze_python_file
from vibe_check.decoder.models import DecodeReport, FileAnalysis
from vibe_check.parsers.file_walker import FileInfo, walk_files
from vibe_check.parsers.python_parser import parse_file


def run_decode(
    project_path: Path,
    ai_backend: object | None = None,
    licensed: bool = False,
) -> DecodeReport:
    """Run a full decode on the given project directory.

    Flow:
    1. Walk files and parse Python ASTs (reuses scan infrastructure)
    2. Analyze each file (Python via AST, others via regex)
    3. Build cross-file references and architecture map
    4. Optionally enhance with AI descriptions (Pro tier)
    5. Assemble DecodeReport
    """
    total_start = time.perf_counter()

    files = list(walk_files(project_path))
    python_asts = _parse_python_asts(files)

    # Analyze each file
    file_analyses: list[FileAnalysis] = []
    for fi in files:
        analysis = _analyze_file(fi, python_asts, project_path)
        if analysis is not None:
            file_analyses.append(analysis)

    # Build cross-references (mutates file_analyses in place)
    build_cross_references(file_analyses, project_path)

    # Mark entry points
    for fa in file_analyses:
        if fa.language == "python" and _is_entry_point(fa):
            fa.entry_point = True

    # Build architecture map
    architecture = build_architecture_map(file_analyses, project_path)

    # AI enhancement (Pro tier)
    ai_enhanced = False
    backend_name = "none"
    if ai_backend is not None and licensed:
        ai_enhanced = _enhance_with_ai(file_analyses, ai_backend, project_path)
        backend_name = getattr(ai_backend, "name", "unknown")

    total_elapsed_ms = (time.perf_counter() - total_start) * 1000

    return DecodeReport(
        project_path=str(project_path.resolve()),
        total_files=len(file_analyses),
        files_by_language=_count_languages(file_analyses),
        files=file_analyses,
        architecture=architecture,
        ai_backend=backend_name,
        ai_enhanced=ai_enhanced,
        decode_time_ms=round(total_elapsed_ms, 2),
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


def _analyze_file(
    fi: FileInfo,
    python_asts: dict,
    project_path: Path,
) -> FileAnalysis | None:
    """Analyze a single file, dispatching to the appropriate analyzer."""
    try:
        if fi.language == "python":
            tree = python_asts.get(fi.path)
            if tree is None:
                return None
            return analyze_python_file(fi, tree, project_path)
        return analyze_generic_file(fi, project_path)
    except Exception:
        return None


def _is_entry_point(fa: FileAnalysis) -> bool:
    """Check if a file analysis represents an entry point."""
    if "__main__" in fa.path:
        return True
    for func in fa.functions:
        if "main.command" in func.decorators or "click.command" in func.decorators:
            return True
        if func.name == "main":
            return True
    return False


def _count_languages(file_analyses: list[FileAnalysis]) -> dict[str, int]:
    """Count files per language."""
    counts: dict[str, int] = {}
    for fa in file_analyses:
        counts[fa.language] = counts.get(fa.language, 0) + 1
    return dict(sorted(counts.items(), key=lambda x: -x[1]))


def _enhance_with_ai(
    file_analyses: list[FileAnalysis],
    ai_backend: object,
    project_path: Path,
) -> bool:
    """Enhance file analyses with AI-generated descriptions.

    Returns True if any enhancement was applied.
    """
    from vibe_check.decoder.ai.base import BaseAIBackend

    if not isinstance(ai_backend, BaseAIBackend):
        return False

    enhanced = False
    for fa in file_analyses:
        try:
            # Read source for context
            full_path = project_path / fa.path
            if not full_path.is_file():
                continue
            source = full_path.read_text(encoding="utf-8", errors="ignore")

            # Enhance file summary
            ai_summary = ai_backend.explain_file(fa, source)
            if ai_summary:
                fa.summary = ai_summary
                enhanced = True

            # Enhance function descriptions
            for func in fa.functions:
                ai_desc = ai_backend.explain_function(func, source, fa.summary)
                if ai_desc:
                    func.description = ai_desc

        except Exception:
            continue

    return enhanced
