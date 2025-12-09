---
title: "Context Assembly: Token Budgets and Priority | Fabra"
description: "Compose LLM context from multiple sources with Fabra's @context decorator. Token budget management, priority-based truncation, and explainability."
keywords: context assembly, token budget, llm context, priority truncation, context composition, rag context
---

# Context Assembly

> **TL;DR:** Use `@context` to compose context from multiple sources. Set token budgets, assign priorities, and let Fabra handle truncation automatically.

## At a Glance

| | |
|:---|:---|
| **Decorator** | `@context(store, max_tokens=4000)` |
| **Token Counting** | tiktoken (GPT-4, Claude-3 supported) |
| **Priority** | 0 = highest (kept first), 3+ = lowest (dropped first) |
| **Required Flag** | `required=True` raises error if can't fit |
| **Debug** | `store.explain_context()` or `GET /context/{id}/explain` |
| **Freshness** | `freshness_sla="5m"` ensures data age (v1.5+) |

## What is Context Assembly?

LLM prompts have token limits. You need to fit:
- System prompt
- Retrieved documents
- User history
- Entity features

**Context Assembly** combines these sources intelligently, truncating lower-priority items when the budget is exceeded.

## Basic Usage

```python
from fabra.context import context, Context, ContextItem

@context(store, max_tokens=4000)
async def chat_context(user_id: str, query: str) -> Context:
    docs = await search_docs(query)
    history = await get_history(user_id)

    return [
        ContextItem(content="You are a helpful assistant.", priority=0, required=True),
        ContextItem(content=str(docs), priority=1, required=True),
        ContextItem(content=history, priority=2),  # Truncated first
    ]
```

## ContextItem

Each piece of context is wrapped in a `ContextItem`:

```python
ContextItem(
    content="The actual text content",
    priority=1,          # Lower = higher priority (kept first)
    required=False,      # If True, raises error when can't fit
    metadata={"source": "docs"}  # Optional tracking info
)
```

### Priority System

| Priority | Description | Example |
| :--- | :--- | :--- |
| 0 | Critical, never truncate | System prompt |
| 1 | High priority | Retrieved documents |
| 2 | Medium priority | User preferences |
| 3+ | Low priority | Suggestions, history |

Items are sorted by priority. When over budget, highest-numbered (lowest priority) items are truncated first.

### Required Flag

```python
ContextItem(content=docs, priority=1, required=True)
```

- `required=True`: Raises `ContextBudgetError` if item can't fit.
- `required=False` (default): Item is silently dropped if over budget.

## Token Counting

Fabra uses tiktoken for accurate token counting:

```python
@context(store, max_tokens=4000, model="gpt-4")
async def chat_context(...) -> Context:
    pass
```

Supported models:
- `gpt-4`, `gpt-4-turbo` (cl100k_base)
- `gpt-3.5-turbo` (cl100k_base)
- `claude-3` (approximation)

## Truncation Strategies

### Default: Drop Items

Lower-priority items are dropped entirely:

```python
@context(store, max_tokens=1000)
async def simple_context(query: str) -> Context:
    return [
        ContextItem(content=short_text, priority=0),     # 100 tokens - kept
        ContextItem(content=medium_text, priority=1),    # 400 tokens - kept
        ContextItem(content=long_text, priority=2),      # 800 tokens - DROPPED
    ]
# Result: 500 tokens (short + medium)
```

### Partial Truncation

Truncate content within an item:

```python
ContextItem(
    content=long_text,
    priority=2,
    # truncate_strategy="end"  # Future: Truncate from end
)
```

Strategies:
- `"end"`: Remove text from end (default for docs)
- `"start"`: Remove text from start (for history)
- `"middle"`: Keep start and end, remove middle

## Explainability

Debug context assembly with the explain API:

```python
# Get detailed trace
trace = await store.explain_context("chat_context", user_id="u1", query="test")
print(trace)
```

Output:
```json
{
  "context_id": "ctx_abc123",
  "max_tokens": 4000,
  "used_tokens": 3847,
  "items": [
    {"priority": 0, "tokens": 50, "status": "included", "source": "system"},
    {"priority": 1, "tokens": 2800, "status": "included", "source": "docs"},
    {"priority": 2, "tokens": 997, "status": "included", "source": "history"},
    {"priority": 3, "tokens": 500, "status": "truncated", "source": "suggestions"}
  ]
}
```

Or via HTTP:
```bash
curl http://localhost:8000/context/ctx_abc123/explain
```

## Combining with Features

Mix features and retrievers in context:

```python
@context(store, max_tokens=4000)
async def rich_context(user_id: str, query: str) -> Context:
    # Retriever results
    docs = await search_docs(query)

    # Feature values
    prefs = await store.get_feature("user_preferences", user_id)
    tier = await store.get_feature("user_tier", user_id)

    return [
        ContextItem(content=SYSTEM_PROMPT, priority=0, required=True),
        ContextItem(content=str(docs), priority=1, required=True),
        ContextItem(content=f"User tier: {tier}", priority=2),
        ContextItem(content=f"Preferences: {prefs}", priority=3),
    ]
```

