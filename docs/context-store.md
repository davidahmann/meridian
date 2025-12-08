---
title: "Context Store for LLMs: RAG Infrastructure | Meridian"
description: "Build production RAG applications with Meridian's Context Store. Vector search with pgvector, automatic chunking, token budgets, and priority-based context assembly."
keywords: context store, rag infrastructure, llm context, pgvector, vector search, token budget, context assembly, retrieval augmented generation
---

# Context Store for LLMs

> **TL;DR:** Meridian's Context Store is RAG infrastructure that actually works. Index documents, search with pgvector, and assemble context with token budgets—all with Python decorators.

## Why Context Store?

Building LLM applications requires more than just features. You need:

1. **Document Indexing:** Store and chunk documents for retrieval.
2. **Vector Search:** Find semantically relevant content.
3. **Context Assembly:** Combine retrieved docs with user data under token limits.
4. **Freshness:** Update context when documents change.

Most teams cobble together Pinecone + LangChain + custom glue code. Meridian provides all of this in one unified system that shares infrastructure with your Feature Store.

## Quick Example

```python
from meridian.core import FeatureStore
from meridian.retrieval import retriever
from meridian.context import context, Context, ContextItem

store = FeatureStore()

# 1. Define a retriever for semantic search
@retriever(store, index="knowledge_base", top_k=5)
async def search_docs(query: str) -> list[str]:
    # Meridian handles vector search automatically
    pass

# 2. Define context assembly with token budget
@context(store, max_tokens=4000)
async def chat_context(user_id: str, query: str) -> Context:
    docs = await search_docs(query)
    user_prefs = await store.get_feature("user_preferences", user_id)

    return Context(items=[
        ContextItem("You are a helpful assistant.", priority=0, required=True),
        ContextItem(docs, priority=1, required=True),
        ContextItem(f"User preferences: {user_prefs}", priority=2),
    ])
```

## Core Concepts

### 1. Indexes

An **Index** is a collection of documents stored with vector embeddings for semantic search.

```python
# Index documents via API
await store.index(
    index_name="knowledge_base",
    entity_id="doc_123",
    text="Meridian is a feature store and context store...",
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
    "text": "Meridian is a feature store...",
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
meridian index create knowledge_base --dimension 1536

# Check index status
meridian index status knowledge_base
# Output: Index: knowledge_base | Rows: 1542
```

### 2. Retrievers

A **Retriever** performs vector search and returns relevant documents.

```python
from meridian.retrieval import retriever

@retriever(store, index="knowledge_base", top_k=5, cache_ttl=300)
async def search_docs(query: str) -> list[str]:
    # The decorator handles:
    # 1. Embedding the query
    # 2. Vector similarity search via pgvector
    # 3. Caching results in Redis for cache_ttl seconds
    pass
```

**Parameters:**
- `index`: Name of the index to search.
- `top_k`: Number of results to return.
- `cache_ttl`: Seconds to cache results (default: 0, no caching).

[Learn more about Retrievers →](retrievers.md)

### 3. Context Assembly

A **Context** combines multiple sources under a token budget.

```python
from meridian.context import context, Context, ContextItem

@context(store, max_tokens=4000)
async def chat_context(user_id: str, query: str) -> Context:
    # Fetch from multiple sources
    docs = await search_docs(query)
    history = await get_chat_history(user_id)

    return Context(items=[
        ContextItem(system_prompt, priority=0, required=True),
        ContextItem(docs, priority=1, required=True),
        ContextItem(history, priority=2),  # Truncated first if over budget
    ])
```

**Priority-Based Truncation:**
- Items sorted by priority (0 = highest priority, kept first).
- Lower-priority items truncated when budget exceeded.
- `required=True` items raise `ContextBudgetError` if they can't fit.

[Learn more about Context Assembly →](context-assembly.md)

### 4. Event-Driven Updates

Keep context fresh by triggering updates on events.

```python
from meridian.core import feature

@feature(entity=Document, trigger="document_updated")
async def doc_summary(doc_id: str, event: AxiomEvent) -> str:
    # Re-compute summary when document changes
    return summarize(event.payload["content"])
```

Events are published via Redis Streams and consumed by `AxiomWorker`.

**Monitor Events:**
```bash
# Tail the event stream in real-time
meridian events listen --stream document_updated
```

[Learn more about Event-Driven Features →](event-driven-features.md)

## Configuration

| Variable | Description | Default |
| :--- | :--- | :--- |
| `OPENAI_API_KEY` | API key for OpenAI embeddings | Required for embeddings |
| `COHERE_API_KEY` | API key for Cohere embeddings (alternative) | Optional |
| `MERIDIAN_EMBEDDING_MODEL` | Embedding model to use | `text-embedding-3-small` |
| `MERIDIAN_CHUNK_SIZE` | Tokens per chunk | `512` |

### Production Tuning

| Variable | Description | Recommendation |
| :--- | :--- | :--- |
| `MERIDIAN_EMBEDDING_CONCURRENCY` | Max concurrent embedding requests | Set to `20+` if you have high Tier limits. Default `10`. |
| `MERIDIAN_PG_POOL_SIZE` | Postgres Connection Pool Size | Set to `10-20` for high-throughput API pods. Default `5`. |
| `MERIDIAN_PG_MAX_OVERFLOW` | Postgres Connection Pool Overflow | Set to `20+` to handle spikes. Default `10`. |

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

Meridian provides built-in observability for your context assembly. Because context is often assembled from multiple stochastic sources (vector search, cached features), understanding *why* a specific prompt was built is crucial.

### The `meridian context` Command

You can trace any context request by its ID:

```bash
meridian context ctx_12345
```

**Output:**
```json
{
  "context_id": "ctx_12345",
  "total_tokens": 3450,
  "budget": 4000,
  "items": [
    {
      "priority": 0,
      "tokens": 150,
      "content": "System Prompt...",
      "status": "INCLUDED"
    },
    {
      "priority": 2,
      "tokens": 500,
      "content": "User Preferences...",
      "status": "DROPPED (Budget Exceeded)"
    }
  ]
}
```

<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "TechArticle",
  "headline": "Context Store for LLMs: RAG Infrastructure",
  "description": "Build production RAG applications with Meridian's Context Store. Vector search with pgvector, automatic chunking, token budgets, and priority-based context assembly.",
  "author": {"@type": "Organization", "name": "Meridian Team"},
  "keywords": "context store, rag, llm, pgvector, vector search",
  "articleSection": "Documentation"
}
</script>
