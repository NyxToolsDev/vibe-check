"""Grade calculation and scoring logic."""

from __future__ import annotations

from vibe_check.engine.models import CategoryResult, Finding, Grade

CATEGORY_WEIGHTS: dict[str, int] = {
    "security": 30,
    "testing": 20,
    "code_quality": 15,
    "architecture": 15,
    "dependencies": 10,
    "hipaa": 10,
}

SEVERITY_DEDUCTIONS: dict[str, int] = {
    "fail": 15,
    "warn": 5,
    "info": 1,
}


def _grade_from_score(score: int) -> Grade:
    """Convert a numeric score (0-100) to a letter grade."""
    if score >= 85:
        return "A"
    if score >= 70:
        return "B"
    if score >= 55:
        return "C"
    if score >= 40:
        return "D"
    return "F"


def score_category(findings: list[Finding]) -> tuple[int, Grade]:
    """Score a list of findings for a single category.

    Returns (score, grade) where score is 0-100.
    """
    score = 100
    for f in findings:
        score -= SEVERITY_DEDUCTIONS.get(f.severity, 0)
    score = max(0, score)
    return score, _grade_from_score(score)


def calculate_overall(
    category_results: list[CategoryResult],
    hipaa_active: bool,
) -> tuple[int, Grade]:
    """Calculate weighted overall score and grade.

    When HIPAA is not active, its weight is redistributed proportionally
    across other categories.
    """
    weights = dict(CATEGORY_WEIGHTS)

    if not hipaa_active:
        hipaa_weight = weights.pop("hipaa", 0)
        remaining_total = sum(weights.values())
        if remaining_total > 0:
            for cat in weights:
                weights[cat] = weights[cat] + (hipaa_weight * weights[cat] / remaining_total)

    total_weight = sum(weights.values())
    if total_weight == 0:
        return 100, "A"

    weighted_sum = 0.0
    for result in category_results:
        cat_weight = weights.get(result.category, 0)
        weighted_sum += result.score * cat_weight

    overall = int(round(weighted_sum / total_weight))
    overall = max(0, min(100, overall))
    return overall, _grade_from_score(overall)
