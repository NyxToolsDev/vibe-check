"""Tests for the HIPAA scanner."""

from __future__ import annotations

from pathlib import Path

from tests.conftest import make_file
from vibe_check.scanners.hipaa import HipaaScanner


def _scan_hipaa(tmp_path: Path, name: str, content: str, language: str = "python"):
    fi = make_file(tmp_path, name, content, language)
    scanner = HipaaScanner()
    return scanner.scan([fi], {}, tmp_path, licensed=True)


class TestPHIInLogs:
    def test_detects_ssn_in_log(self, tmp_path: Path):
        code = 'logger.info(f"Record SSN: {ssn}")'
        findings = _scan_hipaa(tmp_path, "app.py", code)
        assert any(f.rule_id == "HIPAA-001" for f in findings)

    def test_detects_patient_name_in_print(self, tmp_path: Path):
        code = 'print(f"Patient: {patient_name}")'
        findings = _scan_hipaa(tmp_path, "app.py", code)
        assert any(f.rule_id == "HIPAA-001" for f in findings)

    def test_ignores_patient_count(self, tmp_path: Path):
        """patient_count is not PHI — should NOT trigger."""
        code = 'logger.info(f"Total patients: {patient_count}")'
        findings = _scan_hipaa(tmp_path, "app.py", code)
        assert not any(f.rule_id == "HIPAA-001" for f in findings)

    def test_ignores_patient_service(self, tmp_path: Path):
        """patient_service is a class/module name, not PHI."""
        code = 'logger.info(f"Using service: {patient_service}")'
        findings = _scan_hipaa(tmp_path, "app.py", code)
        assert not any(f.rule_id == "HIPAA-001" for f in findings)

    def test_detects_mrn_in_log(self, tmp_path: Path):
        code = 'logger.warning(f"MRN lookup: {mrn}")'
        findings = _scan_hipaa(tmp_path, "app.py", code)
        assert any(f.rule_id == "HIPAA-001" for f in findings)

    def test_detects_date_of_birth(self, tmp_path: Path):
        code = 'print(f"DOB: {date_of_birth}")'
        findings = _scan_hipaa(tmp_path, "app.py", code)
        assert any(f.rule_id == "HIPAA-001" for f in findings)


class TestUpsell:
    def test_returns_upsell_when_unlicensed(self, tmp_path: Path):
        fi = make_file(tmp_path, "app.py", "x = 1")
        scanner = HipaaScanner()
        findings = scanner.scan([fi], {}, tmp_path, licensed=False)
        assert len(findings) == 1
        assert findings[0].rule_id == "HIPAA-000"
        assert "Pro" in findings[0].message
