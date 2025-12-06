# Feature Store That Actually Works Locally: 30-Second Setup

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
