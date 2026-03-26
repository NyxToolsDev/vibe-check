"""Testing scanner — checks for test coverage and configuration."""

from __future__ import annotations

import ast
from pathlib import Path

from vibe_check.engine.models import Finding
from vibe_check.engine.registry import register_scanner
from vibe_check.parsers.file_walker import FileInfo
from vibe_check.scanners.base import BaseScanner

_TEST_DIR_NAMES = {"tests", "test", "__tests__", "spec"}

_TEST_RUNNER_FILES = {
    "pytest.ini",
    "jest.config.js",
    "jest.config.ts",
    "jest.config.mjs",
    "jest.config.cjs",
    ".mocharc.yml",
    ".mocharc.yaml",
    ".mocharc.json",
    ".mocharc.js",
    "vitest.config.ts",
    "vitest.config.js",
}


def _has_pytest_config(project_path: Path) -> bool:
    """Check if pyproject.toml or setup.cfg contain pytest config."""
    for name in ("pyproject.toml", "setup.cfg"):
        cfg = project_path / name
        if cfg.is_file():
            try:
                text = cfg.read_text(encoding="utf-8", errors="ignore")
                if "[tool.pytest" in text or "[tool:pytest]" in text:
                    return True
            except OSError:
                pass
    return False


def _is_test_file(path: Path) -> bool:
    """Heuristic: is this file a test file?"""
    name = path.stem.lower()
    return (
        name.startswith("test_")
        or name.endswith("_test")
        or name.startswith("test")
        or name.endswith(".test")
        or name.endswith(".spec")
    )


def _rel(path: Path, base: Path) -> str:
    try:
        return str(path.relative_to(base))
    except ValueError:
        return str(path)


@register_scanner("testing")
class TestingScanner(BaseScanner):
    """Scans for test coverage and testing configuration."""

    @property
    def category(self) -> str:
        return "testing"

    def scan(
        self,
        files: list[FileInfo],
        python_asts: dict[Path, ast.Module],
        project_path: Path,
    ) -> list[Finding]:
        findings: list[Finding] = []

        try:
            self._check_test_dir(files, project_path, findings)
            self._check_test_coverage(files, project_path, findings)
            self._check_test_ratio(files, findings)
            self._check_test_runner(project_path, findings)
        except Exception:
            pass

        return findings

    def _check_test_dir(
        self,
        files: list[FileInfo],
        project_path: Path,
        findings: list[Finding],
    ) -> None:
        """TST-001: Check if any test directory exists."""
        has_test_dir = False
        for name in _TEST_DIR_NAMES:
            if (project_path / name).is_dir():
                has_test_dir = True
                break

        # Also check if any file lives under a test-like directory
        if not has_test_dir:
            for fi in files:
                parts = set(fi.path.parts)
                if parts & _TEST_DIR_NAMES:
                    has_test_dir = True
                    break

        if not has_test_dir:
            findings.append(Finding(
                rule_id="TST-001",
                category="testing",
                severity="fail",
                message="No test directory found (tests/, test/, __tests__, spec/)",
                suggestion="Create a test directory and add tests for critical paths",
            ))

    def _check_test_coverage(
        self,
        files: list[FileInfo],
        project_path: Path,
        findings: list[Finding],
    ) -> None:
        """TST-002: Check for source files without corresponding test files."""
        test_stems: set[str] = set()
        source_files: list[FileInfo] = []

        for fi in files:
            if _is_test_file(fi.path):
                stem = fi.path.stem.lower()
                # Normalize: test_foo -> foo, foo_test -> foo
                stem = stem.removeprefix("test_")
                stem = stem.removesuffix("_test")
                stem = stem.removesuffix(".test")
                stem = stem.removesuffix(".spec")
                test_stems.add(stem)
            else:
                # Skip init files, config files, etc.
                if fi.path.stem.startswith("_"):
                    continue
                source_files.append(fi)

        untested_count = 0
        for fi in source_files:
            stem = fi.path.stem.lower()
            if stem not in test_stems:
                untested_count += 1
                if untested_count <= 5:  # cap individual findings
                    findings.append(Finding(
                        rule_id="TST-002",
                        category="testing",
                        severity="info",
                        message=f"No test file found for {_rel(fi.path, project_path)}",
                        file_path=_rel(fi.path, project_path),
                        suggestion=f"Add test_{{name}} or {{name}}_test file",
                    ))

        if untested_count > 5:
            findings.append(Finding(
                rule_id="TST-002",
                category="testing",
                severity="warn",
                message=f"{untested_count} source files have no corresponding test file",
                suggestion="Prioritize testing for critical business logic files",
            ))

    def _check_test_ratio(
        self,
        files: list[FileInfo],
        findings: list[Finding],
    ) -> None:
        """TST-003: Check test-to-source file ratio."""
        test_count = sum(1 for fi in files if _is_test_file(fi.path))
        source_count = sum(
            1
            for fi in files
            if not _is_test_file(fi.path) and not fi.path.stem.startswith("_")
        )

        if source_count == 0:
            return

        ratio = test_count / source_count
        if ratio < 0.3:
            findings.append(Finding(
                rule_id="TST-003",
                category="testing",
                severity="fail",
                message=f"Test-to-source ratio is {ratio:.2f} (below 0.3 threshold)",
                suggestion="Add more tests — aim for at least 0.5 test-to-source ratio",
            ))
        elif ratio < 0.5:
            findings.append(Finding(
                rule_id="TST-003",
                category="testing",
                severity="warn",
                message=f"Test-to-source ratio is {ratio:.2f} (below 0.5 ideal)",
                suggestion="Continue adding tests to improve coverage",
            ))

    def _check_test_runner(
        self,
        project_path: Path,
        findings: list[Finding],
    ) -> None:
        """TST-004: Check for test runner configuration."""
        for name in _TEST_RUNNER_FILES:
            if (project_path / name).is_file():
                return

        if _has_pytest_config(project_path):
            return

        findings.append(Finding(
            rule_id="TST-004",
            category="testing",
            severity="warn",
            message="No test runner configuration found",
            suggestion="Add pytest.ini, jest.config.js, or configure pytest in pyproject.toml",
        ))
