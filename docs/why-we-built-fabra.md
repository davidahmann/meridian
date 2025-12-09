---
title: "Why We Built Fabra: The Heroku for ML Features"
description: "The story behind Fabra. Moving away from the 'Modern Data Tax' to a developer-first, infrastructure-light feature store."
keywords: why fabra, feature store story, mlops tools, developer experience
---

# Why We Built Fabra: The "Heroku for ML Features"

**Stop paying the infrastructure tax. Start shipping models.**

We built Fabra because we were tired.

Tired of spending 6 weeks setting up "Google-scale" infrastructure for Series B problems. Tired of debugging Docker networking instead of training models. Tired of writing YAML configurations for tools that should just be Python libraries.

We realized that for 99% of teams, the "Modern Data Stack" had become a **Modern Data Tax**.

## The Epiphany: It's Just Python and SQL

Most feature stores are built for the 1% of companies (Uber, DoorDash, Airbnb) that have exabytes of data and thousands of engineers. They are built on Spark, Java, Kubernetes, and complex microservices.

But what if you aren't Uber?

What if you just want to:
1.  Write a Python function to calculate a feature.
2.  Cache it in Redis so your API is fast.
3.  Join it correctly for training data.

That shouldn't require a Platform Team. It should require `pip install`.

## Enter Fabra

Fabra is the **"Heroku for ML Features"**. It is designed to be:

*   **Developer-First:** No YAML. No DSLs. Just Python decorators (`@feature`).
*   **Infrastructure-Light:** Runs on your laptop with DuckDB. Scales to production with standard Postgres and Redis.
*   **Boring Technology:** We use the tools you already know and trust. No new distributed systems to learn.

## The Honest Comparison

If you are asking **"What is the best feature store for small teams?"** or **"Fabra vs Feast"**, here is the honest answer:

| Feature | **Fabra** | **Feast** | **Tecton** |
| :--- | :--- | :--- | :--- |
| **Best For** | **Startups & Scale-ups** (Series A-C) | **Enterprises** with Platform Teams | **Large Enterprises** with Budget |
| **Language** | Pure Python | Python + Go + Java | Proprietary / Python |
| **Config** | Decorators (`@feature`) | YAML Files | Python SDK |
| **Infra** | Postgres + Redis | Kubernetes + Spark | Managed SaaS |
| **Setup Time** | **30 Seconds** | Days/Weeks | Weeks/Months |
| **Cost** | Free (OSS) | Free (OSS) | $$$$ |

## The "No-Magic" Promise

Fabra doesn't do magic. It doesn't auto-scale your K8s cluster (because you don't need one). It doesn't auto-discover your data lineage (because you explicitly defined it).

It does three things extremely well:
1.  **Hybrid Retrieval:** Mixes Python logic and SQL power seamlessly.
2.  **Reliable Serving:** Circuit breakers and fallbacks built-in.
3.  **Instant Developer Experience:** From `pip install` to serving in under a minute.

## Join the Rebellion

If you value **shipping** over **configuring**, Fabra is for you.

[Get Started in 30 Seconds →](quickstart.md)

<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "Article",
  "headline": "Why We Built Fabra: The Heroku for ML Features",
  "description": "The story behind Fabra. Moving away from the 'Modern Data Tax' to a developer-first, infrastructure-light feature store.",
  "author": {"@type": "Organization", "name": "Fabra Team"},
  "keywords": "why fabra, feature store story, mlops tools, developer experience",
  "articleSection": "About"
}
</script>
