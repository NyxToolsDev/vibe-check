"""Markdown reporter — generates beginner-friendly CODE-GUIDE.md documentation."""

from __future__ import annotations

from vibe_check.decoder.models import DecodeReport, FileAnalysis


def render(report: DecodeReport) -> str:
    """Generate a beginner-friendly CODE-GUIDE.md from a DecodeReport."""
    lines: list[str] = []
    _render_header(report, lines)
    _render_quick_overview(report, lines)
    _render_how_it_starts(report, lines)
    _render_project_map(report, lines)
    _render_whats_inside(report, lines)
    _render_connections(report, lines)
    _render_env_vars(report, lines)
    _render_troubleshooting_tips(report, lines)
    _render_detailed_reference(report, lines)
    _render_footer(report, lines)
    return "\n".join(lines)


def _render_header(report: DecodeReport, lines: list[str]) -> None:
    lines.append("# Code Guide")
    lines.append("")
    lines.append(
        "This guide explains what every part of this project does in plain English. "
        "Use it to understand the codebase, troubleshoot problems, or onboard quickly."
    )
    lines.append("")
    lines.append(f"**Project:** `{report.project_path}`  ")
    lines.append(f"**Generated:** {report.decoded_at}  ")
    lines.append(f"**Total files:** {report.total_files}  ")
    lang_parts = [f"{lang} ({count})" for lang, count in report.files_by_language.items()]
    if lang_parts:
        lines.append(f"**Languages:** {', '.join(lang_parts)}  ")
    lines.append("")


def _render_quick_overview(report: DecodeReport, lines: list[str]) -> None:
    lines.append("## What This Project Does")
    lines.append("")

    # Summarize the project based on its structure
    entry_files = [fa for fa in report.files if fa.entry_point]
    non_test_files = [fa for fa in report.files if "test" not in fa.path.lower()]
    test_files = [fa for fa in report.files if "test" in fa.path.lower()]

    if non_test_files:
        # Group by purpose
        purpose_groups = _group_by_purpose(non_test_files)
        if purpose_groups:
            lines.append("At a high level, this project is made up of:")
            lines.append("")
            for group_name, group_files in purpose_groups:
                file_names = ", ".join(f"`{_short_name(f.path)}`" for f in group_files[:3])
                extra = f" and {len(group_files) - 3} more" if len(group_files) > 3 else ""
                lines.append(f"- **{group_name}** ({file_names}{extra})")
            lines.append("")

    if test_files:
        lines.append(f"There are also **{len(test_files)} test files** that verify everything works correctly.")
        lines.append("")

    # External dependencies explained
    ext_deps = report.architecture.external_deps
    if ext_deps:
        lines.append("### Libraries This Project Depends On")
        lines.append("")
        lines.append(
            "These are external packages (code written by other people) "
            "that this project uses. If something breaks after an update, "
            "check these first."
        )
        lines.append("")
        for dep in ext_deps:
            desc = _explain_dependency(dep)
            lines.append(f"- **{dep}** — {desc}")
        lines.append("")


def _render_how_it_starts(report: DecodeReport, lines: list[str]) -> None:
    entry_files = [fa for fa in report.files if fa.entry_point]
    if not entry_files:
        return

    lines.append("## How This Project Starts Up")
    lines.append("")
    lines.append(
        "When you run this project, execution begins at these files. "
        "Think of them as the \"front door\" — everything else gets called from here."
    )
    lines.append("")

    for fa in entry_files:
        if "test" in fa.path.lower():
            continue
        lines.append(f"**`{fa.path}`**")
        if fa.summary:
            lines.append(f"  \n{fa.summary}")

        # Show what it calls into
        if fa.calls_into:
            lines.append(
                f"  \nFrom here, the code reaches into: "
                + ", ".join(f"`{_short_name(p)}`" for p in fa.calls_into[:5])
            )
        lines.append("")

    lines.append(
        "> **Troubleshooting tip:** If the app won't start, the problem is almost "
        "always in one of these entry point files or something they import."
    )
    lines.append("")