## Dynamic Budgets

Adjust budget based on context:

```python
@context(store, max_tokens=4000)
async def adaptive_context(user_id: str, query: str) -> Context:
    tier = await store.get_feature("user_tier", user_id)

    # Premium users get more context
    budget = 8000 if tier == "premium" else 4000

    docs = await search_docs(query, top_k=10 if tier == "premium" else 5)

    return Context(
        items=[...],
        max_tokens=budget  # Override decorator budget
    )
```

## Error Handling

### ContextBudgetError

Raised when required items can't fit:

```python
from fabra.context import ContextBudgetError

try:
    ctx = await chat_context(user_id, query)
except ContextBudgetError as e:
    print(f"Required content exceeds budget: {e.required_tokens} > {e.budget}")
    # Fallback: use shorter system prompt
```

### Empty Context

If all items are truncated:

```python
ctx = await minimal_context(user_id, query)
if ctx.is_empty:
    # Handle gracefully
    # Note: In practice, you'd handle this in your app logic
    # by returning a default response directly
```

## Best Practices

1. **Always set priority 0 for system prompt** - never truncate instructions.
2. **Mark retrieved docs as required** - they're the core of RAG.
3. **Use lower priority for nice-to-have** - history, suggestions.
4. **Test with edge cases** - very long docs, empty retrievals.
5. **Monitor with explain API** - understand truncation patterns.

## Performance

Context assembly is fast:
- Token counting: ~1ms per 1000 tokens
- Priority sorting: O(n log n)
- Truncation: O(n)

For very large contexts (>50 items), consider pre-filtering.

## Freshness SLAs

Ensure your context uses fresh data with freshness guarantees (v1.5+):

```python
@context(store, max_tokens=4000, freshness_sla="5m")
async def time_sensitive_context(user_id: str, query: str) -> Context:
    tier = await store.get_feature("user_tier", user_id)  # Must be <5m old
    balance = await store.get_feature("account_balance", user_id)
    return [
        ContextItem(content=f"User tier: {tier}", priority=0),
        ContextItem(content=f"Balance: ${balance}", priority=1),
    ]
```

### Checking Freshness

```python
ctx = await time_sensitive_context("user_123", "query")

# Check overall status
print(ctx.is_fresh)  # True if all features within SLA
print(ctx.meta["freshness_status"])  # "guaranteed" or "degraded"

# See violations
for v in ctx.meta["freshness_violations"]:
    print(f"{v['feature']} is {v['age_ms']}ms old (limit: {v['sla_ms']}ms)")
```

### Strict Mode

For critical contexts, fail on stale data:

```python
from fabra.exceptions import FreshnessSLAError

@context(store, freshness_sla="30s", freshness_strict=True)
async def critical_context(...):
    pass  # Raises FreshnessSLAError if any feature exceeds SLA
```

See [Freshness SLAs](freshness-sla.md) for the full guide.

## FAQ

**Q: How do I set a token budget for LLM context?**
A: Use the `@context` decorator with `max_tokens` parameter: `@context(store, max_tokens=4000)`. Fabra automatically truncates lower-priority items when the budget is exceeded.

**Q: What happens when context exceeds token limit?**
A: Items are dropped by priority (highest number first). Items with `required=True` raise `ContextBudgetError` if they can't fit. Items without `required` are silently dropped.

**Q: How do I prioritize content in LLM context?**
A: Set `priority` on `ContextItem`: `priority=0` (critical, kept first), `priority=1` (high), `priority=2+` (lower, dropped first). System prompts should always be priority 0.

**Q: Does Fabra support token counting for Claude and GPT-4?**
A: Yes. Fabra uses tiktoken for accurate counting. Specify model: `@context(store, max_tokens=4000, model="gpt-4")`. Claude-3 uses approximation.

**Q: How do I debug context assembly?**
A: Use the explain API: `await store.explain_context("context_name", ...)` or HTTP endpoint `GET /context/{id}/explain`. Returns which items were included, truncated, or dropped.

**Q: Can I dynamically change the token budget?**
A: Yes. Return a `Context` object with `max_tokens` set: `return Context(items=[...], max_tokens=budget)` to override the decorator's default.

---

## Next Steps

- [Freshness SLAs](freshness-sla.md): Data freshness guarantees
- [Retrievers](retrievers.md): Define semantic search
- [Event-Driven Features](event-driven-features.md): Fresh context
- [Use Case: RAG Chatbot](use-cases/rag-chatbot.md): Full example

<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "TechArticle",
  "headline": "Context Assembly: Token Budgets and Priority",
  "description": "Compose LLM context from multiple sources with Fabra's @context decorator. Token budget management, priority-based truncation, and explainability.",
  "author": {"@type": "Organization", "name": "Fabra Team"},
  "keywords": "context assembly, token budget, llm context, rag",
  "articleSection": "Documentation"
}
</script>
