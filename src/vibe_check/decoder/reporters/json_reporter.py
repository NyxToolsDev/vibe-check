"""JSON reporter — serializes DecodeReport to JSON."""

from __future__ import annotations

import json
from dataclasses import asdict

from vibe_check.decoder.models import DecodeReport


def render(report: DecodeReport) -> str:
    """Serialize a DecodeReport to a JSON string."""
    data = asdict(report)
    data["schema_version"] = "1.0"
    return json.dumps(data, indent=2, ensure_ascii=False)