def _render_project_map(report: DecodeReport, lines: list[str]) -> None:
    lines.append("## Project Map")
    lines.append("")
    lines.append(
        "Here's every folder and what it's responsible for. "
        "When you need to fix or change something, this tells you where to look."
    )
    lines.append("")

    # Group files by directory
    dirs: dict[str, list[FileAnalysis]] = {}
    for fa in report.files:
        parts = fa.path.rsplit("/", 1)
        dir_path = parts[0] if len(parts) == 2 else "root"
        dirs.setdefault(dir_path, []).append(fa)

    for dir_path in sorted(dirs):
        dir_files = dirs[dir_path]
        non_init = [f for f in dir_files if "__init__" not in f.path]
        if not non_init:
            continue

        dir_label = dir_path if dir_path != "root" else "Project root"
        dir_purpose = _infer_directory_purpose(dir_path, non_init)

        lines.append(f"### `{dir_label}/`")
        if dir_purpose:
            lines.append(f"  \n{dir_purpose}")
        lines.append("")

        for fa in non_init:
            short = _short_name(fa.path)
            summary = fa.summary or "Source file"
            lines.append(f"- **`{short}`** — {summary}")

        lines.append("")


def _render_whats_inside(report: DecodeReport, lines: list[str]) -> None:
    """Render file-level details in beginner-friendly language."""
    non_test_files = [
        fa for fa in report.files
        if "test" not in fa.path.lower() and "__init__" not in fa.path
    ]
    if not non_test_files:
        return

    lines.append("## What's Inside Each File")
    lines.append("")
    lines.append(
        "This section breaks down the important files. "
        "For each file, you'll see what it does and what the key pieces are."
    )
    lines.append("")

    for fa in non_test_files:
        _render_friendly_file(fa, lines)


def _render_friendly_file(fa: FileAnalysis, lines: list[str]) -> None:
    lines.append(f"### `{fa.path}`")
    lines.append("")

    if fa.summary:
        lines.append(f"**What it does:** {fa.summary}")
        lines.append("")

    lines.append(f"*{fa.line_count} lines of {fa.language}*")
    lines.append("")

    # Classes — explained simply
    for cls in fa.classes:
        bases_note = ""
        if cls.bases:
            bases_note = f" (extends {', '.join(cls.bases)})"
        lines.append(f"**`{cls.name}`**{bases_note}")
        if cls.description:
            lines.append(f"  \n{cls.description}")
        lines.append("")
        if cls.methods:
            lines.append("What it can do:")
            lines.append("")
            for m in cls.methods:
                if m.name.startswith("_") and m.name != "__init__":
                    continue  # Skip private methods for beginners
                desc = m.description or m.name
                lines.append(f"- `{m.name}` — {desc}")
            private_count = sum(1 for m in cls.methods if m.name.startswith("_") and m.name != "__init__")
            if private_count:
                lines.append(f"- *...plus {private_count} internal helper(s)*")
            lines.append("")

    # Top-level functions — explained simply
    public_funcs = [f for f in fa.functions if not f.name.startswith("_")]
    private_funcs = [f for f in fa.functions if f.name.startswith("_")]

    if public_funcs:
        lines.append("**Key functions:**")
        lines.append("")
        for func in public_funcs:
            desc = func.description or func.name
            lines.append(f"- `{func.name}` — {desc}")
        lines.append("")

    if private_funcs:
        lines.append(
            f"*There are also {len(private_funcs)} internal helper function(s) "
            f"that support the ones above.*"
        )
        lines.append("")

    lines.append("---")
    lines.append("")


def _render_connections(report: DecodeReport, lines: list[str]) -> None:
    """Show how files connect to each other."""
    files_with_deps = [
        fa for fa in report.files
        if (fa.calls_into or fa.called_by) and "test" not in fa.path.lower()
    ]
    if not files_with_deps:
        return

    lines.append("## How Files Connect to Each Other")
    lines.append("")
    lines.append(
        "No file works alone. Here's how they depend on each other. "
        "If you change one file, the files listed under \"Used by\" might be affected."
    )
    lines.append("")

    for fa in files_with_deps:
        if "__init__" in fa.path:
            continue
        short = _short_name(fa.path)
        lines.append(f"**`{short}`**")
        if fa.calls_into:
            lines.append(
                "  \nPulls from: "
                + ", ".join(f"`{_short_name(p)}`" for p in fa.calls_into)
            )
        if fa.called_by:
            lines.append(
                "  \nUsed by: "
                + ", ".join(f"`{_short_name(p)}`" for p in fa.called_by)
            )
        lines.append("")


def _render_env_vars(report: DecodeReport, lines: list[str]) -> None:
    env_vars = report.architecture.env_vars
    if not env_vars:
        return

    lines.append("## Settings You Can Change (Environment Variables)")
    lines.append("")
    lines.append(
        "These are values the project reads from your system environment. "
        "They let you change how the app behaves without editing code. "
        "You typically set these in a `.env` file or your terminal."
    )
    lines.append("")

    var_to_files: dict[str, list[str]] = {}
    for fa in report.files:
        for var in fa.env_vars:
            var_to_files.setdefault(var, []).append(fa.path)

    for var in sorted(var_to_files):
        files_str = ", ".join(f"`{_short_name(f)}`" for f in var_to_files[var])
        lines.append(f"- **`{var}`** — used in {files_str}")

    lines.append("")


