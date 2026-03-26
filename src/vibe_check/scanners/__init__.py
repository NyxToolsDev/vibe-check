"""Import all scanner modules so they auto-register via decorators."""

from vibe_check.scanners import (  # noqa: F401
    architecture,
    code_quality,
    dependencies,
    hipaa,
    security,
    testing,
)
