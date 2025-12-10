---
title: "How to Build Context Infrastructure in 30 Seconds | Fabra Quickstart"
description: "Step-by-step guide to installing Fabra context infrastructure for AI applications. Own the write path with lineage and replay. No Docker or Kubernetes required."
keywords: fabra quickstart, context infrastructure, ai audit trail, python feature store, local feature store, rag quickstart, write path ownership, feature store 30 seconds, rag quickstart python, no docker feature store, feature store without kubernetes, simple ml features
---

# Quickstart: 30 Seconds to Production-Ready AI Infrastructure

> **TL;DR:** Install with `pip install "fabra-ai[ui]"`. Define features or context with Python decorators. Run `fabra serve`. Full lineage and replay included.

## Choose Your Track

<table>
<tr>
<td width="50%" valign="top">

### 🔧 ML Engineer Track
**"I need to serve features without Kubernetes"**

You're building ML models and need:
- Real-time feature serving
- Point-in-time correctness for training
- No infrastructure complexity

**Start here:** [Feature Store Quickstart](#feature-store-in-30-seconds)

</td>
<td width="50%" valign="top">

### 🤖 AI Engineer Track
**"I need RAG with audit trails"**

You're building LLM apps and need:
- Vector search and retrieval
- Token budget management
- Context replay for debugging/compliance

**Start here:** [Context Store Quickstart](#context-store-in-60-seconds)

</td>
</tr>
</table>

---

## Feature Store in 30 Seconds

> **For ML Engineers** — Serve features without Kubernetes, Spark, or YAML.

```bash
pip install "fabra-ai[ui]"
```

```python
# features.py
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
```

**Done.** No Docker. No Kubernetes. No YAML.

**What you get:**
- DuckDB offline store (embedded, no setup)
- In-memory online store (instant reads)
- Point-in-time correctness for training data
- Same code works in production with Postgres + Redis

[Feature Store Deep Dive →](feature-store-without-kubernetes.md) | [Compare vs Feast →](feast-alternative.md)

---

## Context Store in 60 Seconds

> **For AI Engineers** — Build RAG with audit trails and compliance.

> [!IMPORTANT]
> **Prerequisites:** To use Vector Search, you need an API Key (OpenAI, Anthropic, or Cohere).

```bash
pip install "fabra-ai[ui]"
```

```python
# chatbot.py
from fabra.core import FeatureStore
from fabra.retrieval import retriever
from fabra.context import context, ContextItem

store = FeatureStore()

# Index documents
await store.index("docs", "doc_1", "Fabra is context infrastructure...")

# Define retriever (auto-wired to pgvector)
@retriever(index="docs", top_k=3)
async def search_docs(query: str) -> list[str]:
    pass  # Magic wiring

# Assemble context with token budget
@context(store, max_tokens=4000)
async def chat_context(user_id: str, query: str) -> list[ContextItem]:
    docs = await search_docs(query)
    tier = await store.get_feature("user_tier", user_id)
    return [
        ContextItem(content="You are helpful.", priority=0, required=True),
        ContextItem(content=f"User tier: {tier}", priority=1),
        ContextItem(content=str(docs), priority=2),
    ]

# Every call is tracked
ctx = await chat_context("user123", "how do I reset my password?")
print(f"Context ID: {ctx.id}")      # UUIDv7 for audit trail
print(f"Lineage: {ctx.lineage}")    # Full data provenance
```

```bash
fabra serve chatbot.py
```

**What you get:**
- Vector search with pgvector
- Automatic token budgeting
- Full lineage tracking (what data was used)
- Context replay (reproduce any historical context)

[Context Store Deep Dive →](context-store.md) | [RAG Audit Trail →](rag-audit-trail.md)

---

## Production Stack Locally

Want Postgres + Redis locally?

```bash
fabra setup
# Generates docker-compose.yml with pgvector and Redis

docker-compose up -d
```

Then:

```bash
FABRA_ENV=production fabra serve features.py
```

## FAQ

**Q: How do I run a feature store locally without Docker?**
A: Fabra uses DuckDB (embedded) and in-memory cache for local dev. Install with `pip install "fabra-ai[ui]"`, define features in Python, run `fabra serve`. Zero infrastructure required.

**Q: What's the simplest context infrastructure for small ML teams?**
A: Fabra targets "Tier 2" companies (Series B-D, 10-500 engineers) who need real-time ML and LLM features but can't afford Kubernetes ops. We own the write path — ingest, index, track freshness, and serve — giving you lineage and replay that read-only frameworks can't provide.

**Q: How do I migrate from Feast to something simpler?**
A: Fabra eliminates YAML configuration. Define features in Python with `@feature` decorator, same data access patterns but no infrastructure tax.

## Next Steps

- [Compare vs Feast](feast-alternative.md)
- [Deploy to Production](local-to-production.md)
- [Context Store](context-store.md) - RAG infrastructure for LLMs
- [RAG Chatbot Tutorial](use-cases/rag-chatbot.md) - Full example

<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "HowTo",
  "name": "How to Build a Feature Store & Context Store in 30 Seconds",
  "description": "Install Fabra and serve ML features and LLM context from Python in under 30 seconds.",
  "totalTime": "PT30S",
  "tool": [{
    "@type": "HowToTool",
    "name": "Fabra"
  }],
  "step": [{
    "@type": "HowToStep",
    "name": "Install Fabra",
    "text": "Run pip install \"fabra-ai[ui]\" to install the library."
  }, {
    "@type": "HowToStep",
    "name": "Define Features",
    "text": "Create a python file with @feature decorators to define your feature logic."
  }, {
    "@type": "HowToStep",
    "name": "Define Context (Optional)",
    "text": "Use @retriever and @context decorators for RAG applications."
  }, {
    "@type": "HowToStep",
    "name": "Serve",
    "text": "Run fabra serve examples/basic_features.py to start the API."
  }]
}
</script>
