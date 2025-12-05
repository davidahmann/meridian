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

Same code, add 3 environment variables:

```python
store = FeatureStore(
    offline_store="postgresql://prod-db/features",
    online_store="redis://prod-cache:6379"
)
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

We provide a `docker-compose.yml` to spin up a full stack (Meridian + Redis + Postgres + Prometheus) locally.

```bash
# Start the stack
docker compose up -d

# Check health
curl http://localhost:8005/docs

# Check metrics
curl http://localhost:9095/-/healthy
```

This stack mimics a real production environment and is perfect for integration testing or small-scale deployments.

## FAQ

**Q: How do I migrate from local to production?**
A: Change 2 lines of code (offline_store and online_store URLs). Everything else identical. Point-in-time correctness guaranteed in both modes.

**Q: What if I outgrow single Postgres?**
A: Switch offline_store to Snowflake/BigQuery. Online store stays Redis. No code changes beyond config.

**Q: Do I need Kubernetes?**
A: No. Heroku/Railway/ECS work fine. If you want K8s, we have Helm charts, but it's not required.
