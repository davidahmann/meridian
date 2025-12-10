---
title: "Running a Feature Store Locally Without Docker: The DuckDB Approach"
description: "How to run a production-grade feature store on your laptop without Docker or Kubernetes. Using DuckDB for local development that scales to Postgres."
keywords: local feature store, feature store without docker, duckdb feature store, local ml development, feature store setup
date: 2025-01-14
---

# Running a Feature Store Locally Without Docker

Every feature store tutorial starts the same way:

```bash
docker-compose up -d
# Wait 5 minutes for 6 containers to start
# Debug why the registry can't connect to Redis
# Give up and use a managed service
```

What if you could just run `pip install` and start defining features?

## The Problem With Docker-First Development

Docker is great for deployment. It's terrible for development iteration.

When you're experimenting with feature definitions, you want:

1. **Instant feedback** — not waiting for containers to restart
2. **Simple debugging** — print statements, not container logs
3. **No port conflicts** — not managing 5 different services
4. **Works on any machine** — including your M1 Mac with Docker issues

Most feature stores assume you have Docker running. Feast requires it for the registry. Tecton requires a cloud connection. Featureform needs Kubernetes.

## The DuckDB Solution

Fabra uses DuckDB for local development. DuckDB is:

- **Embedded** — runs in your Python process, no server needed
- **Fast** — columnar analytics engine, perfect for feature aggregations
- **Compatible** — same SQL as Postgres for easy migration

Here's how it works:

```python
from fabra.core import FeatureStore, entity, feature

# No connection strings. No Docker. Just Python.
store = FeatureStore()

@entity(store)
class User:
    user_id: str

@feature(entity=User, refresh="5m")
def login_count(user_id: str) -> int:
    return abs(hash(user_id)) % 100

@feature(entity=User, refresh="daily")
def user_tier(user_id: str) -> str:
    return "premium" if hash(user_id) % 2 == 0 else "free"
```

```bash
pip install "fabra-ai[ui]"
fabra serve features.py
# Server running on http://localhost:8000
```

That's it. No containers. No configuration files. The feature store is running.

## What Happens Under the Hood

When you run locally (`FABRA_ENV=development`, the default):

1. **Online Store:** In-memory Python dictionary (instant reads)
2. **Offline Store:** DuckDB file (`.fabra/features.duckdb`)
3. **Scheduler:** APScheduler in-process (no external dependencies)

When you deploy (`FABRA_ENV=production`):

1. **Online Store:** Redis (sub-millisecond reads)
2. **Offline Store:** Postgres with async I/O
3. **Scheduler:** Distributed scheduler with Redis coordination

**Same code. Same decorators. Different backends.**

```bash
# Development (default)
FABRA_ENV=development
fabra serve features.py

# Production
FABRA_ENV=production
FABRA_POSTGRES_URL=postgresql+asyncpg://...
FABRA_REDIS_URL=redis://...
fabra serve features.py
```

## Point-in-Time Correctness, Locally

The hardest problem in feature stores is point-in-time correctness: when generating training data, you need feature values as they existed at prediction time.

Most feature stores solve this with Spark jobs. Fabra solves it with SQL.

**DuckDB (local):**
```sql
SELECT * FROM features
ASOF JOIN events
ON features.user_id = events.user_id
AND features.timestamp <= events.timestamp
```

**Postgres (production):**
```sql
SELECT * FROM events e
LEFT JOIN LATERAL (
    SELECT * FROM features f
    WHERE f.user_id = e.user_id
    AND f.timestamp <= e.timestamp
    ORDER BY f.timestamp DESC
    LIMIT 1
) f ON true
```

Same semantics. Same correctness. No Spark cluster required.

## When You Need More

DuckDB is perfect for:

- Local development and testing
- Small datasets (< 10GB)
- Single-machine deployments
- CI/CD pipelines

When you outgrow it:

```bash
# Generate production configs
fabra deploy fly --name my-app

# Or just set environment variables
export FABRA_ENV=production
export FABRA_POSTGRES_URL=postgresql+asyncpg://...
export FABRA_REDIS_URL=redis://...
```

No code changes. The same `@feature` decorators work with Postgres and Redis.

## Try It Now

```bash
pip install "fabra-ai[ui]"

# Create a features file
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

# Serve it
fabra serve features.py

# Test it
curl http://localhost:8000/features/login_count?user_id=test123
```

No Docker. No Kubernetes. No YAML. Just Python.

[Get started →](../quickstart.md)

<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "BlogPosting",
  "headline": "Running a Feature Store Locally Without Docker: The DuckDB Approach",
  "description": "How to run a production-grade feature store on your laptop without Docker or Kubernetes. Using DuckDB for local development that scales to Postgres.",
  "author": {"@type": "Organization", "name": "Fabra Team"},
  "datePublished": "2025-01-14",
  "keywords": "local feature store, feature store without docker, duckdb feature store, local ml development"
}
</script>
