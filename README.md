# Meridian

<p align="center">
  <img src="https://via.placeholder.com/150x150?text=Meridian" alt="Meridian Logo" width="150"/>
  <br>
  <b>Heroku for ML Features</b>
  <br>
  <a href="https://pypi.org/project/meridian-oss/"><img src="https://img.shields.io/pypi/v/meridian-oss?color=blue" alt="PyPI"></a>
  <a href="https://github.com/davidahmann/meridian/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-Apache%202.0-green" alt="License"></a>
</p>

> **"Define features in Python. Get training data and production serving for free."**

Meridian is a developer-first feature store designed to take you from a Jupyter notebook to production in 30 seconds. It eliminates the infrastructure tax of existing tools—no Kubernetes, no Spark, no YAML. Just pure Python and SQL.

---

## ⚡ The 30-Second Quickstart

**1. Install**
```bash
pip install meridian
```

**2. Define Features (`features.py`)**
```python
from meridian import FeatureStore, entity, feature

store = FeatureStore()

@entity(store)
class User:
    user_id: str

@feature(entity=User, refresh="5m", materialize=True)
def transaction_count_1h(user_id: str) -> int:
    return sql("""
        SELECT COUNT(*) FROM transactions
        WHERE user_id = {user_id}
        AND timestamp > NOW() - INTERVAL '1 hour'
    """)
```

**3. Serve**
```bash
meridian serve features.py
```

**4. Query**
```bash
curl -X POST http://localhost:8000/features \
  -H "Content-Type: application/json" \
  -d '{"entity": {"user_id": "u123"}, "features": ["transaction_count_1h"]}'

# {"user_id": "u123", "features": {"transaction_count_1h": 5}}
```

---

## 🚀 Why Meridian?

### 1. Local-First, Cloud-Ready
Most feature stores require a platform team to set up. Meridian runs on your laptop with zero dependencies (DuckDB + In-Memory) and scales to production with boring technology (Postgres + Redis).

### 2. No Magic, Just Python
We don't use YAML for configuration. Your code is your config.
- **Explicit Caching:** Use `@feature(materialize=True)` to cache hot features.
- **Explicit Refresh:** Use `@feature(refresh="5m")` to define freshness.

### 3. Production-Grade Reliability
- **Redis-Only Caching:** We avoid complex multi-tier caches to guarantee data consistency.
- **Randomized Locking:** Our distributed scheduler is self-healing and requires no leader election.
- **Zero-Code Serving:** Auto-generated FastAPI endpoints with built-in metrics and logging.

---

## 🏗️ Architecture

### Tier 1: Local Development (The "Wedge")
*Perfect for prototyping and single-developer projects.*
* **Offline Store:** DuckDB (Embedded)
* **Online Store:** Python Dictionary (In-Memory)
* **Scheduler:** APScheduler (Background Thread)
* **Infrastructure:** None (Just `pip install`)

### Tier 2: Production (The "Standard")
*Robust, scalable, and boring.*
* **Offline Store:** Postgres / Snowflake / BigQuery
* **Online Store:** Redis
* **Scheduler:** Distributed Workers with Redis Locks
* **Infrastructure:** 1x Postgres, 1x Redis, Nx API Pods

---

## 🗺️ Roadmap

- **Phase 1 (Now):** Core API, DuckDB/Postgres support, Redis caching, FastAPI serving.
- **Phase 2:** Drift detection, RBAC, and multi-region support.

---

## 🤝 Contributing

We love contributions! Please read our [CONTRIBUTING.md](CONTRIBUTING.md) to get started.

## 📄 License

Apache 2.0
