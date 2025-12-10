# Use Case: Churn Prediction

Churn prediction is the "Hello World" of Point-in-Time Correctness. If you get this wrong, your model will look perfect in training but fail in production.

## The Problem: Data Leakage

Imagine you are training a model to predict if a user will churn next month. You have a features table:

| user_id | txn_count | timestamp |
| :--- | :--- | :--- |
| u1 | 10 | 2024-01-01 |
| u1 | 50 | 2024-02-01 |

And a labels table (churn events):

| user_id | churned | timestamp |
| :--- | :--- | :--- |
| u1 | True | 2024-01-15 |

If you naively join these tables on `user_id`, you might accidentally use the `txn_count=50` feature (from Feb 1st) to predict the churn event (on Jan 15th). **This is data leakage.** You are using data from the future to predict the past.

## The Solution: Point-in-Time Correctness

Fabra solves this automatically using `ASOF JOIN` (DuckDB) or `LATERAL JOIN` (Postgres).

```python
# features.py
@feature(entity=User, sql="SELECT * FROM transactions", materialize=True)
def txn_count(user_id: str) -> int:
    return 0

# training.py
training_df = await store.get_training_data(
    entity_df=labels_df,  # Contains user_id and timestamp (Jan 15th)
    features=["txn_count"]
)
```

Fabra ensures that for the label on **Jan 15th**, it only sees the feature value from **Jan 1st** (`txn_count=10`). It ignores the future value.

## Why This Matters
- **Correctness:** Your offline metrics (AUC/F1) will match online performance.
- **Simplicity:** You don't need to write complex window functions or temporal joins manually.
- **Consistency:** The same logic applies whether you are using DuckDB locally or Postgres in production.

---

## Next Steps

- [Feature Store Without K8s](../feature-store-without-kubernetes.md) — Get started in 30 seconds
- [Feast vs Fabra](../feast-alternative.md) — Why we're simpler
- [Quickstart](../quickstart.md) — Full setup guide

<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "HowTo",
  "name": "Churn Prediction with Point-in-Time Correctness",
  "description": "Build churn prediction models with proper point-in-time correctness to prevent data leakage.",
  "totalTime": "PT20M",
  "tool": [{"@type": "HowToTool", "name": "Fabra"}],
  "step": [
    {"@type": "HowToStep", "name": "Define features", "text": "Create transaction count and other features using @feature decorator."},
    {"@type": "HowToStep", "name": "Generate training data", "text": "Use get_training_data with ASOF JOIN to prevent future data leakage."},
    {"@type": "HowToStep", "name": "Train model", "text": "Train your model knowing offline metrics will match production."}
  ]
}
</script>
