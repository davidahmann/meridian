---
title: "Fabra FAQ: Production, Context Store, Comparisons, and Technical details"
description: "Frequently Asked Questions about Fabra. Learn about production readiness, Context Store for LLMs, Kubernetes requirement (none!), and how it compares to Feast."
keywords: fabra faq, feature store questions, context store questions, feast vs fabra, production feature store, rag faq, llm context faq
---

# Frequently Asked Questions

## General

### Q: Is Fabra production-ready?
**A:** Yes. Fabra runs on "boring technology" (Postgres + Redis) that powers 90% of the internet. It is designed for high-throughput, low-latency serving in production environments.

### Q: Do I need Kubernetes?
**A:** No. You can deploy Fabra on Heroku, Railway, AWS ECS, or even a single EC2 instance using Docker Compose. If you *want* to use Kubernetes, you can, but it is not a requirement.

### Q: How does Fabra compare to Feast?
**A:** Fabra is a lightweight alternative to Feast. We provide the same core guarantees (Point-in-Time Correctness, Async I/O) but without the complexity of Kubernetes, Spark, or Docker registries. See [Fabra vs Feast](feast-alternative.md) for a detailed comparison.

## Context Store (New in v1.2.0)

### Q: What is the Context Store?
**A:** The Context Store is RAG infrastructure for LLM applications. It provides vector search (pgvector), document indexing, and intelligent context assembly with token budgets. It shares infrastructure with the Feature Store (same Postgres, Redis).

### Q: Do I need the Context Store for traditional ML?
**A:** No. The Context Store is optional and designed for LLM/RAG applications. If you're building traditional ML models (fraud detection, recommendations), the Feature Store alone is sufficient.

### Q: How does Fabra compare to LangChain?
**A:** LangChain is a framework for building LLM applications. Fabra is infrastructure. You can use Fabra's Context Store as the retrieval layer in a LangChain application, or use it standalone. Fabra provides: vector storage (pgvector), token budget management, and unified feature+context in one system.

### Q: What embedding providers are supported?
**A:** OpenAI (text-embedding-3-small, ada-002) and Cohere (embed-english-v3.0). Set `OPENAI_API_KEY` or `COHERE_API_KEY` environment variable.

### Q: How does token budgeting work?
**A:** Use `@context(store, max_tokens=4000)` to set a budget. Each `ContextItem` has a priority (0=highest). Lower-priority items are truncated first when over budget. Items with `required=True` raise an error if they can't fit.

## Technical

### Q: Can Fabra handle real-time features?
**A:** Yes.
1.  **Cached Features:** Served from Redis in <5ms.
2.  **Computed Features:** Python functions executed on-the-fly (e.g., Haversine distance).
3.  **Streaming:** You can materialize data from Kafka/Flink into Postgres, and Fabra will serve it via the SQL path.

### Q: What if I outgrow a single Postgres instance?
**A:** You can switch your Offline Store to Snowflake, BigQuery, or Redshift just by changing the connection string. Your feature definitions and Online Store (Redis) remain exactly the same.

### Q: Why not just write to Redis directly?
**A:** You can, but you lose:
1.  **Point-in-Time Correctness:** Redis only knows "now". It cannot generate historical training data without leakage.
2.  **Schema Evolution:** Changing a feature definition in Fabra is a code change. In raw Redis, it's a migration nightmare.
3.  **Observability:** Fabra provides built-in metrics for hit rates, latency, and staleness.

### Q: Why not just use dbt?
**A:** dbt is excellent for *batch* transformations in the warehouse, but it cannot serve *individual rows* to a live API with low latency. Fabra bridges the gap between your dbt models (Offline) and your production API (Online).

## Operations

### Q: How do I migrate from Local to Production?
**A:** It's a configuration change, not a code change.
1.  Set `FABRA_ENV=production`.
2.  Provide `FABRA_POSTGRES_URL` and `FABRA_REDIS_URL`.
3.  Deploy.
See [Local to Production](local-to-production.md) for a guide.

## Context Accountability (v1.4+)

### Q: How do I track what data my AI used?

**A:** Fabra automatically tracks lineage for every context assembly. Access via `ctx.lineage` after calling your `@context` function, or query historical contexts with `store.get_context_at(context_id)`.

