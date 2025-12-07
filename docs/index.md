---
title: "Meridian - The Heroku for ML Features | Python Feature Store"
description: "Define features in Python and deploy to production in 30 seconds. Meridian is a local-first feature store for ML engineers. No YAML, no infrastructure tax."
keywords: feature store, python feature engineering, duckdb feature store, mlops, machine learning pipeline
---

# Meridian: Heroku for ML Features

> **"Define features in Python. Get training data and production serving for free."**

Meridian is a developer-first feature store designed to take you from a Jupyter notebook to production in 30 seconds. It eliminates the infrastructure tax of existing tools—no Kubernetes, no Spark, no YAML. Just pure Python and SQL.

---

## ⚡ The 30-Second Quickstart

**1. Install**
```bash
pip install "meridian-oss[ui]"
```

**2. Define Features**
```python
# features.py
from meridian.core import FeatureStore, entity, feature
from datetime import timedelta

store = FeatureStore()

@entity(store)
class User:
    user_id: str

@feature(entity=User, refresh=timedelta(minutes=5), materialize=True)
def user_click_count(user_id: str) -> int:
    return random.randint(0, 1000)
```

**3. Serve & Visualize**
```bash
meridian serve features.py
# OR
meridian ui features.py
```

[Get Started Now →](quickstart.md)

---

## 🚀 Why Meridian?

### 1. Local-First, Cloud-Ready
Most feature stores require a platform team to set up. Meridian runs on your laptop with zero dependencies (DuckDB + In-Memory) and scales to production with boring technology (Postgres + Redis).

### 2. No Magic, Just Python
We don't use YAML for configuration. Your code is your config.
- **Explicit Caching:** Use `@feature(materialize=True)` to cache hot features.
- **Explicit Refresh:** Use `@feature(refresh="5m")` to define freshness.

### 3. Instant Wow ✨
- **Meridian UI:** A built-in Streamlit dashboard with **Visual Dependency Graphs**.
- **Rich Terminal:** Production-grade TUI with live metrics.
- **Jupyter Integration:** Beautiful HTML representations of your feature store objects.

### 4. Production-Grade Reliability 🛡️
- **Self-Healing:** Run `meridian doctor` to diagnose environment issues.
- **Fallback Chain:** Cache -> Compute -> Default. If Redis fails, we compute on-demand.
- **Circuit Breakers:** Built-in protection against cascading failures (fail fast).
- **Deep Observability:** Prometheus metrics (`meridian_feature_requests_total`) and structured JSON logging out of the box.
- **Async Core:** Fully async I/O for high-throughput serving.

### 5. Hybrid Features (New in v1.1.0) 🏭
- **Python Features:** Use `@feature` with Python logic for complex math (e.g., Haversine distance).
- **SQL Features:** Use `@feature(sql="...")` to delegate heavy joins to your warehouse (DuckDB/Postgres).
- **Materialization:** Automatically run SQL queries and bulk-load results into Redis.

### 6. Point-in-Time Correctness (New in v1.1.0) 🕰️
- **No Data Leakage:** We use `ASOF JOIN` (DuckDB) and `LATERAL JOIN` (Postgres) to ensure training data reflects the world *exactly* as it was at the event time.
- **Consistent:** Same logic for offline training and online serving.

### 7. Write Once, Run Anywhere (New in v1.1.0) 🛠️
- **Dev:** `MERIDIAN_ENV=development` (default) uses DuckDB + In-Memory.
- **Prod:** `MERIDIAN_ENV=production` uses Async Postgres + Redis.
- **Zero Code Changes:** Your feature definitions stay exactly the same.

---

## 📚 Documentation

- **[Quickstart](quickstart.md):** Go from zero to served features in 30 seconds.
- **[Philosophy & Trade-offs](philosophy.md):** Why we built this and who it's for.
- **[Meridian vs Feast](feast-alternative.md):** The lightweight alternative for ML engineers.
- **[Local to Production](local-to-production.md):** How to migrate when you're ready.
- **[Architecture](architecture.md):** Boring technology, properly applied.
- **[Use Cases](use-cases/fraud-detection.md):**
    - [Fraud Detection](use-cases/fraud-detection.md)
    - [Churn Prediction (PIT)](use-cases/churn-prediction.md)
    - [Real-Time Recommendations (Async)](use-cases/real-time-recommendations.md)
- **[Hybrid Features](hybrid-features.md):** Mixing Python logic and SQL power.
- **[FAQ](faq.md):** Common questions about production, scaling, and comparisons.
- **[Troubleshooting](troubleshooting.md):** Common issues and fixes.
- **[Why We Built Meridian](why-we-built-meridian.md):** The story behind the "Heroku for ML Features".

---

## 🤝 Contributing

We love contributions! Please read our [CONTRIBUTING.md](https://github.com/davidahmann/meridian/blob/main/CONTRIBUTING.md) to get started.

<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "SoftwareApplication",
  "name": "Meridian",
  "operatingSystem": "Linux, macOS, Windows",
  "applicationCategory": "DeveloperApplication",
  "description": "Heroku for ML Features. Define features in Python. Get training data and production serving for free.",
  "offers": {
    "@type": "Offer",
    "price": "0",
    "priceCurrency": "USD"
  },
  "url": "https://davidahmann.github.io/meridian/"
}
</script>
