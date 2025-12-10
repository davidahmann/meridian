---
title: "Token Budget Management for Production RAG"
description: "How to manage LLM token budgets in production RAG applications. Accurate token counting, priority-based truncation, and cost monitoring."
keywords: token budget management, rag token limits, llm context length, token counting, openai token limit, production rag
date: 2025-01-08
---

# Token Budget Management for Production RAG

Your RAG application works in development. In production, it fails 5% of the time with:

```
InvalidRequestError: This model's maximum context length is 8192 tokens.
```

The 5% failure rate comes from edge cases: long documents, verbose chat history, users who paste entire codebases into the chat.

Here's how to handle token budgets properly.

## The Real Problem

Token limits aren't just about truncation. They're about:

1. **Predictable behavior** — never fail due to context length
2. **Quality control** — include the most important content
3. **Cost management** — tokens = money
4. **Latency optimization** — fewer tokens = faster responses

## Token Counting Basics

Characters != tokens. Words != tokens.

| Text | Characters | Words | Tokens (GPT-4) |
|------|-----------|-------|----------------|
| "hello" | 5 | 1 | 1 |
| "indistinguishable" | 18 | 1 | 1 |
| "Hello, world!" | 13 | 2 | 4 |
| JSON blob (1KB) | 1000 | ~150 | ~250 |

The only accurate way to count tokens is with the model's tokenizer.

### Using tiktoken

```python
import tiktoken

# Get the right encoding for your model
enc = tiktoken.encoding_for_model("gpt-4")

text = "Your text here"
tokens = enc.encode(text)
print(len(tokens))  # Actual token count
```

Fabra wraps this:

```python
from fabra.utils.tokens import OpenAITokenCounter

counter = OpenAITokenCounter(model="gpt-4")
count = counter.count("Your text here")
```

## Priority-Based Truncation

The naive approach:

```python
def build_context(docs, max_chars=8000):
    context = "\n".join(docs)
    return context[:max_chars]  # Terrible idea
```

Problems:

1. Cuts mid-sentence
2. No priority ordering
3. Character count != token count

### The Right Approach

```python
from fabra.context import context, ContextItem

@context(store, max_tokens=4000)
async def build_prompt(query: str):
    docs = await search_docs(query)

    return [
        # Priority 0 = most important (never dropped if required)
        ContextItem(
            content="You are a helpful assistant.",
            priority=0,
            required=True
        ),
        # Priority 1 = important
        ContextItem(
            content=f"Primary document:\n{docs[0]}",
            priority=1
        ),
        # Priority 2-N = progressively less important
        ContextItem(
            content=f"Supporting docs:\n{docs[1]}",
            priority=2
        ),
        ContextItem(
            content=f"Additional context:\n{docs[2:]}",
            priority=3
        ),
    ]
```

Fabra's algorithm:

1. Sort items by priority (lowest number = most important)
2. Add items until budget exhausted
3. Skip items that would exceed budget
4. Always include `required=True` items (or raise error)

## Handling Dynamic Content

Document length varies. Chat history grows. User queries range from 3 words to 3 paragraphs.

### Defensive Budgeting

Reserve space for dynamic content:

```python
@context(store, max_tokens=4000)
async def build_prompt(user_id: str, query: str):
    # Reserve ~500 tokens for user query
    # Reserve ~1000 tokens for response
    # Use ~2500 for context

    docs = await search_docs(query)
    history = await get_history(user_id)

    return [
        ContextItem(content=SYSTEM_PROMPT, priority=0, required=True),
        ContextItem(content=f"Query: {query}", priority=1, required=True),
        ContextItem(content=str(docs[:2]), priority=2),  # Top 2 docs
        ContextItem(content=str(docs[2:]), priority=3),  # Rest
        ContextItem(content=str(history[-5:]), priority=4),  # Last 5 msgs
    ]
```

### Per-Item Limits

For very long documents, truncate individually:

```python
def truncate_doc(doc: str, max_tokens: int = 500) -> str:
    counter = OpenAITokenCounter()
    tokens = counter.count(doc)
    if tokens <= max_tokens:
        return doc

    # Binary search for right length
    # (Or use a chunking strategy)
    ...
```

## Cost Monitoring

Tokens cost money:

