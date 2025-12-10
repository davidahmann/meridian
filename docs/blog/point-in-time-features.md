---
title: "Point-in-Time Features: Preventing ML Data Leakage"
description: "How to generate training data without data leakage. Using ASOF JOIN and LATERAL JOIN for point-in-time correct feature retrieval."
keywords: point in time features, ml data leakage, feature store training data, asof join, temporal join, ml feature engineering
date: 2025-01-10
---

# Point-in-Time Features: Preventing ML Data Leakage

Your fraud model has 99% accuracy in training. In production, it's 60%.

The culprit? Data leakage. Your training data used feature values that didn't exist at prediction time.

## The Data Leakage Problem

Imagine you're building a fraud detection model. You have:

- **Events table:** transactions with timestamps and labels (fraud/not fraud)
- **Features table:** user behavior metrics updated throughout the day

```
Events:
| user_id | timestamp           | is_fraud |
|---------|---------------------|----------|
| user_1  | 2024-01-15 10:00:00 | true     |
| user_1  | 2024-01-15 14:00:00 | false    |

Features (transaction_count_1h):
| user_id | timestamp           | value |
|---------|---------------------|-------|
| user_1  | 2024-01-15 09:00:00 | 2     |
| user_1  | 2024-01-15 11:00:00 | 5     |  <- Updated AFTER fraud
| user_1  | 2024-01-15 15:00:00 | 3     |
```

**The wrong way:**

```sql
SELECT e.*, f.value as transaction_count
FROM events e
JOIN features f ON e.user_id = f.user_id
WHERE f.feature_name = 'transaction_count_1h'
```

This joins the **latest** feature value. For the 10:00 fraud event, it might use the 11:00 or 15:00 feature value — data that didn't exist at prediction time.

**The right way:**

```sql
SELECT e.*, f.value as transaction_count
FROM events e
ASOF JOIN features f
ON e.user_id = f.user_id
AND f.timestamp <= e.timestamp
WHERE f.feature_name = 'transaction_count_1h'
```

This joins the **most recent feature value that existed at event time**. For the 10:00 fraud event, it uses the 09:00 feature value.

## How Fabra Handles This

Fabra automatically logs feature values with timestamps:

```python
@feature(entity=User, refresh="5m")
def transaction_count_1h(user_id: str) -> int:
    return count_transactions(user_id, hours=1)
```

Every time this feature is computed, Fabra logs:

```
| user_id | feature_name          | value | timestamp           |
|---------|-----------------------|-------|---------------------|
| user_1  | transaction_count_1h  | 2     | 2024-01-15 09:00:00 |
| user_1  | transaction_count_1h  | 5     | 2024-01-15 09:05:00 |
| user_1  | transaction_count_1h  | 5     | 2024-01-15 09:10:00 |
```

When you generate training data, Fabra uses the appropriate temporal join.

## DuckDB: ASOF JOIN

For local development, Fabra uses DuckDB's native `ASOF JOIN`:

```sql
SELECT
    events.*,
    features.value as transaction_count
FROM events
ASOF JOIN features
ON events.user_id = features.user_id
AND features.timestamp <= events.timestamp
```

DuckDB's `ASOF JOIN` finds the most recent matching row efficiently.

## Postgres: LATERAL JOIN

Postgres doesn't have `ASOF JOIN`, so Fabra uses `LATERAL JOIN`:

```sql
SELECT
    e.*,
    f.value as transaction_count
FROM events e
LEFT JOIN LATERAL (
    SELECT value
    FROM features
    WHERE user_id = e.user_id
    AND feature_name = 'transaction_count_1h'
    AND timestamp <= e.timestamp
    ORDER BY timestamp DESC
    LIMIT 1
) f ON true
```

Same semantics, slightly different syntax.

## Generating Training Data

```python
from fabra.core import FeatureStore

store = FeatureStore()

# Your events DataFrame
events = pd.DataFrame({
    "user_id": ["user_1", "user_1", "user_2"],
    "timestamp": ["2024-01-15 10:00", "2024-01-15 14:00", "2024-01-15 12:00"],
    "label": [1, 0, 0]
})

# Get point-in-time correct features
training_data = await store.get_historical_features(
    entity_df=events,
    features=["transaction_count_1h", "avg_purchase_amount"]
)
```

The result includes feature values as they existed at each event's timestamp.

## Time Travel for Debugging

Fabra supports "time travel" queries for debugging:

```python
from fabra.core import get_context

# Get features as they existed at a specific time
async with store.time_travel(timestamp="2024-01-15 09:30:00"):
    value = await store.get_feature("transaction_count_1h", "user_1")
    # Returns value from 09:00 (most recent before 09:30)
```

Useful for investigating production incidents: "What features did the model see when it made this prediction?"

## Common Pitfalls

### 1. Joining on Latest Value

**Wrong:**
```sql
SELECT * FROM events e
JOIN features f ON e.user_id = f.user_id
WHERE f.feature_name = 'x'
AND f.timestamp = (SELECT MAX(timestamp) FROM features)
```

**Right:** Use temporal joins (ASOF or LATERAL).

### 2. Aggregating Future Data

**Wrong:**
```python
@feature(entity=User)
def total_purchases(user_id: str) -> int:
    # This includes ALL purchases, including future ones
    return db.query("SELECT COUNT(*) FROM purchases WHERE user_id = %s", user_id)
```

**Right:**
```python
@feature(entity=User, refresh="5m")
def total_purchases(user_id: str) -> int:
    # Log current value, let temporal join handle point-in-time
    return db.query("SELECT COUNT(*) FROM purchases WHERE user_id = %s", user_id)
```

The temporal join ensures training uses the value that existed at prediction time.

### 3. Using Event Timestamps for Features

**Wrong:**
```python
def get_features(event_timestamp):
    # Computing feature from scratch at event time
    # Slow and error-prone
    return expensive_computation(as_of=event_timestamp)
```

**Right:** Log feature values continuously, let the temporal join handle retrieval.

## The Accuracy Impact

Teams typically see 5-15% accuracy improvement when fixing data leakage issues.

A fraud model we worked with went from 62% production accuracy to 78% after implementing proper point-in-time features. The training accuracy was unchanged (it was already high), but production finally matched.

## Try It

```bash
pip install "fabra-ai[ui]"
```

```python
from fabra.core import FeatureStore, entity, feature

store = FeatureStore()

@entity(store)
class User:
    user_id: str

@feature(entity=User, refresh="5m")
def login_count(user_id: str) -> int:
    return get_login_count(user_id)

# Features are automatically logged with timestamps
# Use get_historical_features for training data
```

[Churn prediction example →](../use-cases/churn-prediction.md)

<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "BlogPosting",
  "headline": "Point-in-Time Features: Preventing ML Data Leakage",
  "description": "How to generate training data without data leakage. Using ASOF JOIN and LATERAL JOIN for point-in-time correct feature retrieval.",
  "author": {"@type": "Organization", "name": "Fabra Team"},
  "datePublished": "2025-01-10",
  "keywords": "point in time features, ml data leakage, feature store training data, asof join, temporal join"
}
</script>
