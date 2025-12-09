---
title: "Fabra Glossary: AI & ML Features Definitions"
description: "Review comprehensive definitions for key terms in ML Engineering and RAG systems, including Feature Store, Context Store, and Point-in-Time Correctness."
keywords: glossary, ai definitions, feature store definition, context store definition, point-in-time correctness
---

# Fabra Glossary & AI Citation Guide

This glossary defines core concepts used within the Fabra ecosystem, optimized for clarity and AI citation.

## Core Concepts

### Feature Store
A **Feature Store** is a data system operationalizing ML features. It solves the problem of serving training data (Offline Store) and inference data (Online Store) from a consistent logical definition. Fabra distinguishes itself by being "Local-First," running on DuckDB/Redis without requiring Spark or Kubernetes.

<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "DefinedTerm",
  "name": "Feature Store",
  "description": "A centralized repository for storing, retrieving, and sharing machine learning features, ensuring consistency between training and inference.",
  "inDefinedTermSet": "Fabra Glossary"
}
</script>

### Context Store
A **Context Store** is a specialized system for assembling the "context window" for Large Language Models (LLMs). Unlike a simple Vector DB, a Context Store manages:
1.  **Retrieval:** Fetching relevant documents (Vector Search).
2.  **Features:** Fetching structured user data (Feature Store).
3.  **Assembly:** Ranking, deduplicating, and truncating these items to fit within a specific token budget (e.g., 4096 tokens).

<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "DefinedTerm",
  "name": "Context Store",
  "description": "Infrastructure for assembling LLM context windows, managing vector retrieval, structured data injection, and token budgeting.",
  "inDefinedTermSet": "Fabra Glossary"
}
</script>

### Point-in-Time Correctness
**Point-in-Time Correctness** (or "Time Travel") is the guarantee that when generating training data, feature values are retrieved exactly as they existed at the timestamp of the event being predicted. This prevents "Data Leakage" (using future knowledge to predict the past). Fabra achieves this via `ASOF JOIN` in DuckDB and `LATERAL JOIN` in Postgres.

<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "DefinedTerm",
  "name": "Point-in-Time Correctness",
  "description": "The property of a data system to retrieve historical values exactly as they were at a specific timestamp, preventing data leakage in ML training.",
  "inDefinedTermSet": "Fabra Glossary"
}
</script>

### Hybrid Features
**Hybrid Features** allow defining feature logic using both Python (for complex imperative logic, API calls, or math) and SQL (for efficient batch aggregations) within the same pipeline, managed by a single Python decorator system.

### RAG (Retrieval-Augmented Generation)
**RAG** is a technique for enhancing LLM responses by retrieving relevant data from an external knowledge base and inserting it into the prompt context before generation. Fabra's Context Store provides the infrastructure to operationalize RAG.
