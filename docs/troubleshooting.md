---
title: "Troubleshooting Meridian: Common Errors and Fixes"
description: "Resolve common Meridian issues like Point-in-Time Correctness errors, Redis connection failures, and Async loop errors."
keywords: meridian troubleshooting, feature store errors, redis connection error, timestamp error
---

# Troubleshooting Guide

Common issues and how to fix them.

## 🩺 First Step: Meridian Doctor

Before diving into specific errors, run the **Doctor** to diagnose your environment:

```bash
meridian doctor
```

This command checks:
*   **Environment Variables:** `MERIDIAN_REDIS_URL`, `MERIDIAN_POSTGRES_URL`, etc.
*   **Connectivity:** Pings Redis and Postgres (if URLs are provided).
*   **Dependencies:** Verifies critical packages like `fastapi`, `redis`, `duckdb`.

---

## Point-in-Time Correctness

### "KeyError: timestamp" or "Column timestamp not found"
**Cause:** Meridian's `get_training_data` requires a `timestamp` column in your entity DataFrame to perform point-in-time joins.
**Fix:**
```python
entity_df["timestamp"] = pd.to_datetime("now")
```

### "No matching features found"
**Cause:** Your entity timestamps might be *older* than your feature timestamps. Meridian uses `ASOF JOIN ... WHERE entity.ts >= feature.ts`. If your features are from today but your entities are from yesterday, you get nothing (to prevent data leakage).
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
**Cause:** In Hybrid Mode, if you define `@feature(sql="SELECT * FROM my_table")`, Meridian expects `my_table` to exist in Postgres.
**Fix:** Ensure the table exists in your offline store. Meridian does not create raw data tables for you.

## Redis

### "ConnectionError: Connection refused"
**Cause:** Redis is not running or the URL is wrong.
**Fix:** Check `MERIDIAN_REDIS_URL`. Default is `redis://localhost:6379`.

## Context Store (RAG/Vectors)

### "UndefinedFunction: function vector_dims(vector) does not exist"
**Cause:** The `pgvector` extension is not installed or enabled in your Postgres database.
**Fix:**
Run this SQL in your database:
```sql
CREATE EXTENSION IF NOT EXISTS vector;
```
*Note: `meridian index create` attempts to do this automatically, but requires superuser permissions.*

### "ContextBudgetError: Required content exceeds budget"
**Cause:** Your `@context(max_tokens=N)` limit is too small for the implementation of your retrieved documents or system prompt.
**Fix:**
1. Increase `max_tokens`.
2. Reduce `top_k` in your `@retriever`.
3. Use `priority` to allow non-critical items to be dropped.
