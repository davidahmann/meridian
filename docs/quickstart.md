---
title: "How to Build a Feature Store in 30 Seconds | Meridian Quickstart"
description: "Step-by-step guide to installing Meridian and serving ML features from Python in under 30 seconds. No Docker or Kubernetes required."
keywords: meridian quickstart, feature store tutorial, python feature store, local feature store
---

# Feature Store That Actually Works Locally: 30-Second Setup

> **TL;DR:** Install with `pip install "meridian-oss[ui]"`. Define features in a Python file using `@feature`. Run `meridian serve`. No Docker or YAML required.

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

<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "HowTo",
  "name": "How to Build a Feature Store in 30 Seconds",
  "description": "Install Meridian and serve ML features from Python in under 30 seconds.",
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
    "name": "Serve",
    "text": "Run meridian serve examples/basic_features.py to start the API."
  }]
}
</script>
