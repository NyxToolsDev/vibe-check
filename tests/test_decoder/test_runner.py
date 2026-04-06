"""Tests for the decode runner."""

from __future__ import annotations

from pathlib import Path

from tests.conftest import make_file
from vibe_check.decoder.runner import run_decode


class TestRunDecode:
    def test_decode_simple_project(self, tmp_path: Path) -> None:
        make_file(tmp_path, "app.py", """\
            import os

            def main():
                \"\"\"Entry point.\"\"\"
                name = os.environ.get("APP_NAME", "myapp")
                print(f"Hello from {name}")

            if __name__ == "__main__":
                main()
        """)
        make_file(tmp_path, "utils.py", """\
            def helper():
                return 42
        """)

        report = run_decode(tmp_path)
        assert report.total_files == 2
        assert "python" in report.files_by_language
        assert report.files_by_language["python"] == 2
        assert report.ai_enhanced is False
        assert report.decode_time_ms > 0

        # Check file analyses exist
        paths = [fa.path for fa in report.files]
        assert "app.py" in paths
        assert "utils.py" in paths

    def test_decode_with_imports(self, tmp_path: Path) -> None:
        make_file(tmp_path, "models.py", """\
            class User:
                def __init__(self, name):
                    self.name = name
        """)
        make_file(tmp_path, "service.py", """\
            from models import User

            def get_user():
                return User("test")
        """)

        report = run_decode(tmp_path)
        assert report.total_files == 2

        # Check architecture
        assert report.architecture is not None

    def test_decode_empty_project(self, tmp_path: Path) -> None:
        # No source files
        (tmp_path / "readme.txt").write_text("not a source file")
        report = run_decode(tmp_path)
        assert report.total_files == 0
        assert report.files == []

    def test_decode_env_vars_collected(self, tmp_path: Path) -> None:
        make_file(tmp_path, "config.py", """\
            import os

            DB_URL = os.environ["DATABASE_URL"]
            SECRET = os.getenv("SECRET_KEY")
        """)

        report = run_decode(tmp_path)
        assert "DATABASE_URL" in report.architecture.env_vars
        assert "SECRET_KEY" in report.architecture.env_vars
