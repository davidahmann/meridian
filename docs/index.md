---
title: "Meridian - The Context Store for LLMs & ML Features | RAG + Feature Store"
description: "Define RAG pipelines and ML features in Python. Meridian is a local-first Context Store for LLM applications and Feature Store for ML engineers. No YAML, no infrastructure tax."
keywords: context store, rag pipeline, llm memory, feature store, python features, mlops, pgvector, vector search
---

# Meridian: The Context Store for LLMs & ML Features

> **"Define RAG pipelines in Python. Get production retrieval and vector search for free."**

Meridian is a developer-first **Context Store + Feature Store** designed to take you from a "Notebook Prototype" to "Production RAG" in 30 seconds. It eliminates the infrastructure tax of existing tools—no Kubernetes, no Spark, no YAML. Just pure Python and SQL.

**Core Capabilities:**
1. **Context Store (v1.2.0):** Full RAG infrastructure with vector search (pgvector), token budgets, and intelligent context assembly.
2. **Feature Store:** Traditional ML feature serving with point-in-time correctness.

---

## ⚡ The 30-Second Quickstart

**1. Install**
```bash
pip install "meridian-oss[ui]"
```

**2. Define Features & Context (`features.py`)**
```python
from meridian.core import FeatureStore, entity, feature
from meridian.context import context, ContextItem
from meridian.retrieval import retriever
import random

store = FeatureStore()

@entity(store)
class User:
    user_id: str

# 1. THE FEATURE STORE (Structured Data)
@feature(entity=User, refresh="daily", materialize=True)
def user_tier(user_id: str) -> str:
    # Imagine a DB lookup here; we'll simulate it for speed.
    return "premium" if hash(user_id) % 2 == 0 else "free"

# 2. THE CONTEXT STORE (Unstructured Data)
@retriever(index="docs", top_k=3)
async def find_docs(query: str):
    # Magic wiring: automatically searches "docs" index via pgvector
    # Here we simulate a semantic search result for local dev.
    return [{"content": "Meridian bridges the gap between ML features and RAG.", "score": 0.9}]

# 3. THE UNIFICATION (Context Assembly)
@context(store)
async def build_prompt(user_id: str, query: str):
    # Fetch feature and docs in parallel
    tier = await store.get_feature("user_tier", user_id)
    docs = await find_docs(query)

    return [
        ContextItem(content=f"User is {tier}. Adjust tone accordingly.", priority=0),
        ContextItem(content=str(docs), priority=1)
    ]
```

**3. Serve (Optional)**
```bash
meridian serve features.py
# 🚀 Server running on http://localhost:8000
```

