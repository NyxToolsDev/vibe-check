"""Dependencies scanner — checks dependency management practices."""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path

from vibe_check.engine.models import Finding
from vibe_check.engine.registry import register_scanner
from vibe_check.parsers.file_walker import FileInfo
from vibe_check.scanners.base import BaseScanner

_LOCK_FILES = {
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "Pipfile.lock",
    "poetry.lock",
}

_PINNED_PATTERN = re.compile(r"""[=~><!]=""")
_COMMENT_OR_EMPTY = re.compile(r"""^\s*(?:#|$)""")
_OPTION_LINE = re.compile(r"""^\s*-""")


@register_scanner("dependencies")
class DependenciesScanner(BaseScanner):
    """Scans for dependency management issues."""

    @property
    def category(self) -> str:
        return "dependencies"

    def scan(
        self,
        files: list[FileInfo],
        python_asts: dict[Path, ast.Module],
        project_path: Path,
    ) -> list[Finding]:
        findings: list[Finding] = []

        try:
            self._check_lock_file(project_path, findings)
            self._check_requirements_txt(project_path, findings)
            self._check_package_json(project_path, findings)
        except Exception:
            pass

        return findings

    def _check_lock_file(
        self,
        project_path: Path,
        findings: list[Finding],
    ) -> None:
        """DEP-001: Check for presence of lock file."""
        for name in _LOCK_FILES:
            if (project_path / name).is_file():
                return

        # Check if there's even a dependency file to warrant a lock file
        has_deps = (
            (project_path / "requirements.txt").is_file()
            or (project_path / "package.json").is_file()
            or (project_path / "Pipfile").is_file()
            or (project_path / "pyproject.toml").is_file()
        )
        if has_deps:
            findings.append(Finding(
                rule_id="DEP-001",
                category="dependencies",
                severity="warn",
                message="No dependency lock file found",
                suggestion="Generate a lock file to ensure reproducible builds",
            ))

    def _check_requirements_txt(
        self,
        project_path: Path,
        findings: list[Finding],
    ) -> None:
        """DEP-002 & DEP-004: Check requirements.txt for pinning and count."""
        req_file = project_path / "requirements.txt"
        if not req_file.is_file():
            return

        try:
            text = req_file.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            return

        lines = text.splitlines()
        unpinned: list[tuple[str, int]] = []
        dep_count = 0

        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if _COMMENT_OR_EMPTY.match(stripped):
                continue
            if _OPTION_LINE.match(stripped):
                continue

            dep_count += 1
            # Check if version is pinned
            pkg_name = stripped.split("[")[0]  # handle extras
            if not _PINNED_PATTERN.search(pkg_name) and not _PINNED_PATTERN.search(stripped):
                unpinned.append((stripped, i))

        # DEP-002: Unpinned versions
        if unpinned:
            if len(unpinned) <= 3:
                for pkg, lineno in unpinned:
                    findings.append(Finding(
                        rule_id="DEP-002",
                        category="dependencies",
                        severity="warn",
                        message=f"Unpinned dependency: {pkg}",
                        file_path="requirements.txt",
                        line_number=lineno,
                        suggestion="Pin version with == or use version ranges (>=, ~=)",
                    ))
            else:
                findings.append(Finding(
                    rule_id="DEP-002",
                    category="dependencies",
                    severity="warn",
                    message=f"{len(unpinned)} dependencies without version constraints",
                    file_path="requirements.txt",
                    suggestion="Pin versions to ensure reproducible builds",
                ))

        # DEP-004: Too many dependencies
        if dep_count > 50:
            findings.append(Finding(
                rule_id="DEP-004",
                category="dependencies",
                severity="fail",
                message=f"Too many direct dependencies ({dep_count} in requirements.txt)",
                file_path="requirements.txt",
                suggestion="Review and remove unused dependencies",
            ))
        elif dep_count > 30:
            findings.append(Finding(
                rule_id="DEP-004",
                category="dependencies",
                severity="warn",
                message=f"High number of direct dependencies ({dep_count} in requirements.txt)",
                file_path="requirements.txt",
                suggestion="Review dependencies — consider if all are necessary",
            ))

    def _check_package_json(
        self,
        project_path: Path,
        findings: list[Finding],
    ) -> None:
        """DEP-003 & DEP-004: Check package.json for pinning and count."""
        pkg_file = project_path / "package.json"
        if not pkg_file.is_file():
            return

        try:
            text = pkg_file.read_text(encoding="utf-8", errors="ignore")
            data = json.loads(text)
        except (OSError, json.JSONDecodeError):
            return

        deps = data.get("dependencies", {})
        dev_deps = data.get("devDependencies", {})
        all_deps = {**deps, **dev_deps}

        # DEP-003: Unpinned versions (wildcard or "latest")
        unpinned: list[str] = []
        for name, version in all_deps.items():
            if not isinstance(version, str):
                continue
            if version in ("*", "latest"):
                unpinned.append(name)

        for name in unpinned:
            findings.append(Finding(
                rule_id="DEP-003",
                category="dependencies",
                severity="warn",
                message=f"Unpinned dependency in package.json: {name}",
                file_path="package.json",
                suggestion="Use a specific version range instead of * or latest",
            ))

        # DEP-004: Too many direct dependencies
        total = len(deps)
        if total > 50:
            findings.append(Finding(
                rule_id="DEP-004",
                category="dependencies",
                severity="fail",
                message=f"Too many direct dependencies ({total} in package.json)",
                file_path="package.json",
                suggestion="Review and remove unused dependencies",
            ))
        elif total > 30:
            findings.append(Finding(
                rule_id="DEP-004",
                category="dependencies",
                severity="warn",
                message=f"High number of direct dependencies ({total} in package.json)",
                file_path="package.json",
                suggestion="Review dependencies — consider if all are necessary",
            ))
