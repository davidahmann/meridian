---
title: "How to Build Context Infrastructure in 30 Seconds | Fabra Quickstart"
description: "Step-by-step guide to installing Fabra context infrastructure for AI applications. Own the write path with lineage and replay. No Docker or Kubernetes required."
keywords: fabra quickstart, context infrastructure, ai audit trail, python feature store, local feature store, rag quickstart, write path ownership, feature store 30 seconds, rag quickstart python, no docker feature store, feature store without kubernetes, simple ml features
faq:
  - q: "Where are Context Records stored by default?"
    a: "In development, Fabra persists CRS-001 Context Records to DuckDB at ~/.fabra/fabra.duckdb. Override with FABRA_DUCKDB_PATH."
  - q: "What is the format of a Fabra context_id?"
    a: "A context_id is a CRS-001 identifier like ctx_<UUIDv7>. Some commands also accept the UUID without the ctx_ prefix."
  - q: "Does fabra demo require API keys or Docker?"
    a: "No. fabra demo runs locally, makes a test request, and prints a working context_id without API keys or Docker."
  - q: "How do I diff two receipts without a running server?"
    a: "Use fabra context diff <A> <B> --local to diff CRS-001 receipts directly from DuckDB (no server required)."
  - q: "What happens if evidence persistence fails in production?"
    a: "In FABRA_ENV=production, Fabra defaults to FABRA_EVIDENCE_MODE=required: the request fails if CRS-001 persistence fails (no context_id returned)."
  - q: "How do I avoid storing raw prompt/context text?"
    a: "Set FABRA_RECORD_INCLUDE_CONTENT=0 to persist an empty content string while keeping lineage and integrity hashes for the remaining fields."
---

# Quickstart: 30 Seconds to Production-Ready AI Infrastructure

> **TL;DR:** Install with `pip install fabra-ai`. Define features or context with Python decorators. Run `fabra serve`. Full lineage and replay included.

## Choose Your Track

<table>
<tr>
<td width="50%" valign="top">

### 🔧 ML Engineer Track
**"I need to serve features without Kubernetes"**

You're building ML models and need:
- Real-time feature serving
- Point-in-time correctness for training
- **Context Records** that prove what data your model saw

**Start here:** [Feature Store Quickstart](#feature-store-in-30-seconds)

</td>
<td width="50%" valign="top">

### 🤖 AI Engineer Track
**"I need to prove what my AI knew"**

You're building LLM apps and need:
- Vector search and retrieval
- Token budget management
- **Immutable Context Records** for compliance and debugging

**Start here:** [Context Store Quickstart](#context-store-in-60-seconds)

</td>
</tr>
</table>

---

## Feature Store in 30 Seconds

> **For ML Engineers** — Serve features without Kubernetes, Spark, or YAML.

### Fastest Path: `fabra demo`

```bash
pip install fabra-ai && fabra demo --mode features
```

That's it. Server starts, makes a test request, shows you the result. No Docker. No config files. No API keys.

### Build Your Own Features

```bash
pip install fabra-ai
```

```python
# features.py
from fabra.core import FeatureStore, entity, feature
from datetime import timedelta

store = FeatureStore()

@entity(store)
class User:
    user_id: str

@feature(entity=User, refresh=timedelta(hours=1))
def purchase_count(user_id: str) -> int:
    return db.query("SELECT COUNT(*) FROM purchases WHERE user_id = ?", user_id)

@feature(entity=User, refresh=timedelta(days=1))
def user_tier(user_id: str) -> str:
    return "premium" if is_premium(user_id) else "free"
```

```bash
fabra serve features.py
# Server running on http://localhost:8000

curl localhost:8000/v1/features/purchase_count?entity_id=user123
# {"value": 47, "freshness_ms": 0, "served_from": "online"}
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

### Fastest Path (no API keys): `fabra demo`

```bash
pip install fabra-ai && fabra demo
```

This prints a `context_id` (your receipt) and the next commands to prove value:
`show`, `diff`, and `verify`.

### Build Your Own Context Assembly

```bash
pip install fabra-ai
```

```python
# chatbot.py (no API keys required)
from datetime import timedelta

from fabra.core import FeatureStore, entity, feature
from fabra.retrieval import retriever
from fabra.context import context, ContextItem

store = FeatureStore()

@entity(store)
class User:
    user_id: str

@feature(entity=User, refresh=timedelta(hours=1))
def user_tier(user_id: str) -> str:
    return "premium" if hash(user_id) % 2 == 0 else "free"

@retriever(name="knowledge_base", cache_ttl=timedelta(minutes=5))
async def search_docs(query: str, top_k: int = 3) -> list[str]:
    return [
        "Fabra creates verifiable Context Records.",
        "Use @context for prompt assembly with token budgets.",
        "Use @retriever for retrieval without YAML.",
    ][:top_k]

# Assemble context with token budget
@context(store, max_tokens=4000)
async def chat_context(user_id: str, query: str) -> list[ContextItem]:
    tier = await store.get_feature("user_tier", user_id)
    docs = await search_docs(query)
    return [
        ContextItem(content="You are helpful.", priority=0, required=True),
        ContextItem(content=f"User tier: {tier}", priority=1, required=True),
        ContextItem(content="Docs:\n" + "\n".join(docs), priority=2),
    ]
```

```bash
fabra serve chatbot.py
```

**What you get:**
- Vector search with pgvector
- Automatic token budgeting
- **Immutable Context Records** with cryptographic integrity
- Full lineage tracking (what data was used)
- Context replay and verification (`fabra context verify`)

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
A: Fabra uses DuckDB (embedded) and in-memory cache for local dev. Install with `pip install fabra-ai`, define features in Python, run `fabra serve`. Zero infrastructure required.

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
    "text": "Run pip install fabra-ai to install the library."
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
