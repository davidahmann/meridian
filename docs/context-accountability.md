---
title: "Context Accountability: AI Decision Audit Trail | Fabra"
description: "Full audit trail for AI decisions. Know exactly what your AI knew when it decided. Lineage tracking, context replay, and compliance support for GDPR, SOC2, and regulated industries."
keywords: ai decision audit, ai audit trail, llm explainability, context replay, ai compliance, gdpr ai, soc2 ai, what did ai know, rag audit trail, llm debugging, ai lineage, context lineage
---

# Context Accountability

**Introduced in v1.4+** - Full audit trail for AI decisions. Know exactly what your AI knew when it decided.

## At a Glance

| | |
|:---|:---|
| **Context ID** | UUIDv7 (time-sortable, unique) |
| **Replay API** | `store.get_context_at(context_id)` |
| **List API** | `store.list_contexts(start, end, limit)` |
| **CLI** | `fabra context show <id>`, `fabra context list` |
| **Storage** | `context_log` table in DuckDB/Postgres |
| **Lineage** | Features used, retrievers called, items dropped, freshness timestamps |

## The Problem

When regulators, auditors, or incident responders ask "what did your AI know when it made this decision?", read-only frameworks have no answer. They query external stores but don't track:

- **What data was assembled?** - Exactly which features, documents, and data sources
- **How fresh was the data?** - Was it 5 seconds old or 5 hours stale?
- **Can we reproduce this?** - If there's an incident, can we replay the exact context?

This is why Fabra owns the write path. **You can't audit what you don't control.**

## The Solution

Fabra automatically tracks **lineage** for every context assembly:

```python
from fabra import FeatureStore, context, ContextItem

store = FeatureStore()

@context(store=store, name="recommendation_context", max_tokens=2000)
async def build_recommendation_context(user_id: str) -> list[ContextItem]:
    # Every call to get_feature is automatically tracked
    engagement = await store.get_feature("engagement_score", user_id)
    preferences = await store.get_feature("user_preferences", user_id)

    # Every retriever call is also tracked
    similar_items = await similar_products(user_id)

    return [
        ContextItem(content=f"User Engagement: {engagement}", priority=2),
        ContextItem(content=f"Preferences: {preferences}", priority=1),
        ContextItem(content=f"Similar: {similar_items}", priority=0),
    ]

# After calling the context:
ctx = await build_recommendation_context("user123")

# The context includes full lineage
print(ctx.id)        # UUIDv7: time-sortable unique identifier
print(ctx.lineage)   # Full data provenance
```

## What Gets Tracked

### Feature Lineage

Every feature retrieved during context assembly is recorded:

```python
{
    "feature_name": "engagement_score",
    "entity_id": "user123",
    "value": 85.5,
    "timestamp": "2024-01-15T10:30:00Z",
    "freshness_ms": 150,      # How old the value was at assembly time
    "source": "cache"          # Where the value came from: cache, compute, or fallback
}
```

### Retriever Lineage

Every RAG/vector search call is recorded:

```python
{
    "retriever_name": "similar_products",
    "query": "electronics smartphone",
    "results_count": 5,
    "latency_ms": 45.2,
    "index_name": "product_catalog"
}
```

### Assembly Statistics

Overall context assembly metrics:

```python
{
    "context_id": "01912345-6789-7abc-def0-123456789abc",
    "timestamp": "2024-01-15T10:30:00Z",
    "items_provided": 5,
    "items_included": 4,
    "items_dropped": 1,
    "freshness_status": "guaranteed",  # or "degraded"
    "stalest_feature_ms": 150,
    "token_usage": 1847,
    "max_tokens": 2000,
    "estimated_cost_usd": 0.000185
}
```

## Context Replay API

Retrieve any historical context by ID:

```python
# Get a context by ID
historical_ctx = await store.get_context_at("01912345-6789-7abc-def0-123456789abc")

print(historical_ctx.content)   # Exact content that was assembled
print(historical_ctx.lineage)   # Full lineage of what data was used
print(historical_ctx.meta)      # Assembly metadata

# List recent contexts for debugging
contexts = await store.list_contexts(
    start=datetime(2024, 1, 15, 10, 0),
    end=datetime(2024, 1, 15, 11, 0),
    limit=100
)
```

## REST API Endpoints

### List Contexts

```bash
GET /v1/contexts?start=2024-01-15T10:00:00Z&end=2024-01-15T11:00:00Z&limit=100
```

Returns a list of context summaries:

```json
[
    {
        "context_id": "01912345-6789-7abc-def0-123456789abc",
        "timestamp": "2024-01-15T10:30:00Z",
        "content": "User Engagement: 85.5...",
        "version": "v1"
    }
]
```

### Get Context by ID

```bash
GET /v1/context/{context_id}
```

Returns the full context including lineage:

```json
{
    "context_id": "01912345-6789-7abc-def0-123456789abc",
    "content": "User Engagement: 85.5\nPreferences: electronics...",
    "lineage": {
        "context_id": "01912345-6789-7abc-def0-123456789abc",
        "timestamp": "2024-01-15T10:30:00Z",
        "features_used": [...],
        "retrievers_used": [...],
        "items_dropped": 1,
        "freshness_status": "guaranteed"
    },
    "meta": {...},
    "version": "v1"
}
```

### Get Context Lineage Only

```bash
GET /v1/context/{context_id}/lineage
```

Returns just the lineage data (useful for audit dashboards):

```json
{
    "context_id": "01912345-6789-7abc-def0-123456789abc",
    "lineage": {
        "features_used": [
            {
                "feature_name": "engagement_score",
                "entity_id": "user123",
                "value": 85.5,
                "timestamp": "2024-01-15T10:30:00Z",
                "freshness_ms": 150,
                "source": "cache"
            }
        ],
        "retrievers_used": [...]
    }
}
```

## CLI Commands

### Show a Context

```bash
# Display full context details
fabra context show 01912345-6789-7abc-def0-123456789abc

# Show only lineage information
fabra context show 01912345-6789-7abc-def0-123456789abc --lineage
```

### List Contexts

```bash
# List recent contexts
fabra context list --limit 10

# Filter by time range
fabra context list --start 2024-01-15T10:00:00Z --end 2024-01-15T11:00:00Z
```

### Export for Audit

```bash
# Export as JSON
fabra context export 01912345-6789-7abc-def0-123456789abc --format json

# Export as YAML
fabra context export 01912345-6789-7abc-def0-123456789abc --format yaml -o context.yaml
```

## UUIDv7 Identifiers

Context IDs use UUIDv7 format, which is:
- **Time-sortable**: IDs sort chronologically, making range queries efficient
- **Unique**: Cryptographically random suffix prevents collisions
- **Standard**: Compatible with all UUID tooling

Example: `01912345-6789-7abc-def0-123456789abc`

The first 48 bits encode a Unix timestamp in milliseconds, making it easy to:
- Sort contexts by creation time
- Efficiently query contexts within a time range
- Debug issues by correlating with application logs

## Graceful Degradation

Context accountability is designed to never fail context assembly:

- If logging fails, the context is still returned successfully
- If the offline store is unavailable, lineage is attached to the context object but not persisted
- If feature tracking encounters an error, that feature is skipped in lineage but the value is still used

```python
# Lineage logging errors are logged but don't fail assembly
2024-01-15T10:30:00Z [warning] context_log_failed context_id=abc123 error="Connection refused"
2024-01-15T10:30:00Z [info] context_assembly_complete context_id=abc123 length=1847
```

## Use Cases

### Incident Investigation

When a user reports a bad recommendation:

```python
# Find all contexts for this user in the incident window
contexts = await store.list_contexts(
    start=incident_time - timedelta(hours=1),
    end=incident_time + timedelta(hours=1),
)

# Examine what data was used
for ctx in contexts:
    full_ctx = await store.get_context_at(ctx["context_id"])
    print(f"Context {ctx['context_id']}:")
    print(f"  Features: {[f['feature_name'] for f in full_ctx.lineage.features_used]}")
    print(f"  Freshness: {full_ctx.lineage.stalest_feature_ms}ms")
```

