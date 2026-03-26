"""License key validation via Gumroad API with local caching."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

# Gumroad product permalink — set via env var or hardcode after creating product
_GUMROAD_PRODUCT_ID = os.environ.get("VIBE_CHECK_PRODUCT_ID", "0NHBAyNQ1UyAGTbsfjWsDA==")
_GUMROAD_VERIFY_URL = "https://api.gumroad.com/v2/licenses/verify"

# Cache license validation for 30 days so the tool works offline
_CACHE_TTL_SECONDS = 30 * 24 * 60 * 60  # 30 days
_CACHE_DIR = Path.home() / ".vibe-check"
_CACHE_FILE = _CACHE_DIR / "license.json"


def check_license(key: str | None = None) -> bool:
    """Check if a valid Pro license key is provided.

    Validation flow:
    1. Check CLI flag, then env var for a key
    2. If no key, return False (free tier)
    3. Check local cache — if valid and not expired, return cached result
    4. Call Gumroad API to verify the key
    5. Cache the result locally for offline use

    Args:
        key: License key from --license-key flag.

    Returns:
        True if the key is valid Pro license, False otherwise.
    """
    license_key = _resolve_key(key)
    if not license_key:
        return False

    cached = _read_cache(license_key)
    if cached is not None:
        return cached

    valid = _verify_with_gumroad(license_key)
    _write_cache(license_key, valid)
    return valid


def _resolve_key(key: str | None) -> str:
    """Get the license key from flag or environment."""
    if key and key.strip():
        return key.strip()
    return os.environ.get("VIBE_CHECK_LICENSE_KEY", "").strip()


def _read_cache(license_key: str) -> bool | None:
    """Read cached validation result. Returns None if cache miss or expired."""
    if not _CACHE_FILE.is_file():
        return None
    try:
        data = json.loads(_CACHE_FILE.read_text(encoding="utf-8"))
        if data.get("key") != license_key:
            return None
        cached_at = data.get("cached_at", 0)
        if time.time() - cached_at > _CACHE_TTL_SECONDS:
            return None
        return data.get("valid", False)
    except (json.JSONDecodeError, OSError, KeyError):
        return None


def _write_cache(license_key: str, valid: bool) -> None:
    """Write validation result to local cache."""
    try:
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
        data = {
            "key": license_key,
            "valid": valid,
            "cached_at": time.time(),
            "product_id": _GUMROAD_PRODUCT_ID,
        }
        _CACHE_FILE.write_text(json.dumps(data), encoding="utf-8")
    except OSError:
        pass  # Cache write failure is non-fatal


def _verify_with_gumroad(license_key: str) -> bool:
    """Verify a license key against the Gumroad API.

    Returns True if the key is valid and associated with the product.
    Returns False on invalid key, network error, or API failure.
    """
    try:
        import httpx

        response = httpx.post(
            _GUMROAD_VERIFY_URL,
            data={
                "product_id": _GUMROAD_PRODUCT_ID,
                "license_key": license_key,
                "increment_uses_count": "false",
            },
            timeout=10.0,
        )

        if response.status_code != 200:
            return False

        result = response.json()
        return result.get("success", False)

    except (httpx.HTTPError, OSError, ValueError):
        # Network failure — check if we have a stale cache to fall back on
        return _read_stale_cache(license_key)


def _read_stale_cache(license_key: str) -> bool:
    """Fall back to expired cache on network failure (grace period)."""
    if not _CACHE_FILE.is_file():
        return False
    try:
        data = json.loads(_CACHE_FILE.read_text(encoding="utf-8"))
        if data.get("key") == license_key:
            return data.get("valid", False)
    except (json.JSONDecodeError, OSError):
        pass
    return False
