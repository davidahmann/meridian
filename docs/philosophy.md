---
title: "Fabra Philosophy: The 95% Rule, Local-First Design, and Unified Context"
description: "Why we built Fabra. The 'Heroku for ML Features' philosophy: prioritizing developer experience, simple infrastructure, and unified feature+context over Google-scale complexity."
keywords: fabra philosophy, feature store design, context store design, mlops philosophy, local-first software, rag philosophy
---

# Philosophy & Trade-offs

We built Fabra because we were tired of "Google-scale" tools for Series B problems. Here is the honest truth about why we made these design choices and who they are for.

## The 95% Rule

**95% of feature serving is just:**
```sql
SELECT COUNT(*) FROM events
WHERE user_id = ?
AND timestamp > NOW() - INTERVAL '1 hour'
```
Cached in Redis. Refreshed every 5 minutes. Served in <5ms.

That's it. You don't need Spark. You don't need Kafka. You don't need Kubernetes.

Fabra is optimized for this 95%. If you need the other 5% (sub-second streaming, complex DAGs), you should use Tecton or Feast.

## Why Not Just Redis?

A common question is: *"Why do I need a feature store? Can't I just write to Redis?"*

You can, and for simple apps, you should. But here is where raw Redis breaks down for ML:

1.  **Point-in-Time Correctness:** Redis only knows "now". It doesn't know "what was the value of this feature 3 months ago?" Fabra logs feature values to the Offline Store (Postgres/DuckDB) so you can generate training data that is historically accurate.
2.  **Schema Evolution:** What happens when you change a feature definition? With raw Redis, you have to write a migration script. With Fabra, you just update the `@feature` decorator.
3.  **Observability:** Fabra automatically tracks cache hit rates, latency, and staleness. Raw Redis is a black box.

## Why Not Just dbt?

dbt is fantastic for batch transformations. We love dbt. But dbt stops at the data warehouse.

*   **dbt** creates **tables** (e.g., `daily_user_stats`).
*   **Fabra** serves **rows** (e.g., `user_id: 123`).

If you only need features refreshed once a day, dbt is enough. But if you need to serve those features to a live API with <10ms latency, you need a serving layer. Fabra bridges that gap.

## Why Context Store?

With the rise of LLMs, we saw teams building parallel infrastructure:

1. **Feature Store** for ML models (fraud, recommendations)
2. **Vector Database** for RAG (Pinecone, Weaviate)
3. **Glue Code** to combine them (LangChain chains)

This is the same complexity trap. Three systems to maintain, three sets of credentials, three failure modes.

**Fabra's Context Store** unifies this:

*   **Same Postgres:** Features in tables, embeddings in pgvector.
*   **Same Redis:** Feature cache and retriever cache.
*   **Same API:** `/features` and `/context` from one server.
*   **Same Decorators:** `@feature`, `@retriever`, `@context`.

If you're building an LLM app that needs user personalization (features) + document retrieval (context), you don't need two systems. You need Fabra.

## The "Confession"

We didn't start by building Fabra. We started by trying to use existing tools.

We spent 6 weeks setting up a popular open-source feature store. We fought with Docker networking, Kubernetes manifests, and registry sync issues. We realized we were spending 90% of our time on infrastructure and 10% on ML.

So we gave up.

We built Fabra in 2 weeks with a simple goal: **"It must run in a Jupyter notebook with `pip install`."**

If you value "works on my laptop" over "scales to exabytes", Fabra is for you.

<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "TechArticle",
  "headline": "Fabra Philosophy: The 95% Rule, Local-First Design, and Unified Context",
  "description": "Why we built Fabra. The 'Heroku for ML Features' philosophy: prioritizing developer experience, simple infrastructure, and unified feature+context over Google-scale complexity.",
  "author": {"@type": "Organization", "name": "Fabra Team"},
  "keywords": "fabra philosophy, feature store design, local-first software, mlops",
  "articleSection": "Philosophy"
}
</script>
