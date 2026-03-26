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
        tree = python_asts.get(fi.path)
        self._check_long_functions(fi, content, tree, rel_path, findings)
        self._check_long_file(len(lines), rel_path, findings)
        self._check_deep_nesting(fi, content, rel_path, findings)
        self._check_todos(lines, rel_path, findings)

    def _check_long_functions(
        self, fi: FileInfo, content: str, tree: ast.Module | None,
        rel: str, findings: list[Finding],
    ) -> None:
        if tree is not None:
            for name, lineno, _, func_lines in get_functions(tree):
                if func_lines > 50:
                    findings.append(Finding(
                        rule_id="CQ-001", category="code_quality", severity="warn",
                        message=f"Function '{name}' is {func_lines} lines (>50)",
                        file_path=rel, line_number=lineno,
                        suggestion="Break into smaller, focused functions",
                    ))
        if fi.language in ("javascript", "typescript"):
            for name, lineno, func_lines in _count_js_function_lines(content):
                if func_lines > 50:
                    findings.append(Finding(
                        rule_id="CQ-001", category="code_quality", severity="warn",
                        message=f"Function '{name}' is ~{func_lines} lines (>50)",
                        file_path=rel, line_number=lineno,
                        suggestion="Break into smaller, focused functions",
                    ))

    def _check_long_file(self, line_count: int, rel: str, findings: list[Finding]) -> None:
        if line_count > 500:
            findings.append(Finding(
                rule_id="CQ-002", category="code_quality", severity="warn",
                message=f"File is {line_count} lines (>500)", file_path=rel,
                suggestion="Split into smaller, focused modules",
            ))

    def _check_deep_nesting(
        self, fi: FileInfo, content: str, rel: str, findings: list[Finding],
    ) -> None:
        if fi.language == "python":
            deep = _max_indent_depth_python(content)
        elif fi.language in ("javascript", "typescript"):
            deep = _max_brace_depth_js(content)
        else:
            return
        if deep:
            worst = max(deep, key=lambda x: x[1])
            label = "brace levels" if fi.language != "python" else "levels"
            findings.append(Finding(
                rule_id="CQ-003", category="code_quality", severity="warn",
                message=f"Deeply nested code ({worst[1]} {label}) detected",
                file_path=rel, line_number=worst[0],
                suggestion="Reduce nesting with early returns, guard clauses, or extraction",
            ))

    def _check_todos(self, lines: list[str], rel: str, findings: list[Finding]) -> None:
        count = sum(1 for line in lines if _TODO_PATTERN.search(line))
        if count > 10:
            findings.append(Finding(
                rule_id="CQ-004", category="code_quality", severity="fail",
                message=f"File has {count} TODO/FIXME/HACK comments (>10)", file_path=rel,
                suggestion="Resolve outstanding TODOs before production deployment",
            ))
        elif count > 5:
            findings.append(Finding(
                rule_id="CQ-004", category="code_quality", severity="warn",
                message=f"File has {count} TODO/FIXME/HACK comments (>5)", file_path=rel,
                suggestion="Address outstanding TODOs to reduce technical debt",
            ))
