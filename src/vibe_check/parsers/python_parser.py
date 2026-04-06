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


def get_all_call_names(tree: ast.Module) -> list[str]:
    """Extract all function/method call names from an AST."""
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name):
                names.append(func.id)
            elif isinstance(func, ast.Attribute):
                names.append(func.attr)
    return names


def get_classes(
    tree: ast.Module,
) -> list[tuple[str, int, int, list[str], str | None]]:
    """Extract classes from an AST.

    Returns list of (name, start_line, end_line, base_names, docstring).
    """
    results: list[tuple[str, int, int, list[str], str | None]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            start = node.lineno
            end = node.end_lineno or start
            bases: list[str] = []
            for base in node.bases:
                if isinstance(base, ast.Name):
                    bases.append(base.id)
                elif isinstance(base, ast.Attribute):
                    bases.append(f"{_unparse_attr(base)}")
            docstring = get_docstring(node)
            results.append((node.name, start, end, bases, docstring))
    return results


def get_function_signature(source: str, func_name: str) -> str:
    """Extract the full signature line for a function by name.

    Searches source text for the def line rather than reconstructing from AST,
    which preserves the original formatting and type annotations.
    """
    for line in source.splitlines():
        stripped = line.strip()
        if stripped.startswith(("def ", "async def ")) and func_name in stripped:
            # Return up to the colon
            colon_idx = stripped.find(":")
            if colon_idx != -1:
                return stripped[: colon_idx + 1]
            return stripped
    return f"def {func_name}(...):"


def get_env_var_references(tree: ast.Module) -> list[str]:
    """Find environment variable names referenced in the AST.

    Detects: os.environ["X"], os.environ.get("X"), os.getenv("X").
    Single pass over the AST.
    """
    env_vars: list[str] = []
    for node in ast.walk(tree):
        # os.getenv("X") or os.environ.get("X") — Call nodes
        if isinstance(node, ast.Call):
            func = node.func
            if (
                isinstance(func, ast.Attribute)
                and func.attr == "getenv"
                and isinstance(func.value, ast.Name)
                and func.value.id == "os"
            ):
                if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                    env_vars.append(node.args[0].value)
            elif (
                isinstance(func, ast.Attribute)
                and func.attr == "get"
                and isinstance(func.value, ast.Attribute)
                and func.value.attr == "environ"
                and isinstance(func.value.value, ast.Name)
                and func.value.value.id == "os"
            ):
                if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                    env_vars.append(node.args[0].value)

        # os.environ["X"] — Subscript node
        elif isinstance(node, ast.Subscript):
            value = node.value
            if (
                isinstance(value, ast.Attribute)
                and isinstance(value.value, ast.Name)
                and value.value.id == "os"
                and value.attr == "environ"
                and isinstance(node.slice, ast.Constant)
                and isinstance(node.slice.value, str)
            ):
                env_vars.append(node.slice.value)

    return sorted(set(env_vars))


def get_decorators(node: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef) -> list[str]:
    """Extract decorator names from a function or class node."""
    names: list[str] = []
    for dec in node.decorator_list:
        if isinstance(dec, ast.Name):
            names.append(dec.id)
        elif isinstance(dec, ast.Attribute):
            names.append(_unparse_attr(dec))
        elif isinstance(dec, ast.Call):
            if isinstance(dec.func, ast.Name):
                names.append(dec.func.id)
            elif isinstance(dec.func, ast.Attribute):
                names.append(_unparse_attr(dec.func))
    return names


def get_docstring(node: ast.AST) -> str | None:
    """Extract the docstring from a function, class, or module node."""
    if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Module)):
        return None
    if not node.body:
        return None
    first = node.body[0]
    if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) and isinstance(first.value.value, str):
        return first.value.value.strip()
    return None


def _unparse_attr(node: ast.Attribute) -> str:
    """Recursively unparse an Attribute node to a dotted string."""
    if isinstance(node.value, ast.Name):
        return f"{node.value.id}.{node.attr}"
    if isinstance(node.value, ast.Attribute):
        return f"{_unparse_attr(node.value)}.{node.attr}"
    return node.attr
