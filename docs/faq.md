# Frequently Asked Questions

## General

### Q: Is Meridian production-ready?
**A:** Yes. Meridian runs on "boring technology" (Postgres + Redis) that powers 90% of the internet. It is designed for high-throughput, low-latency serving in production environments.

### Q: Do I need Kubernetes?
**A:** No. You can deploy Meridian on Heroku, Railway, AWS ECS, or even a single EC2 instance using Docker Compose. If you *want* to use Kubernetes, you can, but it is not a requirement.

### Q: How does Meridian compare to Feast?
**A:** Meridian is a lightweight alternative to Feast. We provide the same core guarantees (Point-in-Time Correctness, Async I/O) but without the complexity of Kubernetes, Spark, or Docker registries. See [Meridian vs Feast](feast-alternative.md) for a detailed comparison.

## Technical

### Q: Can Meridian handle real-time features?
**A:** Yes.
1.  **Cached Features:** Served from Redis in <5ms.
2.  **Computed Features:** Python functions executed on-the-fly (e.g., Haversine distance).
3.  **Streaming:** You can materialize data from Kafka/Flink into Postgres, and Meridian will serve it via the SQL path.

### Q: What if I outgrow a single Postgres instance?
**A:** You can switch your Offline Store to Snowflake, BigQuery, or Redshift just by changing the connection string. Your feature definitions and Online Store (Redis) remain exactly the same.

### Q: Why not just write to Redis directly?
**A:** You can, but you lose:
1.  **Point-in-Time Correctness:** Redis only knows "now". It cannot generate historical training data without leakage.
2.  **Schema Evolution:** Changing a feature definition in Meridian is a code change. In raw Redis, it's a migration nightmare.
3.  **Observability:** Meridian provides built-in metrics for hit rates, latency, and staleness.

### Q: Why not just use dbt?
**A:** dbt is excellent for *batch* transformations in the warehouse, but it cannot serve *individual rows* to a live API with low latency. Meridian bridges the gap between your dbt models (Offline) and your production API (Online).

## Operations

### Q: How do I migrate from Local to Production?
**A:** It's a configuration change, not a code change.
1.  Set `MERIDIAN_ENV=production`.
2.  Provide `MERIDIAN_POSTGRES_URL` and `MERIDIAN_REDIS_URL`.
3.  Deploy.
See [Local to Production](local-to-production.md) for a guide.