### Regulatory Compliance

Export context lineage for regulatory review. Every AI decision traces back through the data that informed it:

```bash
# Export all contexts for a time period
for ctx_id in $(curl -fsS "http://127.0.0.1:8000/v1/contexts?start=2024-01-01T00:00:00Z&end=2024-01-31T23:59:59Z&limit=10000" | jq -r '.[].context_id'); do
    fabra context export $ctx_id --format json -o "audit/$ctx_id.json"
done
```

### Performance Debugging

Identify slow features in context assembly:

```python
ctx = await build_context(user_id)

# Find the slowest feature
slowest = max(ctx.lineage.features_used, key=lambda f: f.freshness_ms)
print(f"Slowest feature: {slowest.feature_name} ({slowest.freshness_ms}ms)")

# Find slow retrievers
for r in ctx.lineage.retrievers_used:
    if r.latency_ms > 100:
        print(f"Slow retriever: {r.retriever_name} ({r.latency_ms}ms)")
```

## Configuration

Context accountability is enabled automatically when using a `FeatureStore` with an offline store:

```python
from fabra import FeatureStore
from fabra.store.offline import DuckDBOfflineStore, PostgresOfflineStore

# Local development - uses DuckDB
store = FeatureStore()  # Includes DuckDB by default

# Production - use Postgres for durable storage
store = FeatureStore(
    offline_store=PostgresOfflineStore(postgres_url)
)
```

Contexts are stored in the `context_log` table in your offline store and can be queried directly if needed:

```sql
-- DuckDB / Postgres
SELECT context_id, timestamp, content, lineage
FROM context_log
WHERE timestamp BETWEEN '2024-01-15 10:00:00' AND '2024-01-15 11:00:00'
ORDER BY timestamp DESC
LIMIT 100;
```

## Best Practices

1. **Always use a store** - Pass the `FeatureStore` to the `@context` decorator to enable lineage tracking
2. **Use meaningful context names** - The `name` parameter helps identify contexts in logs and audits
3. **Set appropriate max_tokens** - Token budgeting helps track what got dropped
4. **Review stale features** - Monitor `stalest_feature_ms` to catch freshness issues
5. **Archive old contexts** - Set up retention policies for the `context_log` table

## FAQ

**Q: How do I track what data my LLM used?**
A: Fabra automatically tracks lineage for every context assembly. Access via `ctx.lineage` after calling your `@context` function, or query historical contexts with `store.get_context_at(context_id)`.

**Q: Can I replay an AI decision for debugging?**
A: Yes. Every context gets a UUIDv7 ID. Use `store.get_context_at(id)` to retrieve the exact content, features, and retriever results that were assembled.

**Q: What is UUIDv7 and why use it for context IDs?**
A: UUIDv7 encodes a timestamp in the first 48 bits, making IDs time-sortable. This enables efficient range queries (`WHERE id > X`) and chronological ordering without a separate timestamp column.

**Q: How do I audit AI decisions for compliance?**
A: Use `fabra context export <id> --format json` to export full context with lineage. For bulk export, use `fabra context list` to get IDs in a time range.

**Q: What happens if lineage logging fails?**
A: Context assembly succeeds anyway. Fabra uses graceful degradation—logging errors are recorded but don't block the response.

**Q: Where is context lineage stored?**
A: In the `context_log` table in your offline store (DuckDB or Postgres). You can query it directly with SQL.

---

<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "TechArticle",
  "headline": "Context Accountability: AI Decision Audit Trail",
  "description": "Track exactly what data was used when your AI made a decision. Full lineage tracking, context replay, and compliance audit support.",
  "author": {"@type": "Organization", "name": "Fabra Team"},
  "keywords": "ai audit, context lineage, llm debugging, ai compliance, context replay",
  "articleSection": "Documentation"
}
</script>
