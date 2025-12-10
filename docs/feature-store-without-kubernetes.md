---
title: "Feature Store Without Kubernetes: Run ML Features Locally | Fabra"
description: "Run a production-grade feature store without Kubernetes or Docker. DuckDB for local dev, Postgres for production. Python decorators instead of YAML."
keywords: feature store without kubernetes, feature store no docker, local feature store, simple feature store, feast alternative, feature store startup, python feature store, duckdb feature store, ml features local
---

# Feature Store Without Kubernetes

> **TL;DR:** Run a production-grade feature store with `pip install` and Python decorators. No Kubernetes, no Docker, no YAML. DuckDB locally, Postgres in production.

## The Problem

You want to serve ML features. Every tutorial says:

1. Set up a Kubernetes cluster
2. Deploy Feast with 6 containers
3. Configure Spark/Flink pipelines
4. Write 500 lines of YAML
5. Hire a platform team to maintain it

**For what?** To serve a few features to your model.

## The Alternative

```bash
pip install "fabra-ai[ui]"
```

```python
from fabra.core import FeatureStore, entity, feature

store = FeatureStore()

@entity(store)
class User:
    user_id: str

@feature(entity=User, refresh="hourly")
def purchase_count(user_id: str) -> int:
    return db.query("SELECT COUNT(*) FROM purchases WHERE user_id = ?", user_id)

@feature(entity=User, refresh="daily")
def user_tier(user_id: str) -> str:
    return "premium" if is_premium(user_id) else "free"
```

```bash
fabra serve features.py
# Server running on http://localhost:8000

curl http://localhost:8000/features/purchase_count?user_id=user123
# {"value": 42, "timestamp": "2024-01-15T10:30:00Z"}
```

**That's it.** No containers. No orchestration. Just Python.

## How It Works

### Local Development (Default)

When you run locally (`FABRA_ENV=development`):

| Component | Technology | Notes |
|:---|:---|:---|
| **Online Store** | In-memory dict | Instant reads |
| **Offline Store** | DuckDB | Embedded, no server |
| **Scheduler** | APScheduler | In-process |

Zero external dependencies. Works on any machine with Python.

### Production

When you deploy (`FABRA_ENV=production`):

| Component | Technology | Notes |
|:---|:---|:---|
| **Online Store** | Redis | Sub-millisecond reads |
| **Offline Store** | Postgres | With pgvector for RAG |
| **Scheduler** | Distributed | Redis coordination |

**Same code. Same decorators. Different backends.**

```bash
# Local (default)
fabra serve features.py

# Production
FABRA_ENV=production \
FABRA_POSTGRES_URL=postgresql+asyncpg://... \
FABRA_REDIS_URL=redis://... \
fabra serve features.py
```

## Why Not Kubernetes?

| | Kubernetes | Fabra |
|:---|:---|:---|
| **Setup time** | Days | 30 seconds |
| **Minimum cost** | $70-150/month | $0 (local) |
| **Config files** | 500+ lines YAML | 0 |
| **Team required** | Platform engineers | Just you |
| **Learning curve** | 47 concepts | 3 decorators |

For a feature store serving 1-10k requests per second, Kubernetes adds complexity without proportional benefit.

## Feature Parity

Fabra matches Feast on the hard problems:

### Point-in-Time Correctness

Training ML models requires feature values as they existed at prediction time. We use:

- **DuckDB (local):** `ASOF JOIN` for temporal lookups
- **Postgres (production):** `LATERAL JOIN` with index optimization

```sql
-- DuckDB (local)
SELECT * FROM features
ASOF JOIN events
ON features.user_id = events.user_id
AND features.timestamp <= events.timestamp

-- Postgres (production)
SELECT * FROM events e
LEFT JOIN LATERAL (
    SELECT * FROM features f
    WHERE f.user_id = e.user_id
    AND f.timestamp <= e.timestamp
    ORDER BY f.timestamp DESC LIMIT 1
) f ON true
```

Same semantics. Same correctness. No Spark cluster required.

