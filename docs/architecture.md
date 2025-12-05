# Meridian Architecture: Boring Technology, Properly Applied

## Design Philosophy

1. **Redis-Only Caching (No L1)**
   - Most feature stores use in-memory L1 + Redis L2
   - This creates cache coherence bugs (pods see stale values)
   - We use Redis-only: 1ms localhost latency, strong consistency
   - Correctness > micro-optimization for fraud/finance

2. **Randomized Distributed Locking (No Leader Election)**
   - Most systems use consistent hashing or leader election
   - We use randomized work selection + Redis SETNX locks
   - Self-healing, no topology awareness required
   - "Even enough" statistically, brutally simple

3. **Explicit Over Magic**
   - No auto-caching hot features
   - No query optimization
   - User writes `materialize=True`, we cache. That's it.
   - Predictability > cleverness

## The Stack

**Local Mode:**
- **Offline:** DuckDB (embedded SQL engine)
- **Online:** Python dict (in-memory)
- **Scheduler:** APScheduler (background thread)
- **Infrastructure:** None (Just `pip install`)

**Production Mode:**
- **Offline:** Postgres 13+ (Async with `asyncpg`)
- **Online:** Redis 6+ (standalone or cluster)
- **Scheduler:** Distributed Workers with Redis Locks
- **Infrastructure:** 1x Postgres, 1x Redis, Nx API Pods

## Point-in-Time Correctness

Training/serving skew is the #1 killer of ML models in production.

**Problem:** Your model trains on Monday's features but serves Tuesday's features.

**Solution:** Meridian's `get_training_data()` uses "as-of" joins to ensure zero leakage.

### DuckDB (Development)
Uses native `ASOF JOIN` for high performance:
```sql
SELECT e.*, f.value
FROM entity_df e
ASOF LEFT JOIN feature_table f
ON e.entity_id = f.entity_id AND e.timestamp >= f.timestamp
```

### Postgres (Production)
Uses `LATERAL JOIN` for standard SQL compatibility:
```sql
LEFT JOIN LATERAL (
    SELECT value FROM feature_table f
    WHERE f.entity_id = e.entity_id AND f.timestamp <= e.timestamp
    ORDER BY f.timestamp DESC LIMIT 1
) f ON TRUE
```

Same logic offline (training) and online (serving). Guaranteed consistency.

## Hybrid Retrieval (Python + SQL)

Meridian supports a unique hybrid architecture:
1.  **Python Features:** Computed on-the-fly (Online) or via `apply()` (Offline).
2.  **SQL Features:** Computed via SQL queries (Offline) and materialized to Redis (Online).
3.  **Unified API:** `get_training_data` automatically orchestrates both and joins the results.
