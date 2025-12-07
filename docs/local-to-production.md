---
title: "Deploying Meridian: From Local Laptop to Production API"
description: "Guide to deploying Meridian. Move from DuckDB/In-Memory on your laptop to Postgres/Redis in production with zero code changes."
keywords: deploy feature store, meridian production, postgres redis feature store, mlops deployment
---

# From Laptop to Production in 3 Steps

## Step 1: Local Development (Day 1)

Your laptop is your feature store:

```python
# features.py - works locally, no setup
store = FeatureStore()  # DuckDB + In-Memory

@feature(entity=User, refresh="5m", materialize=True)
def fraud_score(user_id: str) -> float:
    # In reality, this would query your data warehouse
    return 0.85
```

Test in Jupyter. Iterate fast. Zero infrastructure.

## Step 2: Single-Server Production (Week 2)

Same code, just set environment variables:

```bash
export MERIDIAN_ENV=production
export MERIDIAN_POSTGRES_URL="postgresql+asyncpg://prod-db/features"
export MERIDIAN_REDIS_URL="redis://prod-cache:6379"
```

And initialize the store without arguments:
```python
# features.py
store = FeatureStore()  # Auto-detects Prod
```

Infrastructure needed:
- AWS RDS Postgres ($50/month)
- AWS ElastiCache Redis ($30/month)
- Deploy API to Heroku/Railway ($20/month)

**Total cost:** $100/month
**Setup time:** 1 hour

## Step 3: Horizontal Scale (Month 3)

No code changes. Just deploy more API pods.

Infrastructure:
- Same Postgres (vertically scale if needed)
- Redis cluster mode ($200/month)
- 3-5 API pods behind load balancer

**Total cost:** $500/month
**Setup time:** 2 hours

## Step 4: Local Production (Docker Compose)

We provide a `docker-compose.prod.yml` to spin up a full stack (Meridian + Redis + Postgres) locally.

```bash
# Start the stack
make prod-up

# Check health
curl http://localhost:8000/health
```

This stack mimics a real production environment and is perfect for integration testing or small-scale deployments.
