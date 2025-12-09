from prometheus_client import Counter, Histogram
import time
from typing import Optional, Any

# --- Metric Definitions ---

CONTEXT_ASSEMBLY_TOTAL = Counter(
    "meridian_context_assembly_total",
    "Total number of context assembly operations",
    ["name", "status"],
)

CONTEXT_LATENCY_SECONDS = Histogram(
    "meridian_context_latency_seconds",
    "Latency of context assembly operations",
    ["name"],
)

CONTEXT_TOKENS_TOTAL = Counter(
    "meridian_context_tokens_total", "Total tokens generated in contexts", ["name"]
)

CONTEXT_CACHE_HIT_TOTAL = Counter(
    "meridian_context_cache_hit_total",
    "Total number of cache hits for context assembly",
    ["name"],
)

INDEX_WRITE_TOTAL = Counter(
    "meridian_index_write_total",
    "Total number of documents written to vector index",
    ["index_name"],
)

# --- Freshness SLA Metrics (v1.5) ---

CONTEXT_FRESHNESS_STATUS_TOTAL = Counter(
    "meridian_context_freshness_status_total",
    "Total contexts by freshness status",
    ["name", "status"],  # status: "guaranteed" or "degraded"
)

CONTEXT_FRESHNESS_VIOLATIONS_TOTAL = Counter(
    "meridian_context_freshness_violations_total",
    "Total freshness SLA violations by feature",
    ["name", "feature"],
)

CONTEXT_STALEST_FEATURE_SECONDS = Histogram(
    "meridian_context_stalest_feature_seconds",
    "Age of the stalest feature used in context assembly",
    ["name"],
    buckets=(0.1, 0.5, 1, 5, 10, 30, 60, 300, 600, 1800, 3600),
)


class ContextMetrics:
    """Helper to track context metrics."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.start_time = 0.0

    def __enter__(self) -> "ContextMetrics":
        self.start_time = time.time()
        return self

    def __exit__(
        self,
        exc_type: Optional[type],
        exc_val: Optional[BaseException],
        exc_tb: Optional[Any],
    ) -> None:
        duration = time.time() - self.start_time
        status = "failure" if exc_type else "success"

        CONTEXT_ASSEMBLY_TOTAL.labels(name=self.name, status=status).inc()
        CONTEXT_LATENCY_SECONDS.labels(name=self.name).observe(duration)

    def record_tokens(self, count: int) -> None:
        CONTEXT_TOKENS_TOTAL.labels(name=self.name).inc(count)

    def record_cache_hit(self) -> None:
        CONTEXT_CACHE_HIT_TOTAL.labels(name=self.name).inc()

    def record_freshness_status(self, status: str) -> None:
        """Record freshness status (guaranteed or degraded)."""
        CONTEXT_FRESHNESS_STATUS_TOTAL.labels(name=self.name, status=status).inc()

    def record_freshness_violation(self, feature: str) -> None:
        """Record a freshness SLA violation for a specific feature."""
        CONTEXT_FRESHNESS_VIOLATIONS_TOTAL.labels(name=self.name, feature=feature).inc()

    def record_stalest_feature(self, age_seconds: float) -> None:
        """Record the age of the stalest feature in seconds."""
        CONTEXT_STALEST_FEATURE_SECONDS.labels(name=self.name).observe(age_seconds)
