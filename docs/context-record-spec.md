---
title: "Context Record Specification (CRS-001)"
description: "Technical specification for the Context Record format - the atomic unit of the Inference Context Ledger."
keywords: context record, crs-001, inference context ledger, ai audit trail, context replay, cryptographic integrity
---

# Context Record Specification (CRS-001)

> **Status:** v1.0.0
> **Purpose:** Canonical system-of-record format for inference context

## Definition

A **Context Record** is an immutable, replayable snapshot of all data used to assemble AI context at a specific moment in time. It is the atomic unit of the Inference Context Ledger.

---

## Why Context Records?

When your AI makes a decision, you need to know:
- What features (structured data) were used?
- What documents were retrieved?
- What was included vs dropped due to token limits?
- Was the data fresh or stale?

Context Records answer these questions with cryptographic proof.

---

## Record Structure

```json
{
  "context_id": "ctx_018f3a2b-7def-7abc-8901-234567890abc",
  "created_at": "2025-02-14T18:42:31.221Z",
  "environment": "production",
  "schema_version": "1.0.0",

  "inputs": {
    "user_id": "user_123",
    "query": "how do I reset my password?"
  },
  "context_function": "chat_context",

  "content": "You are a helpful assistant...",
  "token_count": 1523,

  "features": [...],
  "retrieved_items": [...],
  "assembly": {...},
  "lineage": {...},
  "integrity": {...}
}
```

---

## Field Reference

### Identity Fields

| Field | Type | Description |
|:------|:-----|:------------|
| `context_id` | string | Unique ID in format `ctx_<UUIDv7>` |
| `created_at` | datetime | When context was assembled (ISO 8601) |
| `environment` | string | `"development"` \| `"staging"` \| `"production"` |
| `schema_version` | string | CRS schema version (currently `"1.0.0"`) |

### Input Fields (for Replay)

| Field | Type | Description |
|:------|:-----|:------------|
| `inputs` | object | Arguments passed to context function |
| `context_function` | string | Name of the `@context` decorated function |

### Output Fields

| Field | Type | Description |
|:------|:-----|:------------|
| `content` | string | Final assembled text content |
| `token_count` | integer | Token count of final content |

### Features Array

Each feature used in the context:

```json
{
  "name": "user_tier",
  "entity_id": "user_123",
  "value": "premium",
  "source": "cache",
  "as_of": "2025-02-14T18:42:30.100Z",
  "freshness_ms": 1121
}
```

| Field | Type | Description |
|:------|:-----|:------------|
| `name` | string | Feature name |
| `entity_id` | string | Entity ID for this feature |
| `value` | any | The feature value |
| `source` | string | `"cache"` \| `"compute"` \| `"fallback"` |
| `as_of` | datetime | When this value was computed |
| `freshness_ms` | integer | Age in ms at assembly time |

### Retrieved Items Array

Each document/chunk retrieved:

```json
{
  "retriever": "search_docs",
  "chunk_id": "chunk_abc123",
  "document_id": "doc_456",
  "content_hash": "sha256:def789...",
  "content": "Password reset instructions...",
  "token_count": 150,
  "priority": 50,
  "similarity_score": 0.89,
  "source_url": "https://docs.example.com/password-reset",
  "as_of": "2025-02-10T12:00:00Z",
  "freshness_ms": 345600000,
  "is_stale": false
}
```

| Field | Type | Description |
|:------|:-----|:------------|
| `retriever` | string | Name of the retriever |
| `chunk_id` | string | Unique chunk identifier |
| `document_id` | string | Parent document ID |
| `content_hash` | string | SHA256 hash of content |
| `content` | string? | Full content (optional) |
| `token_count` | integer | Tokens in this chunk |
| `priority` | integer | Priority in assembly |
| `similarity_score` | float | Vector similarity score |
| `source_url` | string? | Original document URL |
| `as_of` | datetime | When indexed |
| `freshness_ms` | integer | Age in ms at retrieval |
| `is_stale` | boolean | Exceeded freshness SLA? |

### Assembly Decisions

How the context was assembled under constraints:

```json
{
  "max_tokens": 4000,
  "tokens_used": 1523,
  "items_provided": 8,
  "items_included": 5,
  "dropped_items": [
    {
      "source_id": "chunk_xyz",
      "priority": 10,
      "token_count": 500,
      "reason": "budget_exceeded"
    }
  ],
  "required_items_included": true,
  "freshness_sla_ms": 300000,
  "freshness_status": "guaranteed",
  "freshness_violations": []
}
```

