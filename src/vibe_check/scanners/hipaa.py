"""HIPAA compliance scanner — detects PHI handling violations."""

from __future__ import annotations

import ast
import re
from pathlib import Path

from vibe_check.engine.models import Finding
from vibe_check.engine.registry import register_scanner
from vibe_check.parsers.file_walker import FileInfo
from vibe_check.parsers.python_parser import get_imports
from vibe_check.scanners.base import BaseScanner

# High-confidence PHI fields — these are almost always actual PHI
_PHI_DIRECT_FIELDS = re.compile(
    r"""\b(?:ssn|social_security|date_of_birth|mrn|medical_record_number"""
    r"""|diagnosis_code|icd_code|insurance_id|policy_number"""
    r"""|beneficiary_id|medicare_id|medicaid_id)\b""",
    re.IGNORECASE,
)

# Contextual PHI fields — only flag when combined with a PHI-related suffix
# e.g. patient_name, patient_ssn, patient_address → flagged
# e.g. patient_count, patient_list, patient_service → not flagged
_PHI_CONTEXTUAL_PREFIX = re.compile(
    r"""\bpatient[_.](?:name|first_name|last_name|dob|ssn|mrn|email"""
    r"""|phone|address|zip|city|state|birth|gender|sex|race"""
    r"""|diagnosis|insurance|id_number|social|record)\b""",
    re.IGNORECASE,
)

# Standalone PII fields that are sensitive in healthcare context
_PHI_PII_FIELDS = re.compile(
    r"""\b(?:phone_number|email_address|street_address|zip_code"""
    r"""|date_of_birth|dob|birth_date|maiden_name"""
    r"""|drivers_license|passport_number)\b""",
    re.IGNORECASE,
)


def _has_phi(line: str) -> bool:
    """Check if a line contains PHI field references with context awareness."""
    return bool(
        _PHI_DIRECT_FIELDS.search(line)
        or _PHI_CONTEXTUAL_PREFIX.search(line)
        or _PHI_PII_FIELDS.search(line)
    )

_LOG_CALL_PATTERNS = re.compile(
    r"""(?:logger\.\w+|logging\.\w+|print|console\.log|console\.error"""
    r"""|console\.warn|console\.info)\s*\(""",
    re.IGNORECASE,
)

_ENCRYPTION_MODULES = {
    "cryptography",
    "hashlib",
    "bcrypt",
    "argon2",
    "passlib",
    "cryptography.fernet",
    "nacl",
}

_DB_MODULES = {
    "sqlalchemy",
    "psycopg2",
    "pymongo",
    "sqlite3",
    "asyncpg",
    "databases",
    "tortoise",
    "peewee",
    "django.db",
    "prisma",
    "supabase",
    "motor",
}

_SSL_PATTERNS = re.compile(
    r"""(?:ssl_context|ssl=|https|TLS|HTTPS|ssl_certfile|ssl_keyfile"""
    r"""|SECURE_SSL_REDIRECT|force_https)""",
    re.IGNORECASE,
)

_SESSION_TIMEOUT_PATTERNS = re.compile(
    r"""(?:session.?timeout|session.?expir|session.?lifetime"""
    r"""|SESSION_COOKIE_AGE|PERMANENT_SESSION_LIFETIME|session.?max.?age"""
    r"""|cookie.?maxAge|express.?session.*maxAge|idle.?timeout)""",
    re.IGNORECASE,
)

_AUDIT_PATTERNS = re.compile(
    r"""(?:audit|audit_log|AuditLog|audit_trail)""",
)

_EXCEPT_BLOCK_PY = re.compile(r"""^\s*except""")
_CATCH_BLOCK_JS = re.compile(r"""\.catch\s*\(|catch\s*\(""")

_UPSELL_MESSAGE = (
    "Upgrade to Pro for HIPAA compliance scanning "
    "— nyxtools.gumroad.com/l/vibe-check-pro"
)


def _rel(path: Path, base: Path) -> str:
    try:
        return str(path.relative_to(base))
    except ValueError:
        return str(path)


