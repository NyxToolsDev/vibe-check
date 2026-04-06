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
        assert "0.2.0" in result.output

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


class TestDecodeCLI:
    def test_decode_help(self):
        runner = CliRunner()
        result = runner.invoke(main, ["decode", "--help"])
        assert result.exit_code == 0
        assert "Decode" in result.output or "decode" in result.output

    def test_decode_terminal_format(self, tmp_path):
        (tmp_path / "hello.py").write_text("x = 1\n", encoding="utf-8")
        runner = CliRunner()
        result = runner.invoke(main, ["decode", str(tmp_path), "-f", "terminal"])
        assert result.exit_code == 0

    def test_decode_json_format(self, tmp_path):
        (tmp_path / "hello.py").write_text("x = 1\n", encoding="utf-8")
        runner = CliRunner()
        result = runner.invoke(main, ["decode", str(tmp_path), "-f", "json"])
        assert result.exit_code == 0
        assert '"project_path"' in result.output

    def test_decode_markdown_format(self, tmp_path):
        (tmp_path / "hello.py").write_text(
            "def greet():\n    return 'hello'\n", encoding="utf-8",
        )
        runner = CliRunner()
        output_file = tmp_path / "CODE-GUIDE.md"
        result = runner.invoke(
            main, ["decode", str(tmp_path), "-f", "markdown", "-o", str(output_file)],
        )
        assert result.exit_code == 0
        assert output_file.is_file()
        content = output_file.read_text(encoding="utf-8")
        assert "# Code Guide" in content
        assert "greet" in content

    def test_decode_ai_backend_requires_license(self, tmp_path):
        (tmp_path / "hello.py").write_text("x = 1\n", encoding="utf-8")
        runner = CliRunner()
        result = runner.invoke(
            main, ["decode", str(tmp_path), "--ai-backend", "claude", "-f", "terminal"],
        )
        assert result.exit_code == 0
        # Should show license warning but not crash
        assert "Pro license" in result.output or "Decoding" in result.output
