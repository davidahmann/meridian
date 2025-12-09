---
title: "Why We Built a Feast Alternative: The Story Behind Fabra"
description: "We spent 6 weeks fighting Feast's Kubernetes complexity. Then we built Fabra in 2 weeks. Here's why Python decorators beat YAML for feature stores."
keywords: feast alternative, feature store comparison, python feature store, mlops without kubernetes, lightweight feature store
date: 2025-01-15
---

# Why We Built a Feast Alternative

We didn't set out to build a feature store. We set out to ship an ML model.

## The 6-Week Detour

Our team needed real-time features for a fraud detection model. Standard stuff: user transaction counts, average purchase amounts, time since last login. The kind of features every ML team needs.

We chose Feast because it's the "industry standard." Open source. Battle-tested. What could go wrong?

**Week 1:** Docker networking issues. The registry container couldn't talk to the feature server.

**Week 2:** Kubernetes manifests. Our staging cluster didn't match the example configs.

**Week 3:** YAML debugging. A missing indent broke feature materialization.

**Week 4:** Registry sync issues. Features defined locally weren't appearing in production.

**Week 5:** Spark job failures. The batch materialization pipeline kept timing out.

**Week 6:** We gave up.

## The 2-Week Solution

We asked ourselves: what do we actually need?

1. Define features in Python (not YAML)
2. Cache them in Redis (for <10ms serving)
3. Log them to Postgres (for training data)
4. Serve them via HTTP (for our model)

That's it. We don't need Spark. We don't need Kubernetes. We don't need a 47-file configuration.

So we built Fabra.

```python
from fabra.core import FeatureStore, entity, feature

store = FeatureStore()

@entity(store)
class User:
    user_id: str

@feature(entity=User, refresh="5m")
def transaction_count_1h(user_id: str) -> int:
    # Your logic here - SQL, API call, whatever
    return query_transactions(user_id, hours=1)

@feature(entity=User, refresh="daily")
def avg_purchase_amount(user_id: str) -> float:
    return calculate_average(user_id)
```

```bash
fabra serve features.py
# That's it. Server running on :8000
```

## What We Kept From Feast

Feast solves real problems. We kept the solutions:

**Point-in-Time Correctness:** When you generate training data, you need features as they existed at prediction time—not today's values. Feast uses complex Spark jobs for this. Fabra uses `ASOF JOIN` in DuckDB and `LATERAL JOIN` in Postgres. Same correctness, no Spark.

**Online/Offline Split:** Hot features in Redis, historical features in the database. Same architecture, simpler implementation.

**Async I/O:** Production serving needs non-blocking calls. We use `asyncpg` and `redis-py` async clients throughout.

## What We Dropped

**YAML Configuration:** Features are code. Define them in Python.

**Kubernetes Dependency:** DuckDB runs on your laptop. Postgres runs anywhere.

**Spark/Flink Requirement:** SQL is enough for 95% of feature transformations.

**Platform Team Assumption:** Fabra is for the ML engineer who wants to ship, not the platform team managing infrastructure.

## What We Added

Feast is a feature store. Fabra is a feature store + context store.

If you're building LLM applications, you need more than structured features. You need:

- Vector search for document retrieval
- Token budget management for context assembly
- Priority-based truncation when context exceeds limits

```python
from fabra.retrieval import retriever
from fabra.context import context, ContextItem

@retriever(index="docs", top_k=5)
async def search_docs(query: str):
    pass  # Auto-wired to pgvector

@context(store, max_tokens=4000)
async def build_prompt(user_id: str, query: str):
    tier = await store.get_feature("user_tier", user_id)
    docs = await search_docs(query)
    return [
        ContextItem(content=f"User tier: {tier}", priority=0, required=True),
        ContextItem(content=str(docs), priority=1),
    ]
```

Feast doesn't do this. You'd need to add Pinecone, LangChain, and glue code.

## When to Use Feast Instead

Be honest with yourself:

- **Use Feast** if you have 5+ platform engineers and existing Spark infrastructure
- **Use Feast** if you need 100k+ QPS (Fabra handles 10k+ comfortably)
- **Use Feast** if you're a Google-scale company with Google-scale problems

**Use Fabra** if you're a Series A-D startup with 10-500 engineers who want to ship ML features this week, not this quarter.

## Try It

```bash
pip install "fabra[ui]"
fabra serve examples/basic_features.py
```

No Docker. No Kubernetes. No YAML.

[Read the full comparison →](../feast-alternative.md)
