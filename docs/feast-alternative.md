# Meridian vs Feast: The Lightweight Feature Store Alternative

If you are looking for a **lightweight feature store** that runs on your laptop but scales to production, you have likely found Feast. And you likely found it complicated.

Meridian is the **developer-first alternative to Feast**. We provide the same core guarantees (Point-in-Time Correctness, Async I/O) without the infrastructure tax.

## Feature Comparison

| Feature | Feast | Meridian |
| :--- | :--- | :--- |
| **Setup Time** | Days (Kubernetes, Docker) | Seconds (`pip install`) |
| **Configuration** | YAML Hell | Python Code (`@feature`) |
| **Infrastructure** | Spark / Flink / K8s | DuckDB (Local) / Postgres (Prod) |
| **Point-in-Time Joins** | ✅ Yes | ✅ **Yes (v1.1.0)** |
| **Async I/O** | ✅ Yes | ✅ **Yes (v1.1.0)** |
| **Hybrid Features** | ❌ No (Complex) | ✅ **Yes (Python + SQL)** |
| **Target User** | Platform Teams | ML Engineers |

## Why Choose Meridian?

### 1. No Kubernetes Required
Feast assumes you have a platform team managing a Kubernetes cluster. Meridian assumes you are a developer who wants to ship code.
- **Feast:** Requires Docker, K8s, and complex registry syncing.
- **Meridian:** Runs on your laptop with DuckDB. Deploys to standard Postgres + Redis.

### 2. Python, Not YAML
Feast relies heavily on YAML for feature definitions. Meridian uses Python decorators.
- **Feast:**
  ```yaml
  # features.yaml
  name: user_clicks
  type: int64
  ...
  ```
- **Meridian:**
  ```python
  @feature(entity=User, materialize=True)
  def user_clicks(user_id: str) -> int:
      return 42
  ```

### 3. Feature Parity (Now in v1.1.0)
With the release of v1.1.0, Meridian matches Feast on the critical "hard" problems of feature engineering:
- **Point-in-Time Correctness:** We use `ASOF JOIN` (DuckDB) and `LATERAL JOIN` (Postgres) to prevent data leakage, just like Feast.
- **Async I/O:** Our production serving path uses `asyncpg` and `redis-py` for high-throughput, non-blocking performance.

## When to Use Feast
Feast is a great tool for massive scale. Use Feast if:
- You have a dedicated platform team of 5+ engineers.
- You are already running Spark/Flink pipelines.
- You need to serve 100k+ QPS (though Meridian handles 10k+ easily).

## Conclusion
If you want "Google Scale" complexity, use Feast.
If you want **"Heroku for ML Features"**, use Meridian.
