---
title: "The Feature Store for Startups: ML Infrastructure Without the Platform Team"
description: "Why Series A-D startups don't need enterprise feature stores. How to ship ML features without Kubernetes, Spark, or a dedicated platform team."
keywords: feature store startups, ml infrastructure startup, lightweight mlops, feature store small team, ml without platform team
date: 2025-01-12
---

# The Feature Store for Startups

You're a Series B startup. You have:

- 3 ML engineers
- 1 data engineer (maybe)
- 0 platform engineers
- A production ML model that needs real-time features

Every feature store assumes you have a dedicated platform team. Feast's getting started guide mentions Kubernetes 47 times. Tecton requires enterprise contracts. Featureform needs a distributed cluster.

You don't have time for this. You need to ship.

## The 95% Rule

Here's a secret the enterprise vendors don't want you to know:

**95% of feature serving is just:**

```sql
SELECT COUNT(*) FROM events
WHERE user_id = ?
AND timestamp > NOW() - INTERVAL '1 hour'
```

Cached in Redis. Refreshed every 5 minutes. Served in <5ms.

That's it. You don't need Spark. You don't need Kafka. You don't need Kubernetes.

Fabra is built for this 95%.

## What Startups Actually Need

After talking to dozens of ML teams at startups, we found the common requirements:

### 1. Python-First Definitions

Your ML engineers write Python. Your feature definitions should be Python.

```python
@feature(entity=User, refresh="5m")
def transaction_count_1h(user_id: str) -> int:
    return db.query(
        "SELECT COUNT(*) FROM transactions "
        "WHERE user_id = %s AND created_at > NOW() - INTERVAL '1 hour'",
        user_id
    )
```

Not YAML. Not a separate DSL. Just Python functions.

### 2. Works on Laptops

Your ML engineers need to test features locally before deploying. They shouldn't need Docker running 6 containers.

```bash
pip install "fabra[ui]"
fabra serve features.py
# Running on localhost:8000
```

DuckDB handles local storage. No external dependencies.

### 3. Standard Production Stack

When you deploy, you want boring technology:

- **Postgres** — you already have it
- **Redis** — you already have it
- **FastAPI** — your team knows it

No Spark clusters. No Kafka topics. No new infrastructure to learn.

### 4. Scales to Series C Problems

When you grow, the same code should handle more load:

```bash
# Just add more replicas
FABRA_ENV=production
FABRA_POSTGRES_URL=postgresql+asyncpg://...
FABRA_REDIS_URL=redis://...
```

Fabra's async I/O handles 10k+ requests per second. That's enough for most Series D companies.

## What You Don't Need (Yet)

Enterprise feature stores solve problems you don't have:

| Problem | Enterprise Solution | Startup Reality |
|---------|-------------------|-----------------|
| 100k+ QPS | Distributed caching layer | You have 1k QPS |
| Petabyte-scale training data | Spark/Flink pipelines | Your data fits in Postgres |
| Multi-team governance | RBAC, feature marketplace | You have 3 ML engineers |
| Sub-second streaming | Kafka, real-time ETL | 5-minute refresh is fine |

When you hit these problems, you'll have the engineering team (and budget) to solve them. Until then, ship features.

## Real Startup Use Cases

### Fraud Detection (Fintech)

```python
@feature(entity=Transaction, refresh="realtime")
async def user_velocity_1h(user_id: str) -> int:
    """Number of transactions in last hour."""
    return await db.fetchval(
        "SELECT COUNT(*) FROM transactions "
        "WHERE user_id = $1 AND created_at > NOW() - INTERVAL '1 hour'",
        user_id
    )

@feature(entity=Transaction, refresh="5m")
def avg_transaction_amount(user_id: str) -> float:
    """30-day average transaction amount."""
    return calculate_average(user_id, days=30)
```

### Recommendations (E-commerce)

```python
@feature(entity=User, refresh="1h")
def recent_categories(user_id: str) -> list:
    """Categories user browsed in last 24h."""
    return get_browse_history(user_id, hours=24)

@feature(entity=User, refresh="daily")
def purchase_affinity(user_id: str) -> dict:
    """Category purchase scores."""
    return calculate_affinity_scores(user_id)
```

### Personalization (SaaS)

```python
@feature(entity=User, refresh="5m")
def active_session(user_id: str) -> bool:
    """Is user currently active?"""
    return check_session(user_id)

@feature(entity=User, refresh="daily")
def user_segment(user_id: str) -> str:
    """Power user, regular, or churning."""
    return classify_user(user_id)
```

## The Math on Build vs Buy

Enterprise feature stores cost $50k-$500k/year. That buys a lot of engineering time.

But the real cost is engineering complexity:

| Approach | Setup Time | Maintenance | Flexibility |
|----------|------------|-------------|-------------|
| Enterprise vendor | 2-4 weeks | Vendor manages | Limited |
| Feast self-hosted | 4-8 weeks | Your team | High (but complex) |
| Fabra | 30 minutes | Minimal | High (and simple) |

Fabra is open source (Apache 2.0). The code is simple enough to fork if you need to.

## One-Command Deploy

When you're ready for production:

```bash
# Set your environment
export FABRA_ENV=production
export FABRA_POSTGRES_URL=postgresql+asyncpg://...
export FABRA_REDIS_URL=redis://...

# Generate deploy configs
fabra deploy fly --name my-features
# Creates: Dockerfile, fly.toml, requirements.txt

# Deploy
fly deploy
```

Supported platforms: Fly.io, Google Cloud Run, AWS ECS, Render, Railway.

## Try It

```bash
pip install "fabra[ui]"
fabra serve examples/basic_features.py
```

Ship ML features this week, not this quarter.

[Quickstart guide →](../quickstart.md)
