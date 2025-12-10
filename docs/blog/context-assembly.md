---
title: "Context Assembly: Fitting LLM Prompts in Token Budgets"
description: "How to assemble LLM context that always fits your token budget. Priority-based truncation, required vs optional content, and token counting that works."
keywords: llm context assembly, token budget management, rag context window, prompt engineering, context truncation, llm token limits
date: 2025-01-11
---

# Context Assembly: Fitting LLM Prompts in Token Budgets

Every RAG application hits this error eventually:

```
openai.error.InvalidRequestError:
This model's maximum context length is 8192 tokens.
However, your messages resulted in 12847 tokens.
```

The naive fix is truncation. The right fix is priority-based context assembly.

## The Problem

Your LLM context includes:

- System prompt (required)
- User query (required)
- Retrieved documents (important but variable)
- User history (nice to have)
- Feature values (depends on use case)

You don't know the final size until runtime. Document retrieval might return 2 results or 20. User history might be empty or extensive.

## The Naive Solution (Don't Do This)

```python
def build_context(docs, history, features):
    context = f"""
    System: You are helpful.
    Docs: {docs}
    History: {history}
    Features: {features}
    """
    # Truncate if too long
    if len(context) > 8000:
        context = context[:8000]
    return context
```

Problems:

1. **Character count != token count** — "hello" is 1 token, but so is " indistinguishable"
2. **Arbitrary truncation** — you might cut off mid-sentence or mid-document
3. **No priority** — you lose important content while keeping fluff

## The Fabra Solution

Fabra's `@context` decorator handles this properly:

```python
from fabra.context import context, ContextItem

@context(store, max_tokens=4000)
async def build_prompt(user_id: str, query: str):
    docs = await search_docs(query)
    history = await get_chat_history(user_id)
    tier = await store.get_feature("user_tier", user_id)

    return [
        # Priority 0 = lowest priority number = most important
        ContextItem(
            content="You are a helpful assistant for our SaaS product.",
            priority=0,
            required=True  # Never drop this
        ),
        ContextItem(
            content=f"User tier: {tier}",
            priority=1,
            required=True  # Never drop this either
        ),
        ContextItem(
            content=f"Relevant documentation:\n{docs[0]}",
            priority=2
        ),
        ContextItem(
            content=f"Additional docs:\n{docs[1:]}",
            priority=3
        ),
        ContextItem(
            content=f"Chat history:\n{history}",
            priority=4  # Dropped first if over budget
        ),
    ]
```

### How It Works

1. **Token counting** — uses `tiktoken` for accurate OpenAI token counts
2. **Priority sorting** — items sorted by priority (0 = most important)
3. **Greedy assembly** — adds items until budget exhausted
4. **Required enforcement** — `required=True` items always included
5. **Budget error** — raises `ContextBudgetError` if required items exceed budget

### The Result

```python
ctx = await build_prompt("user_123", "how do I reset my password?")

print(ctx.content)
# Assembled context string, guaranteed <= 4000 tokens

print(ctx.meta)
# {
#   "token_usage": 3847,
#   "max_tokens": 4000,
#   "items_included": 4,
#   "items_dropped": 1,
#   "freshness_status": "guaranteed"
# }
```

You know exactly what was included and what was dropped.

## Token Counting That Works

Fabra uses `tiktoken` for accurate token counting:

```python
from fabra.utils.tokens import OpenAITokenCounter

counter = OpenAITokenCounter(model="gpt-4")
tokens = counter.count("Your text here")
```

This matches OpenAI's actual tokenization. No more guessing with `len(text) / 4`.

Different models use different tokenizers:

- GPT-4 / GPT-3.5: `cl100k_base`
- Claude: Different tokenizer (approximate)
- Local models: Varies

Fabra defaults to OpenAI's tokenizer but the counter is configurable.

## Cost Estimation

Context assembly includes cost estimation:

```python
ctx = await build_prompt("user_123", "query")

print(ctx.meta["cost_usd"])
# 0.000423 (estimated input cost)
```

Useful for monitoring and budgeting API costs.

## Rich Display in Notebooks

The `Context` object has a rich HTML display for Jupyter notebooks:

```python
ctx = await build_prompt("user_123", "query")
ctx  # Displays formatted HTML with token usage bar
```

Shows:
- Freshness status (fresh vs degraded)
- Token usage bar with color coding
- Content preview
- Metadata

## Common Patterns

### Fixed System Prompt + Variable Retrieval

```python
@context(store, max_tokens=4000)
async def build(query: str):
    docs = await search(query)  # Variable size

    items = [
        ContextItem(content=SYSTEM_PROMPT, priority=0, required=True),
    ]

    # Add docs with increasing priority (lower = more important)
    for i, doc in enumerate(docs):
        items.append(ContextItem(content=doc, priority=i + 1))

    return items
```

### User Personalization + Documents

```python
@context(store, max_tokens=4000)
async def build(user_id: str, query: str):
    tier = await store.get_feature("user_tier", user_id)
    prefs = await store.get_feature("preferences", user_id)
    docs = await search(query)

    return [
        ContextItem(content=SYSTEM_PROMPT, priority=0, required=True),
        ContextItem(content=f"User: {tier}, prefs: {prefs}", priority=1),
        ContextItem(content=str(docs), priority=2),
    ]
```

### Graceful Degradation

```python
@context(store, max_tokens=4000)
async def build(query: str):
    try:
        detailed_docs = await detailed_search(query)
    except TimeoutError:
        detailed_docs = []

    return [
        ContextItem(content=SYSTEM_PROMPT, priority=0, required=True),
        ContextItem(content=str(detailed_docs), priority=1),
        ContextItem(content="If docs are missing, ask user to clarify.", priority=2),
    ]
```

## Try It

```bash
pip install "fabra-ai[ui]"
```

```python
from fabra.core import FeatureStore
from fabra.context import context, ContextItem

store = FeatureStore()

@context(store, max_tokens=1000)
async def demo(query: str):
    return [
        ContextItem(content="System prompt here", priority=0, required=True),
        ContextItem(content="Important info", priority=1),
        ContextItem(content="Nice to have " * 100, priority=2),  # Will be dropped
    ]

ctx = await demo("test")
print(f"Used {ctx.meta['token_usage']} tokens")
print(f"Dropped {ctx.meta['items_dropped']} items")
```

[Full context store docs →](../context-assembly.md)

<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "BlogPosting",
  "headline": "Context Assembly: Fitting LLM Prompts in Token Budgets",
  "description": "How to assemble LLM context that always fits your token budget. Priority-based truncation, required vs optional content, and token counting that works.",
  "author": {"@type": "Organization", "name": "Fabra Team"},
  "datePublished": "2025-01-11",
  "keywords": "llm context assembly, token budget management, rag context window, prompt engineering"
}
</script>
