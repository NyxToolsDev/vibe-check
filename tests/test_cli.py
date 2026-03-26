"""Tests for the CLI interface."""

from __future__ import annotations

from click.testing import CliRunner

from vibe_check.cli import main


class TestCLI:
    def test_help_output(self):
        runner = CliRunner()
        result = runner.invoke(main, ["--help"])
        assert result.exit_code == 0
        assert "Vibe Check" in result.output

    def test_version_output(self):
        runner = CliRunner()
        result = runner.invoke(main, ["--version"])
        assert result.exit_code == 0
        assert "0.1.0" in result.output

    def test_scan_nonexistent_path(self):
        runner = CliRunner()
        result = runner.invoke(main, ["scan", "/nonexistent/path"])
        assert result.exit_code != 0

    def test_scan_current_dir_runs(self, tmp_path):
        """Scan an empty temp dir — should complete without error."""
        (tmp_path / "hello.py").write_text("x = 1\n", encoding="utf-8")
        runner = CliRunner()
        result = runner.invoke(main, ["scan", str(tmp_path)])
        assert result.exit_code == 0

    def test_json_output_format(self, tmp_path):
        (tmp_path / "hello.py").write_text("x = 1\n", encoding="utf-8")
        runner = CliRunner()
        result = runner.invoke(main, ["scan", str(tmp_path), "-f", "json"])
        assert result.exit_code == 0
        assert '"overall_score"' in result.output

    def test_ci_mode_passes_with_clean_project(self, tmp_path):
        (tmp_path / "hello.py").write_text("x = 1\n", encoding="utf-8")
        runner = CliRunner()
        result = runner.invoke(main, ["scan", str(tmp_path), "--ci", "--threshold", "F"])
        assert result.exit_code == 0
