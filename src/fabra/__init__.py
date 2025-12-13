"""
Fabra: Context infrastructure for AI applications.
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version


def _resolve_version() -> str:
    for dist_name in ("fabra-ai", "fabra_ai"):
        try:
            return version(dist_name)
        except PackageNotFoundError:
            continue
    return "0.0.0"


__version__ = _resolve_version()
