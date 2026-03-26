"""Security scanner — detects common security anti-patterns."""

from __future__ import annotations

import ast
import re
from pathlib import Path

from vibe_check.engine.models import Finding
from vibe_check.engine.registry import register_scanner
from vibe_check.parsers.file_walker import FileInfo
from vibe_check.parsers.python_parser import get_function_calls
from vibe_check.scanners.base import BaseScanner

# --- Compiled regex patterns ---

_HARDCODED_SECRET_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"""(?:API_KEY|APIKEY)\s*[=:]\s*['"][A-Za-z0-9+/=_\-]{8,}['"]""", re.IGNORECASE), "API key"),
    (re.compile(r"""(?:SECRET|SECRET_KEY)\s*[=:]\s*['"][A-Za-z0-9+/=_\-]{8,}['"]""", re.IGNORECASE), "secret key"),
    (re.compile(r"""(?:PASSWORD|PASSWD|PWD)\s*[=:]\s*['"][^'"]{4,}['"]""", re.IGNORECASE), "password"),
    (re.compile(r"""(?:TOKEN|AUTH_TOKEN|ACCESS_TOKEN)\s*[=:]\s*['"][A-Za-z0-9+/=_\-]{8,}['"]""", re.IGNORECASE), "token"),
    (re.compile(r"""(?:aws_access_key_id|aws_secret_access_key)\s*[=:]\s*['"][A-Za-z0-9+/=]{16,}['"]""", re.IGNORECASE), "AWS credential"),
    (re.compile(r"""AKIA[0-9A-Z]{16}"""), "AWS access key ID"),
    (re.compile(r"""(?:PRIVATE_KEY|private_key)\s*[=:]\s*['"]-----BEGIN""", re.IGNORECASE), "private key"),
]

_SQL_KEYWORDS = re.compile(
    r"""(?:SELECT|INSERT|UPDATE|DELETE|DROP|CREATE|ALTER)\s""",
    re.IGNORECASE,
)

_SQL_INJECTION_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"""f['"].*(?:SELECT|INSERT|UPDATE|DELETE|DROP)\s""", re.IGNORECASE),
    re.compile(r"""\.format\s*\(.*(?:SELECT|INSERT|UPDATE|DELETE|DROP)\s""", re.IGNORECASE),
    re.compile(r"""%\s*(?:\(|[sd]).*(?:SELECT|INSERT|UPDATE|DELETE|DROP)\s""", re.IGNORECASE),
    re.compile(r"""['"].*(?:SELECT|INSERT|UPDATE|DELETE|DROP)\s.*['"]\s*\+""", re.IGNORECASE),
    re.compile(r"""\+\s*['"].*(?:SELECT|INSERT|UPDATE|DELETE|DROP)\s""", re.IGNORECASE),
]

_DEBUG_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"""DEBUG\s*=\s*True"""), "DEBUG=True"),
    (re.compile(r"""NODE_ENV\s*[=:]\s*['"]development['"]"""), "NODE_ENV=development"),
    (re.compile(r"""app\.debug\s*=\s*True"""), "app.debug=True"),
]

_CORS_WILDCARD_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"""Access-Control-Allow-Origin.*\*"""),
    re.compile(r"""origin\s*:\s*['"]?\*['"]?"""),
    re.compile(r"""allow_origins\s*=\s*\[['"]?\*['"]?\]"""),
    re.compile(r"""cors\(\s*\*\s*\)""", re.IGNORECASE),
]

_DANGEROUS_INNER_HTML = re.compile(r"""dangerouslySetInnerHTML""")
_DOMPURIFY = re.compile(r"""DOMPurify""", re.IGNORECASE)

_CONNECTION_STRING = re.compile(
    r"""(?:postgres|postgresql|mysql|mongodb|redis|amqp|elasticsearch)://[^:]+:[^@]+@""",
    re.IGNORECASE,
)

