"""JSON reporter — serializes ScanReport to JSON."""

from __future__ import annotations

import json
from dataclasses import asdict

from vibe_check.engine.models import ScanReport


def render(report: ScanReport) -> str:
    """Serialize a ScanReport to a JSON string.

    Includes a schema_version field for forward compatibility.
    """
    data = asdict(report)
    data["schema_version"] = "1.0"
    return json.dumps(data, indent=2, ensure_ascii=False)