def _render_troubleshooting_tips(report: DecodeReport, lines: list[str]) -> None:
    lines.append("## If Something Breaks")
    lines.append("")
    lines.append("Common places to look when things go wrong:")
    lines.append("")

    # Entry points
    entry_files = [fa for fa in report.files if fa.entry_point and "test" not in fa.path.lower()]
    if entry_files:
        names = ", ".join(f"`{_short_name(f.path)}`" for f in entry_files[:3])
        lines.append(f"- **App won't start?** Check the entry points: {names}")

    # Env vars
    if report.architecture.env_vars:
        lines.append(
            f"- **Weird behavior or missing config?** Make sure all "
            f"{len(report.architecture.env_vars)} environment variables are set "
            f"(see [Settings](#settings-you-can-change-environment-variables) above)"
        )

    # External deps
    if report.architecture.external_deps:
        deps = ", ".join(f"`{d}`" for d in report.architecture.external_deps[:5])
        lines.append(
            f"- **Import errors?** You may need to install dependencies: {deps}"
        )

    # Files with most connections (likely to cause cascading issues)
    most_used = sorted(
        [fa for fa in report.files if fa.called_by],
        key=lambda f: len(f.called_by),
        reverse=True,
    )[:3]
    if most_used:
        names = ", ".join(f"`{_short_name(f.path)}`" for f in most_used)
        lines.append(
            f"- **Changes causing unexpected side effects?** These files are used "
            f"by the most other files — changes here ripple: {names}"
        )

    lines.append("")


def _render_detailed_reference(report: DecodeReport, lines: list[str]) -> None:
    """Appendix with detailed technical reference for deeper investigation."""
    non_test = [
        fa for fa in report.files
        if "test" not in fa.path.lower()
        and "__init__" not in fa.path
        and (fa.functions or fa.classes)
    ]
    if not non_test:
        return

    lines.append("## Detailed Reference")
    lines.append("")
    lines.append(
        "*This section has the full technical details — function signatures, "
        "line numbers, and class hierarchies. Use this when you need to find "
        "exactly where something is defined.*"
    )
    lines.append("")

    for fa in non_test:
        if not fa.functions and not fa.classes:
            continue

        lines.append(f"### `{fa.path}`")
        lines.append("")

        for cls in fa.classes:
            bases_str = f" ({', '.join(cls.bases)})" if cls.bases else ""
            lines.append(f"**Class `{cls.name}`{bases_str}** — lines {cls.start_line}-{cls.end_line}")
            lines.append("")
            if cls.methods:
                lines.append("| Method | Lines | Description |")
                lines.append("|--------|-------|-------------|")
                for m in cls.methods:
                    desc = m.description or ""
                    lines.append(f"| `{m.name}` | {m.start_line}-{m.end_line} | {desc} |")
                lines.append("")

        if fa.functions:
            lines.append("| Function | Lines | Signature |")
            lines.append("|----------|-------|-----------|")
            for func in fa.functions:
                sig = func.signature[:80] if func.signature else ""
                lines.append(f"| `{func.name}` | {func.start_line}-{func.end_line} | `{sig}` |")
            lines.append("")

    lines.append("---")
    lines.append("")


def _render_footer(report: DecodeReport, lines: list[str]) -> None:
    lines.append("---")
    lines.append(
        f"*Generated by [vibe-check decode](https://github.com/NyxToolsDev/vibe-check) "
        f"v{report.version} in {report.decode_time_ms:.0f}ms*"
    )
    lines.append("")


# --- Helpers ---


def _short_name(path: str) -> str:
    """Get just the filename from a path."""
    return path.rsplit("/", 1)[-1] if "/" in path else path


def _make_anchor(path: str) -> str:
    """Convert a file path to a markdown-compatible anchor."""
    return path.lower().replace("/", "").replace("\\", "").replace(".", "").replace("_", "-")


def _group_by_purpose(files: list[FileAnalysis]) -> list[tuple[str, list[FileAnalysis]]]:
    """Group files by inferred purpose category."""
    groups: dict[str, list[FileAnalysis]] = {}
    for fa in files:
        if "__init__" in fa.path:
            continue
        category = _categorize_file(fa)
        groups.setdefault(category, []).append(fa)

    # Sort by size of group (largest first), filter tiny groups
    sorted_groups = sorted(groups.items(), key=lambda x: -len(x[1]))
    return [(name, files) for name, files in sorted_groups if files]


