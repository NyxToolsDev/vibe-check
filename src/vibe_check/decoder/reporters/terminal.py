"""Rich-based terminal reporter for decode results."""

from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.tree import Tree

from vibe_check.decoder.models import DecodeReport


def render(report: DecodeReport, console: Console | None = None) -> None:
    """Render a decode report summary to the terminal using Rich."""
    if console is None:
        console = Console()
    console.print()
    _render_header(report, console)
    _render_file_tree(report, console)
    _render_architecture(report, console)
    _render_footer(report, console)


def _render_header(report: DecodeReport, console: Console) -> None:
    lang_parts = [f"{lang}: {count}" for lang, count in report.files_by_language.items()]
    lang_str = ", ".join(lang_parts) if lang_parts else "none detected"
    ai_str = f"Yes ({report.ai_backend})" if report.ai_enhanced else "No (free tier)"
    header_text = (
        f"[bold]Project:[/] {report.project_path}\n"
        f"[bold]Files analyzed:[/] {report.total_files}\n"
        f"[bold]Languages:[/] {lang_str}\n"
        f"[bold]AI-enhanced:[/] {ai_str}"
    )
    console.print(Panel(header_text, title="[bold cyan]Vibe Check Decode[/]", border_style="cyan"))


def _render_file_tree(report: DecodeReport, console: Console) -> None:
    tree = Tree("[bold]Project Structure[/]")
    # Group files by directory
    dirs: dict[str, list[tuple[str, str]]] = {}
    for fa in report.files:
        parts = fa.path.rsplit("/", 1)
        if len(parts) == 2:
            dir_path, filename = parts
        else:
            dir_path, filename = ".", parts[0]
        dirs.setdefault(dir_path, []).append((filename, fa.summary or ""))

    for dir_path in sorted(dirs):
        if dir_path == ".":
            branch = tree
        else:
            branch = tree.add(f"[bold blue]{dir_path}/[/]")
        for filename, summary in sorted(dirs[dir_path]):
            summary_str = f" [dim]— {summary}[/]" if summary else ""
            branch.add(f"[green]{filename}[/]{summary_str}")

    console.print(tree)
    console.print()


def _render_architecture(report: DecodeReport, console: Console) -> None:
    arch = report.architecture

    # Entry points
    if arch.entry_points:
        console.print("[bold]Entry Points:[/]")
        for ep in arch.entry_points:
            console.print(f"  [cyan]{ep}[/]")
        console.print()

    # External dependencies
    if arch.external_deps:
        table = Table(title="External Dependencies", show_header=False)
        table.add_column("Package", style="yellow")
        # Show in rows of 4
        row: list[str] = []
        for dep in arch.external_deps:
            row.append(dep)
            if len(row) == 4:
                table.add_row(*row)
                row = []
        if row:
            row.extend([""] * (4 - len(row)))
            table.add_row(*row)
        console.print(table)
        console.print()

    # Environment variables
    if arch.env_vars:
        console.print("[bold]Environment Variables:[/]")
        for var in arch.env_vars:
            console.print(f"  [yellow]{var}[/]")
        console.print()


def _render_footer(report: DecodeReport, console: Console) -> None:
    console.print(Panel(
        f"[bold]Decoded {report.total_files} files[/] in {report.decode_time_ms:.0f}ms",
        border_style="green",
    ))
    if not report.ai_enhanced:
        console.print()
        console.print(
            "[dim]Upgrade to Pro for AI-enhanced explanations: "
            "nyxtools.gumroad.com/l/vibe-check-pro[/]"
        )
    console.print()
