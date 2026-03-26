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
    from vibe_check.engine.runner import run_scan

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

    _emit_report(report, output_format, output_path)
    _check_ci_threshold(report, ci, threshold, console)


def _emit_report(
    report: object, output_format: str, output_path: str | None,
) -> None:
    """Write the scan report in the requested format(s)."""
    from vibe_check.reporters import json_reporter, markdown
    from vibe_check.reporters.terminal import render as terminal_render

    if output_format in ("terminal", "all"):
        terminal_render(report)

    if output_format in ("json", "all"):
        json_str = json_reporter.render(report)
        _route_output(json_str, output_format, output_path, "json")

    if output_format in ("markdown", "all"):
        md_str = markdown.render(report)
        _route_output(md_str, output_format, output_path, "markdown")


def _route_output(
    content: str, output_format: str, output_path: str | None, fmt: str,
) -> None:
    """Route rendered output to file or stdout."""
    if output_path and output_format == fmt:
        _write_file(output_path, content)
    elif output_format == fmt:
        click.echo(content)
    elif output_format == "all" and output_path:
        ext = "json" if fmt == "json" else "md"
        _write_file(f"{output_path}.{ext}", content)


def _check_ci_threshold(
    report: object, ci: bool, threshold: str, console: Console,
) -> None:
    """Exit non-zero if the grade is below the CI threshold."""
    if not ci:
        return
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


@main.command()
@click.argument("license_key")
def activate(license_key: str) -> None:
    """Activate a Pro license key for HIPAA compliance scanning.

    After purchasing at nyxtools.gumroad.com, run:

        vibe-check activate YOUR-LICENSE-KEY

    Or set the environment variable:

        export VIBE_CHECK_LICENSE_KEY=YOUR-LICENSE-KEY
    """
    console = Console()
    console.print(f"[cyan]Validating license key...[/]")

    valid = check_license(license_key)
    if valid:
        console.print("[bold green]License activated successfully![/]")
        console.print("HIPAA compliance scanning is now unlocked.")
        console.print(
            "\n[dim]Tip: set VIBE_CHECK_LICENSE_KEY as an environment variable "
            "so you don't need to pass it every time.[/]"
        )
    else:
        console.print("[bold red]Invalid license key.[/]")
        console.print(
            "Please check your key and try again.\n"
            "Purchase a Pro license at: [link]https://nyxtools.gumroad.com/l/vibe-check-pro[/]"
        )
        sys.exit(1)


@main.command()
def status() -> None:
    """Show current license status."""
    console = Console()
    licensed = check_license()
    if licensed:
        console.print("[bold green]Pro license:[/] Active")
        console.print("HIPAA compliance scanning is enabled.")
    else:
        console.print("[bold yellow]Free tier:[/] 5 of 6 scan categories available")
        console.print(
            "Upgrade to Pro for HIPAA compliance scanning: "
            "[link]https://nyxtools.gumroad.com/l/vibe-check-pro[/]"
        )


def _write_file(path: str, content: str) -> None:
    """Write content to a file and print confirmation."""
    p = Path(path)
    p.write_text(content, encoding="utf-8")
    click.echo(f"Report written to {p}", err=True)
