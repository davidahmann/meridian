import pytest
import time
from meridian.core import FeatureStore
from meridian.store.online import InMemoryOnlineStore


@pytest.mark.asyncio
async def test_feature_latency_sla() -> None:
    """
    Performance Requirement: P99 Latency < 50ms for hot-path feature retrieval.
    """
    # Setup - use In-Memory for baseline "code overhead" check
    store = InMemoryOnlineStore()
    fs = FeatureStore(online_store=store)
    fs.register_entity(name="bench_user", id_column="id")
    fs.register_feature(
        name="bench_feature", entity_name="bench_user", func=lambda x: 1
    )

    # Pre-populate
    await store.set("bench_feature:bench_user:u1", b"1")

    # Warmup
    for _ in range(10):
        await fs.get_online_features("bench_user", "u1", ["bench_feature"])

    start_time = time.perf_counter()
    iterations = 1000

    for _ in range(iterations):
        await fs.get_online_features("bench_user", "u1", ["bench_feature"])

    total_time = time.perf_counter() - start_time
    avg_latency = total_time / iterations

    # 50ms is huge for in-memory. We expect < 1ms for pure overhead.
    # The requirement < 50ms usually includes network RTT to Redis.
    # Here we verify the Python layer overhead is negligible.
    assert (
        avg_latency < 0.005
    ), f"Avg Latency {avg_latency*1000:.2f}ms exceeds 5ms overhead budget"
