"""Tests for decode reporters."""

from __future__ import annotations

import json

from vibe_check.decoder.models import (
    ArchitectureMap,
    DecodeReport,
    FileAnalysis,
    FunctionInfo,
)
from vibe_check.decoder.reporters import json_reporter, markdown
from vibe_check.decoder.reporters.terminal import render as terminal_render


def _sample_report() -> DecodeReport:
    """Create a sample DecodeReport for testing."""
    return DecodeReport(
        project_path="/tmp/test-project",
        total_files=2,
        files_by_language={"python": 2},
        files=[
            FileAnalysis(
                path="main.py",
                language="python",
                line_count=15,
                summary="CLI entry point",
                imports=["click", "os"],
                functions=[
                    FunctionInfo(
                        name="main",
                        start_line=5,
                        end_line=10,
                        line_count=6,
                        signature="def main() -> None:",
                        description="Application entry point",
                    ),
                ],
                env_vars=["API_KEY"],
                entry_point=True,
            ),
            FileAnalysis(
                path="utils.py",
                language="python",
                line_count=8,
                summary="Utility functions",
                imports=[],
                functions=[
                    FunctionInfo(
                        name="helper",
                        start_line=1,
                        end_line=3,
                        line_count=3,
                        signature="def helper() -> int:",
                        description="Returns a constant value",
                    ),
                ],
                called_by=["main.py"],
            ),
        ],
        architecture=ArchitectureMap(
            entry_points=["main.py"],
            dependency_graph={"main.py": ["utils.py"]},
            external_deps=["click"],
            env_vars=["API_KEY"],
        ),
    )


class TestMarkdownReporter:
    def test_render_produces_markdown(self) -> None:
        report = _sample_report()
        result = markdown.render(report)
        assert "# Code Guide" in result
        assert "main.py" in result
        assert "utils.py" in result

    def test_render_includes_project_overview(self) -> None:
        report = _sample_report()
        result = markdown.render(report)
        assert "What This Project Does" in result

    def test_render_includes_startup_section(self) -> None:
        report = _sample_report()
        result = markdown.render(report)
        assert "How This Project Starts Up" in result
        assert "front door" in result

    def test_render_includes_functions(self) -> None:
        report = _sample_report()
        result = markdown.render(report)
        assert "`main`" in result
        assert "`helper`" in result

    def test_render_includes_env_vars(self) -> None:
        report = _sample_report()
        result = markdown.render(report)
        assert "API_KEY" in result
        assert "Settings You Can Change" in result

    def test_render_includes_connections(self) -> None:
        report = _sample_report()
        result = markdown.render(report)
        assert "How Files Connect" in result

    def test_render_includes_troubleshooting(self) -> None:
        report = _sample_report()
        result = markdown.render(report)
        assert "If Something Breaks" in result

    def test_render_includes_detailed_reference(self) -> None:
        report = _sample_report()
        result = markdown.render(report)
        assert "Detailed Reference" in result
        assert "def main() -> None:" in result

    def test_render_explains_dependencies(self) -> None:
        report = _sample_report()
        result = markdown.render(report)
        assert "click" in result
        assert "command-line interface" in result

    def test_render_no_upsell_when_ai_enhanced(self) -> None:
        report = _sample_report()
        report.ai_enhanced = True
        result = markdown.render(report)
        assert "Upgrade to Pro" not in result


class TestJsonReporter:
    def test_render_valid_json(self) -> None:
        report = _sample_report()
        result = json_reporter.render(report)
        data = json.loads(result)
        assert data["project_path"] == "/tmp/test-project"
        assert data["total_files"] == 2
        assert data["schema_version"] == "1.0"

    def test_render_includes_files(self) -> None:
        report = _sample_report()
        result = json_reporter.render(report)
        data = json.loads(result)
        assert len(data["files"]) == 2
        assert data["files"][0]["path"] == "main.py"

    def test_render_includes_architecture(self) -> None:
        report = _sample_report()
        result = json_reporter.render(report)
        data = json.loads(result)
        assert "entry_points" in data["architecture"]


class TestTerminalReporter:
    def test_render_does_not_crash(self) -> None:
        report = _sample_report()
        # Just verify it doesn't raise
        terminal_render(report)
