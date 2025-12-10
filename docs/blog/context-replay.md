---
title: "What Did Your AI Know? Introducing Context Replay"
description: "Debug AI behavior by replaying exactly what context your model received at any point in time."
keywords: context replay, ai debugging, llm observability, context accountability, ai audit
date: 2025-01-15
---

# What Did Your AI Know? Introducing Context Replay

**TL;DR:** Fabra v1.4 introduces Context Replay — the ability to see exactly what data your AI had when it made a decision. Think `git log` for your LLM's context window.

---

## The Debugging Nightmare

You deploy an AI assistant. A user reports: *"Your AI gave me completely wrong advice yesterday at 3pm."*

You check your logs. You see the request came in. You see a response went out. But what was *in* that response? What context did the model actually receive?

If you're like most teams, you're guessing. Maybe you can reconstruct it from application logs. Maybe you have some partial data in your observability stack. But you can't replay exactly what the model saw.

**Until now.**

---

## Enter Context Replay

Fabra v1.4 introduces automatic context logging. Every time you assemble context, Fabra captures:

- **The full context string** — Exactly what went into the prompt
- **Feature lineage** — Which features were used and their values
- **Retriever lineage** — Which documents were retrieved, latency, result counts
- **Freshness status** — Was the data cached? Computed fresh? Fallback?
- **Token usage** — How many tokens, what got truncated

All tied to a **UUIDv7 context ID** that's time-sortable and globally unique.

---

## How It Works

### Automatic Tracking

The `@context` decorator now tracks everything automatically:

```python
from fabra.context import context, ContextItem

@context(store, max_tokens=4000)
async def build_support_prompt(user_id: str, query: str):
    tier = await store.get_feature("user_tier", user_id)
    docs = await find_relevant_docs(query)
    return [
        ContextItem(content=f"User tier: {tier}", priority=0),
        ContextItem(content=str(docs), priority=1),
    ]

# Call your context function
result = await build_support_prompt("user_123", "How do I reset my password?")

# The context ID is embedded in the result
print(result.id)  # "01948c9a-2b3e-7d4f-8e5a-1c2d3e4f5a6b"
```

### Replay Any Context

Got a bug report? Pull up exactly what the model saw:

```bash
# CLI
fabra context show 01948c9a-2b3e-7d4f-8e5a-1c2d3e4f5a6b

# Or via REST API
curl http://localhost:8000/v1/context/01948c9a-2b3e-7d4f-8e5a-1c2d3e4f5a6b
```

```json
{
  "context_id": "01948c9a-2b3e-7d4f-8e5a-1c2d3e4f5a6b",
  "timestamp": "2025-01-15T15:30:00Z",
  "content": "User tier: premium\n\nRelevant documents:\n1. Password Reset Guide...",
  "lineage": {
    "features_used": [
      {
        "feature_name": "user_tier",
        "entity_id": "user_123",
        "value": "premium",
        "freshness_ms": 15,
        "source": "cache"
      }
    ],
    "retrievers_used": [
      {
        "retriever_name": "find_relevant_docs",
        "query": "How do I reset my password?",
        "results_count": 3,
        "latency_ms": 45.2
      }
    ]
  }
}
```

### Browse Historical Contexts

Need to investigate a time range?

```bash
# List contexts from a specific period
fabra context list --start 2025-01-15T14:00:00 --end 2025-01-15T16:00:00 --limit 50
```

---

## Real-World Use Cases

### 1. Customer Support Escalations

Customer claims the AI gave bad advice? Pull the exact context ID from your logs, replay it, and see exactly what information the model had access to.

### 2. Model Evaluation

Running A/B tests? Compare context assembly across model versions. See if context quality correlates with user satisfaction.

### 3. Compliance Audits

Regulators asking what data influenced AI decisions? Export contexts for any time period with full lineage.

```bash
fabra context export 01948c9a-... --format yaml > audit_evidence.yaml
```

### 4. Debugging Data Freshness

User got stale information? Check the lineage to see if features came from cache, were computed fresh, or fell back to defaults.

---

## The Technical Details

### Storage

Contexts are stored in your offline store (DuckDB for development, Postgres for production). We use a simple schema:

```sql
CREATE TABLE context_log (
    context_id VARCHAR PRIMARY KEY,
    timestamp TIMESTAMP NOT NULL,
    content TEXT NOT NULL,
    lineage JSON NOT NULL,
    meta JSON NOT NULL,
    version VARCHAR DEFAULT 'v1'
);
```

### Zero Performance Impact

Context logging happens asynchronously after your context is assembled. If logging fails, your application continues — we never block the hot path.

### Configurable Retention

Set retention policies per environment. Keep 7 days in dev, 90 days in production, whatever compliance requires.

---

## Getting Started

Upgrade to Fabra v1.4:

```bash
pip install --upgrade "fabra-ai[ui]"
```

Context replay is enabled by default. No configuration required.

---

## What's Next

Context Replay is just the foundation. Coming in v1.5:

- **Context Diff:** Compare two contexts side-by-side
- **Replay Simulation:** Re-run a context through updated prompts
- **Drift Detection:** Alert when context patterns change unexpectedly

---

*Fabra v1.4 is available now. [Full documentation →](../context-accountability.md)*

<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "BlogPosting",
  "headline": "What Did Your AI Know? Introducing Context Replay",
  "description": "Debug AI behavior by replaying exactly what context your model received at any point in time.",
  "author": {"@type": "Organization", "name": "Fabra Team"},
  "datePublished": "2025-01-15",
  "keywords": "context replay, ai debugging, llm observability, context accountability"
}
</script>
