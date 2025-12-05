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
    return 42
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
- **Meridian UI:** A built-in Streamlit dashboard to explore your data.
- **Rich Terminal:** Production-grade TUI with live metrics.
- **Jupyter Integration:** Beautiful HTML representations of your feature store objects.

### 4. Production-Grade Reliability 🛡️
- **Fallback Chain:** Cache -> Compute -> Default. If Redis fails, we compute on-demand.
- **Circuit Breakers:** Built-in protection against cascading failures (fail fast).
- **Deep Observability:** Prometheus metrics (`meridian_feature_requests_total`) and structured JSON logging out of the box.
- **Async Core:** Fully async I/O for high-throughput serving.

---

## 📚 Documentation

- **[Quickstart](quickstart.md):** Go from zero to served features in 30 seconds.
- **[Philosophy & Trade-offs](philosophy.md):** Why we built this and who it's for.
- **[Why Not Feast?](why-not-feast.md):** A honest comparison for small teams.
- **[Local to Production](local-to-production.md):** How to migrate when you're ready.
- **[Architecture](architecture.md):** Boring technology, properly applied.
- **[Use Cases](use-cases/fraud-detection.md):** Real-world examples like Fraud Detection.

---

## 🤝 Contributing

We love contributions! Please read our [CONTRIBUTING.md](https://github.com/davidahmann/meridian/blob/main/CONTRIBUTING.md) to get started.
