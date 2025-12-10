<div align="center">
  <h1>Fabra</h1>
  <p><b>Context Infrastructure for AI Applications</b></p>

  <p>
    <a href="https://pypi.org/project/fabra-ai/"><img src="https://img.shields.io/pypi/v/fabra-ai?color=blue&label=pypi" alt="PyPI version" /></a>
    <a href="https://github.com/davidahmann/fabra/blob/main/LICENSE"><img src="https://img.shields.io/github/license/davidahmann/fabra?color=green" alt="License" /></a>
    <img src="https://img.shields.io/badge/python-3.9+-blue.svg" alt="Python Version" />
  </p>

  <p>
    <a href="https://fabraoss.vercel.app"><b>Try in Browser</b></a> ·
    <a href="https://davidahmann.github.io/fabra/docs/quickstart"><b>Quickstart</b></a> ·
    <a href="https://davidahmann.github.io/fabra/docs/"><b>Docs</b></a>
  </p>
</div>

---

**Fabra** is the system of record for what your AI knows. We ingest, index, track freshness, and serve context data — not just query it.

This "write path ownership" enables:
- **Replay any AI decision** — What exactly did the model know?
- **Full lineage tracking** — Which features, documents, and retrievers were used?
- **Freshness guarantees** — Was the data stale when the decision was made?

```bash
pip install "fabra-ai[ui]"
```

---

## Choose Your Path

<table>
<tr>
<td width="50%" valign="top">

### ML Engineers
**"Feast needs Kubernetes. I just need features."**

```python
from fabra import FeatureStore, entity, feature

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
curl localhost:8000/features/purchase_count?user_id=123
```

No Kubernetes. No Spark. No YAML. Just Python.

