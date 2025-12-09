---
title: "Context Store for LLMs: RAG Infrastructure | Fabra"
description: "Build production RAG applications with Fabra's Context Store. Vector search with pgvector, automatic chunking, token budgets, and priority-based context assembly."
keywords: context store, rag infrastructure, llm context, pgvector, vector search, token budget, context assembly, retrieval augmented generation
---

# Context Store for LLMs

> **TL;DR:** Fabra's Context Store is RAG infrastructure that actually works. Index documents, search with pgvector, and assemble context with token budgets—all with Python decorators.

## Why Context Store?

Building LLM applications requires more than just features. You need:

1. **Document Indexing:** Store and chunk documents for retrieval.
2. **Vector Search:** Find semantically relevant content.
3. **Context Assembly:** Combine retrieved docs with user data under token limits.
4. **Freshness:** Update context when documents change.

Most teams cobble together Pinecone + LangChain + custom glue code. Fabra provides all of this in one unified system that shares infrastructure with your Feature Store.

## Quick Example

```python
from fabra.core import FeatureStore
from fabra.context import context, Context, ContextItem
from fabra.retrieval import retriever

store = FeatureStore()

# 1. Define a retriever for semantic search
# 1. Define a retriever for semantic search
@retriever(index="knowledge_base", top_k=5)
async def search_docs(query: str):
    # Magic: Automatically searches "knowledge_base" index using
    # the configured offline store (Postgres + pgvector).
    pass

# 2. Define context assembly with token budget
@context(store, max_tokens=4000)
async def chat_context(user_id: str, query: str) -> list[ContextItem]:
    docs = await search_docs(query)
    # Access store instance via global or closure if needed
    user_prefs = await store.get_feature("user_preferences", user_id)

    return [
        ContextItem(content="You are a helpful assistant.", priority=0, required=True),
        ContextItem(content=str(docs), priority=1, required=True),
        ContextItem(content=f"User preferences: {user_prefs}", priority=2),
    ]
```

## Core Concepts

### 1. Indexes

An **Index** is a collection of documents stored with vector embeddings for semantic search.

```python
# Index documents via API
await store.index(
    index_name="knowledge_base",
    entity_id="doc_123",
    text="Fabra is a feature store and context store...",
    metadata={"source": "docs", "version": "1.2.0"}
)
```

Or via HTTP:
```bash
curl -X POST http://localhost:8000/ingest/document \
  -H "Content-Type: application/json" \
  -d '{
    "index_name": "knowledge_base",
    "entity_id": "doc_123",
    "text": "Fabra is a feature store...",
    "metadata": {"source": "docs"}
  }'
```

**Automatic Features:**
- **Chunking:** Documents are split using tiktoken (default: 512 tokens per chunk).
- **Embedding:** Chunks are embedded using OpenAI or Cohere (configurable).
- **Storage:** Embeddings stored in Postgres with pgvector extension.

**Management via CLI:**
```bash
# Manually create an index
fabra index create knowledge_base --dimension 1536

# Check index status
fabra index status knowledge_base
# Output: Index: knowledge_base | Rows: 1542
```

### 2. Retrievers

A **Retriever** performs vector search and returns relevant documents.

```python
from fabra.retrieval import retriever

@retriever(index="knowledge_base", cache_ttl=300)
async def search_docs(query: str):
    # "Magic Wiring": Setting `index` connects this function directly
    # to the vector store. No body implementation needed!
    pass
```

**Parameters:**
- `cache_ttl`: Seconds to cache results (default: 0, no caching).

[Learn more about Retrievers →](retrievers.md)

### 3. Context Assembly

A **Context** combines multiple sources under a token budget.

```python
from fabra.context import context, ContextItem

@context(store, max_tokens=4000)
async def chat_context(user_id: str, query: str) -> list[ContextItem]:
    # Fetch from multiple sources
    docs = await search_docs(query)
    history = await get_chat_history(user_id)

    return [
        ContextItem(content=system_prompt, priority=0, required=True),
        ContextItem(content=str(docs), priority=1, required=True),
        ContextItem(content=history, priority=2),  # Truncated first if over budget
    ]
```

**Example: Multiple Retrievers**

```python
@retriever(name="products_search")
async def search_products(query: str) -> list[str]:
    # Implement product search logic here
    return []

@retriever(name="tickets_search")
async def search_tickets(query: str) -> list[str]:
    # Implement ticket search logic here
    return []

# Combine in context assembly
@context(store, max_tokens=4000)
async def support_context(query: str) -> list[ContextItem]:
    products = await search_products(query)
    tickets = await search_tickets(query)
    return [
        ContextItem(content=str(products), priority=1),
        ContextItem(content=str(tickets), priority=2),
    ]
```

