import asyncio
import time
import os
from datetime import timedelta
from meridian.context import context, ContextItem
from meridian.core import FeatureStore
from meridian.retrieval import retriever

# Initialize Store (tries to connect to Redis if env var set)
store = FeatureStore()

# Explicitly check for Redis availability for valid benchmark
redis_url = os.environ.get("MERIDIAN_REDIS_URL")
if not redis_url and not store.online_store:
    print("⚠️  WARNING: MERIDIAN_REDIS_URL not set. Caching will NOT work.")
    print(
        "   To run actual benchmark: export MERIDIAN_REDIS_URL=redis://localhost:6379"
    )


@retriever(name="slow_search", cache_ttl=timedelta(seconds=60))  # type: ignore[untyped-decorator]
async def slow_search(query: str) -> list[str]:
    # Simulate IO latency
    await asyncio.sleep(0.5)
    return [f"Result for {query}"]


@context(store=store, max_tokens=1000, cache_ttl=timedelta(seconds=60))
async def cached_context(query: str) -> list[ContextItem]:
    data = await slow_search(query)
    return [ContextItem(content=str(data))]


async def measure(name: str) -> float:
    start = time.perf_counter()
    ctx = await cached_context(query="benchmark")
    end = time.perf_counter()
    latency_ms = (end - start) * 1000
    print(f"[{name}] Latency: {latency_ms:.2f}ms | Cached: {ctx.is_fresh}")
    return latency_ms


async def main() -> None:
    print("🚀 Starting Benchmark: Cold vs Hot Cache")

    # 1. Cold Run
    t1 = await measure("Cold Run (Miss)")

    # 2. Hot Run
    t2 = await measure("Hot Run (Hit) ")

    if t1 > 0:
        speedup = t1 / t2 if t2 > 0 else 0
        print(f"\n⚡ Speedup: {speedup:.1f}x")

    if t2 > 100 and redis_url:
        print("\n❌ Cache Miss suspected? Hot run took > 100ms.")
    elif redis_url:
        print("\n✅ Cache Hit verified.")


if __name__ == "__main__":
    asyncio.run(main())