### Async I/O

Production serving uses non-blocking I/O:

- `asyncpg` for Postgres connections
- `redis-py` async client
- Connection pooling with circuit breakers

### Refresh Scheduling

```python
@feature(entity=User, refresh="5m")      # Every 5 minutes
@feature(entity=User, refresh="hourly")  # Every hour
@feature(entity=User, refresh="daily")   # Daily at midnight
```

Schedules run in-process locally, distributed in production.

## One-Command Deploy

When you're ready for production:

```bash
# Fly.io
fabra deploy fly --name my-features

# Google Cloud Run
fabra deploy cloudrun --name my-features --project my-gcp

# AWS ECS
fabra deploy ecs --name my-features

# Railway
fabra deploy railway --name my-features
```

Each command generates the right config files (Dockerfile, fly.toml, cloudbuild.yaml) and deploys.

## Cost Comparison

| Platform | Minimum | With Traffic |
|:---|:---|:---|
| Local (DuckDB) | $0 | $0 |
| Fly.io | $5/month | $15-50/month |
| Cloud Run | $0 (scale to zero) | $10-50/month |
| Railway | $5/month | $15-40/month |
| **Kubernetes (GKE)** | **$70/month** | **$100-300/month** |

Kubernetes is 10-20x more expensive for the same workload.

## Quick Start

```bash
pip install "fabra-ai[ui]"

# Create features file
cat > features.py << 'EOF'
from fabra.core import FeatureStore, entity, feature

store = FeatureStore()

@entity(store)
class User:
    user_id: str

@feature(entity=User, refresh="5m")
def login_count(user_id: str) -> int:
    return abs(hash(user_id)) % 100
EOF

# Serve
fabra serve features.py

# Test
curl http://localhost:8000/features/login_count?user_id=test123
```

## FAQ

**Q: Can I run a feature store without Docker?**
A: Yes. Fabra uses DuckDB (embedded database) for local development. No Docker, no containers, no external services. Just `pip install` and Python.

**Q: How do I avoid Kubernetes for ML features?**
A: Use Fabra with standard Postgres + Redis for production. Deploy to Fly.io, Railway, Cloud Run — any container platform. No K8s cluster required.

**Q: Is this production-ready without Kubernetes?**
A: Yes. We use asyncpg connection pooling, Redis with circuit breakers, and Prometheus metrics. Same reliability, simpler ops.

**Q: What about scaling?**
A: Fabra handles ~1000 requests/second per instance. Scale horizontally on any platform. Most startups never need more than 2-3 instances.

**Q: Can I migrate from Feast?**
A: Yes. Convert YAML feature definitions to Python `@feature` decorators. Same data access patterns, no infrastructure tax.

**Q: What if I need RAG/LLM features too?**
A: Fabra includes a Context Store with `@retriever` and `@context` decorators. Same infrastructure, unified deployment.

## Next Steps

- [Quickstart](quickstart.md) — Full setup guide
- [Feast vs Fabra](feast-alternative.md) — Detailed comparison
- [Deploy to Production](local-to-production.md) — When you're ready
- [Context Store](context-store.md) — Add RAG capabilities

---

## Also Building LLM/RAG Features?

Fabra includes a Context Store for LLM applications — vector search, token budgets, and full audit trails. Same infrastructure, same deployment.

[Context Store →](context-store.md) | [RAG Audit Trail →](rag-audit-trail.md) | [Compliance Guide →](compliance-guide.md)

---

## You Might Also Search For

- "feature store without kubernetes"
- "feast too complex setup"
- "run feature store locally without docker"
- "simple python feature store"
- "feature store for startups"

<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "TechArticle",
  "headline": "Feature Store Without Kubernetes",
  "description": "Run a production-grade feature store without Kubernetes or Docker. DuckDB for local dev, Postgres for production.",
  "author": {"@type": "Organization", "name": "Fabra Team"},
  "keywords": "feature store without kubernetes, local feature store, feast alternative, python feature store",
  "articleSection": "Documentation"
}
</script>
