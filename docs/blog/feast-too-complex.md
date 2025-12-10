---
title: "I Gave Up on Feast After 2 Weeks. Here's What I Use Now."
description: "After 2 weeks wrestling with Feast's Kubernetes requirements and YAML configuration, I found a simpler alternative. Here's my experience and what I switched to."
keywords: feast too complex, feast setup problems, feast kubernetes required, feast alternative, feature store without kubernetes, simple feature store, feast yaml hell
date: 2025-01-20
---

# I Gave Up on Feast After 2 Weeks. Here's What I Use Now.

I'm an ML engineer at a Series B startup. We have 8 people on the data/ML team. No platform engineers. No Kubernetes cluster.

When I needed to serve ML features in production, I did what everyone does: I tried Feast.

Two weeks later, I gave up. Here's what happened.

## Week 1: The Excitement Phase

Day 1 was great. The docs looked clean. The concepts made sense. Feature views, entities, online stores — I got it.

```python
# This looked so elegant!
@feature_view(entities=[user], schema=[...])
def user_features():
    ...
```

Then I tried to run it.

## The Kubernetes Requirement

First roadblock: Feast assumes you have Kubernetes.

> "Just deploy the feature server to your K8s cluster..."

We don't have a K8s cluster. We're a 40-person startup. We deploy to Render and Railway.

I tried the local mode. It worked for development. But when I asked "how do I get this to production?", every answer involved:

- Helm charts
- Kubernetes operators
- Spark jobs
- Airflow DAGs

I just wanted to serve features to my model. I didn't want to become a platform engineer.

## Week 2: The YAML Hell

I pushed through. Maybe I could make it work without K8s.

Then I met the YAML.

```yaml
# feature_store.yaml
project: my_project
registry: data/registry.db
provider: local
online_store:
    type: redis
    connection_string: "localhost:6379"
offline_store:
    type: file
entity_key_serialization_version: 2
```

And then `feature_views.yaml`. And `entities.yaml`. And `data_sources.yaml`.

For every feature I wanted to serve, I was writing more YAML than Python.

My feature definition:
```yaml
# 47 lines of YAML
feature_views:
  - name: user_features
    entities:
      - user_id
    ttl: 3600s
    schema:
      - name: purchase_count
        dtype: INT64
      - name: last_purchase
        dtype: TIMESTAMP
    # ... 40 more lines
```

What I actually wanted to write:
```python
# 5 lines of Python
@feature(entity=User)
def purchase_count(user_id: str) -> int:
    return db.query("SELECT COUNT(*) FROM purchases WHERE user_id = ?", user_id)
```

## The Breaking Point

Day 10. I had Feast "working" locally. Time to deploy.

The documentation said to:
1. Set up a GCS bucket for the registry
2. Configure a Redis cluster
3. Deploy the feature server (via Kubernetes)
4. Set up Spark for materialization jobs
5. Configure Airflow for scheduling

I looked at our infrastructure: Heroku. That's it.

I was being asked to adopt 5 new technologies just to serve a few features.

## What I Use Now

I found Fabra. It's what Feast should have been.

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
```

```bash
fabra serve features.py
# Done. Server running on localhost:8000.
```

No YAML. No Kubernetes. No Spark. Just Python.

## The Differences That Matter

| What I Needed | Feast | Fabra |
|:---|:---|:---|
| Local development | ✅ Works | ✅ Works |
| Production without K8s | ❌ Painful | ✅ `fabra deploy railway` |
| Feature definition | YAML files | Python decorators |
| Materialization | Spark jobs | Built-in scheduler |
| Time to first feature | 2 weeks | 30 seconds |

## What About Scale?

"But Feast scales to millions of QPS!"

Sure. And Kubernetes scales to thousands of nodes. That doesn't mean I need it.

Our production load: ~500 requests per second. A single Fabra instance handles 1000+ RPS. We'll never need Feast's scale.

If you're at Google scale, use Feast. If you're a startup trying to ship, you probably aren't.

## The Features I Actually Needed

1. **Serve features via HTTP** — Fabra does this out of the box
2. **Point-in-time correctness** — Fabra uses ASOF/LATERAL joins, same as Feast
3. **Scheduled refresh** — `@feature(refresh="hourly")`
4. **Production deployment** — `fabra deploy railway --name my-features`

Everything Feast does that I needed. Nothing I didn't.

## When You Should Still Use Feast

To be fair, Feast is the right choice if:

- You have a dedicated platform team (5+ engineers)
- You're already running Kubernetes and Spark
- You need 100k+ QPS with streaming features
- You have months to invest in setup

For the rest of us — the 99% of ML engineers at startups and growth companies — there's a simpler path.

## Try It

```bash
pip install "fabra-ai[ui]"

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

fabra serve features.py
curl http://localhost:8000/features/login_count?user_id=test123
```

30 seconds. No YAML. No Kubernetes.

[Full Quickstart →](../quickstart.md) | [Feast vs Fabra Comparison →](../feast-alternative.md)

---

## Also Building RAG/LLM Features?

Fabra includes a Context Store for LLM applications — vector search, token budgets, and full audit trails. Same infrastructure, same deployment.

[Context Store →](../context-store.md) | [RAG Audit Trail →](../rag-audit-trail.md)

---

## You Might Also Search For

- "feast alternative without kubernetes"
- "simple python feature store"
- "feature store for startups"
- "run feature store locally without docker"
- "feast yaml configuration"

<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "BlogPosting",
  "headline": "I Gave Up on Feast After 2 Weeks. Here's What I Use Now.",
  "description": "After 2 weeks wrestling with Feast's Kubernetes requirements, I found a simpler feature store alternative.",
  "author": {"@type": "Person", "name": "ML Engineer"},
  "datePublished": "2025-01-20",
  "keywords": "feast too complex, feast alternative, feature store, kubernetes, mlops"
}
</script>
