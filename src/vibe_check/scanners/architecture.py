"""Architecture scanner — detects structural and design issues."""

from __future__ import annotations

import ast
import re
from pathlib import Path

from vibe_check.engine.models import Finding
from vibe_check.engine.registry import register_scanner
from vibe_check.parsers.file_walker import FileInfo
from vibe_check.parsers.python_parser import get_imports
from vibe_check.scanners.base import BaseScanner

_TRY_CATCH_JS = re.compile(r"""\btry\s*\{""")
_TYPING_MODULES = {"typing", "typing_extensions", "collections.abc"}


def _rel(path: Path, base: Path) -> str:
    try:
        return str(path.relative_to(base))
    except ValueError:
        return str(path)


def _has_bare_except(tree: ast.Module) -> list[int]:
    """Find bare except clauses (except: without exception type)."""
    lines: list[int] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ExceptHandler):
            if node.type is None:
                lines.append(node.lineno)
    return lines


def _has_try_except(tree: ast.Module) -> bool:
    """Check if AST contains any try/except blocks."""
    for node in ast.walk(tree):
        if isinstance(node, ast.Try):
            return True
    return False


@register_scanner("architecture")
class ArchitectureScanner(BaseScanner):
    """Scans for architectural and structural issues."""

    @property
    def category(self) -> str:
        return "architecture"

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
        line_count = len(content.splitlines())
        tree = python_asts.get(fi.path)
        self._check_god_file(line_count, rel_path, findings)
        self._check_error_handling(fi, content, tree, line_count, rel_path, findings)
        self._check_bare_except(tree, rel_path, findings)
        self._check_type_hints(fi, content, tree, line_count, rel_path, findings)

    def _check_god_file(self, line_count: int, rel: str, findings: list[Finding]) -> None:
        if line_count > 500:
            findings.append(Finding(
                rule_id="ARC-001", category="architecture", severity="warn",
                message=f"Large file with {line_count} lines — possible god file",
                file_path=rel, suggestion="Split into smaller modules with clear responsibilities",
            ))

    def _check_error_handling(
        self, fi: FileInfo, content: str, tree: ast.Module | None,
        line_count: int, rel: str, findings: list[Finding],
    ) -> None:
        if fi.language == "python" and tree is not None:
            if line_count > 20 and fi.path.stem != "__init__" and not _has_try_except(tree):
                findings.append(Finding(
                    rule_id="ARC-002", category="architecture", severity="info",
                    message="No try/except blocks found in Python file", file_path=rel,
                    suggestion="Add error handling for I/O, network, and parsing operations",
                ))
        elif fi.language in ("javascript", "typescript") and line_count > 20:
            if not _TRY_CATCH_JS.search(content):
                findings.append(Finding(
                    rule_id="ARC-002", category="architecture", severity="info",
                    message="No try/catch blocks found in JS/TS file", file_path=rel,
                    suggestion="Add error handling for async operations and external calls",
                ))

    def _check_bare_except(
        self, tree: ast.Module | None, rel: str, findings: list[Finding],
    ) -> None:
        if tree is None:
            return
        for lineno in _has_bare_except(tree):
            findings.append(Finding(
                rule_id="ARC-003", category="architecture", severity="warn",
                message="Bare except clause — catches all exceptions including SystemExit",
                file_path=rel, line_number=lineno,
                suggestion="Specify exception type: except ValueError: or except Exception:",
            ))

    def _check_type_hints(
        self, fi: FileInfo, content: str, tree: ast.Module | None,
        line_count: int, rel: str, findings: list[Finding],
    ) -> None:
        if fi.language != "python" or tree is None or line_count <= 50:
            return
        if set(get_imports(tree)) & _TYPING_MODULES:
            return
        if "from __future__ import annotations" in content:
            return
        has_inline = any(
            isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
            and (n.returns is not None or any(a.annotation is not None for a in n.args.args))
            for n in ast.walk(tree)
        )
        if not has_inline:
            findings.append(Finding(
                rule_id="ARC-004", category="architecture", severity="info",
                message="No type hints found in Python file over 50 lines", file_path=rel,
                suggestion="Add type hints to improve code clarity and catch bugs",
            ))