# SEC-008: Unsafe deserialization
_UNSAFE_DESERIALIZE_PY = re.compile(
    r"""\b(?:pickle\.load|pickle\.loads|shelve\.open|marshal\.load|marshal\.loads"""
    r"""|yaml\.load\s*\((?!.*Loader\s*=\s*(?:yaml\.)?SafeLoader)"""
    r"""|yaml\.unsafe_load)\b""",
)

# SEC-009: Shell injection via subprocess/os
_SHELL_INJECTION_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"""\bsubprocess\.\w+\(.*shell\s*=\s*True""", re.DOTALL), "subprocess with shell=True"),
    (re.compile(r"""\bos\.system\s*\("""), "os.system()"),
    (re.compile(r"""\bos\.popen\s*\("""), "os.popen()"),
    (re.compile(r"""\bcommands\.get(?:output|statusoutput)\s*\("""), "commands.get*()"),
]

# SEC-010: Path traversal
_PATH_TRAVERSAL_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"""open\s*\(.*(?:request|req|params|query|input|args)\b.*\+""", re.IGNORECASE),
    re.compile(r"""(?:send_file|send_from_directory|static)\s*\(.*(?:request|req|params|query|input|args)\b""", re.IGNORECASE),
    re.compile(r"""Path\s*\(.*(?:request|req|params|query|input|args)\b""", re.IGNORECASE),
]

# SEC-011: .env file committed
_ENV_FILE_PATTERN = re.compile(r"""^\.env(?:\.local|\.production|\.staging)?$""")


_TEST_PATH_PATTERNS = re.compile(
    r"""(?:^|[/\\])(?:tests?|__tests__|spec)[/\\]"""
    r"""|(?:^|[/\\])test_[^/\\]+\.py$"""
    r"""|(?:^|[/\\])[^/\\]+_test\.py$"""
    r"""|(?:^|[/\\])[^/\\]+\.(?:test|spec)\.[jt]sx?$""",
)


def _rel(path: Path, base: Path) -> str:
    try:
        return str(path.relative_to(base))
    except ValueError:
        return str(path)


def _is_test_file(fi: FileInfo, project_path: Path) -> bool:
    """Check if a file is a test file (should be excluded from security scanning)."""
    rel_path = _rel(fi.path, project_path)
    return bool(_TEST_PATH_PATTERNS.search(rel_path))


_LOG_STATEMENT = re.compile(
    r"""^\s*(?:logger|logging)\.\w+\s*\(|^\s*(?:print|console\.(?:log|error|warn))\s*\(""",
    re.IGNORECASE,
)


def _is_log_statement(line: str) -> bool:
    """Check if a line is a log/print statement (not an actual SQL query)."""
    return bool(_LOG_STATEMENT.search(line))


def _is_pattern_definition(line: str) -> bool:
    """Check if a line is defining a regex pattern or a string constant (not actual vulnerable code)."""
    stripped = line.strip()
    return (
        stripped.startswith("re.compile(")
        or stripped.startswith("(re.compile(")
        or stripped.startswith("r\"\"\"")
        or stripped.startswith("r'''")
        or stripped.startswith("suggestion=")
        or stripped.startswith("message=")
    )


class _FileCtx:
    """Context for a single file being scanned."""

    __slots__ = ("fi", "content", "lines", "rel", "tree")

    def __init__(
        self, fi: FileInfo, content: str, lines: list[str], rel: str, tree: ast.Module | None,
    ) -> None:
        self.fi = fi
        self.content = content
        self.lines = lines
        self.rel = rel
        self.tree = tree


def _check_hardcoded_secrets(ctx: _FileCtx, findings: list[Finding]) -> None:
    for i, line in enumerate(ctx.lines, 1):
        for pattern, secret_type in _HARDCODED_SECRET_PATTERNS:
            if pattern.search(line):
                findings.append(Finding(
                    rule_id="SEC-001", category="security", severity="fail",
                    message=f"Possible hardcoded {secret_type} detected",
                    file_path=ctx.rel, line_number=i,
                    suggestion="Move secrets to environment variables",
                    snippet=line.strip()[:120],
                ))
                break


