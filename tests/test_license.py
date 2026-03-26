"""Tests for license validation and CLI commands."""

from __future__ import annotations

import json
import time
from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner

from vibe_check.cli import main
from vibe_check.utils.license import (
    _read_cache,
    _write_cache,
    check_license,
)


class TestCheckLicense:
    def test_no_key_returns_false(self):
        with patch.dict("os.environ", {}, clear=True):
            assert check_license(None) is False

    def test_empty_key_returns_false(self):
        assert check_license("") is False
        assert check_license("   ") is False


class TestLicenseCache:
    def test_write_and_read_cache(self, tmp_path: Path):
        cache_file = tmp_path / "license.json"
        with patch("vibe_check.utils.license._CACHE_FILE", cache_file):
            with patch("vibe_check.utils.license._CACHE_DIR", tmp_path):
                _write_cache("test-key-123", True)
                result = _read_cache("test-key-123")
                assert result is True

    def test_cache_miss_wrong_key(self, tmp_path: Path):
        cache_file = tmp_path / "license.json"
        with patch("vibe_check.utils.license._CACHE_FILE", cache_file):
            with patch("vibe_check.utils.license._CACHE_DIR", tmp_path):
                _write_cache("key-A", True)
                result = _read_cache("key-B")
                assert result is None

    def test_expired_cache_returns_none(self, tmp_path: Path):
        cache_file = tmp_path / "license.json"
        data = {
            "key": "test-key",
            "valid": True,
            "cached_at": time.time() - (31 * 24 * 60 * 60),  # 31 days ago
        }
        cache_file.write_text(json.dumps(data))
        with patch("vibe_check.utils.license._CACHE_FILE", cache_file):
            result = _read_cache("test-key")
            assert result is None

    def test_missing_cache_file_returns_none(self, tmp_path: Path):
        cache_file = tmp_path / "nonexistent.json"
        with patch("vibe_check.utils.license._CACHE_FILE", cache_file):
            result = _read_cache("any-key")
            assert result is None


class TestCLICommands:
    def test_activate_invalid_key(self):
        runner = CliRunner()
        with patch("vibe_check.cli.check_license", return_value=False):
            result = runner.invoke(main, ["activate", "bad-key"])
            assert result.exit_code == 1
            assert "Invalid" in result.output

    def test_activate_valid_key(self):
        runner = CliRunner()
        with patch("vibe_check.cli.check_license", return_value=True):
            result = runner.invoke(main, ["activate", "good-key"])
            assert result.exit_code == 0
            assert "activated" in result.output

    def test_status_free_tier(self):
        runner = CliRunner()
        with patch("vibe_check.cli.check_license", return_value=False):
            result = runner.invoke(main, ["status"])
            assert result.exit_code == 0
            assert "Free tier" in result.output

    def test_status_pro(self):
        runner = CliRunner()
        with patch("vibe_check.cli.check_license", return_value=True):
            result = runner.invoke(main, ["status"])
            assert result.exit_code == 0
            assert "Pro" in result.output
