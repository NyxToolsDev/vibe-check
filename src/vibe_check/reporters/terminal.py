"""Rich-based terminal reporter."""

from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from vibe_check.engine.models import CategoryResult, Grade, ScanReport, Severity

_SEVERITY_ICONS: dict[str, str] = {
    "fail": "[bold red]FAIL[/]",
    "warn": "[bold yellow]WARN[/]",
    "info": "[dim]INFO[/]",
}

_GRADE_COLORS: dict[str, str] = {
    "A": "bold green",
    "B": "green",
    "C": "yellow",
    "D": "bold yellow",
    "F": "bold red",
}


def _grade_styled(grade: Grade) -> str:
    color = _GRADE_COLORS.get(grade, "white")
    return f"[{color}]{grade}[/]"


def _severity_counts(result: CategoryResult) -> tuple[int, int, int]:
    """Count pass/warn/fail for a category (info counts as pass here)."""
    fails = sum(1 for f in result.findings if f.severity == "fail")
    warns = sum(1 for f in result.findings if f.severity == "warn")
    infos = sum(1 for f in result.findings if f.severity == "info")
    return infos, warns, fails


def render(report: ScanReport, console: Console | None = None) -> None:
    """Render a scan report to the terminal using Rich."""
    if console is None:
        console = Console()

    # Header
    console.print()
    lang_parts = [f"{lang}: {count}" for lang, count in report.files_by_language.items()]
    lang_str = ", ".join(lang_parts) if lang_parts else "none detected"

    header_text = (
        f"[bold]Project:[/] {report.project_path}\n"
        f"[bold]Files scanned:[/] {report.total_files}\n"
        f"[bold]Languages:[/] {lang_str}"
    )
    console.print(Panel(header_text, title="[bold cyan]Vibe Check[/]", border_style="cyan"))

    # Category summary table
    table = Table(title="Category Results", show_header=True, header_style="bold")
    table.add_column("Category", style="bold", min_width=15)
    table.add_column("Info", justify="right")
    table.add_column("Warn", justify="right")
    table.add_column("Fail", justify="right")
    table.add_column("Score", justify="right")
    table.add_column("Grade", justify="center")

    for result in report.categories:
        infos, warns, fails = _severity_counts(result)
        table.add_row(
            result.category.replace("_", " ").title(),
            str(infos) if infos else "[dim]-[/]",
            f"[yellow]{warns}[/]" if warns else "[dim]-[/]",
            f"[red]{fails}[/]" if fails else "[dim]-[/]",
            str(result.score),
            _grade_styled(result.grade),
        )

    console.print(table)
    console.print()

    # Top findings
    all_findings = []
    for result in report.categories:
        all_findings.extend(result.findings)

    # Sort: fail first, then warn, then info
    severity_order: dict[str, int] = {"fail": 0, "warn": 1, "info": 2}
    all_findings.sort(key=lambda f: severity_order.get(f.severity, 3))
    top = all_findings[:10]

    if top:
        console.print("[bold]Top Findings:[/]")
        for finding in top:
            icon = _SEVERITY_ICONS.get(finding.severity, "")
            location = ""
            if finding.file_path:
                location = f" [dim]{finding.file_path}"
                if finding.line_number:
                    location += f":{finding.line_number}"
                location += "[/]"
            console.print(
                f"  {icon} [{finding.rule_id}] {finding.message}{location}"
            )
        if len(all_findings) > 10:
            console.print(f"  [dim]... and {len(all_findings) - 10} more findings[/]")
        console.print()

    # Overall grade
    grade_color = _GRADE_COLORS.get(report.overall_grade, "white")
    grade_display = Text(f" {report.overall_grade} ", style=f"{grade_color} reverse")
    console.print(Panel(
        Text.assemble(
            "Overall Grade: ",
            grade_display,
            f"  Score: {report.overall_score}/100",
        ),
        border_style=grade_color.replace("bold ", ""),
    ))

    # Scan time
    console.print(f"[dim]Scan completed in {report.total_scan_time_ms:.0f}ms[/]")

    # Upsell for unlicensed
    if not report.licensed:
        console.print()
        console.print(
            "[dim]Unlock HIPAA compliance scanning: "
            "nyxtools.gumroad.com/l/vibe-check-pro[/]"
        )

    console.print()