def _check_sql_injection(ctx: _FileCtx, findings: list[Finding]) -> None:
    for i, line in enumerate(ctx.lines, 1):
        if _SQL_KEYWORDS.search(line) and not _is_log_statement(line):
            for pat in _SQL_INJECTION_PATTERNS:
                if pat.search(line):
                    findings.append(Finding(
                        rule_id="SEC-002", category="security", severity="fail",
                        message="Potential SQL injection via string interpolation",
                        file_path=ctx.rel, line_number=i,
                        suggestion="Use parameterized queries instead",
                        snippet=line.strip()[:120],
                    ))
                    break


def _check_eval_exec(ctx: _FileCtx, findings: list[Finding]) -> None:
    if ctx.tree is not None:
        for func_name in ("eval", "exec"):
            for lineno in get_function_calls(ctx.tree, func_name):
                findings.append(Finding(
                    rule_id="SEC-003", category="security", severity="fail",
                    message=f"Use of {func_name}() detected",
                    file_path=ctx.rel, line_number=lineno,
                    suggestion=f"Avoid {func_name}() — use safer alternatives",
                ))
    if ctx.fi.language in ("javascript", "typescript"):
        for i, line in enumerate(ctx.lines, 1):
            if re.search(r"""\beval\s*\(""", line):
                findings.append(Finding(
                    rule_id="SEC-003", category="security", severity="fail",
                    message="Use of eval() detected",
                    file_path=ctx.rel, line_number=i,
                    suggestion="Avoid eval() — use safer alternatives",
                    snippet=line.strip()[:120],
                ))


def _check_debug_mode(ctx: _FileCtx, findings: list[Finding]) -> None:
    for i, line in enumerate(ctx.lines, 1):
        if _is_pattern_definition(line):
            continue
        for pat, desc in _DEBUG_PATTERNS:
            if pat.search(line):
                findings.append(Finding(
                    rule_id="SEC-004", category="security", severity="warn",
                    message=f"Debug mode appears enabled: {desc}",
                    file_path=ctx.rel, line_number=i,
                    suggestion="Disable debug mode in production configs",
                    snippet=line.strip()[:120],
                ))


def _check_wildcard_cors(ctx: _FileCtx, findings: list[Finding]) -> None:
    for i, line in enumerate(ctx.lines, 1):
        if _is_pattern_definition(line):
            continue
        for pat in _CORS_WILDCARD_PATTERNS:
            if pat.search(line):
                findings.append(Finding(
                    rule_id="SEC-005", category="security", severity="warn",
                    message="Wildcard CORS origin detected",
                    file_path=ctx.rel, line_number=i,
                    suggestion="Restrict CORS to specific allowed origins",
                    snippet=line.strip()[:120],
                ))
                break


def _check_dangerous_html(ctx: _FileCtx, findings: list[Finding]) -> None:
    if ctx.fi.language not in ("javascript", "typescript"):
        return
    has_dompurify = bool(_DOMPURIFY.search(ctx.content))
    for i, line in enumerate(ctx.lines, 1):
        if _DANGEROUS_INNER_HTML.search(line) and not has_dompurify:
            findings.append(Finding(
                rule_id="SEC-006", category="security", severity="fail",
                message="dangerouslySetInnerHTML used without DOMPurify",
                file_path=ctx.rel, line_number=i,
                suggestion="Sanitize HTML with DOMPurify before rendering",
                snippet=line.strip()[:120],
            ))


def _check_connection_strings(ctx: _FileCtx, findings: list[Finding]) -> None:
    for i, line in enumerate(ctx.lines, 1):
        if _CONNECTION_STRING.search(line):
            findings.append(Finding(
                rule_id="SEC-007", category="security", severity="fail",
                message="Hardcoded database connection string with credentials",
                file_path=ctx.rel, line_number=i,
                suggestion="Use environment variables for connection strings",
                snippet=line.strip()[:120],
            ))


