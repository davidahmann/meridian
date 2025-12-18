---
title: "Fabra - The Inference Context Ledger"
description: "Prove what your AI knew. Fabra is the Inference Context Ledger — capturing exactly what data an AI used at decision time with full lineage, freshness guarantees, and replay."
keywords: inference context ledger, context record, context store, rag pipeline, llm memory, feature store, python features, mlops, pgvector, vector search, ai traceability, rag lineage, feature store without kubernetes, langchain alternative simple, what did ai know, context replay
---

# Fabra: The Inference Context Ledger

> **Prove what your AI knew.**

Fabra captures exactly what data your AI used at decision time — with full lineage, freshness guarantees, and replay. From notebook to production in 30 seconds.

[Get Started →](quickstart.md) | [Try in Browser →](https://fabraoss.vercel.app)

## At a Glance

| | |
|:---|:---|
| **What** | Inference Context Ledger — we own the write path |
| **Context Record** | Immutable snapshot of AI decision context |
| **Install** | `pip install fabra-ai` |
| **Features** | `@feature` decorator for ML features |
| **RAG** | `@retriever` + `@context` for LLM context assembly |
| **Vector DB** | pgvector (Postgres extension) |
| **Local** | DuckDB + in-memory (zero setup) |
| **Production** | Postgres + Redis (one env var) |
| **Deploy** | `fabra deploy fly\|cloudrun\|ecs\|railway\|render` |

---

## The Problem

You're building an AI app. You need:

- **Structured features** (user tier, purchase history) for personalization
- **Unstructured context** (relevant docs, chat history) for your LLM
- **Vector search** for semantic retrieval
- **Token budgets** to fit your context window

Today, this means stitching together LangChain, Pinecone, a feature store, Redis, and prayer.

**Fabra stores, indexes, and serves the data your AI uses — and tracks exactly what was retrieved for every decision.**

This is "write path ownership": we ingest and manage your context data, not just query it. This enables replay, lineage, and traceability that read-only wrappers cannot provide.

---

## The 30-Second Quickstart

### Fastest Path

```bash
pip install fabra-ai && fabra demo
```

That's it. Server starts, makes a test request, and prints a `context_id` (your receipt). No Docker. No config files. No API keys.

Next:

```bash
fabra context show <context_id>
fabra context verify <context_id>
```

### Build Your Own

```bash
pip install fabra-ai
```

```python
from fabra.core import FeatureStore, entity, feature
from fabra.context import context, ContextItem
from fabra.retrieval import retriever
from datetime import timedelta

store = FeatureStore()

@entity(store)
class User:
    user_id: str

@feature(entity=User, refresh=timedelta(days=1))
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
fabra serve features.py
# Server running on http://localhost:8000

curl localhost:8000/v1/features/user_tier?entity_id=user123
# {"value": "premium", "freshness_ms": 0, "served_from": "online"}
```

**That's it.** No infrastructure. No config files. Just Python.

---

## Why Fabra?

| | Traditional Stack | Fabra |
|:---|:---|:---|
| **Config** | 500 lines of YAML | Python decorators |
| **Infrastructure** | Kubernetes + Spark + Pinecone | Your laptop (DuckDB) |
| **RAG Pipeline** | LangChain spaghetti | `@retriever` + `@context` |
| **Feature Serving** | Separate feature store | Same `@feature` decorator |
| **Time to Production** | Weeks | 30 seconds |

### We Own the Write Path

LangChain and other frameworks are read-only wrappers — they query your data but don't manage it. Fabra is the **system of record** for inference context. Every context assembly becomes a durable **Context Record** with:

- **Cryptographic integrity** (tamper-evident hashes)
- **Full lineage** (what data was used, when, from where)
- **Point-in-time replay** (reproduce any decision exactly)

### Infrastructure, Not a Framework

Fabra is not an orchestration layer. It's the system of record for what your AI knows. Features, retrievers, and context assembly in one infrastructure layer with production reliability.

### Local-First, Production-Ready

```bash
FABRA_ENV=development  # DuckDB + In-Memory (default)
FABRA_ENV=production   # Postgres + Redis + pgvector
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

- **Self-Healing:** `fabra doctor` diagnoses environment issues
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

- **[One-Command Deploy](local-to-production.md):** `fabra deploy fly|cloudrun|ecs|railway|render`
- **[Visual UI](webui.md):** Dependency graphs, live metrics, context debugging
- **[Unit Testing](unit_testing.md):** Test features in isolation

### For Compliance & Debugging

- **[Context Accountability](context-accountability.md):** Full lineage tracking — every AI decision traces back through the data that informed it
- **Context Replay:** Reproduce exactly what your AI knew at any point in time for debugging and compliance
- **Traceability:** UUIDv7-based context IDs with complete data provenance
- **[Freshness SLAs](freshness-sla.md):** Ensure data freshness with configurable thresholds and degraded mode

---

## Use Cases

- **[RAG Chatbot](use-cases/rag-chatbot.md):** Build a production RAG application
- **[Fraud Detection](use-cases/fraud-detection.md):** Real-time feature serving
- **[Churn Prediction](use-cases/churn-prediction.md):** Point-in-time correct training data
- **[Real-Time Recommendations](use-cases/real-time-recommendations.md):** Async feature pipelines

---

## Start Here

| **I'm an ML Engineer** | **I'm an AI Engineer** |
|:---|:---|
| *"I need to serve features without Kubernetes"* | *"I need RAG with traceability"* |
| [Feature Store Without K8s →](feature-store-without-kubernetes.md) | [Context Accountability →](context-accountability.md) |
| [Feast vs Fabra →](feast-alternative.md) | [Context Store →](context-store.md) |
| [Quickstart (ML Track) →](quickstart.md#feature-store-in-30-seconds) | [Quickstart (AI Track) →](quickstart.md#context-store-in-60-seconds) |

**Building in a regulated industry?** [Compliance Guide →](compliance-guide.md)

---

## Documentation

### Getting Started

- [Quickstart](quickstart.md) — Zero to served features in 30 seconds
- [Philosophy](philosophy.md) — Why we built this and who it's for
- [Architecture](architecture.md) — Boring technology, properly applied

### For ML Engineers

- [Feature Store Without Kubernetes](feature-store-without-kubernetes.md) — No K8s, no Docker, just Python
- [Fabra vs Feast](feast-alternative.md) — The lightweight alternative
- [Local to Production](local-to-production.md) — Deploy when you're ready

### For AI Engineers

- [Context Store](context-store.md) — RAG infrastructure with full lineage
- [Context Accountability](context-accountability.md) — Know what your AI knew
- [Compliance Guide](compliance-guide.md) — GDPR, SOC2, and regulated industries

### Guides

- [Comparisons](comparisons.md) — vs Feast, LangChain, Pinecone, Tecton

### Tools

- [WebUI](webui.md) — Visual feature store & context explorer

### Specifications

- [Context Record Spec (CRS-001)](context-record-spec.md) — Technical specification for Context Records

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
- [Traceability for AI Decisions](blog/ai-audit-trail.md)
- [Freshness SLAs: When Your AI Needs Fresh Data](blog/freshness-guarantees.md)
- [Fabra vs Context Engineering Platforms: Choosing the Right Tool](blog/fabra-vs-context-platforms.md)

---

## Quick FAQ

**Q: What is Fabra?**
A: Fabra is context infrastructure for AI applications. It stores, indexes, and serves the data your AI uses — and tracks exactly what was retrieved for every decision. We call this "write path ownership": we manage your context data, not just query it.

**Q: How is Fabra different from LangChain?**
A: LangChain is a framework (orchestration). Fabra is infrastructure (storage + serving). LangChain queries external stores; Fabra owns the write path with freshness tracking, replay, and full lineage. You can use both together.

**Q: How is Fabra different from Feast?**
A: Fabra is a lightweight alternative with Python decorators instead of YAML, plus built-in context/RAG support (vector search, token budgeting, lineage) that Feast doesn't have.

**Q: Do I need Kubernetes or Docker?**
A: No. Fabra runs locally with DuckDB and in-memory cache. For production, set `FABRA_ENV=production` with Postgres and Redis.

**Q: What vector database does Fabra use?**
A: pgvector (Postgres extension). Your vectors live alongside your relational data—no separate vector database required.

---

## Contributing

We love contributions! See [CONTRIBUTING.md](https://github.com/davidahmann/fabra/blob/main/CONTRIBUTING.md) to get started.

<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "SoftwareApplication",
  "name": "Fabra",
  "operatingSystem": "Linux, macOS, Windows",
  "applicationCategory": "DeveloperApplication",
  "description": "Know what your AI knew. Fabra stores, indexes, and serves the data your AI uses — and tracks exactly what was retrieved for every decision.",
  "offers": {
    "@type": "Offer",
    "price": "0",
    "priceCurrency": "USD"
  },
  "url": "https://davidahmann.github.io/fabra/",
  "featureList": [
    "Context Infrastructure with Write Path Ownership",
    "Full Lineage and Traceability",
    "Vector Search with pgvector",
    "Token Budget Management",
    "Point-in-Time Correctness",
    "Context Replay for Compliance",
    "Freshness SLAs"
  ],
  "softwareVersion": "2.0.6",
  "license": "https://opensource.org/licenses/Apache-2.0"
}
</script>
