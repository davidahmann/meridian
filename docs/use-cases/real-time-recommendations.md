# Use Case: Real-Time Recommendations

Real-time recommendations require low latency (<50ms) and high throughput. This is where Fabra's **Async I/O** and **Hybrid Features** shine.

## The Problem: Latency vs. Freshness

You need to recommend products to a user based on:
1.  **Long-term history:** What they bought last month (SQL, heavy query).
2.  **Short-term context:** What they clicked 5 seconds ago (Real-time).
3.  **Complex Logic:** Cosine similarity between user and item embeddings (Python).

Doing this in a standard feature store is hard. You often have to pre-compute everything (stale) or compute everything on-demand (slow).

## The Solution: Hybrid Features

Fabra lets you mix both strategies in a single API call.

```python
# 1. SQL Feature (Materialized)
# Pre-computed in Postgres, served from Redis. Fast (1ms).
@feature(entity=User, sql="SELECT user_id, favorite_category FROM orders", materialize=True)
def favorite_category(user_id: str) -> str:
    return "unknown"

# 2. Python Feature (On-Demand)
# Computed in real-time. Flexible.
@feature(entity=User)
def current_session_embedding(user_id: str) -> List[float]:
    # Fetch from real-time session store (e.g. Redis)
    return get_session_embedding(user_id)

# 3. Serving
features = await store.get_online_features(
    "User", "u1", ["favorite_category", "current_session_embedding"]
)
```

## Why This Matters
- **Async I/O:** Fabra uses `asyncpg` and `redis-py` to fetch both features in parallel.
- **Performance:** The SQL feature is fetched from Redis in <2ms. The Python feature runs in the same event loop.
- **Simplicity:** You don't need a separate "Streaming Feature Store". You just write Python.

---

## Next Steps

- [Feature Store Without K8s](../feature-store-without-kubernetes.md) — Get started in 30 seconds
- [Hybrid Features](../hybrid-features.md) — Mix SQL and Python
- [Quickstart](../quickstart.md) — Full setup guide

<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "HowTo",
  "name": "Real-Time Recommendations with Fabra",
  "description": "Build real-time recommendation features combining pre-computed and on-demand data with <50ms latency.",
  "totalTime": "PT15M",
  "tool": [{"@type": "HowToTool", "name": "Fabra"}],
  "step": [
    {"@type": "HowToStep", "name": "Define materialized features", "text": "Create SQL features for long-term history with materialize=True."},
    {"@type": "HowToStep", "name": "Define on-demand features", "text": "Create Python features for real-time context like session embeddings."},
    {"@type": "HowToStep", "name": "Serve features", "text": "Use async get_online_features to fetch both in parallel."}
  ]
}
</script>
