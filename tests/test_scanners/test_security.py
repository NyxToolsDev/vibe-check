"""Tests for the security scanner."""

from __future__ import annotations

from pathlib import Path

from tests.conftest import make_file, parse_python
from vibe_check.scanners.security import SecurityScanner


def _scan(tmp_path: Path, name: str, content: str, language: str = "python"):
    fi = make_file(tmp_path, name, content, language)
    scanner = SecurityScanner()
    asts = {}
    if language == "python":
        import ast

        try:
            asts[fi.path] = ast.parse(content)
        except SyntaxError:
            pass
    return scanner.scan([fi], asts, tmp_path)


class TestHardcodedSecrets:
    def test_detects_api_key(self, tmp_path: Path):
        findings = _scan(tmp_path, "config.py", 'API_KEY = "sk-abc123456789"')
        assert any(f.rule_id == "SEC-001" for f in findings)

    def test_ignores_empty_values(self, tmp_path: Path):
        findings = _scan(tmp_path, "config.py", 'API_KEY = ""')
        assert not any(f.rule_id == "SEC-001" for f in findings)


class TestSQLInjection:
    def test_detects_fstring_sql(self, tmp_path: Path):
        code = 'query = f"SELECT * FROM users WHERE id = {user_id}"'
        findings = _scan(tmp_path, "db.py", code)
        assert any(f.rule_id == "SEC-002" for f in findings)

    def test_allows_parameterized(self, tmp_path: Path):
        code = 'cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))'
        findings = _scan(tmp_path, "db.py", code)
        assert not any(f.rule_id == "SEC-002" for f in findings)


class TestEvalExec:
    def test_detects_eval(self, tmp_path: Path):
        findings = _scan(tmp_path, "bad.py", "result = eval(user_input)")
        assert any(f.rule_id == "SEC-003" for f in findings)

    def test_detects_js_eval(self, tmp_path: Path):
        findings = _scan(tmp_path, "bad.js", "const x = eval(input)", "javascript")
        assert any(f.rule_id == "SEC-003" for f in findings)


class TestUnsafeDeserialization:
    def test_detects_pickle_load(self, tmp_path: Path):
        code = "import pickle\ndata = pickle.load(f)"
        findings = _scan(tmp_path, "loader.py", code)
        assert any(f.rule_id == "SEC-008" for f in findings)

    def test_detects_yaml_load_without_safe(self, tmp_path: Path):
        code = "import yaml\ndata = yaml.load(f)"
        findings = _scan(tmp_path, "loader.py", code)
        assert any(f.rule_id == "SEC-008" for f in findings)

    def test_allows_yaml_safe_load(self, tmp_path: Path):
        code = "import yaml\ndata = yaml.safe_load(f)"
        findings = _scan(tmp_path, "loader.py", code)
        assert not any(f.rule_id == "SEC-008" for f in findings)

    def test_allows_yaml_load_with_safeloader(self, tmp_path: Path):
        code = "import yaml\ndata = yaml.load(f, Loader=yaml.SafeLoader)"
        findings = _scan(tmp_path, "loader.py", code)
        assert not any(f.rule_id == "SEC-008" for f in findings)


class TestShellInjection:
    def test_detects_subprocess_shell_true(self, tmp_path: Path):
        code = 'import subprocess\nsubprocess.run(cmd, shell=True)'
        findings = _scan(tmp_path, "runner.py", code)
        assert any(f.rule_id == "SEC-009" for f in findings)

    def test_detects_os_system(self, tmp_path: Path):
        code = 'import os\nos.system("rm -rf /")'
        findings = _scan(tmp_path, "runner.py", code)
        assert any(f.rule_id == "SEC-009" for f in findings)

    def test_allows_subprocess_list_args(self, tmp_path: Path):
        code = 'import subprocess\nsubprocess.run(["ls", "-la"])'
        findings = _scan(tmp_path, "runner.py", code)
        assert not any(f.rule_id == "SEC-009" for f in findings)


class TestEnvFile:
    def test_detects_env_file_without_gitignore(self, tmp_path: Path):
        (tmp_path / ".env").write_text("SECRET=value", encoding="utf-8")
        scanner = SecurityScanner()
        findings = scanner.scan([], {}, tmp_path)
        assert any(f.rule_id == "SEC-011" for f in findings)

    def test_ignores_env_when_gitignored(self, tmp_path: Path):
        (tmp_path / ".env").write_text("SECRET=value", encoding="utf-8")
        (tmp_path / ".gitignore").write_text(".env\n", encoding="utf-8")
        scanner = SecurityScanner()
        findings = scanner.scan([], {}, tmp_path)
        assert not any(f.rule_id == "SEC-011" for f in findings)