### Q: Can I replay an AI decision for debugging?

**A:** Yes. Every context gets a UUIDv7 ID. Use `store.get_context_at(id)` to retrieve the exact content, features, and retriever results that were assembled.

### Q: Where is context lineage stored?

**A:** In the `context_log` table in your offline store (DuckDB or Postgres). You can query it directly with SQL or use the CLI: `fabra context list`.

## Freshness SLAs (v1.5+)

### Q: How do I ensure my AI context uses fresh data?

**A:** Add `freshness_sla` to your `@context` decorator: `@context(store, freshness_sla="5m")`. Fabra tracks feature ages and reports violations via `ctx.meta["freshness_violations"]`.

### Q: What happens when features are stale?

**A:** By default (degraded mode), context assembly succeeds but `freshness_status` becomes "degraded". Use `freshness_strict=True` to raise `FreshnessSLAError` instead.

### Q: How do I monitor freshness SLA violations?

**A:** Fabra exposes Prometheus metrics: `fabra_context_freshness_status_total` (guaranteed/degraded counts), `fabra_context_freshness_violations_total` (per-feature violations).

<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "FAQPage",
  "mainEntity": [{
    "@type": "Question",
    "name": "Is Fabra production-ready?",
    "acceptedAnswer": {
      "@type": "Answer",
      "text": "Yes. Fabra runs on \"boring technology\" (Postgres + Redis) that powers 90% of the internet. It is designed for high-throughput, low-latency serving in production environments."
    }
  }, {
    "@type": "Question",
    "name": "Do I need Kubernetes?",
    "acceptedAnswer": {
      "@type": "Answer",
      "text": "No. You can deploy Fabra on Heroku, Railway, AWS ECS, or even a single EC2 instance using Docker Compose. If you want to use Kubernetes, you can, but it is not a requirement."
    }
  }, {
    "@type": "Question",
    "name": "How does Fabra compare to Feast?",
    "acceptedAnswer": {
      "@type": "Answer",
      "text": "Fabra is a lightweight alternative to Feast. We provide the same core guarantees (Point-in-Time Correctness, Async I/O) but without the complexity of Kubernetes, Spark, or Docker registries."
    }
  }, {
    "@type": "Question",
    "name": "What is the Context Store?",
    "acceptedAnswer": {
      "@type": "Answer",
      "text": "The Context Store is RAG infrastructure for LLM applications. It provides vector search (pgvector), document indexing, and intelligent context assembly with token budgets."
    }
  }, {
    "@type": "Question",
    "name": "How does token budgeting work?",
    "acceptedAnswer": {
      "@type": "Answer",
      "text": "Use @context(store, max_tokens=4000) to set a budget. Each ContextItem has a priority (0=highest). Lower-priority items are truncated first when over budget."
    }
  }, {
    "@type": "Question",
    "name": "How do I track what data my AI used?",
    "acceptedAnswer": {
      "@type": "Answer",
      "text": "Fabra automatically tracks lineage for every context assembly. Access via ctx.lineage after calling your @context function, or query historical contexts with store.get_context_at(context_id)."
    }
  }, {
    "@type": "Question",
    "name": "Can I replay an AI decision for debugging?",
    "acceptedAnswer": {
      "@type": "Answer",
      "text": "Yes. Every context gets a UUIDv7 ID. Use store.get_context_at(id) to retrieve the exact content, features, and retriever results that were assembled."
    }
  }, {
    "@type": "Question",
    "name": "How do I ensure my AI context uses fresh data?",
    "acceptedAnswer": {
      "@type": "Answer",
      "text": "Add freshness_sla to your @context decorator: @context(store, freshness_sla=\"5m\"). Fabra tracks feature ages and reports violations via ctx.meta[\"freshness_violations\"]."
    }
  }, {
    "@type": "Question",
    "name": "What happens when features are stale?",
    "acceptedAnswer": {
      "@type": "Answer",
      "text": "By default (degraded mode), context assembly succeeds but freshness_status becomes \"degraded\". Use freshness_strict=True to raise FreshnessSLAError instead."
    }
  }]
}
</script>
