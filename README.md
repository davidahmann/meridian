<div align="center">
  <h1>Fabra</h1>
  <p><strong>Stop spending hours debugging AI decisions you can't reproduce.</strong></p>
  <p>Fabra makes AI context durable. Every request becomes a replayable Context Record.<br/>Record → replay → diff. Turn “the AI was wrong” into a fixable ticket.</p>

  <p>
    <a href="https://pypi.org/project/fabra-ai/"><img src="https://img.shields.io/pypi/v/fabra-ai?color=blue&label=pypi" alt="PyPI version" /></a>
    <a href="https://github.com/davidahmann/fabra/blob/main/LICENSE"><img src="https://img.shields.io/github/license/davidahmann/fabra?color=green" alt="License" /></a>
    <img src="https://img.shields.io/badge/python-3.9+-blue.svg" alt="Python Version" />
  </p>
</div>

---

## The Problem

**Incident risk:** Your AI shipped a bad answer and you can't explain why.

**Credibility risk:** Support escalations are vibes and screenshots — not fixable tickets.

**Velocity risk:** You're scared to ship because you can't debug regressions.

Every AI team hits this wall: **you can't fix what you can't reproduce.**

---

## 30 Seconds to Proof

```bash
pip install fabra-ai && fabra demo
```

That's it. Server starts, makes a test request, prints a `context_id` (your receipt). No Docker. No config files. No API keys.

By default, Context Records are stored durably in DuckDB at `~/.fabra/fabra.duckdb` (override with `FABRA_DUCKDB_PATH`).

### Requirements

- Python `>= 3.9`
- `pip` (or `uv`, optional)
- `curl` (used in quickstart verification commands)
- Optional:
  - Node.js (only for `fabra ui`)
  - Docker (only for Docker-based examples / local production stack)

Need help or want to see everything Fabra can do?

```bash
fabra --help
fabra context --help
fabra doctor
```

Already using LangChain or calling OpenAI directly? Add receipts without a rewrite:

- `docs/exporters-and-adapters.md` (LangChain-style callbacks, OpenAI wrapper, logs/OTEL)

<details>
<summary><strong>What you'll see</strong></summary>

```
  Fabra Demo Server

  Context Store working!
  Context ID: ctx_...

  Receipt (paste into a ticket):
    ctx_...

  Next (proves the value):
    fabra context show ctx_...
    fabra context verify ctx_...

  Press Ctrl+C to stop, or visit http://localhost:8000/docs
```

</details>

---

## The Solution: Context Records

Fabra creates a **Context Record** for every AI decision — an immutable snapshot that turns "the AI was wrong" into a fixable ticket.

```python
ctx = await build_prompt("user_123", "how do I get a refund?")

print(ctx.id)       # ctx_018f3a2b-... (your receipt)
print(ctx.lineage)  # Exactly what data was used
```

That `ctx.id` is permanent. Days later, you can:

```bash
# See exactly what the AI knew
fabra context show ctx_018f3a2b-...

# Verify the record hasn't been tampered with
fabra context verify ctx_018f3a2b-...

# Compare two decisions side-by-side
fabra context diff ctx_a ctx_b
```

**This is the difference between "we think it worked" and "here's the proof."**

---

## Two Entry Points, One Infrastructure

<table>
<tr>
<td width="50%" valign="top">

### For ML Engineers

**"I need features in production, not a platform team."**

```python
from fabra import FeatureStore, entity, feature
from datetime import timedelta

store = FeatureStore()

@entity(store)
class User:
    user_id: str

@feature(entity=User, refresh=timedelta(hours=1))
def purchase_count(user_id: str) -> int:
    return db.query(
        "SELECT COUNT(*) FROM purchases WHERE user_id = ?",
        user_id
    )
```

```bash
fabra serve features.py
curl localhost:8000/features/purchase_count?entity_id=u123
# {"value": 47, "freshness_ms": 0, "served_from": "online"}
```

