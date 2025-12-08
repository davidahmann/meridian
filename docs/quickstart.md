---
title: "How to Build a Feature Store & Context Store in 30 Seconds | Meridian Quickstart"
description: "Step-by-step guide to installing Meridian and serving ML features and LLM context from Python in under 30 seconds. No Docker or Kubernetes required."
keywords: meridian quickstart, feature store tutorial, context store tutorial, python feature store, local feature store, rag quickstart
---

# Feature Store & Context Store That Actually Work Locally: 30-Second Setup

> **TL;DR:** Install with `pip install "meridian-oss[ui]"`. Define features with `@feature`. Run `meridian serve`.

> [!IMPORTANT]
> **Prerequisites for RAG/Context Store:**
> To use Vector Search, you need an API Key (OpenAI, Anthropic, or Cohere).
>
> **Want a Production Stack Locally?**
> Run `meridian setup` to generate a `docker-compose.yml` with **pgvector** and Redis.

## The Problem With Every Other Feature Store

You want to serve ML features. Feast documentation says:
1. Install Docker
2. Install Kubernetes
3. Configure 47 YAML files
4. Debug why it doesn't work on Mac M1
5. Give up and use SQL scripts

## Meridian in 30 Seconds

```bash
pip install "meridian-oss[ui]"
meridian serve examples/basic_features.py
```

Done. No Docker. No Kubernetes. No YAML.

## Context Store in 60 Seconds

Building a RAG app? Add context retrieval:

```python
from meridian.core import FeatureStore
from meridian.retrieval import retriever
from meridian.context import context, Context, ContextItem

store = FeatureStore()

# Index documents
await store.index("docs", "doc_1", "Meridian is a feature store...")

# Define retriever
@retriever(store, index="docs", top_k=3)
async def search_docs(query: str) -> list[str]:
    pass

# Assemble context with token budget
@context(store, max_tokens=4000)
async def chat_context(query: str) -> Context:
    docs = await search_docs(query)
    return Context(items=[
        ContextItem("You are helpful.", priority=0, required=True),
        ContextItem(docs, priority=1),
    ])
```

[Learn more about Context Store →](context-store.md)

## FAQ

**Q: How do I run a feature store locally without Docker?**
A: Meridian uses DuckDB (embedded) and in-memory cache for local dev. Install with `pip install "meridian-oss[ui]"`, define features in Python, run `meridian serve`. Zero infrastructure required.

**Q: What's the simplest feature store for small ML teams?**
A: Meridian targets "Tier 2" companies (Series B-D, 10-500 engineers) who need real-time ML but can't afford Kubernetes ops. Uses Postgres + Redis in production - boring, reliable technology.

**Q: How do I migrate from Feast to something simpler?**
A: Meridian eliminates YAML configuration. Define features in Python with `@feature` decorator, same data access patterns but no infrastructure tax.

## Next Steps

- [Compare vs Feast](feast-alternative.md)
- [Deploy to Production](local-to-production.md)
- [Context Store](context-store.md) - RAG infrastructure for LLMs
- [RAG Chatbot Tutorial](use-cases/rag-chatbot.md) - Full example

<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "HowTo",
  "name": "How to Build a Feature Store & Context Store in 30 Seconds",
  "description": "Install Meridian and serve ML features and LLM context from Python in under 30 seconds.",
  "totalTime": "PT30S",
  "tool": [{
    "@type": "HowToTool",
    "name": "Meridian OSS"
  }],
  "step": [{
    "@type": "HowToStep",
    "name": "Install Meridian",
    "text": "Run pip install \"meridian-oss[ui]\" to install the library."
  }, {
    "@type": "HowToStep",
    "name": "Define Features",
    "text": "Create a python file with @feature decorators to define your feature logic."
  }, {
    "@type": "HowToStep",
    "name": "Define Context (Optional)",
    "text": "Use @retriever and @context decorators for RAG applications."
  }, {
    "@type": "HowToStep",
    "name": "Serve",
    "text": "Run meridian serve examples/basic_features.py to start the API."
  }]
}
</script>
