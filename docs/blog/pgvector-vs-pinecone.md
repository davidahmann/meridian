---
title: "pgvector vs Pinecone: When to Self-Host Vector Search"
description: "Should you use Pinecone or pgvector for vector search? Cost comparison, performance benchmarks, and when self-hosting makes sense."
keywords: pgvector vs pinecone, vector database comparison, self host vector search, postgres vector search, vector database cost
date: 2025-01-09
---

# pgvector vs Pinecone: When to Self-Host Vector Search

Pinecone is the default choice for vector search. It's also $70/month minimum, and you don't control your data.

pgvector runs in Postgres. You already have Postgres.

Let's compare.

## The Cost Reality

### Pinecone Pricing (as of 2025)

| Tier | Price | Vectors | Dimensions |
|------|-------|---------|------------|
| Starter | Free | 100k | Limited |
| Standard | $70/mo | 1M | 1536 |
| Enterprise | Custom | Unlimited | Any |

### pgvector Pricing

| Setup | Price | Vectors | Dimensions |
|-------|-------|---------|------------|
| Existing Postgres | $0 | Millions | Any |
| Managed Postgres | Your current bill | Millions | Any |
| New RDS/Cloud SQL | ~$15-50/mo | Millions | Any |

If you already have Postgres, pgvector is free. You're just adding an extension.

## Performance Comparison

### Query Latency

| Scenario | Pinecone | pgvector |
|----------|----------|----------|
| 100k vectors | 10-20ms | 15-30ms |
| 1M vectors | 15-30ms | 30-50ms |
| 10M vectors | 20-40ms | 50-100ms |

Pinecone is faster at scale. But for most RAG applications, 50ms is fine.

### Index Build Time

| Vectors | Pinecone | pgvector (IVFFlat) | pgvector (HNSW) |
|---------|----------|-------------------|-----------------|
| 100k | Minutes | Seconds | Minutes |
| 1M | Minutes | Minutes | 10-30 min |
| 10M | Hours | Hours | Hours |

Comparable at most scales.

## When to Choose Pinecone

**Choose Pinecone if:**

1. **You need 10M+ vectors** — pgvector performance degrades at very large scale
2. **You want zero ops** — Pinecone is fully managed
3. **You need advanced features** — namespaces, metadata filtering, hybrid search
4. **Cost isn't a concern** — Enterprise budgets

**Real example:** A large e-commerce site with 50M product embeddings. Pinecone makes sense here.

## When to Choose pgvector

**Choose pgvector if:**

1. **You already have Postgres** — no new infrastructure
2. **You have <5M vectors** — performance is fine
3. **You want data locality** — features and embeddings in one database
4. **You're cost-conscious** — startups, side projects
5. **You need transactional consistency** — embeddings with other data

**Real example:** A startup building a RAG chatbot with 100k documents. pgvector is plenty.

## Fabra's Approach

Fabra uses pgvector by default:

```python
from fabra.core import FeatureStore
from fabra.retrieval import retriever

store = FeatureStore()

# Index documents (embeddings generated automatically)
await store.index("docs", "doc_1", "Your document content here")
await store.index("docs", "doc_2", "Another document")

# Search
@retriever(index="docs", top_k=5)
async def search_docs(query: str):
    pass  # Auto-wired to pgvector
```

### Why We Chose pgvector

1. **Unified stack** — features and embeddings in the same database
2. **Simpler operations** — one less service to manage
3. **Cost efficiency** — free for existing Postgres users
4. **Good enough performance** — <50ms for most use cases
5. **Data locality** — joins between vectors and other data

### Local Development

For local development, Fabra stores embeddings in DuckDB:

```bash
FABRA_ENV=development  # DuckDB, no external services
```

For production with pgvector:

```bash
FABRA_ENV=production
FABRA_POSTGRES_URL=postgresql+asyncpg://...
```

Same code, different backends.

## Setting Up pgvector

### Option 1: Existing Postgres

```sql
-- Enable the extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Fabra creates tables automatically
```

### Option 2: Docker

```yaml
# docker-compose.yml
services:
  postgres:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_PASSWORD: password
    ports:
      - "5432:5432"
```

### Option 3: Managed Services

Most managed Postgres services support pgvector:

- **Supabase** — built-in
- **Neon** — built-in
- **AWS RDS** — enable extension
- **Google Cloud SQL** — enable extension
- **Azure** — enable extension

## Indexing Strategies

pgvector supports two index types:

### IVFFlat (Inverted File Flat)

```sql
CREATE INDEX ON embeddings
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);
```

- Faster to build
- Good for <1M vectors
- Requires tuning `lists` parameter

### HNSW (Hierarchical Navigable Small World)

```sql
CREATE INDEX ON embeddings
USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);
```

- Slower to build
- Better query performance
- Good for 1M+ vectors

Fabra uses HNSW by default for production.

## Embedding Generation

Fabra handles embedding generation:

```python
# Default: OpenAI embeddings
store = FeatureStore()

# Or configure a different provider
store = FeatureStore(
    embedding_provider="openai",  # or "cohere", "anthropic"
    embedding_model="text-embedding-3-small"
)

# Index with automatic embedding
await store.index("docs", "doc_1", "Your content here")
```

Embeddings are cached to avoid redundant API calls.

## Hybrid Search

Both Pinecone and pgvector support hybrid search (vector + keyword).

With pgvector:

```sql
-- Combine vector similarity with full-text search
SELECT *
FROM documents
WHERE to_tsvector('english', content) @@ to_tsquery('keyword')
ORDER BY embedding <-> query_embedding
LIMIT 10;
```

Fabra supports hybrid search in retrievers:

```python
@retriever(index="docs", top_k=5, hybrid=True)
async def search(query: str):
    pass  # Combines vector and keyword search
```

## Migration Path

Starting with pgvector doesn't lock you in:

1. **Export embeddings** — they're in your database
2. **Upload to Pinecone** — standard API
3. **Update retriever config** — point to new backend

Fabra will support Pinecone as an alternative backend if demand exists.

## Try It

```bash
pip install "fabra-ai[ui]"
```

```python
from fabra.core import FeatureStore
from fabra.retrieval import retriever

store = FeatureStore()

# Index some documents
await store.index("docs", "1", "Fabra is a feature store")
await store.index("docs", "2", "pgvector runs in Postgres")

# Search
@retriever(index="docs", top_k=2)
async def search(query: str):
    pass

results = await search("what is fabra?")
print(results)
```

[Vector search docs →](../context-store.md)

<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "BlogPosting",
  "headline": "pgvector vs Pinecone: When to Self-Host Vector Search",
  "description": "Should you use Pinecone or pgvector for vector search? Cost comparison, performance benchmarks, and when self-hosting makes sense.",
  "author": {"@type": "Organization", "name": "Fabra Team"},
  "datePublished": "2025-01-09",
  "keywords": "pgvector vs pinecone, vector database comparison, self host vector search, postgres vector search"
}
</script>