| Field | Type | Description |
|:------|:-----|:------------|
| `max_tokens` | integer? | Token budget limit |
| `tokens_used` | integer | Actual tokens used |
| `items_provided` | integer | Items from context function |
| `items_included` | integer | Items that fit budget |
| `dropped_items` | array | Items dropped with reasons |
| `required_items_included` | boolean | All required items fit? |
| `freshness_sla_ms` | integer? | Freshness SLA in ms |
| `freshness_status` | string | `"guaranteed"` \| `"degraded"` \| `"unknown"` |
| `freshness_violations` | array | Features that violated SLA |

### Lineage Metadata

Complete dependency graph:

```json
{
  "features_used": ["user_tier", "user_engagement_score"],
  "retrievers_used": ["search_docs"],
  "indexes_used": ["knowledge_base"],
  "code_version": "abc123",
  "fabra_version": "2.0.7",
  "assembly_latency_ms": 45.2,
  "estimated_cost_usd": 0.0023
}
```

| Field | Type | Description |
|:------|:-----|:------------|
| `features_used` | array | Feature names used |
| `retrievers_used` | array | Retriever names used |
| `indexes_used` | array | Index/collection names |
| `code_version` | string? | Git SHA |
| `fabra_version` | string | Fabra version |
| `assembly_latency_ms` | float | Assembly time in ms |
| `estimated_cost_usd` | float | Estimated cost |

### Integrity Metadata

Cryptographic guarantees:

```json
{
  "record_hash": "sha256:abc123...",
  "content_hash": "sha256:def456...",
  "previous_context_id": null,
  "signed_at": null,
  "signature": null
}
```

| Field | Type | Description |
|:------|:-----|:------------|
| `record_hash` | string | SHA256 of canonical JSON (excl. this field) |
| `content_hash` | string | SHA256 of `content` field only |
| `previous_context_id` | string? | Chain linking (optional) |
| `signed_at` | datetime? | When signed |
| `signature` | string? | Cryptographic signature |

---

## Creating a Context Record

Context Records are created automatically by the `@context` decorator:

```python
from fabra.context import context, ContextItem

@context(store, name="chat_context", max_tokens=4000)
async def chat_context(user_id: str, query: str):
    tier = await store.get_feature("user_tier", user_id)
    docs = await search_docs(query)
    return [
        ContextItem(content=f"User tier: {tier}", priority=90),
        ContextItem(content=str(docs), priority=50),
    ]

# Every call creates an immutable Context Record
ctx = await chat_context("user_123", "how do I reset?")
record = ctx.to_record()
print(record.context_id)  # ctx_018f3a2b-...
```

---

## Verifying Integrity

```python
from fabra.utils.integrity import verify_record_integrity, verify_content_integrity

# Verify the record hasn't been tampered with
assert verify_record_integrity(record)  # True if hash matches

# Verify content separately
assert verify_content_integrity(record)  # True if content_hash matches
```

CLI verification:

```bash
fabra context verify ctx_018f3a2b-7def-7abc-8901-234567890abc
# ✓ Record integrity verified (hash matches)
```

---

## CLI Commands

```bash
# Show a Context Record
fabra context show ctx_018f3a2b-...

# Show as JSON
fabra context show ctx_018f3a2b-... --format json

# Verify integrity
fabra context verify ctx_018f3a2b-...

# Compare two records
fabra context diff ctx_abc123 ctx_def456

# Export for audit
fabra context export ctx_018f3a2b-... > record.json

# Replay (re-execute with same inputs)
fabra context replay ctx_018f3a2b-...
```

---

## Storage

Context Records are stored in the offline store:

| Environment | Storage |
|:------------|:--------|
| Development | DuckDB (`~/.fabra/fabra.duckdb`) |
| Production | PostgreSQL |

Records are stored with indexes on:
- `context_id` (primary key)
- `created_at` (for time-range queries)
- `context_function` (for filtering by context type)
- `record_hash` (for integrity lookups)

---

## Use Cases

### Compliance & Audit

When asked "what did the AI know?", pull the Context Record:

```bash
fabra context show ctx_018f3a2b-... --format json > evidence.json
```

### Debugging

When a response is wrong, compare to a working one:

```bash
fabra context diff ctx_bad ctx_good
```

### Replay

Reproduce exact historical behavior:

```bash
fabra context replay ctx_018f3a2b-...
```

---

## Schema Evolution

- Schema version is stored in each record (`schema_version: "1.0.0"`)
- Fabra supports reading older schema versions
- New fields are additive (backwards compatible)
- Breaking changes increment the major version

---

## Related Documentation

- [Context Store](context-store.md) — Context assembly infrastructure
- [Context Accountability](context-accountability.md) — Why lineage matters
- [Compliance Guide](compliance-guide.md) — Using Context Records for compliance