@register_scanner("hipaa")
class HipaaScanner(BaseScanner):
    """Scans for HIPAA compliance issues in healthcare applications."""

    @property
    def category(self) -> str:
        return "hipaa"

    def scan(
        self,
        files: list[FileInfo],
        python_asts: dict[Path, ast.Module],
        project_path: Path,
        licensed: bool = False,
    ) -> list[Finding]:
        if not licensed:
            return [
                Finding(
                    rule_id="HIPAA-000",
                    category="hipaa",
                    severity="info",
                    message=_UPSELL_MESSAGE,
                )
            ]

        findings: list[Finding] = []
        try:
            self._check_phi_in_logs(files, project_path, findings)
            self._check_phi_in_errors(files, project_path, findings)
            self._check_https(files, project_path, findings)
            self._check_audit_logging(files, python_asts, project_path, findings)
            self._check_session_timeout(files, project_path, findings)
            self._check_encryption(files, python_asts, project_path, findings)
        except Exception:
            pass
        return findings

    def _check_phi_in_logs(
        self,
        files: list[FileInfo],
        project_path: Path,
        findings: list[Finding],
    ) -> None:
        """HIPAA-001: PHI field names in log/print statements."""
        for fi in files:
            content = fi.content
            if not content:
                continue
            rel_path = _rel(fi.path, project_path)
            for i, line in enumerate(content.splitlines(), 1):
                if _LOG_CALL_PATTERNS.search(line) and _has_phi(line):
                    findings.append(Finding(
                        rule_id="HIPAA-001",
                        category="hipaa",
                        severity="fail",
                        message="Possible PHI in log/print statement",
                        file_path=rel_path,
                        line_number=i,
                        suggestion="Use hashed identifiers instead of raw PHI",
                        snippet=line.strip()[:120],
                    ))

    def _check_phi_in_errors(
        self,
        files: list[FileInfo],
        project_path: Path,
        findings: list[Finding],
    ) -> None:
        """HIPAA-004: PHI fields in error/exception messages."""
        for fi in files:
            content = fi.content
            if not content:
                continue
            rel_path = _rel(fi.path, project_path)
            lines = content.splitlines()
            in_except = False
            for i, line in enumerate(lines, 1):
                if _EXCEPT_BLOCK_PY.match(line) or _CATCH_BLOCK_JS.search(line):
                    in_except = True
                elif in_except and line.strip() and not line[0].isspace():
                    in_except = False

                if in_except and _has_phi(line):
                    findings.append(Finding(
                        rule_id="HIPAA-004",
                        category="hipaa",
                        severity="fail",
                        message="Possible PHI in error handling block",
                        file_path=rel_path,
                        line_number=i,
                        suggestion="Sanitize error messages — never include PHI",
                        snippet=line.strip()[:120],
                    ))

    def _check_https(
        self,
        files: list[FileInfo],
        project_path: Path,
        findings: list[Finding],
    ) -> None:
        """HIPAA-002: Missing HTTPS enforcement."""
        server_patterns = re.compile(
            r"""(?:app\.listen|app\.run|createServer|uvicorn\.run|gunicorn)""",
        )
        has_server_file = False
        has_ssl_config = False

        for fi in files:
            content = fi.content
            if not content:
                continue
            if server_patterns.search(content):
                has_server_file = True
                if _SSL_PATTERNS.search(content):
                    has_ssl_config = True
                    break

        if has_server_file and not has_ssl_config:
            findings.append(Finding(
                rule_id="HIPAA-002",
                category="hipaa",
                severity="fail",
                message="No SSL/TLS configuration detected in server files",
                suggestion="Configure HTTPS/TLS for all PHI transmission",
            ))

    def _check_audit_logging(
        self,
        files: list[FileInfo],
        python_asts: dict[Path, ast.Module],
        project_path: Path,
        findings: list[Finding],
    ) -> None:
        """HIPAA-003: No audit logging detected."""
        has_audit = False
        for fi in files:
            content = fi.content
            if not content:
                continue
            if _AUDIT_PATTERNS.search(content):
                has_audit = True
                break

        if not has_audit and len(files) > 5:
            findings.append(Finding(
                rule_id="HIPAA-003",
                category="hipaa",
                severity="warn",
                message="No audit logging mechanism detected",
                suggestion="Implement audit trails for all PHI access",
            ))

    def _check_session_timeout(
        self,
        files: list[FileInfo],
        project_path: Path,
        findings: list[Finding],
    ) -> None:
        """HIPAA-005: Missing session timeout configuration."""
        has_timeout = False
        for fi in files:
            content = fi.content
            if not content:
                continue
            if _SESSION_TIMEOUT_PATTERNS.search(content):
                has_timeout = True
                break

        if not has_timeout and len(files) > 5:
            findings.append(Finding(
                rule_id="HIPAA-005",
                category="hipaa",
                severity="warn",
                message="No session timeout configuration detected",
                suggestion="Configure session timeouts for inactive users",
            ))

    def _check_encryption(
        self,
        files: list[FileInfo],
        python_asts: dict[Path, ast.Module],
        project_path: Path,
        findings: list[Finding],
    ) -> None:
        """HIPAA-006: No encryption library in files with DB operations."""
        has_db = False
        has_encryption = False

        for fi in files:
            tree = python_asts.get(fi.path)
            if tree is not None:
                imports = set(get_imports(tree))
                if imports & _DB_MODULES:
                    has_db = True
                if imports & _ENCRYPTION_MODULES:
                    has_encryption = True
            else:
                # For JS/TS, check string content
                content = fi.content
                if not content:
                    continue
                if any(kw in content for kw in ("prisma", "mongoose", "sequelize", "knex", "typeorm")):
                    has_db = True
                if any(kw in content for kw in ("bcrypt", "crypto", "argon2", "scrypt")):
                    has_encryption = True

        if has_db and not has_encryption:
            findings.append(Finding(
                rule_id="HIPAA-006",
                category="hipaa",
                severity="warn",
                message="Database operations found but no encryption library detected",
                suggestion="Use encryption for sensitive data at rest (cryptography, bcrypt, argon2)",
            ))