**Python decorators. Not YAML.**

</td>
<td width="50%" valign="top">

### For AI Engineers

**"Compliance asked what the AI knew. I need an answer."**

```python
from fabra import FeatureStore
from fabra.context import context, ContextItem

store = FeatureStore()

@context(store, max_tokens=4000, freshness_sla="5m")
async def build_prompt(user_id: str, query: str):
    tier = await store.get_feature("user_tier", user_id)
    docs = await search_docs(query)
    return [
        ContextItem(content=f"User tier: {tier}", priority=1),
        ContextItem(content=docs, priority=2),
    ]

ctx = await build_prompt("user_123", "question")
print(ctx.id)       # ctx_018f3a2b-... (stable Context Record ID)
print(ctx.lineage)  # exact data used, full provenance
```

**Full audit trail. Not a black box.**

</td>
</tr>
</table>

---

## Why It Works

### 1. You Own Your Data

LangChain queries your vector DB. Fabra *is* your vector DB. We ingest, index, track freshness, and serve. When someone asks "what did the AI know?", we have the answer because we never lost sight of the data.

```bash
# Replay any historical context
fabra context show ctx_018f3a2b-7def-7abc-8901-234567890abc

# Compare what changed between two decisions
fabra context diff ctx_abc123 ctx_def456
```

### 2. Same Code Everywhere

Development uses DuckDB (zero setup). Production uses Postgres + Redis (just add env vars). Your feature definitions don't change.

```bash
# Development (right now, on your laptop)
fabra serve features.py

# Production (same code, different backends)
FABRA_ENV=production \
FABRA_POSTGRES_URL=postgresql://... \
FABRA_REDIS_URL=redis://... \
fabra serve features.py
```

### 3. Point-in-Time Correctness

Training ML models? We use `ASOF JOIN` to ensure your training data reflects exactly what the model would have seen at prediction time. No data leakage. No training-serving skew.

### 4. Token Budgets That Work

No more prompt length errors in production. Set a budget, assign priorities, and low-priority items get dropped automatically.

```python
@context(store, max_tokens=4000)
async def build_prompt(user_id: str, query: str):
    return [
        ContextItem(content=system_prompt, priority=0, required=True),
        ContextItem(content=user_history, priority=1),  # dropped first if over budget
        ContextItem(content=docs, priority=2),
    ]
```

---

## What's Real

This isn't a framework that wraps other tools. This is infrastructure:

| Capability | What It Does |
|:-----------|:-------------|
| **Feature Store** | `@feature` decorators, online/offline stores, point-in-time joins |
| **Context Store** | `@context` decorators, token budgeting, lineage tracking |
| **Vector Search** | Built-in pgvector, automatic chunking, freshness tracking |
| **Context Replay** | `fabra context show <id>` returns exact historical state |
| **Context Diff** | `fabra context diff <id1> <id2>` shows what changed |
| **Freshness SLAs** | `freshness_sla="5m"` fails if data is stale |
| **Diagnostics** | `fabra doctor` validates your setup |

### CLI

```bash
fabra serve features.py      # Start the server
fabra demo                   # Interactive demo (no setup)
fabra doctor                 # Diagnose configuration issues
fabra context show <id>      # Replay historical context
fabra context diff <a> <b>   # Compare two contexts
fabra context list           # List recent contexts
fabra context export <id>    # Export for audit
fabra deploy fly|railway     # Generate deployment config
fabra ui features.py         # Launch the dashboard (requires Node.js)
```

> **Note:** `fabra ui` requires Node.js. Run `npm install` in `src/fabra/ui-next/` if dependencies aren't installed.

---

## How Fabra Fits in Your Stack

Fabra is **not** a replacement for:

