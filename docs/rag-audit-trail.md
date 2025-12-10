---
title: "RAG Audit Trail: Know What Your AI Knew | Fabra"
description: "Build RAG applications with full audit trails. Track exactly what documents and data your LLM used for every decision. Context replay for compliance and debugging."
keywords: rag audit trail, llm audit trail, ai decision audit, what did ai know, context replay, rag compliance, llm debugging, ai explainability, rag lineage, context lineage, gdpr ai, soc2 ai
---

# RAG Audit Trail: Know What Your AI Knew

> **TL;DR:** Fabra tracks exactly what data your LLM used for every decision. Full lineage, context replay, and compliance-ready audit trails — not just read-only wrappers.

## The Problem

Your RAG application retrieves documents, assembles context, and calls an LLM. But when something goes wrong:

- **"Why did the AI say that?"** — You can't reproduce the exact context that was assembled
- **"What documents were used?"** — Your retriever logs don't capture what actually made it into the prompt
- **"Was the data fresh?"** — No tracking of when features and documents were last updated
- **"Can we audit this decision?"** — Regulators ask, and you have no answer

Most RAG frameworks are **read-only wrappers** — they query external stores but don't track what was retrieved. When the auditor asks "what did your AI know when it decided?", they have no answer.

## The Solution: Write Path Ownership

Fabra owns the write path. We ingest, index, track freshness, and serve — not just query. This enables:

| Capability | Read-Only Frameworks | Fabra |
|:---|:---|:---|
| Track retrieved documents | ❌ No | ✅ Yes |
| Track feature values used | ❌ No | ✅ Yes |
| Replay exact context | ❌ No | ✅ Yes |
| Freshness timestamps | ❌ No | ✅ Yes |
| Compliance audit export | ❌ No | ✅ Yes |

## How It Works

### 1. Every Context Gets a UUIDv7 ID

When you assemble context, Fabra automatically assigns a time-sortable unique identifier:

```python
from fabra import FeatureStore, context, ContextItem

store = FeatureStore()

@context(store, name="support_context", max_tokens=4000)
async def build_support_context(user_id: str, query: str) -> list[ContextItem]:
    docs = await search_docs(query)
    tier = await store.get_feature("user_tier", user_id)

    return [
        ContextItem(content=f"User tier: {tier}", priority=0),
        ContextItem(content=str(docs), priority=1),
    ]

# Call the context
ctx = await build_support_context("user123", "how do I reset my password?")

print(ctx.id)       # 01912345-6789-7abc-def0-123456789abc (UUIDv7)
print(ctx.lineage)  # Full data provenance
```

### 2. Full Lineage Tracking

Every context assembly records:

```python
{
    "context_id": "01912345-6789-7abc-def0-123456789abc",
    "timestamp": "2024-01-15T10:30:00Z",

    # What features were used
    "features_used": [
        {
            "feature_name": "user_tier",
            "entity_id": "user123",
            "value": "premium",
            "freshness_ms": 150,
            "source": "cache"
        }
    ],

    # What retrievers were called
    "retrievers_used": [
        {
            "retriever_name": "search_docs",
            "query": "how do I reset my password?",
            "results_count": 5,
            "latency_ms": 45
        }
    ],

    # Assembly statistics
    "items_included": 4,
    "items_dropped": 1,
    "token_usage": 1847,
    "freshness_status": "guaranteed"
}
```

### 3. Context Replay

Reproduce any historical context by ID:

```python
# Get the exact context that was assembled
historical_ctx = await store.get_context_at("01912345-6789-7abc-def0-123456789abc")

print(historical_ctx.content)   # Exact prompt content
print(historical_ctx.lineage)   # Full data provenance
```

### 4. CLI Tools

```bash
# Show a context by ID
fabra context show 01912345-6789-7abc-def0-123456789abc

# List recent contexts
fabra context list --limit 10

# Export for audit
fabra context export 01912345-6789-7abc-def0-123456789abc --format json
```

## Use Cases

### Incident Investigation

