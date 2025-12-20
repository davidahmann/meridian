"""Custom exceptions for Fabra."""

from typing import List, Dict, Any


class FabraError(Exception):
    """Base exception for all Fabra errors."""

    pass


class FreshnessSLAError(FabraError):
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


class ContextBudgetError(FabraError):
    """Raised when context exceeds max_tokens even after dropping optional items."""

    pass


class StoreConnectionError(FabraError):
    """Raised when unable to connect to a backend store."""

    pass


class FeatureNotFoundError(FabraError):
    """Raised when a requested feature does not exist."""

    pass


class ImmutableRecordError(FabraError):
    """Raised when attempting to overwrite an existing Context Record."""

    def __init__(
        self,
        *,
        context_id: str,
        existing_record_hash: str,
        attempted_record_hash: str,
    ) -> None:
        super().__init__(
            "Context Record immutability violation: record already exists with a different hash"
        )
        self.context_id = context_id
        self.existing_record_hash = existing_record_hash
        self.attempted_record_hash = attempted_record_hash