| Tool | Purpose | Relationship to Fabra |
|:-----|:--------|:---------------------|
| **Airflow / Dagster** | Batch workflow orchestration | Use for pipelines that *feed* Fabra |
| **MLflow / W&B** | Model training & experiment tracking | Use for training; Fabra handles inference-time context |
| **LangChain / LlamaIndex** | LLM orchestration & chains | Use for orchestration; Fabra provides the data layer |

Fabra **replaces or complements**:

| Tool | Fabra Advantage |
|:-----|:----------------|
| **Feast** | Simpler setup, built-in context assembly |
| **Custom feature serving** | Production-ready out of the box |
| **Ad-hoc RAG pipelines** | Lineage, freshness SLAs, token budgets |

> **See [full comparison guide](docs/comparisons.md)** for detailed breakdowns vs Feast, Tecton, LangChain, and Pinecone.

---

## Honest Comparison

### vs Feast

| | Feast | Fabra |
|:---|:---|:---|
| Can you prove what happened? | Partial (features only) | Full Context Record |
| Can you replay a decision? | No | Yes, built-in |
| Setup time | Days/Weeks | 30 seconds |
| Infrastructure | Kubernetes | None required |

**Choose Feast if:** You have a platform team and existing K8s infrastructure.

### vs LangChain

| | LangChain | Fabra |
|:---|:---|:---|
| Can you prove what happened? | No | Full Context Record |
| Can you explain why it missed something? | No | Yes, dropped items logged |
| Can you replay a decision? | Manual | Built-in |
| Data ownership | Queries external stores | Owns the write path |

**Choose LangChain if:** You need agent chains and don't need compliance.

> **Note:** You can use Fabra + LangChain together — Fabra for storage/serving, LangChain for orchestration.

---

## Production Checklist

- [x] **Observability:** Prometheus metrics at `/metrics`, structured logging
- [x] **Reliability:** Circuit breakers, fallback chains, health checks
- [x] **Security:** Self-hosted, your data stays in your infrastructure
- [x] **Deployment:** One-command deploy to Fly.io, Railway, Cloud Run, Render

---

## Quick Start (Detailed)

### Feature Store

```bash
pip install fabra-ai
fabra serve examples/demo_features.py
```

Test it:
```bash
curl localhost:8000/features/user_engagement?entity_id=user_123
```

Response:
```json
{"value": 87.5, "freshness_ms": 0, "served_from": "online"}
```

### Context Store

```bash
pip install fabra-ai
fabra serve examples/demo_context.py
```

Test it:
```bash
curl -X POST localhost:8000/v1/context/chat_context \
  -H "Content-Type: application/json" \
  -d '{"user_id":"user_123","query":"how do features work?"}'
```

Response:
```json
{
  "id": "ctx_018f3a2b-...",
  "content": "You are a helpful AI assistant...",
  "meta": {
    "freshness_status": "guaranteed",
    "token_usage": 150
  },
  "lineage": {
    "features_used": ["user_tier", "user_engagement_score"],
    "retrievers_used": ["demo_docs"]
  }
}
```

Replay it later:
```bash
fabra context show ctx_018f3a2b-...
```

---

## What Fabra Does Not Do

- **Agent orchestration** - Use LangChain
- **Workflow scheduling** - Use Airflow/Dagster
- **High-QPS streaming inference** - Use Tecton
- **No-code builders** - This is Python infrastructure

Fabra focuses on one thing: **turning "the AI was wrong" into a fixable ticket.**

---

<p align="center">
  <a href="https://fabraoss.vercel.app"><strong>Try in Browser</strong></a> ·
  <a href="https://davidahmann.github.io/fabra/docs/quickstart"><strong>Quickstart</strong></a> ·
  <a href="https://davidahmann.github.io/fabra/docs/"><strong>Docs</strong></a>
</p>

---

<div align="center">
  <p><strong>Fabra</strong> · Apache 2.0 · 2025</p>
  <p><em>Stop bleeding time and credibility when AI misbehaves.</em></p>
</div>