**Priority-Based Truncation:**
- Items sorted by priority (0 = highest priority, kept first).
- Lower-priority items truncated when budget exceeded.
- `required=True` items raise `ContextBudgetError` (or return partial context with warning) if they can't fit.

[Learn more about Context Assembly →](context-assembly.md)

<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "TechArticle",
  "headline": "Fabra Context Store: RAG Infrastructure for Developers",
  "description": "Complete guide to the Fabra Context Store. Manage vector embeddings, token budgets, and context assembly for Large Language Models.",
  "articleSection": "Context Store",
  "keywords": "context store, rag, vector database, pgvector, llm token management, context assembly",
  "author": {
    "@type": "Person",
    "name": "David Ahmann"
  }
}
</script>

### 4. Event-Driven Updates

Keep context fresh by triggering updates on events.

```python
from fabra.core import feature

@feature(entity=Document, trigger="document_updated")
async def doc_summary(doc_id: str, event: AxiomEvent) -> str:
    # Re-compute summary when document changes
    return summarize(event.payload["content"])
```

Events are published via Redis Streams and consumed by `AxiomWorker`.

**Monitor Events:**
```bash
# Tail the event stream in real-time
fabra events listen --stream document_updated
```

[Learn more about Event-Driven Features →](event-driven-features.md)

## Configuration

| Variable | Description | Default |
| :--- | :--- | :--- |
| `OPENAI_API_KEY` | API key for OpenAI embeddings | Required for embeddings |
| `COHERE_API_KEY` | API key for Cohere embeddings (alternative) | Optional |
| `FABRA_EMBEDDING_MODEL` | Embedding model to use | `text-embedding-3-small` |
| `FABRA_CHUNK_SIZE` | Tokens per chunk | `512` |

### Production Tuning

| Variable | Description | Recommendation |
| :--- | :--- | :--- |
| `FABRA_EMBEDDING_CONCURRENCY` | Max concurrent embedding requests | Set to `20+` if you have high Tier limits. Default `10`. |
| `FABRA_PG_POOL_SIZE` | Postgres Connection Pool Size | Set to `10-20` for high-throughput API pods. Default `5`. |
| `FABRA_PG_MAX_OVERFLOW` | Postgres Connection Pool Overflow | Set to `20+` to handle spikes. Default `10`. |

## Architecture

```mermaid
graph LR
    Doc[Document] -->|Chunk| Chunks[Chunks]
    Chunks -->|Embed| Vectors[Vectors]
    Vectors -->|Store| PG[(Postgres + pgvector)]

    Query[Query] -->|Embed| QVec[Query Vector]
    QVec -->|Similarity| PG
    PG -->|Top-K| Results[Results]
    Results -->|Assemble| Context[Context]
```

## When to Use Context Store

**Use Context Store when:**
- Building RAG chatbots or Q&A systems
- Need semantic search over documents
- Want unified infrastructure for features + context
- Need token budget management for LLM prompts

**Use Feature Store alone when:**
- Building traditional ML models
- Only need numerical/categorical features
- No document retrieval required

## Next Steps

- [Retrievers](retrievers.md): Deep dive into vector search
- [Context Assembly](context-assembly.md): Token budgets and priority
- [Event-Driven Features](event-driven-features.md): Real-time updates
- [Use Case: RAG Chatbot](use-cases/rag-chatbot.md): End-to-end example

## 🐛 Debugging & Tracing

Fabra provides built-in observability for your context assembly. Because context is often assembled from multiple stochastic sources (vector search, cached features), understanding *why* a specific prompt was built is crucial.

### The `fabra context explain` Command

You can trace any context request by its ID:

```bash
fabra context explain ctx_12345
```

**Output:**
```json
{
  "context_id": "ctx_12345",
  "created_at": "2025-12-08T21:00:00Z",
  "latency_ms": 45.2,
  "token_usage": 3450,
  "cost_usd": 0.002,
  "freshness_status": "guaranteed",
  "source_ids": ["doc_123", "user_prefs_456"],
  "stale_sources": [],
  "cache_hit": false,
  "meta": {
    "dropped_items": 1,
    "budget_exceeded": false
  }
}
```

<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "TechArticle",
  "headline": "Context Store for LLMs: RAG Infrastructure",
  "description": "Build production RAG applications with Fabra's Context Store. Vector search with pgvector, automatic chunking, token budgets, and priority-based context assembly.",
  "author": {"@type": "Organization", "name": "Fabra Team"},
  "keywords": "context store, rag, llm, pgvector, vector search",
  "articleSection": "Documentation"
}
</script>
