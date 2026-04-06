"""Cross-file reference tracker — builds import graph and caller/callee maps."""

from __future__ import annotations

import os
from pathlib import Path

from vibe_check.decoder.models import ArchitectureMap, FileAnalysis

# Config/env file patterns to detect
_CONFIG_PATTERNS: set[str] = {
    ".env", ".env.local", ".env.production", ".env.staging", ".env.development",
    "pyproject.toml", "setup.cfg", "setup.py", "package.json", "tsconfig.json",
    "Dockerfile", "docker-compose.yml", "docker-compose.yaml",
    ".gitlab-ci.yml", ".github", "Makefile", "tox.ini", "pytest.ini",
    "requirements.txt", "requirements-dev.txt", "Pipfile", "poetry.lock",
    "Cargo.toml", "go.mod", "go.sum",
}


def build_cross_references(
    file_analyses: list[FileAnalysis],
    project_path: Path,
) -> None:
    """Populate called_by and calls_into fields on each FileAnalysis.

    Mutates the FileAnalysis objects in place.
    """
    # Build a map: module import name -> file path
    import_to_path = _build_import_map(file_analyses, project_path)

    # For each file, resolve its imports to internal file paths
    path_to_analysis: dict[str, FileAnalysis] = {fa.path: fa for fa in file_analyses}

    for fa in file_analyses:
        internal_deps: list[str] = []
        for imp in fa.imports:
            resolved = _resolve_import(imp, import_to_path)
            if resolved and resolved != fa.path:
                internal_deps.append(resolved)
        fa.calls_into = sorted(set(internal_deps))

    # Invert: for each file that is imported, record who imports it
    for fa in file_analyses:
        for dep_path in fa.calls_into:
            dep_fa = path_to_analysis.get(dep_path)
            if dep_fa is not None and fa.path not in dep_fa.called_by:
                dep_fa.called_by.append(fa.path)

    # Sort called_by for deterministic output
    for fa in file_analyses:
        fa.called_by.sort()


def detect_entry_points(file_analyses: list[FileAnalysis]) -> list[str]:
    """Identify entry points — files explicitly marked as entry points.

    A file is an entry point if it has a __main__ guard, CLI decorators,
    or a main() function. Being an orphan (no callers) alone is NOT enough
    — many files are imported indirectly via __init__.py re-exports
    (e.g., scanners, reporters) and would be false positives.
    """
    entry_points: list[str] = []
    for fa in file_analyses:
        if fa.entry_point:
            entry_points.append(fa.path)
    return sorted(entry_points)


def build_architecture_map(
    file_analyses: list[FileAnalysis],
    project_path: Path,
) -> ArchitectureMap:
    """Build a high-level architecture map from file analyses."""
    entry_points = detect_entry_points(file_analyses)

    # Dependency graph
    dep_graph: dict[str, list[str]] = {}
    for fa in file_analyses:
        if fa.calls_into:
            dep_graph[fa.path] = fa.calls_into

    # External dependencies (imports not resolved to internal files)
    internal_modules = _build_import_map(file_analyses, project_path)
    all_imports: set[str] = set()
    for fa in file_analyses:
        for imp in fa.imports:
            top_module = imp.split(".")[0]
            all_imports.add(top_module)
    internal_top_modules = {imp.split(".")[0] for imp in internal_modules}
    stdlib = _known_stdlib()
    external = sorted(all_imports - internal_top_modules - stdlib)

    # Config files
    config_files = _detect_config_files(project_path)

    # All env vars
    all_env_vars: set[str] = set()
    for fa in file_analyses:
        all_env_vars.update(fa.env_vars)

    return ArchitectureMap(
        entry_points=entry_points,
        dependency_graph=dep_graph,
        external_deps=external,
        config_files=config_files,
        env_vars=sorted(all_env_vars),
    )


def _build_import_map(
    file_analyses: list[FileAnalysis],
    project_path: Path,
) -> dict[str, str]:
    """Map Python module import names to relative file paths.

    e.g., 'vibe_check.engine.models' -> 'src/vibe_check/engine/models.py'
    """
    mapping: dict[str, str] = {}
    for fa in file_analyses:
        if fa.language != "python":
            continue
        # Convert path to module-style name
        path = fa.path
        # Remove .py extension
        mod_path = path.replace(".py", "").replace("/", ".").replace("\\", ".")
        # Remove __init__ from package paths
        if mod_path.endswith(".__init__"):
            mod_path = mod_path[:-9]
        mapping[mod_path] = fa.path

        # Also register short forms (without src/ prefix or similar)
        parts = mod_path.split(".")
        for i in range(len(parts)):
            short = ".".join(parts[i:])
            if short and short not in mapping:
                mapping[short] = fa.path
    return mapping


def _resolve_import(
    import_name: str,
    import_map: dict[str, str],
) -> str | None:
    """Try to resolve an import name to an internal file path."""
    # Direct match
    if import_name in import_map:
        return import_map[import_name]
    # Try progressively shorter prefixes
    parts = import_name.split(".")
    for i in range(len(parts), 0, -1):
        candidate = ".".join(parts[:i])
        if candidate in import_map:
            return import_map[candidate]
    return None


def _detect_config_files(project_path: Path) -> list[str]:
    """Detect configuration files in the project root."""
    config_files: list[str] = []
    try:
        for entry in project_path.iterdir():
            if entry.name in _CONFIG_PATTERNS or entry.name.startswith(".env"):
                config_files.append(entry.name)
    except OSError:
        pass
    return sorted(config_files)


def _known_stdlib() -> set[str]:
    """Return a set of known Python stdlib top-level module names."""
    return {
        "abc", "ast", "asyncio", "base64", "collections", "concurrent",
        "configparser", "contextlib", "copy", "csv", "dataclasses", "datetime",
        "decimal", "difflib", "email", "enum", "functools", "glob", "gzip",
        "hashlib", "hmac", "html", "http", "importlib", "inspect", "io",
        "itertools", "json", "logging", "math", "mimetypes", "multiprocessing",
        "operator", "os", "pathlib", "pickle", "platform", "pprint",
        "queue", "random", "re", "secrets", "shutil", "signal", "socket",
        "sqlite3", "ssl", "string", "struct", "subprocess", "sys",
        "tempfile", "textwrap", "threading", "time", "timeit", "traceback",
        "types", "typing", "unittest", "urllib", "uuid", "warnings",
        "weakref", "xml", "zipfile", "zlib",
        # typing extensions
        "typing_extensions",
        # common test
        "pytest", "doctest",
        # __future__ is always internal
        "__future__",
    }
