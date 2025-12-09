---
title: "Troubleshooting Fabra: Common Errors and Fixes"
description: "Resolve common Fabra issues like Point-in-Time Correctness errors, Redis connection failures, and Async loop errors."
keywords: fabra troubleshooting, feature store errors, redis connection error, timestamp error
---

# Troubleshooting Guide

Common issues and how to fix them.

## 🩺 First Step: Fabra Doctor

Before diving into specific errors, run the **Doctor** to diagnose your environment:

```bash
fabra doctor
```

This command checks:
*   **Environment Variables:** `FABRA_REDIS_URL`, `FABRA_POSTGRES_URL`, etc.
*   **Connectivity:** Pings Redis and Postgres (if URLs are provided).
*   **Dependencies:** Verifies critical packages like `fastapi`, `redis`, `duckdb`.

---

## Point-in-Time Correctness

### "KeyError: timestamp" or "Column timestamp not found"
**Cause:** Fabra.s `get_training_data` requires a `timestamp` column in your entity DataFrame to perform point-in-time joins.
**Fix:**
```python
entity_df["timestamp"] = pd.to_datetime("now")
```

### "No matching features found"
**Cause:** Your entity timestamps might be *older* than your feature timestamps. Fabra uses `ASOF JOIN ... WHERE entity.ts >= feature.ts`. If your features are from today but your entities are from yesterday, you get nothing (to prevent data leakage).
**Fix:** Ensure your feature data covers the time range of your training labels.

## Production (Async/Postgres)

### "RuntimeError: Event loop is closed"
**Cause:** You might be trying to run `FeatureStore` methods (which are `async`) in a synchronous context without `asyncio.run()`, or mixing sync/async incorrectly.
**Fix:**
```python
import asyncio
async def main():
    await store.initialize()

if __name__ == "__main__":
    asyncio.run(main())
```

### "UndefinedTableError: relation ... does not exist"
**Cause:** In Hybrid Mode, if you define `@feature(sql="SELECT * FROM my_table")`, Fabra expects `my_table` to exist in Postgres.
**Fix:** Ensure the table exists in your offline store. Fabra does not create raw data tables for you.

## Redis

### "ConnectionError: Connection refused"
**Cause:** Redis is not running or the URL is wrong.
**Fix:**
Ensure your `redis` service name in `docker-compose.yml` matches `FABRA_REDIS_URL`. If using the default `redis://localhost:6379`, ensure you mapped ports (`6379:6379`) in Docker.

### "asyncpg.exceptions.DataError: invalid input for query argument"
**Cause:** Postgres is strict about Timezone Aware (`TIMESTAMPTZ`) vs Naive (`TIMESTAMP`) datetimes. If you pass a Naive datetime (e.g., from `datetime.now()`) to a component expecting an Aware one (or vice versa), `asyncpg` may fail.
**Fix:**
Fabra v1.1.8+ handles this automatically for `get_training_data`. However, if you are manually inserting data:
- Use `TIMESTAMPTZ` for your column definitions: `CREATE TABLE ... timestamp TIMESTAMPTZ`.
- Ensure your Python datetimes are UTC aware: `datetime.now(timezone.utc)`.

## Context Store (RAG/Vectors)

### "UndefinedFunction: function vector_dims(vector) does not exist"
**Cause:** The `pgvector` extension is not installed or enabled in your Postgres database.
**Fix:**
Run this SQL in your database:
```sql
CREATE EXTENSION IF NOT EXISTS vector;
```
*Note: `fabra index create` attempts to do this automatically, but requires superuser permissions.*

### "ContextBudgetError: Required content exceeds budget"
**Cause:** Your `@context(max_tokens=N)` limit is too small for the implementation of your retrieved documents or system prompt.
**Fix:**
1. Increase `max_tokens`.
2. Reduce `top_k` in your `@retriever`.
3. Use `priority` to allow non-critical items to be dropped.

<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "TechArticle",
  "headline": "Troubleshooting Fabra: Common Errors and Fixes",
  "description": "Resolve common Fabra issues like Point-in-Time Correctness errors, Redis connection failures, and Async loop errors.",
  "author": {"@type": "Organization", "name": "Fabra Team"},
  "keywords": "fabra troubleshooting, feature store errors, redis connection error, context budget error",
  "articleSection": "Support"
}
</script>
