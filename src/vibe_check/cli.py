"""Click-based CLI for vibe-check."""

from __future__ import annotations

import sys
from pathlib import Path

import click
from rich.console import Console

from vibe_check import __version__
from vibe_check.engine.models import Grade
from vibe_check.utils.license import check_license

_VALID_CATEGORIES = [
    "security", "testing", "code_quality", "architecture", "dependencies", "hipaa",
]

_VALID_FORMATS = ["terminal", "json", "markdown", "all"]

_GRADE_ORDER: dict[str, int] = {"A": 5, "B": 4, "C": 3, "D": 2, "F": 1}


@click.group(invoke_without_command=True)
@click.version_option(version=__version__, prog_name="vibe-check")
@click.pass_context
def main(ctx: click.Context) -> None:
    """Vibe Check — Production-readiness scanner for AI/vibe-coded projects."""
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


@main.command()
@click.argument("path", default=".", type=click.Path(exists=True, file_okay=False))
@click.option(
    "--format", "-f",
    "output_format",
    type=click.Choice(_VALID_FORMATS, case_sensitive=False),
    default="terminal",
    help="Output format (terminal, json, markdown, all).",
)
@click.option(
    "--output", "-o",
    "output_path",
    type=click.Path(),
    default=None,
    help="Write report to file instead of stdout.",
)
@click.option(
    "--category", "-c",
    "categories",
    multiple=True,
    type=click.Choice(_VALID_CATEGORIES, case_sensitive=False),
    help="Scan only specific categories (repeatable).",
)
@click.option(
    "--ci",
    is_flag=True,
    default=False,
    help="CI mode: exit non-zero if grade is below threshold.",
)
@click.option(
    "--threshold",
    type=click.Choice(["A", "B", "C", "D", "F"], case_sensitive=True),
    default="C",
    help="Minimum passing grade for --ci mode (default: C).",
)
@click.option(
    "--license-key",
    envvar="VIBE_CHECK_LICENSE_KEY",
    default=None,
    help="License key for Pro features (or set VIBE_CHECK_LICENSE_KEY).",
)
def scan(
    path: str,
    output_format: str,
    output_path: str | None,
    categories: tuple[str, ...],
    ci: bool,
    threshold: str,
    license_key: str | None,
) -> None:
    """Scan a project for production-readiness issues."""
    # Import here to ensure scanners are registered
    from vibe_check.engine.runner import run_scan
    from vibe_check.reporters import json_reporter, markdown
    from vibe_check.reporters.terminal import render as terminal_render

    project_path = Path(path).resolve()
    licensed = check_license(license_key)
    cat_list = list(categories) if categories else None

    console = Console(stderr=True)
    console.print(f"[cyan]Scanning {project_path}...[/]")

    report = run_scan(
        project_path=project_path,
        categories=cat_list,
        licensed=licensed,
    )

    # Output
    if output_format in ("terminal", "all"):
        terminal_render(report)

    if output_format in ("json", "all"):
        json_str = json_reporter.render(report)
        if output_path and output_format == "json":
            _write_file(output_path, json_str)
        elif output_format == "json":
            click.echo(json_str)
        elif output_format == "all" and output_path:
            _write_file(f"{output_path}.json", json_str)

    if output_format in ("markdown", "all"):
        md_str = markdown.render(report)
        if output_path and output_format == "markdown":
            _write_file(output_path, md_str)
        elif output_format == "markdown":
            click.echo(md_str)
        elif output_format == "all" and output_path:
            _write_file(f"{output_path}.md", md_str)

    # CI mode: exit non-zero if below threshold
    if ci:
        report_rank = _GRADE_ORDER.get(report.overall_grade, 0)
        threshold_rank = _GRADE_ORDER.get(threshold, 3)
        if report_rank < threshold_rank:
            console.print(
                f"[bold red]CI check failed:[/] Grade {report.overall_grade} "
                f"is below threshold {threshold}"
            )
            sys.exit(1)
        else:
            console.print(
                f"[bold green]CI check passed:[/] Grade {report.overall_grade} "
                f"meets threshold {threshold}"
            )


def _write_file(path: str, content: str) -> None:
    """Write content to a file and print confirmation."""
    p = Path(path)
    p.write_text(content, encoding="utf-8")
    click.echo(f"Report written to {p}", err=True)
