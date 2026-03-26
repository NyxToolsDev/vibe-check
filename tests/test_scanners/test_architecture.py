"""Tests for the architecture scanner."""

from __future__ import annotations

import ast
from pathlib import Path

from tests.conftest import make_file
from vibe_check.scanners.architecture import ArchitectureScanner


def _scan_arch(tmp_path: Path, name: str, content: str, language: str = "python"):
    fi = make_file(tmp_path, name, content, language)
    scanner = ArchitectureScanner()
    asts = {}
    if language == "python":
        try:
            asts[fi.path] = ast.parse(content)
        except SyntaxError:
            pass
    return scanner.scan([fi], asts, tmp_path)


class TestGodFiles:
    def test_flags_file_over_500_lines(self, tmp_path: Path):
        code = "\n".join(f"x_{i} = {i}" for i in range(501))
        findings = _scan_arch(tmp_path, "big.py", code)
        assert any(f.rule_id == "ARC-001" for f in findings)

    def test_allows_file_under_500_lines(self, tmp_path: Path):
        code = "\n".join(f"x_{i} = {i}" for i in range(100))
        findings = _scan_arch(tmp_path, "small.py", code)
        assert not any(f.rule_id == "ARC-001" for f in findings)


class TestBareExcept:
    def test_detects_bare_except(self, tmp_path: Path):
        code = "try:\n    pass\nexcept:\n    pass"
        findings = _scan_arch(tmp_path, "handler.py", code)
        assert any(f.rule_id == "ARC-003" for f in findings)

    def test_allows_typed_except(self, tmp_path: Path):
        code = "try:\n    pass\nexcept ValueError:\n    pass"
        findings = _scan_arch(tmp_path, "handler.py", code)
        assert not any(f.rule_id == "ARC-003" for f in findings)
