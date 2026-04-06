"""Generic file analyzer — regex-based analysis for non-Python files."""

from __future__ import annotations

import re
from pathlib import Path

from vibe_check.decoder.models import FileAnalysis, FunctionInfo
from vibe_check.parsers.file_walker import FileInfo

# Regex patterns for extracting structure from JS/TS files
_JS_FUNCTION = re.compile(
    r"""(?:export\s+)?(?:async\s+)?function\s+(\w+)\s*\(""",
)
_JS_ARROW = re.compile(
    r"""(?:export\s+)?(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?\(""",
)
_JS_CLASS = re.compile(
    r"""(?:export\s+)?class\s+(\w+)""",
)
_JS_IMPORT = re.compile(
    r"""(?:import\s+.*\s+from\s+['"]([^'"]+)['"]|require\s*\(\s*['"]([^'"]+)['"]\s*\))""",
)
_JS_ENV = re.compile(
    r"""process\.env\.(\w+)|process\.env\[['"](\w+)['"]\]""",
)

# Go patterns
_GO_FUNCTION = re.compile(r"""^func\s+(?:\(\w+\s+\*?\w+\)\s+)?(\w+)\s*\(""", re.MULTILINE)
_GO_IMPORT = re.compile(r'"([^"]+)"')

# Rust patterns
_RUST_FUNCTION = re.compile(r"""(?:pub\s+)?(?:async\s+)?fn\s+(\w+)""")

# Generic env var patterns (works across languages)
_GENERIC_ENV = re.compile(
    r"""(?:os\.environ|os\.getenv|process\.env|ENV|std::env::var)\s*[\[.(]\s*['"](\w+)['"]""",
)


def analyze_generic_file(
    fi: FileInfo,
    project_path: Path,
) -> FileAnalysis:
    """Analyze a non-Python source file using regex extraction.

    Produces a simpler FileAnalysis than the Python analyzer but still
    captures functions, imports, and env vars.
    """
    content = fi.content
    rel_path = _rel(fi.path, project_path)
    lines = content.splitlines()
    lang = fi.language

    functions: list[FunctionInfo] = []
    imports: list[str] = []
    env_vars: list[str] = []

    if lang in ("javascript", "typescript"):
        functions = _extract_js_functions(content)
        imports = _extract_js_imports(content)
        env_vars = _extract_js_env_vars(content)
    elif lang == "go":
        functions = _extract_go_functions(content)
        imports = _extract_go_imports(content)
    elif lang == "rust":
        functions = _extract_rust_functions(content)

    # Generic env var fallback
    if not env_vars:
        env_vars = _extract_generic_env_vars(content)

    summary = _infer_summary(fi.path.name, lang, functions, imports)

    return FileAnalysis(
        path=rel_path,
        language=lang,
        line_count=len(lines),
        summary=summary,
        imports=imports,
        functions=functions,
        env_vars=env_vars,
    )


def _rel(path: Path, base: Path) -> str:
    try:
        return str(path.relative_to(base)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def _extract_js_functions(content: str) -> list[FunctionInfo]:
    functions: list[FunctionInfo] = []
    lines = content.splitlines()
    for i, line in enumerate(lines, 1):
        match = _JS_FUNCTION.search(line) or _JS_ARROW.search(line)
        if match:
            name = match.group(1)
            functions.append(FunctionInfo(
                name=name,
                start_line=i,
                end_line=i,
                line_count=1,
                signature=line.strip()[:120],
            ))
    return functions


def _extract_js_imports(content: str) -> list[str]:
    imports: list[str] = []
    for match in _JS_IMPORT.finditer(content):
        module = match.group(1) or match.group(2)
        if module:
            imports.append(module)
    return imports


def _extract_js_env_vars(content: str) -> list[str]:
    env_vars: list[str] = []
    for match in _JS_ENV.finditer(content):
        var = match.group(1) or match.group(2)
        if var:
            env_vars.append(var)
    return sorted(set(env_vars))


def _extract_go_functions(content: str) -> list[FunctionInfo]:
    functions: list[FunctionInfo] = []
    for i, line in enumerate(content.splitlines(), 1):
        match = _GO_FUNCTION.search(line)
        if match:
            functions.append(FunctionInfo(
                name=match.group(1),
                start_line=i,
                end_line=i,
                line_count=1,
                signature=line.strip()[:120],
            ))
    return functions


def _extract_go_imports(content: str) -> list[str]:
    return [m.group(1) for m in _GO_IMPORT.finditer(content)]


def _extract_rust_functions(content: str) -> list[FunctionInfo]:
    functions: list[FunctionInfo] = []
    for i, line in enumerate(content.splitlines(), 1):
        match = _RUST_FUNCTION.search(line)
        if match:
            functions.append(FunctionInfo(
                name=match.group(1),
                start_line=i,
                end_line=i,
                line_count=1,
                signature=line.strip()[:120],
            ))
    return functions


def _extract_generic_env_vars(content: str) -> list[str]:
    return sorted({m.group(1) for m in _GENERIC_ENV.finditer(content)})


def _infer_summary(filename: str, language: str, functions: list[FunctionInfo], imports: list[str]) -> str:
    parts: list[str] = []
    lang_label = language.replace("typescript", "TypeScript").replace("javascript", "JavaScript").capitalize()
    parts.append(f"{lang_label} module")
    if functions:
        parts.append(f"with {len(functions)} function(s)")
    return " ".join(parts)