def _categorize_file(fa: FileAnalysis) -> str:
    """Categorize a file into a human-friendly group name."""
    path_lower = fa.path.lower()
    summary_lower = (fa.summary or "").lower()

    if "test" in path_lower:
        return "Tests"
    if "cli" in path_lower or "command" in summary_lower:
        return "Command-line interface"
    if "model" in path_lower or "schema" in path_lower:
        return "Data structures"
    if "report" in path_lower or "render" in summary_lower or "terminal" in summary_lower:
        return "Output and display"
    if "scan" in path_lower or "analyz" in path_lower or "check" in summary_lower:
        return "Analysis and scanning"
    if "parse" in path_lower or "walk" in path_lower:
        return "File reading and parsing"
    if "util" in path_lower or "helper" in path_lower:
        return "Utility helpers"
    if "config" in path_lower or "setting" in path_lower:
        return "Configuration"
    if "auth" in path_lower or "license" in path_lower:
        return "Authentication and licensing"
    if "ai" in path_lower or "backend" in path_lower:
        return "AI integration"
    if "engine" in path_lower or "runner" in path_lower or "core" in path_lower:
        return "Core engine"
    if "api" in path_lower or "route" in path_lower or "server" in path_lower:
        return "API and server"
    if "db" in path_lower or "database" in path_lower or "migration" in path_lower:
        return "Database"
    return "Core logic"


def _infer_directory_purpose(dir_path: str, files: list[FileAnalysis]) -> str:
    """Infer what a directory is responsible for."""
    dir_lower = dir_path.lower()
    if "test" in dir_lower:
        return "Automated tests that verify the code works correctly."
    if "scanner" in dir_lower or "analyz" in dir_lower:
        return "The code that actually inspects and analyzes source files."
    if "reporter" in dir_lower:
        return "Turns analysis results into readable output (terminal, markdown, JSON)."
    if "parser" in dir_lower:
        return "Reads and understands the structure of source code files."
    if "engine" in dir_lower or "core" in dir_lower:
        return "The central logic that coordinates everything else."
    if "util" in dir_lower:
        return "Shared helper code used by multiple parts of the project."
    if "model" in dir_lower:
        return "Data structures that define how information is organized."
    if "ai" in dir_lower:
        return "Connects to AI services for enhanced analysis."
    if "decoder" in dir_lower:
        return "The code explanation and documentation engine."
    if "tool" in dir_lower:
        return "Individual tools and capabilities the project provides."
    if "client" in dir_lower:
        return "Code that connects to external services."
    if "pacs" in dir_lower:
        return "Medical imaging system (PACS) connectivity."
    if "knowledge" in dir_lower:
        return "Reference data and lookup tables."
    return ""


# Common dependency descriptions
_DEP_DESCRIPTIONS: dict[str, str] = {
    "click": "Powers the command-line interface (the commands you type in terminal)",
    "rich": "Makes terminal output look nice with colors, tables, and formatting",
    "httpx": "Sends and receives HTTP requests (talks to web APIs)",
    "requests": "Sends and receives HTTP requests (talks to web APIs)",
    "pathspec": "Understands .gitignore patterns to skip files that shouldn't be scanned",
    "flask": "Web framework for building websites and APIs",
    "fastapi": "Modern web framework for building fast APIs",
    "django": "Full-featured web framework",
    "pydantic": "Validates data and ensures it has the right structure",
    "sqlalchemy": "Talks to databases (SQL) using Python objects",
    "pytest": "Runs automated tests to verify the code works",
    "celery": "Runs background tasks asynchronously",
    "redis": "Fast in-memory data store, often used for caching",
    "pydicom": "Reads and writes DICOM medical imaging files",
    "pynetdicom": "Network communication with medical imaging systems (PACS)",
    "mcp": "Model Context Protocol — lets AI assistants use tools",
    "anthropic": "Anthropic's SDK for connecting to Claude AI",
    "boto3": "Amazon Web Services (AWS) SDK",
    "stripe": "Payment processing integration",
    "cryptography": "Encryption and security operations",
    "jinja2": "Template engine for generating HTML or text files",
    "aiohttp": "Async HTTP client and server",
}


def _explain_dependency(dep: str) -> str:
    """Return a plain-English explanation of a dependency."""
    return _DEP_DESCRIPTIONS.get(dep, "Third-party library")
