"""Python file analyzer — AST-based static analysis for Python files."""

from __future__ import annotations

import ast
from pathlib import Path

from vibe_check.decoder.analyzers.pattern_matcher import (
    infer_class_description,
    infer_file_summary,
    infer_function_description,
)
from vibe_check.decoder.models import ClassInfo, FileAnalysis, FunctionInfo
from vibe_check.parsers.file_walker import FileInfo
from vibe_check.parsers.python_parser import (
    get_all_call_names,
    get_classes,
    get_decorators,
    get_docstring,
    get_env_var_references,
    get_function_signature,
    get_functions,
    get_imports,
)


def analyze_python_file(
    fi: FileInfo,
    tree: ast.Module,
    project_path: Path,
) -> FileAnalysis:
    """Analyze a single Python file using AST inspection.

    Returns a FileAnalysis with functions, classes, imports, env vars,
    and heuristic-inferred descriptions.
    """
    content = fi.content
    rel_path = _rel(fi.path, project_path)
    lines = content.splitlines()
    imports = get_imports(tree)
    env_vars = get_env_var_references(tree)
    has_main_guard = _has_main_guard(content)

    # Extract functions (top-level only, not methods inside classes)
    class_method_lines: set[int] = set()
    raw_classes = get_classes(tree)
    class_infos: list[ClassInfo] = []
    all_decorators: list[list[str]] = []
    class_names: list[str] = []
    class_bases: list[list[str]] = []

    for cls_name, cls_start, cls_end, bases, cls_docstring in raw_classes:
        class_names.append(cls_name)
        class_bases.append(bases)
        methods = _extract_methods(tree, cls_name, cls_start, cls_end, content)
        for m in methods:
            for ln in range(m.start_line, m.end_line + 1):
                class_method_lines.add(ln)
        cls_node = _find_class_node(tree, cls_name)
        cls_decs = get_decorators(cls_node) if cls_node else []
        all_decorators.append(cls_decs)
        class_infos.append(ClassInfo(
            name=cls_name,
            start_line=cls_start,
            end_line=cls_end,
            bases=bases,
            methods=methods,
            docstring=cls_docstring,
            description=infer_class_description(cls_name, bases, cls_docstring),
        ))

    # Top-level functions (not inside classes)
    raw_funcs = get_functions(tree)
    func_infos: list[FunctionInfo] = []
    func_names: list[str] = []
    for name, start, end, line_count in raw_funcs:
        if start in class_method_lines:
            continue
        func_node = _find_function_node(tree, name, start)
        decs = get_decorators(func_node) if func_node else []
        all_decorators.append(decs)
        doc = get_docstring(func_node) if func_node else None
        sig = get_function_signature(content, name)
        calls = _get_calls_in_range(tree, start, end)
        func_names.append(name)
        func_infos.append(FunctionInfo(
            name=name,
            start_line=start,
            end_line=end,
            line_count=line_count,
            signature=sig,
            decorators=decs,
            docstring=doc,
            calls=calls,
            description=infer_function_description(name, decs, doc, calls),
        ))

    summary = infer_file_summary(
        filename=fi.path.name,
        imports=imports,
        class_names=class_names,
        class_bases=class_bases,
        function_names=func_names,
        decorators=all_decorators,
        has_main_guard=has_main_guard,
    )

    return FileAnalysis(
        path=rel_path,
        language="python",
        line_count=len(lines),
        summary=summary,
        imports=imports,
        functions=func_infos,
        classes=class_infos,
        env_vars=env_vars,
    )


def _rel(path: Path, base: Path) -> str:
    try:
        return str(path.relative_to(base)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def _has_main_guard(content: str) -> bool:
    return 'if __name__ ==' in content or "if __name__==" in content


def _find_class_node(tree: ast.Module, name: str) -> ast.ClassDef | None:
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == name:
            return node
    return None


def _find_function_node(
    tree: ast.Module, name: str, start_line: int,
) -> ast.FunctionDef | ast.AsyncFunctionDef | None:
    for node in ast.walk(tree):
        if (
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == name
            and node.lineno == start_line
        ):
            return node
    return None


def _extract_methods(
    tree: ast.Module,
    class_name: str,
    cls_start: int,
    cls_end: int,
    source: str,
) -> list[FunctionInfo]:
    """Extract methods from a class by finding functions within its line range."""
    methods: list[FunctionInfo] = []
    cls_node = _find_class_node(tree, class_name)
    if cls_node is None:
        return methods

    for node in ast.iter_child_nodes(cls_node):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        name = node.name
        start = node.lineno
        end = node.end_lineno or start
        line_count = end - start + 1
        decs = get_decorators(node)
        doc = get_docstring(node)
        sig = get_function_signature(source, name)
        calls = _get_calls_in_range(tree, start, end)
        methods.append(FunctionInfo(
            name=name,
            start_line=start,
            end_line=end,
            line_count=line_count,
            signature=sig,
            decorators=decs,
            docstring=doc,
            calls=calls,
            description=infer_function_description(name, decs, doc, calls),
        ))
    return methods


def _get_calls_in_range(tree: ast.Module, start: int, end: int) -> list[str]:
    """Get function call names within a line range."""
    names: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not hasattr(node, "lineno") or node.lineno < start or node.lineno > end:
            continue
        func = node.func
        if isinstance(func, ast.Name):
            names.append(func.id)
        elif isinstance(func, ast.Attribute):
            names.append(func.attr)
    return sorted(set(names))