def _check_unsafe_deserialization(ctx: _FileCtx, findings: list[Finding]) -> None:
    if ctx.fi.language != "python":
        return
    for i, line in enumerate(ctx.lines, 1):
        if _UNSAFE_DESERIALIZE_PY.search(line) and not _is_pattern_definition(line):
            findings.append(Finding(
                rule_id="SEC-008", category="security", severity="fail",
                message="Unsafe deserialization detected",
                file_path=ctx.rel, line_number=i,
                suggestion="Use yaml.safe_load(), json, or validated formats instead",
                snippet=line.strip()[:120],
            ))


def _check_shell_injection(ctx: _FileCtx, findings: list[Finding]) -> None:
    for i, line in enumerate(ctx.lines, 1):
        if _is_pattern_definition(line):
            continue
        for pat, desc in _SHELL_INJECTION_PATTERNS:
            if pat.search(line):
                findings.append(Finding(
                    rule_id="SEC-009", category="security", severity="fail",
                    message=f"Potential shell injection via {desc}",
                    file_path=ctx.rel, line_number=i,
                    suggestion="Use subprocess.run() with a list of args (no shell=True)",
                    snippet=line.strip()[:120],
                ))
                break


def _check_path_traversal(ctx: _FileCtx, findings: list[Finding]) -> None:
    for i, line in enumerate(ctx.lines, 1):
        for pat in _PATH_TRAVERSAL_PATTERNS:
            if pat.search(line):
                findings.append(Finding(
                    rule_id="SEC-010", category="security", severity="warn",
                    message="Potential path traversal — user input in file path",
                    file_path=ctx.rel, line_number=i,
                    suggestion="Validate and sanitize file paths; use Path.resolve() and check prefix",
                    snippet=line.strip()[:120],
                ))
                break


@register_scanner("security")
class SecurityScanner(BaseScanner):
    """Scans for common security vulnerabilities."""

    @property
    def category(self) -> str:
        return "security"

    def scan(
        self,
        files: list[FileInfo],
        python_asts: dict[Path, ast.Module],
        project_path: Path,
    ) -> list[Finding]:
        findings: list[Finding] = []
        for fi in files:
            if _is_test_file(fi, project_path):
                continue
            try:
                self._scan_file(fi, python_asts, project_path, findings)
            except Exception:
                continue

        # SEC-011: .env file committed to repo
        self._check_env_files(project_path, findings)

        return findings

    def _check_env_files(
        self, project_path: Path, findings: list[Finding],
    ) -> None:
        """SEC-011: Check for .env files that shouldn't be committed."""
        for entry in project_path.iterdir():
            if entry.is_file() and _ENV_FILE_PATTERN.match(entry.name):
                # Check if there's a .gitignore that excludes it
                gitignore = project_path / ".gitignore"
                ignored = False
                if gitignore.is_file():
                    try:
                        content = gitignore.read_text(encoding="utf-8", errors="ignore")
                        if entry.name in content or ".env" in content:
                            ignored = True
                    except OSError:
                        pass
                if not ignored:
                    findings.append(Finding(
                        rule_id="SEC-011",
                        category="security",
                        severity="fail",
                        message=f"Environment file '{entry.name}' found and not in .gitignore",
                        file_path=entry.name,
                        suggestion="Add .env* to .gitignore and use environment variables",
                    ))

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
        rel = _rel(fi.path, project_path)
        lines = content.splitlines()
        tree = python_asts.get(fi.path)
        ctx = _FileCtx(fi, content, lines, rel, tree)
        _check_hardcoded_secrets(ctx, findings)
        _check_sql_injection(ctx, findings)
        _check_eval_exec(ctx, findings)
        _check_debug_mode(ctx, findings)
        _check_wildcard_cors(ctx, findings)
        _check_dangerous_html(ctx, findings)
        _check_connection_strings(ctx, findings)
        _check_unsafe_deserialization(ctx, findings)
        _check_shell_injection(ctx, findings)
        _check_path_traversal(ctx, findings)
