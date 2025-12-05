# Philosophy & Trade-offs

We built Meridian because we were tired of "Google-scale" tools for Series B problems. Here is the honest truth about why we made these design choices and who they are for.

## The 95% Rule

**95% of feature serving is just:**
```sql
SELECT COUNT(*) FROM events
WHERE user_id = ?
AND timestamp > NOW() - INTERVAL '1 hour'
```
Cached in Redis. Refreshed every 5 minutes. Served in <5ms.

That's it. You don't need Spark. You don't need Kafka. You don't need Kubernetes.

Meridian is optimized for this 95%. If you need the other 5% (sub-second streaming, complex DAGs), you should use Tecton or Feast.

## Why Not Just Redis?

A common question is: *"Why do I need a feature store? Can't I just write to Redis?"*

You can, and for simple apps, you should. But here is where raw Redis breaks down for ML:

1.  **Point-in-Time Correctness:** Redis only knows "now". It doesn't know "what was the value of this feature 3 months ago?" Meridian logs feature values to the Offline Store (Postgres/DuckDB) so you can generate training data that is historically accurate.
2.  **Schema Evolution:** What happens when you change a feature definition? With raw Redis, you have to write a migration script. With Meridian, you just update the `@feature` decorator.
3.  **Observability:** Meridian automatically tracks cache hit rates, latency, and staleness. Raw Redis is a black box.

## Why Not Just dbt?

dbt is fantastic for batch transformations. We love dbt. But dbt stops at the data warehouse.

*   **dbt** creates **tables** (e.g., `daily_user_stats`).
*   **Meridian** serves **rows** (e.g., `user_id: 123`).

If you only need features refreshed once a day, dbt is enough. But if you need to serve those features to a live API with <10ms latency, you need a serving layer. Meridian bridges that gap.

## The "Confession"

We didn't start by building Meridian. We started by trying to use existing tools.

We spent 6 weeks setting up a popular open-source feature store. We fought with Docker networking, Kubernetes manifests, and registry sync issues. We realized we were spending 90% of our time on infrastructure and 10% on ML.

So we gave up.

We built Meridian in 2 weeks with a simple goal: **"It must run in a Jupyter notebook with `pip install`."**

If you value "works on my laptop" over "scales to exabytes", Meridian is for you.