**[Feature Store Without K8s →](https://davidahmann.github.io/fabra/docs/feature-store-without-kubernetes)** · **[Feast vs Fabra →](https://davidahmann.github.io/fabra/docs/feast-alternative)**

</td>
<td width="50%" valign="top">

### AI Engineers
**"Someone asked what the AI knew. I couldn't tell them."**

```python
from fabra import FeatureStore, context, ContextItem
from fabra.retrieval import retriever

store = FeatureStore()

@retriever(index="docs", top_k=5)
async def search_docs(query: str):
    pass  # Auto-wired to pgvector

@context(store, max_tokens=4000)
async def build_prompt(user_id: str, query: str):
    docs = await search_docs(query)
    return [ContextItem(content=str(docs), priority=0)]

ctx = await build_prompt("user_123", "query")
print(ctx.id)       # Replay this exact context anytime
print(ctx.lineage)  # What data was used?
```

**[Context Traceability →](https://davidahmann.github.io/fabra/docs/rag-audit-trail)** · **[Compliance Guide →](https://davidahmann.github.io/fabra/docs/compliance-guide)**

</td>
</tr>
</table>

---

## Why Engineers Choose Fabra

### 1. We Own the Write Path

LangChain, Pinecone, and other tools are **read-only wrappers** — they query your data but don't manage it. When compliance asks "what did the AI know?", they have no answer.

Fabra ingests, indexes, and serves context data. Every decision traces back through the data that informed it.

```python
# Replay any historical context
ctx = await store.get_context_at("01912345-6789-7abc-def0-123456789abc")
print(ctx.content)   # Exact prompt from that moment
print(ctx.lineage)   # Complete data provenance
```

### 2. Local-First, Production-Ready

Same code runs everywhere. DuckDB locally, Postgres + Redis in production.

```bash
# Development (zero setup)
fabra serve features.py

# Production (just add env vars)
FABRA_ENV=production \
FABRA_POSTGRES_URL=postgresql+asyncpg://... \
FABRA_REDIS_URL=redis://... \
fabra serve features.py
```

No Docker for local dev. No Kubernetes for production. Deploy to Fly.io, Railway, Cloud Run, or any container platform with one command.

### 3. Point-in-Time Correctness

Training ML models? We use `ASOF JOIN` (DuckDB) and `LATERAL JOIN` (Postgres) to ensure your training data reflects the world exactly as it was — no data leakage, ever.

### 4. Token Budget Management

No more "context too long" errors. Priority-based truncation keeps your prompts under budget.

```python
@context(store, max_tokens=4000)
async def build_prompt(user_id: str, query: str):
    return [
        ContextItem(content=system_prompt, priority=0, required=True),
        ContextItem(content=docs, priority=1),
        ContextItem(content=history, priority=2),  # Dropped first if over budget
    ]
```

---

## Key Capabilities

### For ML Engineers

| Capability | Description |
|:-----------|:------------|
| **Python Decorators** | `@feature` instead of 500 lines of YAML |
| **DuckDB + Postgres** | Local dev with embedded DB, production with Postgres |
| **Point-in-Time Joins** | ASOF/LATERAL joins for training data correctness |
| **Hybrid Features** | Mix Python logic and SQL in the same pipeline |
| **One-Command Deploy** | `fabra deploy fly\|cloudrun\|railway\|render` |

### For AI Engineers

| Capability | Description |
|:-----------|:------------|
| **Context Accountability** | UUIDv7 IDs, full lineage, replay any decision |
| **Vector Search** | Built-in pgvector with automatic chunking |
| **Token Budgets** | `max_tokens` with priority-based truncation |
| **Freshness SLAs** | Fail-safe when data is stale |
| **Export** | `fabra context export` for debugging and compliance |

### Production Features

- **Observability:** Prometheus metrics, OpenTelemetry tracing
- **Reliability:** Circuit breakers, fallback chains, `fabra doctor`
- **Security:** Self-hosted, your data never leaves your infrastructure

---

## Architecture

```
Development                         Production
┌─────────────────────┐            ┌─────────────────────────┐
│  Your Python Code   │            │   Your Python Code      │
│  (@feature, @context)│            │   (@feature, @context)  │
└──────────┬──────────┘            └───────────┬─────────────┘
           │                                   │
           ▼                                   ▼
┌─────────────────────┐            ┌─────────────────────────┐
│  DuckDB (embedded)  │            │  Postgres + pgvector    │
│  In-Memory Cache    │            │  Redis                  │
└─────────────────────┘            └─────────────────────────┘

Same code. Same decorators. Different backends.
FABRA_ENV=development → FABRA_ENV=production
```

---

## Comparison

### vs Feast (Feature Store)

| | Feast | Fabra |
|:---|:---|:---|
| Setup | Kubernetes + Spark | `pip install` |
| Configuration | YAML | Python decorators |
| Time to production | Weeks | 30 seconds |
| RAG support | None | Built-in Context Store |
| Traceability | None | Full lineage |

**Use Feast when:** You have a platform team and existing K8s/Spark infrastructure.

### vs LangChain (RAG)

| | LangChain | Fabra |
|:---|:---|:---|
| Type | Framework (orchestration) | Infrastructure (storage + serving) |
| Traceability | None | Full lineage + replay |
| Token budgets | DIY | Built-in |
| Data ownership | Read-only wrapper | Write path owner |

**Use LangChain when:** You need agent orchestration and don't need compliance.

---

## Get Started

```bash
pip install "fabra-ai[ui]"

# ML Engineers: Serve features
fabra serve features.py

# AI Engineers: Index documents and serve context
fabra serve chatbot.py
```

<p align="center">
  <a href="https://fabraoss.vercel.app"><b>Try in Browser</b></a> ·
  <a href="https://davidahmann.github.io/fabra/docs/quickstart"><b>Quickstart Guide</b></a> ·
  <a href="https://davidahmann.github.io/fabra/docs/"><b>Full Documentation</b></a>
</p>

---

## Roadmap

- [x] **v1.0:** Core Feature Store (DuckDB, Postgres, Redis)
- [x] **v1.2:** Context Store (pgvector, retrievers, token budgets)
- [x] **v1.3:** UI, Magic Retrievers, One-Command Deploy
- [x] **v1.4:** Context Accountability (lineage, replay, traceability)
- [x] **v1.5:** Freshness SLAs (data freshness guarantees)
- [ ] **v1.6:** Drift detection, RBAC, multi-region

---

## Contributing

We welcome contributions! See [CONTRIBUTING.md](CONTRIBUTING.md) to get started.

<div align="center">
  <p><b>Fabra</b> · Apache 2.0 · 2025</p>
</div>
