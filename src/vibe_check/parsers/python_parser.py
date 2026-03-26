"""Python AST parsing helpers."""

from __future__ import annotations

import ast
from pathlib import Path


def parse_file(path: Path) -> ast.Module | None:
    """Parse a Python file into an AST, returning None on failure."""
    try:
        source = path.read_text(encoding="utf-8", errors="ignore")
        return ast.parse(source, filename=str(path))
    except (SyntaxError, ValueError, OSError):
        return None


def get_functions(
    tree: ast.Module,
) -> list[tuple[str, int, int, int]]:
    """Extract functions from an AST.

    Returns list of (name, start_line, end_line, line_count).
    """
    results: list[tuple[str, int, int, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            start = node.lineno
            end = node.end_lineno or start
            line_count = end - start + 1
            results.append((node.name, start, end, line_count))
    return results


def get_imports(tree: ast.Module) -> list[str]:
    """Extract all imported module names from an AST."""
    modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                modules.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                modules.append(node.module)
    return modules


def get_string_literals(tree: ast.Module) -> list[tuple[str, int]]:
    """Extract string literals from an AST.

    Returns list of (value, line_number).
    """
    results: list[tuple[str, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            results.append((node.value, node.lineno))
    return results


def get_function_calls(tree: ast.Module, name: str) -> list[int]:
    """Find all calls to a function by name, returning line numbers."""
    lines: list[int] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            # Direct call: eval(...)
            if isinstance(func, ast.Name) and func.id == name:
                lines.append(node.lineno)
            # Attribute call: obj.eval(...)
            elif isinstance(func, ast.Attribute) and func.attr == name:
                lines.append(node.lineno)
    return lines
