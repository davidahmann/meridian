"""Custom exceptions for Meridian."""

from typing import List, Dict, Any


class MeridianError(Exception):
    """Base exception for all Meridian errors."""

    pass


class FreshnessSLAError(MeridianError):
    """
    Raised when context assembly violates a freshness SLA in strict mode.

    This exception is raised when `freshness_strict=True` is set on a
    `@context` decorator and one or more features exceed the specified
    `freshness_sla` threshold.

    Attributes:
        message: Human-readable error message
        violations: List of features that violated the SLA with details
    """

    def __init__(self, message: str, violations: List[Dict[str, Any]]) -> None:
        super().__init__(message)
        self.message = message
        self.violations = violations

    def __str__(self) -> str:
        violation_details = ", ".join(
            f"{v['feature']} ({v['age_ms']}ms > {v['sla_ms']}ms)"
            for v in self.violations
        )
        return f"{self.message}: {violation_details}"

    def __repr__(self) -> str:
        return f"FreshnessSLAError(message={self.message!r}, violations={self.violations!r})"


class ContextBudgetError(MeridianError):
    """Raised when context exceeds max_tokens even after dropping optional items."""

    pass


class StoreConnectionError(MeridianError):
    """Raised when unable to connect to a backend store."""

    pass


class FeatureNotFoundError(MeridianError):
    """Raised when a requested feature does not exist."""

    pass
