"""Scanner plugin registry using decorator pattern."""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from vibe_check.scanners.base import BaseScanner

_registry: dict[str, type[BaseScanner]] = {}


def register_scanner(category: str) -> Callable[[type[BaseScanner]], type[BaseScanner]]:
    """Decorator to register a scanner class for a given category."""

    def decorator(cls: type[BaseScanner]) -> type[BaseScanner]:
        _registry[category] = cls
        return cls

    return decorator


def get_scanner(category: str) -> type[BaseScanner] | None:
    """Get a registered scanner class by category name."""
    return _registry.get(category)


def get_all_scanners() -> dict[str, type[BaseScanner]]:
    """Return all registered scanners."""
    return dict(_registry)
