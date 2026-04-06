"""Tests for decoder analyzers."""

from __future__ import annotations

import ast
import textwrap
from pathlib import Path

import pytest

from tests.conftest import make_file, parse_python
from vibe_check.decoder.analyzers.cross_ref import (
    build_architecture_map,
    build_cross_references,
)
from vibe_check.decoder.analyzers.pattern_matcher import (
    infer_class_description,
    infer_file_summary,
    infer_function_description,
)
from vibe_check.decoder.analyzers.python_analyzer import analyze_python_file
from vibe_check.decoder.analyzers.generic_analyzer import analyze_generic_file


class TestPatternMatcher:
    def test_infer_file_summary_flask(self) -> None:
        result = infer_file_summary(
            filename="routes.py",
            imports=["flask"],
            class_names=[],
            class_bases=[],
            function_names=["get_users"],
            decorators=[[]],
            has_main_guard=False,
        )
        assert "flask" in result.lower() or "web" in result.lower() or "route" in result.lower()

    def test_infer_file_summary_test(self) -> None:
        result = infer_file_summary(
            filename="test_auth.py",
            imports=["pytest"],
            class_names=[],
            class_bases=[],
            function_names=["test_login"],
            decorators=[[]],
            has_main_guard=False,
        )
        assert "test" in result.lower()

    def test_infer_file_summary_cli(self) -> None:
        result = infer_file_summary(
            filename="cli.py",
            imports=["click"],
            class_names=[],
            class_bases=[],
            function_names=["main"],
            decorators=[["main.command"]],
            has_main_guard=False,
        )
        assert "cli" in result.lower() or "command" in result.lower()

    def test_infer_file_summary_empty(self) -> None:
        result = infer_file_summary(
            filename="empty.py",
            imports=[],
            class_names=[],
            class_bases=[],
            function_names=[],
            decorators=[],
            has_main_guard=False,
        )
        assert result  # Should return something

    def test_infer_function_description_from_docstring(self) -> None:
        result = infer_function_description(
            name="do_something",
            decorators=[],
            docstring="Performs the main calculation.",
            calls=[],
        )
        assert result == "Performs the main calculation."

    def test_infer_function_description_from_name(self) -> None:
        result = infer_function_description(
            name="get_user_by_id",
            decorators=[],
            docstring=None,
            calls=[],
        )
        assert "user" in result.lower()

    def test_infer_function_description_test_prefix(self) -> None:
        result = infer_function_description(
            name="test_login_success",
            decorators=[],
            docstring=None,
            calls=[],
        )
        assert "login" in result.lower()

    def test_infer_function_description_private(self) -> None:
        result = infer_function_description(
            name="_helper",
            decorators=[],
            docstring=None,
            calls=[],
        )
        assert "internal" in result.lower() or "helper" in result.lower()

    def test_infer_class_description_from_docstring(self) -> None:
        result = infer_class_description("MyClass", ["ABC"], "An abstract handler.")
        assert result == "An abstract handler."

    def test_infer_class_description_from_base(self) -> None:
        result = infer_class_description("MyScanner", ["ABC"], None)
        assert "abstract" in result.lower()


class TestPythonAnalyzer:
    def test_basic_file_analysis(self, tmp_path: Path) -> None:
        fi = make_file(tmp_path, "example.py", """\
            import os

            def get_name():
                \"\"\"Get the user's name.\"\"\"
                return os.environ.get("USER_NAME", "default")

            class Config:
                \"\"\"Application configuration.\"\"\"
                pass
        """)
        tree = parse_python(fi.content)
        result = analyze_python_file(fi, tree, tmp_path)
        assert result.language == "python"
        assert result.line_count > 0
        assert len(result.functions) >= 1
        assert result.functions[0].name == "get_name"
        assert result.functions[0].docstring == "Get the user's name."
        assert len(result.classes) >= 1
        assert result.classes[0].name == "Config"
        assert "USER_NAME" in result.env_vars

    def test_entry_point_detection(self, tmp_path: Path) -> None:
        fi = make_file(tmp_path, "main.py", """\
            def main():
                pass

            if __name__ == "__main__":
                main()
        """)
        tree = parse_python(fi.content)
        result = analyze_python_file(fi, tree, tmp_path)
        assert "executable" in result.summary.lower() or "entry" in result.summary.lower()

    def test_class_methods_extracted(self, tmp_path: Path) -> None:
        fi = make_file(tmp_path, "scanner.py", """\
            from abc import ABC, abstractmethod

            class BaseScanner(ABC):
                @abstractmethod
                def scan(self):
                    pass

                def _helper(self):
                    return True
        """)
        tree = parse_python(fi.content)
        result = analyze_python_file(fi, tree, tmp_path)
        assert len(result.classes) == 1
        cls = result.classes[0]
        assert cls.name == "BaseScanner"
        assert "ABC" in cls.bases
        method_names = [m.name for m in cls.methods]
        assert "scan" in method_names
        assert "_helper" in method_names


class TestGenericAnalyzer:
    def test_js_file_analysis(self, tmp_path: Path) -> None:
        fi = make_file(tmp_path, "app.js", """\
            import express from 'express';
            const PORT = process.env.PORT;

            function handleRequest(req, res) {
                res.send('hello');
            }

            export default handleRequest;
        """, language="javascript")
        result = analyze_generic_file(fi, tmp_path)
        assert result.language == "javascript"
        assert len(result.functions) >= 1
        assert any("express" in imp for imp in result.imports)
        assert "PORT" in result.env_vars


class TestCrossRef:
    def test_cross_references(self, tmp_path: Path) -> None:
        from vibe_check.decoder.models import FileAnalysis

        fa_models = FileAnalysis(
            path="src/models.py",
            language="python",
            line_count=10,
            imports=[],
        )
        fa_cli = FileAnalysis(
            path="src/cli.py",
            language="python",
            line_count=20,
            imports=["src.models", "click"],
        )
        analyses = [fa_models, fa_cli]
        build_cross_references(analyses, tmp_path)
        # cli should call into models
        assert "src/models.py" in fa_cli.calls_into
        # models should be called by cli
        assert "src/cli.py" in fa_models.called_by

    def test_architecture_map(self, tmp_path: Path) -> None:
        from vibe_check.decoder.models import FileAnalysis

        fa = FileAnalysis(
            path="main.py",
            language="python",
            line_count=5,
            imports=["click", "httpx"],
            entry_point=True,
        )
        arch = build_architecture_map([fa], tmp_path)
        assert "main.py" in arch.entry_points
        assert "click" in arch.external_deps or "httpx" in arch.external_deps
