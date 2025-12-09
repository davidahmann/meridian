---
title: "Hybrid Features in Fabra: Mixing Python and SQL"
description: "Learn how to use Hybrid Features in Fabra using Python for complex logic and SQL for heavy data lifting in the same API."
keywords: hybrid features, python feature store, sql feature store, on-demand features
---

# Hybrid Features: Python + SQL

Fabra v1.1.0 introduces **Hybrid Features**, allowing you to choose the best tool for the job: Python for complex logic, and SQL for heavy lifting.

## The Two Modes

### 1. Python Features (On-Demand)
Perfect for real-time transformations, complex math, or logic that is hard to express in SQL.

```python
@feature(entity=User)
def name_length(user_id: str) -> int:
    # Complex logic in pure Python
    user = fetch_user_profile(user_id)
    return len(user.name)
```

**How it works:**
- **Online:** The function is executed in real-time when you request the feature.
- **Offline:** The function is applied row-by-row to your entity dataframe using `apply()`.

### 2. SQL Features (Batch / Materialized)
Perfect for aggregations, joins, and large-scale data processing that should happen in the warehouse.

```python
@feature(
    entity=User,
    sql="SELECT user_id, count(*) as txn_count FROM transactions GROUP BY user_id",
    materialize=True,
    refresh=timedelta(minutes=10)
)
def user_txn_count(user_id: str) -> int:
    return 0 # Fallback value or type hint
```

**How it works:**
- **Offline Retrieval:** Fabra executes the SQL query against your Offline Store (DuckDB or Postgres) and joins the result to your entity dataframe.
- **Materialization:** The Scheduler executes the SQL query periodically and bulk-loads the results into Redis.
- **Online Serving:** The API serves the pre-computed value from Redis.

> [!IMPORTANT]
> **Point-in-Time Correctness:** For SQL features, your entity dataframe must have a timestamp column (default: `event_timestamp` or `timestamp`) to perform the ASOF join correctly.

## Mixing Both
You can mix both types in the same request!

```python
training_df = await store.get_training_data(
    entity_df,
    features=["name_length", "user_txn_count"]
)
```

Fabra automatically handles the orchestration:
1.  Computes `name_length` in Python.
2.  Delegates `user_txn_count` to the database.
3.  Merges everything into a single DataFrame.

<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "TechArticle",
  "headline": "Hybrid Features in Fabra: Mixing Python and SQL",
  "description": "Learn how to use Hybrid Features in Fabra using Python for complex logic and SQL for heavy data lifting in the same API.",
  "author": {"@type": "Organization", "name": "Fabra Team"},
  "keywords": "hybrid features, python feature store, sql feature store, on-demand features",
  "articleSection": "Documentation"
}
</script>
