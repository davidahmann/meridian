# Meridian

<p align="center">

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

**2. Try the Quickstart Script**
Run a self-contained script to see the API in action:
```bash
python examples/quickstart.py
```

**3. Define Features (`examples/basic_features.py`)**
Or define features in a file to serve them:
```python
from meridian.core import FeatureStore, entity, feature
from datetime import timedelta

store = FeatureStore()

@entity(store)
class User:
    user_id: str

@feature(entity=User, refresh=timedelta(minutes=5), materialize=True)
def user_click_count(user_id: str) -> int:
    return 42
```

**4. Serve**
```bash
meridian serve examples/basic_features.py
```

**5. Query**
```bash
curl -X POST http://localhost:8000/features \
  -H "Content-Type: application/json" \
  -d '{"entity_name": "User", "entity_id": "u1", "features": ["user_click_count"]}'

# {"user_click_count": 100}
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