[Get Started Now →](quickstart.md) | [Try in Browser →](https://meridianoss.vercel.app)

---

## 🚀 Why Meridian?

### 1. Local-First, Cloud-Ready
Most feature stores require a platform team to set up. Meridian runs on your laptop with zero dependencies (DuckDB + In-Memory) and scales to production with boring technology (Postgres + Redis).

### 2. No Magic, Just Python
We don't use YAML for configuration. Your code is your config.
- **Explicit Caching:** Use `@feature(materialize=True)` to cache hot features.
- **Explicit Refresh:** Use `@feature(refresh="5m")` to define freshness.

### 3. Instant Wow ✨
- **Meridian UI:** A built-in Streamlit dashboard with **Visual Dependency Graphs**.
- **Rich Terminal:** Production-grade TUI with live metrics.
- **Jupyter Integration:** Beautiful HTML representations of your feature store objects.

### 4. Production-Grade Reliability 🛡️
- **Self-Healing:** Run `meridian doctor` to diagnose environment issues.
- **Fallback Chain:** Cache -> Compute -> Default. If Redis fails, we compute on-demand.
- **Circuit Breakers:** Built-in protection against cascading failures (fail fast).
- **Deep Observability:** Prometheus metrics (`meridian_feature_requests_total`) and structured JSON logging out of the box.
- **Async Core:** Fully async I/O for high-throughput serving.

### 5. Hybrid Features (New in v1.1.0) 🏭
- **Python Features:** Use `@feature` with Python logic for complex math (e.g., Haversine distance).
- **SQL Features:** Use `@feature(sql="...")` to delegate heavy joins to your warehouse (DuckDB/Postgres).
- **Materialization:** Automatically run SQL queries and bulk-load results into Redis.

### 6. Point-in-Time Correctness (New in v1.1.0) 🕰️
- **No Data Leakage:** We use `ASOF JOIN` (DuckDB) and `LATERAL JOIN` (Postgres) to ensure training data reflects the world *exactly* as it was at the event time.
- **Consistent:** Same logic for offline training and online serving.

### 7. Write Once, Run Anywhere (New in v1.1.0) 🛠️
- **Dev:** `MERIDIAN_ENV=development` (default) uses DuckDB + In-Memory.
- **Prod:** `MERIDIAN_ENV=production` uses Async Postgres + Redis.
- **Zero Code Changes:** Your feature definitions stay exactly the same.

### 8. Context Store for LLMs (New in v1.2.0) 🤖
Meridian isn't just for ML features. It's now a full **Context Infrastructure** for LLM applications.

- **Vector Search:** Built-in pgvector integration with automatic chunking and embedding (OpenAI, Cohere).
- **Retrievers:** Use `@retriever` to define semantic search functions with caching and DAG wiring.
- **Context Assembly:** Use `@context` to compose multiple retrievers with token budgets and priority-based truncation.
- **Event-Driven Updates:** Push fresh context instantly via Redis Streams with `trigger="event_name"`.
- **Explainability:** Debug context assembly with `/context/{id}/explain` API endpoint.

```python
from meridian.core import FeatureStore
from meridian.retrieval import retriever
from meridian.context import context

store = FeatureStore()

@retriever(index="docs", top_k=3)
async def relevant_docs(query: str) -> list[str]:
    # Automatic vector search via pgvector
    pass

@context(store, max_tokens=4000)
async def chat_context(user_id: str, query: str) -> list[ContextItem]:
    docs = await relevant_docs(query)
    user_prefs = await user_preferences(user_id)  # Feature from store
    return [
        ContextItem(content=str(docs), priority=1, required=True),
        ContextItem(content=str(user_prefs), priority=2),
    ]
```

[Learn More About Context Store →](context-store.md)

---

## 📚 Documentation

- **[Quickstart](quickstart.md):** Go from zero to served features in 30 seconds.
- **[Philosophy & Trade-offs](philosophy.md):** Why we built this and who it's for.
- **[Meridian vs Feast](feast-alternative.md):** The lightweight alternative for ML engineers.
- **[Local to Production](local-to-production.md):** How to migrate when you're ready.
- **[Architecture](architecture.md):** Boring technology, properly applied.

### Feature Store
- **[Use Cases](use-cases/fraud-detection.md):**
    - [Fraud Detection](use-cases/fraud-detection.md)
    - [Churn Prediction (PIT)](use-cases/churn-prediction.md)
    - [Real-Time Recommendations (Async)](use-cases/real-time-recommendations.md)
- **[Hybrid Features](hybrid-features.md):** Mixing Python logic and SQL power.

### Context Store (New in v1.2.0)
- **[Context Store Overview](context-store.md):** Vector search and RAG infrastructure.
- **[Retrievers](retrievers.md):** Define semantic search with `@retriever`.
- **[Context Assembly](context-assembly.md):** Token budgets and priority-based composition.
- **[Event-Driven Features](event-driven-features.md):** Real-time updates via Redis Streams.
- **[Use Case: RAG Chatbot](use-cases/rag-chatbot.md):** Build a production RAG application.

### Reference
- **[Glossary](glossary.md):** Definitions of key terms (Context Store, Feature, Entity).
- **[FAQ](faq.md):** Common questions about production, scaling, and comparisons.
- **[Troubleshooting](troubleshooting.md):** Common issues and fixes.
- **[Why We Built Meridian](why-we-built-meridian.md):** The story behind the "Heroku for ML Features".

---

## 🤝 Contributing

We love contributions! Please read our [CONTRIBUTING.md](https://github.com/davidahmann/meridian/blob/main/CONTRIBUTING.md) to get started.

<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "SoftwareApplication",
  "name": "Meridian",
  "operatingSystem": "Linux, macOS, Windows",
  "applicationCategory": "DeveloperApplication",
  "description": "Heroku for ML Features & Context. Define features in Python. Get training data, production serving, and LLM context assembly for free.",
  "offers": {
    "@type": "Offer",
    "price": "0",
    "priceCurrency": "USD"
  },
  "url": "https://davidahmann.github.io/meridian/",
  "featureList": [
    "Feature Store with Point-in-Time Correctness",
    "Context Store for LLM/RAG Applications",
    "Vector Search with pgvector",
    "Token Budget Management",
    "Event-Driven Updates via Redis Streams"
  ]
}
</script>
