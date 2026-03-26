"""Code quality scanner — detects complexity and maintainability issues."""

from __future__ import annotations

import ast
import re
from pathlib import Path

from vibe_check.engine.models import Finding
from vibe_check.engine.registry import register_scanner
from vibe_check.parsers.file_walker import FileInfo
from vibe_check.parsers.python_parser import get_functions
from vibe_check.scanners.base import BaseScanner

_TODO_PATTERN = re.compile(r"""\b(?:TODO|FIXME|HACK|XXX)\b""", re.IGNORECASE)


def _rel(path: Path, base: Path) -> str:
    try:
        return str(path.relative_to(base))
    except ValueError:
        return str(path)


def _count_js_function_lines(content: str) -> list[tuple[str, int, int]]:
    """Rough heuristic for JS/TS function lengths.

    Returns list of (description, line_number, line_count).
    Tracks brace-delimited blocks after function/arrow keywords.
    """
    results: list[tuple[str, int, int]] = []
    lines = content.splitlines()
    func_pattern = re.compile(
        r"""(?:function\s+(\w+)|(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s*)?\(|(\w+)\s*\(.*\)\s*\{)"""
    )

    i = 0
    while i < len(lines):
        line = lines[i]
        match = func_pattern.search(line)
        if match and "{" in line:
            name = match.group(1) or match.group(2) or match.group(3) or "anonymous"
            start_line = i + 1
            brace_depth = 0
            for j in range(i, len(lines)):
                brace_depth += lines[j].count("{") - lines[j].count("}")
                if brace_depth <= 0 and j > i:
                    length = j - i + 1
                    results.append((name, start_line, length))
                    break
        i += 1
    return results


def _max_indent_depth_python(content: str) -> list[tuple[int, int]]:
    """Find lines with deep indentation in Python.

    Returns list of (line_number, depth) where depth > 4.
    """
    results: list[tuple[int, int]] = []
    for i, line in enumerate(content.splitlines(), 1):
        stripped = line.lstrip()
        if not stripped or stripped.startswith("#"):
            continue
        indent = len(line) - len(stripped)
        # Assume 4 spaces per level (standard Python)
        depth = indent // 4
        if depth > 4:
            results.append((i, depth))
    return results


def _max_brace_depth_js(content: str) -> list[tuple[int, int]]:
    """Find lines with deep brace nesting in JS/TS.

    Returns list of (line_number, depth) where depth > 4.
    """
    results: list[tuple[int, int]] = []
    depth = 0
    for i, line in enumerate(content.splitlines(), 1):
        depth += line.count("{") - line.count("}")
        if depth > 4 and line.strip():
            results.append((i, depth))
    return results


@register_scanner("code_quality")
class CodeQualityScanner(BaseScanner):
    """Scans for code complexity and maintainability issues."""

    @property
    def category(self) -> str:
        return "code_quality"

    def scan(
        self,
        files: list[FileInfo],
        python_asts: dict[Path, ast.Module],
        project_path: Path,
    ) -> list[Finding]:
        findings: list[Finding] = []
        for fi in files:
            try:
                self._scan_file(fi, python_asts, project_path, findings)
            except Exception:
                continue
        return findings

    def _scan_file(
        self,
        fi: FileInfo,
        python_asts: dict[Path, ast.Module],
        project_path: Path,
        findings: list[Finding],
    ) -> None:
        content = fi.content
        if not content:
            return

        rel_path = _rel(fi.path, project_path)
        lines = content.splitlines()
        line_count = len(lines)

        # CQ-001: Long functions
        tree = python_asts.get(fi.path)
        if tree is not None:
            for name, lineno, _, func_lines in get_functions(tree):
                if func_lines > 50:
                    findings.append(Finding(
                        rule_id="CQ-001",
                        category="code_quality",
                        severity="warn",
                        message=f"Function '{name}' is {func_lines} lines (>50)",
                        file_path=rel_path,
                        line_number=lineno,
                        suggestion="Break into smaller, focused functions",
                    ))

        if fi.language in ("javascript", "typescript"):
            for name, lineno, func_lines in _count_js_function_lines(content):
                if func_lines > 50:
                    findings.append(Finding(
                        rule_id="CQ-001",
                        category="code_quality",
                        severity="warn",
                        message=f"Function '{name}' is ~{func_lines} lines (>50)",
                        file_path=rel_path,
                        line_number=lineno,
                        suggestion="Break into smaller, focused functions",
                    ))

        # CQ-002: Long files
        if line_count > 500:
            findings.append(Finding(
                rule_id="CQ-002",
                category="code_quality",
                severity="warn",
                message=f"File is {line_count} lines (>500)",
                file_path=rel_path,
                suggestion="Split into smaller, focused modules",
            ))

        # CQ-003: Deep nesting
        if fi.language == "python":
            deep_lines = _max_indent_depth_python(content)
            if deep_lines:
                worst = max(deep_lines, key=lambda x: x[1])
                findings.append(Finding(
                    rule_id="CQ-003",
                    category="code_quality",
                    severity="warn",
                    message=f"Deeply nested code ({worst[1]} levels) detected",
                    file_path=rel_path,
                    line_number=worst[0],
                    suggestion="Reduce nesting with early returns, guard clauses, or extraction",
                ))
        elif fi.language in ("javascript", "typescript"):
            deep_lines = _max_brace_depth_js(content)
            if deep_lines:
                worst = max(deep_lines, key=lambda x: x[1])
                findings.append(Finding(
                    rule_id="CQ-003",
                    category="code_quality",
                    severity="warn",
                    message=f"Deeply nested code ({worst[1]} brace levels) detected",
                    file_path=rel_path,
                    line_number=worst[0],
                    suggestion="Reduce nesting with early returns or extraction",
                ))

        # CQ-004: Excessive TODO/FIXME/HACK comments
        todo_count = sum(1 for line in lines if _TODO_PATTERN.search(line))
        if todo_count > 10:
            findings.append(Finding(
                rule_id="CQ-004",
                category="code_quality",
                severity="fail",
                message=f"File has {todo_count} TODO/FIXME/HACK comments (>10)",
                file_path=rel_path,
                suggestion="Resolve outstanding TODOs before production deployment",
            ))
        elif todo_count > 5:
            findings.append(Finding(
                rule_id="CQ-004",
                category="code_quality",
                severity="warn",
                message=f"File has {todo_count} TODO/FIXME/HACK comments (>5)",
                file_path=rel_path,
                suggestion="Address outstanding TODOs to reduce technical debt",
            ))
