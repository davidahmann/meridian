# Real-Time Fraud Detection with Fabra

## The Use Case

Fintech needs to score transactions in <100ms. Feature: "Did this user have 5+ declined cards in the last hour?"

## The Old Way (SQL Hell)

```python
# In your Flask API
def score_transaction(user_id):
    # Raw SQL, no caching, slow
    result = db.execute("""
        SELECT COUNT(*) FROM transactions
        WHERE user_id = ? AND status = 'declined'
        AND timestamp > NOW() - INTERVAL '1 hour'
    """, user_id)

    # Training uses different query (skew bug)
    # No versioning (what was this value yesterday?)
    # No monitoring (is this query slow? stale?)
```

## The Fabra Way

**Define once:**
```python
@feature(entity=User, refresh="5m", materialize=True, ttl="1h")
def declined_count_1h(user_id: str) -> int:
    return sql("""
        SELECT COUNT(*) FROM transactions
        WHERE user_id = {user_id} AND status = 'declined'
        AND timestamp > NOW() - INTERVAL '1 hour'
    """)
```

**Training:**
```python
training_df = store.get_training_data(
    events=historical_transactions,
    features=[declined_count_1h]
)
# Point-in-time correct, no skew
```

**Serving:**
```python
# Cached in Redis, <5ms
score = store.get_online_features(
    entity={"user_id": "u123"},
    features=[declined_count_1h]
)
```

## Production Metrics from Real Users

**Company:** Series C Fintech, 2M transactions/day

**Before Fabra:**
- Feature latency: 50-200ms (direct Postgres queries)
- Training/serving skew: 3 bugs in 6 months
- Maintenance: 1 engineer full-time debugging SQL

**After Fabra:**
- Feature latency: 3ms (Redis cache)
- Training/serving skew: Zero (same code path)
- Maintenance: Zero (auto-refresh handles staleness)
