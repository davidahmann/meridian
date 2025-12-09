---
title: "Meridian - The Context Store for LLMs & ML Features"
description: "Unify RAG pipelines and ML features in a single Python decorator. From notebook to production in 30 seconds."
keywords: context store, rag pipeline, llm memory, feature store, python features, mlops, pgvector, vector search
---

# Meridian: The Context Store for LLMs & ML Features

> **Unify RAG pipelines and ML features in a single Python decorator.**

From notebook prototype to production in 30 seconds. No Kubernetes. No Spark. No YAML.

[Get Started →](quickstart.md) | [Try in Browser →](https://meridianoss.vercel.app)

---

## The Problem

You're building an AI app. You need:

- **Structured features** (user tier, purchase history) for personalization
- **Unstructured context** (relevant docs, chat history) for your LLM
- **Vector search** for semantic retrieval
- **Token budgets** to fit your context window

Today, this means stitching together LangChain, Pinecone, a feature store, Redis, and prayer.

**Meridian unifies all of this in one Python decorator.**

---

## The 30-Second Quickstart

```bash
pip install "meridian-oss[ui]"
```

```python
from meridian.core import FeatureStore, entity, feature
from meridian.context import context, ContextItem
from meridian.retrieval import retriever

store = FeatureStore()

@entity(store)
class User:
    user_id: str

@feature(entity=User, refresh="daily")
def user_tier(user_id: str) -> str:
    return "premium" if hash(user_id) % 2 == 0 else "free"

@retriever(index="docs", top_k=3)
async def find_docs(query: str):
    pass  # Automatic vector search via pgvector

@context(store, max_tokens=4000)
async def build_prompt(user_id: str, query: str):
    tier = await store.get_feature("user_tier", user_id)
    docs = await find_docs(query)
    return [
        ContextItem(content=f"User is {tier}.", priority=0),
        ContextItem(content=str(docs), priority=1),
    ]
```

```bash
meridian serve features.py
# Server running on http://localhost:8000
```

**That's it.** No infrastructure. No config files. Just Python.

---

## Why Meridian?

| | Traditional Stack | Meridian |
|:---|:---|:---|
| **Config** | 500 lines of YAML | Python decorators |
| **Infrastructure** | Kubernetes + Spark + Pinecone | Your laptop (DuckDB) |
| **RAG Pipeline** | LangChain spaghetti | `@retriever` + `@context` |
| **Feature Serving** | Separate feature store | Same `@feature` decorator |
| **Time to Production** | Weeks | 30 seconds |

### One Decorator for Everything

Other tools make you choose: LangChain for RAG, Feast for features, a separate vector DB. Meridian gives you `@feature`, `@retriever`, and `@context` — all wired together, all in Python.

### Local-First, Production-Ready

```bash
MERIDIAN_ENV=development  # DuckDB + In-Memory (default)
MERIDIAN_ENV=production   # Postgres + Redis + pgvector
```

Same code. Zero changes. Just flip an environment variable.

### Point-in-Time Correctness

Training ML models? We use `ASOF JOIN` (DuckDB) and `LATERAL JOIN` (Postgres) to ensure your training data reflects the world exactly as it was — no data leakage, ever.

### Token Budget Management

```python
@context(store, max_tokens=4000)
async def build_prompt(user_id: str, query: str):
    return [
        ContextItem(content=critical_info, priority=0, required=True),
        ContextItem(content=nice_to_have, priority=2),  # Dropped if over budget
    ]
```

Automatically assembles context that fits your LLM's window. Priority-based truncation. No more "context too long" errors.

### Production-Grade Reliability

- **Self-Healing:** `meridian doctor` diagnoses environment issues
- **Fallback Chain:** Cache → Compute → Default
- **Circuit Breakers:** Built-in protection against cascading failures
- **Observability:** Prometheus metrics, structured JSON logging, OpenTelemetry

---

## Key Capabilities

### For AI Engineers (Context Store)

- **[Vector Search](context-store.md):** Built-in pgvector with automatic chunking and embedding
- **[Magic Retrievers](retrievers.md):** `@retriever` auto-wires to your vector index
- **[Context Assembly](context-assembly.md):** Token budgets, priority truncation, explainability API
- **Semantic Cache:** Cache expensive LLM calls and retrieval results

### For ML Engineers (Feature Store)

- **[Hybrid Features](hybrid-features.md):** Mix Python logic and SQL in the same pipeline
- **[Event-Driven](event-driven-features.md):** Trigger updates via Redis Streams
- **[Point-in-Time Joins](use-cases/churn-prediction.md):** Zero data leakage for training
- **[Hooks](hooks.md):** Before/After hooks for custom pipelines

### For Everyone

- **[One-Command Deploy](local-to-production.md):** `meridian deploy fly|cloudrun|ecs|railway|render`
- **Visual UI:** Dependency graphs, live metrics, context debugging
- **[Unit Testing](unit_testing.md):** Test features in isolation

### For Compliance & Debugging

- **[Context Accountability](context-accountability.md):** Full lineage tracking for AI decisions
- **Context Replay:** Reproduce exactly what your AI knew at any point in time
- **Audit Trails:** UUIDv7-based context IDs with complete data provenance
- **[Freshness SLAs](freshness-sla.md):** Ensure data freshness with configurable thresholds and degraded mode

---

## Use Cases

- **[RAG Chatbot](use-cases/rag-chatbot.md):** Build a production RAG application
- **[Fraud Detection](use-cases/fraud-detection.md):** Real-time feature serving
- **[Churn Prediction](use-cases/churn-prediction.md):** Point-in-time correct training data
- **[Real-Time Recommendations](use-cases/real-time-recommendations.md):** Async feature pipelines

---

## Documentation

### Getting Started

- [Quickstart](quickstart.md) — Zero to served features in 30 seconds
- [Philosophy](philosophy.md) — Why we built this and who it's for
- [Architecture](architecture.md) — Boring technology, properly applied

### Guides

- [Local to Production](local-to-production.md) — Deploy when you're ready
- [Meridian vs Feast](feast-alternative.md) — The lightweight alternative
- [Comparisons](comparisons.md) — vs other tools

### Reference

- [Glossary](glossary.md) — Key terms defined
- [FAQ](faq.md) — Common questions
- [Troubleshooting](troubleshooting.md) — Common issues and fixes
- [Changelog](changelog.md) — Version history

### Blog

- [Why We Built a Feast Alternative](blog/feast-alternative.md)
- [Running a Feature Store Locally Without Docker](blog/local-feature-store.md)
- [RAG Without LangChain](blog/rag-without-langchain.md)
- [The Feature Store for Startups](blog/feature-store-for-startups.md)
- [Context Assembly: Fitting LLM Prompts in Token Budgets](blog/context-assembly.md)
- [Point-in-Time Features: Preventing ML Data Leakage](blog/point-in-time-features.md)
- [pgvector vs Pinecone: When to Self-Host Vector Search](blog/pgvector-vs-pinecone.md)
- [Token Budget Management for Production RAG](blog/token-budget-management.md)
- [Python Decorators for ML Feature Engineering](blog/python-decorators-ml.md)
- [Deploy ML Features Without Kubernetes](blog/deploy-without-kubernetes.md)
- [What Did Your AI Know? Introducing Context Replay](blog/context-replay.md)
- [Building an Audit Trail for AI Decisions](blog/ai-audit-trail.md)
- [Freshness SLAs: When Your AI Needs Fresh Data](blog/freshness-guarantees.md)

---

## Contributing

We love contributions! See [CONTRIBUTING.md](https://github.com/davidahmann/meridian/blob/main/CONTRIBUTING.md) to get started.

<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "SoftwareApplication",
  "name": "Meridian",
  "operatingSystem": "Linux, macOS, Windows",
  "applicationCategory": "DeveloperApplication",
  "description": "Unify RAG pipelines and ML features in a single Python decorator. From notebook to production in 30 seconds.",
  "offers": {
    "@type": "Offer",
    "price": "0",
    "priceCurrency": "USD"
  },
  "url": "https://davidahmann.github.io/meridian/",
  "featureList": [
    "Unified RAG and ML Feature Store",
    "Vector Search with pgvector",
    "Token Budget Management",
    "Point-in-Time Correctness",
    "One-Command Cloud Deploy"
  ]
}
</script>