| Model | Input Cost | Output Cost |
|-------|------------|-------------|
| GPT-4 Turbo | $0.01/1K | $0.03/1K |
| GPT-3.5 Turbo | $0.0005/1K | $0.0015/1K |
| Claude 3.5 Sonnet | $0.003/1K | $0.015/1K |

Fabra tracks costs:

```python
ctx = await build_prompt("user_123", "query")

print(ctx.meta["token_usage"])  # 3847
print(ctx.meta["cost_usd"])     # 0.0384 (estimated input cost)
```

### Cost Alerts

```python
@context(store, max_tokens=4000)
async def build_prompt(query: str):
    items = [...]
    return items

# After assembly
ctx = await build_prompt("expensive query")
if ctx.meta["cost_usd"] > 0.10:
    logger.warning(f"High cost context: ${ctx.meta['cost_usd']:.4f}")
```

## Latency Optimization

Fewer tokens = faster responses. LLM latency scales roughly linearly with output tokens and sub-linearly with input tokens.

### Strategies

1. **Tighter budgets for simple queries**

```python
@context(store, max_tokens=2000)  # Small budget
async def simple_query(query: str):
    ...

@context(store, max_tokens=8000)  # Large budget
async def complex_query(query: str):
    ...
```

2. **Streaming for long responses**

Token budget applies to input. For output, use streaming to improve perceived latency.

3. **Caching**

Fabra caches context assembly:

```python
@context(store, max_tokens=4000, cache_ttl="5m")
async def build_prompt(query: str):
    ...
```

Same query within 5 minutes? Return cached context.

## Production Patterns

### Fallback on Budget Error

```python
from fabra.context import ContextBudgetError

try:
    ctx = await build_prompt(query)
except ContextBudgetError:
    # Required items exceeded budget
    ctx = await build_minimal_prompt(query)
```

### Monitoring Dashboard

Track these metrics:

- Token usage distribution (p50, p95, p99)
- Budget exhaustion rate (how often we drop content)
- Cost per query
- Items dropped per query

Fabra exposes Prometheus metrics:

```python
# fabra_context_tokens_total
# fabra_context_items_dropped_total
# fabra_context_budget_exceeded_total
```

### A/B Testing Budgets

Different budgets affect quality:

```python
import random

@context(store, max_tokens=4000 if random.random() > 0.5 else 2000)
async def build_prompt(query: str):
    ...
```

Measure: response quality, user satisfaction, cost.

## Common Mistakes

### 1. Hardcoding Character Limits

```python
# Wrong
context = text[:8000]

# Right
from fabra.utils.tokens import OpenAITokenCounter
counter = OpenAITokenCounter()
# Use counter.count() and proper truncation
```

### 2. Ignoring Required Content

```python
# Wrong: might drop system prompt
items = [
    ContextItem(content=system_prompt, priority=0),  # Not required!
    ContextItem(content=docs, priority=1),
]

# Right
items = [
    ContextItem(content=system_prompt, priority=0, required=True),
    ContextItem(content=docs, priority=1),
]
```

### 3. Not Monitoring Drops

```python
ctx = await build_prompt(query)

# Always log this in production
if ctx.meta["items_dropped"] > 0:
    logger.info(f"Dropped {ctx.meta['items_dropped']} items for query: {query[:50]}")
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
        ContextItem(content="System prompt", priority=0, required=True),
        ContextItem(content="Important", priority=1),
        ContextItem(content="Nice to have " * 50, priority=2),
        ContextItem(content="Filler " * 100, priority=3),
    ]

ctx = await demo("test")
print(f"Tokens: {ctx.meta['token_usage']}")
print(f"Dropped: {ctx.meta['items_dropped']}")
print(f"Cost: ${ctx.meta['cost_usd']:.6f}")
```

[Context assembly docs →](../context-assembly.md)

<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "BlogPosting",
  "headline": "Token Budget Management for Production RAG",
  "description": "How to manage LLM token budgets in production RAG applications. Accurate token counting, priority-based truncation, and cost monitoring.",
  "author": {"@type": "Organization", "name": "Fabra Team"},
  "datePublished": "2025-01-08",
  "keywords": "token budget management, rag token limits, llm context length, token counting, openai token limit"
}
</script>