When a user reports a bad AI response:

```python
# Find all contexts for this user in the incident window
contexts = await store.list_contexts(
    start=incident_time - timedelta(hours=1),
    end=incident_time + timedelta(hours=1),
)

# Examine what data was used
for ctx in contexts:
    full_ctx = await store.get_context_at(ctx["context_id"])
    print(f"Features: {[f['feature_name'] for f in full_ctx.lineage.features_used]}")
    print(f"Freshness: {full_ctx.lineage.stalest_feature_ms}ms")
```

### Regulatory Compliance

Export context lineage for auditors:

```bash
# Export all contexts for a time period
for ctx_id in $(fabra context list --start 2024-01-01 --end 2024-01-31 | jq -r '.[].context_id'); do
    fabra context export $ctx_id --format json -o "audit/$ctx_id.json"
done
```

### Debugging Stale Data

Identify when stale data affected decisions:

```python
ctx = await build_context(user_id, query)

# Find the slowest/stalest feature
slowest = max(ctx.lineage.features_used, key=lambda f: f.freshness_ms)
print(f"Stalest feature: {slowest.feature_name} ({slowest.freshness_ms}ms)")
```

## Quick Start

```bash
pip install "fabra-ai[ui]"
```

```python
from fabra import FeatureStore, context, ContextItem
from fabra.retrieval import retriever

store = FeatureStore()

@retriever(index="docs", top_k=5)
async def search_docs(query: str):
    pass  # Auto-wired to pgvector

@context(store, max_tokens=4000)
async def chat_context(user_id: str, query: str) -> list[ContextItem]:
    docs = await search_docs(query)
    tier = await store.get_feature("user_tier", user_id)
    return [
        ContextItem(content=f"User tier: {tier}", priority=0),
        ContextItem(content=str(docs), priority=1),
    ]

# Every call is tracked
ctx = await chat_context("user123", "help me")
print(f"Context ID: {ctx.id}")
print(f"Lineage: {ctx.lineage}")
```

## FAQ

**Q: What is a RAG audit trail?**
A: A complete record of what data (documents, features, retrieved results) was used to assemble context for each LLM call. Fabra tracks this automatically with full lineage.

**Q: How do I know what my AI knew when it made a decision?**
A: Use `store.get_context_at(context_id)` to replay the exact context that was assembled. Every context gets a UUIDv7 ID for retrieval.

**Q: Can I use this for GDPR/SOC2 compliance?**
A: Yes. Export context lineage with `fabra context export`. Every AI decision traces back through the data that informed it.

**Q: How is this different from LangChain?**
A: LangChain is a framework that queries external stores. Fabra is infrastructure that owns the write path — we track what was retrieved, not just how to retrieve it.

**Q: Does lineage tracking add latency?**
A: Minimal. Lineage is recorded asynchronously after context assembly completes. Context is still returned immediately.

## Next Steps

- [Context Accountability](context-accountability.md) — Deep dive into lineage tracking
- [Compliance Guide](compliance-guide.md) — GDPR, SOC2, and regulated industries
- [Context Store](context-store.md) — Full RAG infrastructure docs
- [Quickstart](quickstart.md) — Get started in 30 seconds

---

## Also Need ML Features?

Fabra includes a Feature Store for serving ML features — user personalization, risk scores, recommendations. Same infrastructure, same deployment.

[Feature Store →](feature-store-without-kubernetes.md) | [Feast vs Fabra →](feast-alternative.md)

---

## You Might Also Search For

- "rag audit trail"
- "what did ai know compliance"
- "llm decision audit"
- "context replay llm"
- "ai explainability debugging"

<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "TechArticle",
  "headline": "RAG Audit Trail: Know What Your AI Knew",
  "description": "Build RAG applications with full audit trails. Track exactly what documents and data your LLM used for every decision.",
  "author": {"@type": "Organization", "name": "Fabra Team"},
  "keywords": "rag audit trail, llm audit, ai compliance, context replay, ai explainability",
  "articleSection": "Documentation"
}
</script>
