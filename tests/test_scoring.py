"""Tests for scoring and grading logic."""

from __future__ import annotations

from vibe_check.engine.models import CategoryResult, Finding
from vibe_check.engine.scoring import calculate_overall, score_category


def _finding(severity: str = "fail") -> Finding:
    return Finding(
        rule_id="TEST-001",
        category="security",
        severity=severity,
        message="test finding",
    )


class TestScoreCategory:
    def test_perfect_score_no_findings(self):
        score, grade = score_category([])
        assert score == 100
        assert grade == "A"

    def test_single_fail_deducts_15(self):
        score, grade = score_category([_finding("fail")])
        assert score == 85
        assert grade == "A"

    def test_single_warn_deducts_5(self):
        score, grade = score_category([_finding("warn")])
        assert score == 95
        assert grade == "A"

    def test_single_info_deducts_1(self):
        score, grade = score_category([_finding("info")])
        assert score == 99
        assert grade == "A"

    def test_many_fails_floor_at_zero(self):
        score, grade = score_category([_finding("fail")] * 10)
        assert score == 0
        assert grade == "F"

    def test_grade_boundaries(self):
        # B boundary: 70-84
        findings = [_finding("fail")] * 2  # 100 - 30 = 70
        score, grade = score_category(findings)
        assert grade == "B"

        # C boundary: 55-69
        findings = [_finding("fail")] * 3  # 100 - 45 = 55
        score, grade = score_category(findings)
        assert grade == "C"

        # D boundary: 40-54
        findings = [_finding("fail")] * 4  # 100 - 60 = 40
        score, grade = score_category(findings)
        assert grade == "D"

        # F boundary: <40
        findings = [_finding("fail")] * 5  # 100 - 75 = 25
        score, grade = score_category(findings)
        assert grade == "F"


class TestCalculateOverall:
    def test_all_perfect_scores(self):
        results = [
            CategoryResult(category="security", findings=[], score=100, grade="A", scan_time_ms=1.0),
            CategoryResult(category="testing", findings=[], score=100, grade="A", scan_time_ms=1.0),
            CategoryResult(category="code_quality", findings=[], score=100, grade="A", scan_time_ms=1.0),
            CategoryResult(category="architecture", findings=[], score=100, grade="A", scan_time_ms=1.0),
            CategoryResult(category="dependencies", findings=[], score=100, grade="A", scan_time_ms=1.0),
        ]
        score, grade = calculate_overall(results, hipaa_active=False)
        assert score == 100
        assert grade == "A"

    def test_hipaa_weight_redistribution(self):
        """When HIPAA is inactive, its 10% weight redistributes to other categories."""
        results = [
            CategoryResult(category="security", findings=[], score=100, grade="A", scan_time_ms=1.0),
            CategoryResult(category="testing", findings=[], score=0, grade="F", scan_time_ms=1.0),
            CategoryResult(category="code_quality", findings=[], score=100, grade="A", scan_time_ms=1.0),
            CategoryResult(category="architecture", findings=[], score=100, grade="A", scan_time_ms=1.0),
            CategoryResult(category="dependencies", findings=[], score=100, grade="A", scan_time_ms=1.0),
        ]
        score_no_hipaa, _ = calculate_overall(results, hipaa_active=False)

        # Add HIPAA result and enable it
        results.append(
            CategoryResult(category="hipaa", findings=[], score=100, grade="A", scan_time_ms=1.0),
        )
        score_with_hipaa, _ = calculate_overall(results, hipaa_active=True)

        # With HIPAA active, testing's 0 has less relative weight → higher overall
        assert score_with_hipaa > score_no_hipaa

    def test_security_weight_dominates(self):
        """Security has 30% weight — a bad security score should tank overall."""
        results = [
            CategoryResult(category="security", findings=[], score=0, grade="F", scan_time_ms=1.0),
            CategoryResult(category="testing", findings=[], score=100, grade="A", scan_time_ms=1.0),
            CategoryResult(category="code_quality", findings=[], score=100, grade="A", scan_time_ms=1.0),
            CategoryResult(category="architecture", findings=[], score=100, grade="A", scan_time_ms=1.0),
            CategoryResult(category="dependencies", findings=[], score=100, grade="A", scan_time_ms=1.0),
        ]
        score, grade = calculate_overall(results, hipaa_active=False)
        assert score <= 70  # Security 0 at 30% weight should pull below A
