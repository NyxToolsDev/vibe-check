"""License key validation (MVP: check if key is non-empty)."""

from __future__ import annotations

import os


def check_license(key: str | None = None) -> bool:
    """Check if a valid license key is provided.

    For MVP, any non-empty key is considered valid.
    Real Lemon Squeezy validation will be added in a future release.

    Args:
        key: License key from CLI flag. Falls back to VIBE_CHECK_LICENSE_KEY env var.

    Returns:
        True if licensed, False otherwise.
    """
    if key:
        return True

    env_key = os.environ.get("VIBE_CHECK_LICENSE_KEY", "").strip()
    return bool(env_key)
