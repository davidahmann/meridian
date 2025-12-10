---
title: "Python Decorators for ML Feature Engineering"
description: "How to use Python decorators to define ML features. Replace YAML configuration with clean, testable Python code."
keywords: python decorators ml, feature engineering python, ml feature definition, python feature store, decorators machine learning
date: 2025-01-07
---

# Python Decorators for ML Feature Engineering

Most feature stores use YAML for feature definitions:

```yaml
# feature_views.yaml
feature_view:
  name: user_features
  entities:
    - user_id
  features:
    - name: transaction_count
      dtype: INT64
      value_type: INT64
  ttl: 3600s
  online: true
  batch_source:
    type: BigQuerySource
    query: SELECT user_id, COUNT(*) as transaction_count...
```

This is 15 lines of YAML for one feature. Now imagine 50 features.

There's a better way.

## The Decorator Approach

```python
@feature(entity=User, refresh="5m")
def transaction_count(user_id: str) -> int:
    return db.query(
        "SELECT COUNT(*) FROM transactions WHERE user_id = %s",
        user_id
    )
```

That's it. One decorator, one function, one feature.

## Why Decorators Work

### 1. Features Are Functions

At its core, a feature is a function: input an entity ID, output a value.

```python
def user_tier(user_id: str) -> str:
    return lookup_tier(user_id)
```

Decorators add metadata without changing the core abstraction:

```python
@feature(entity=User, refresh="daily")
def user_tier(user_id: str) -> str:
    return lookup_tier(user_id)
```

### 2. Python Is the Configuration

YAML is a poor programming language. Python is a great one.

**YAML limitations:**

- No variables
- No loops
- No conditionals
- No imports
- No IDE support

**Python advantages:**

- Full programming language
- IDE autocomplete and type checking
- Testable with pytest
- Refactorable with standard tools

### 3. Type Hints for Free

```python
@feature(entity=User, refresh="5m")
def transaction_count(user_id: str) -> int:
    ...

@feature(entity=User, refresh="daily")
def user_preferences(user_id: str) -> dict:
    ...

@feature(entity=User, refresh="1h")
def is_active(user_id: str) -> bool:
    ...
```

Return types are explicit. Your IDE knows. Your tests know.

## Fabra's @feature Decorator

### Basic Usage

```python
from fabra.core import FeatureStore, entity, feature

store = FeatureStore()

@entity(store)
class User:
    user_id: str

@feature(entity=User)
def login_count(user_id: str) -> int:
    return get_login_count(user_id)
```

### Refresh Schedules

```python
@feature(entity=User, refresh="5m")      # Every 5 minutes
def realtime_feature(user_id: str) -> int: ...

@feature(entity=User, refresh="1h")       # Hourly
def hourly_feature(user_id: str) -> int: ...

@feature(entity=User, refresh="daily")    # Daily at midnight
def daily_feature(user_id: str) -> int: ...

@feature(entity=User, refresh="realtime") # On every request
def live_feature(user_id: str) -> int: ...
```

### Async Features

For I/O-bound features:

```python
@feature(entity=User, refresh="5m")
async def external_api_feature(user_id: str) -> dict:
    async with httpx.AsyncClient() as client:
        response = await client.get(f"https://api.example.com/users/{user_id}")
        return response.json()
```

### SQL Features

For database-backed features:

```python
@feature(entity=User, refresh="5m", backend="postgres")
def transaction_count_sql(user_id: str) -> int:
    return """
    SELECT COUNT(*)
    FROM transactions
    WHERE user_id = :user_id
    AND created_at > NOW() - INTERVAL '1 hour'
    """
```

The decorator handles parameterization and execution.

## Testing Features

Features are just functions. Test them like functions:

```python
# test_features.py
import pytest
from features import transaction_count, user_tier

def test_transaction_count():
    # Mock your database
    with mock_db():
        result = transaction_count("user_123")
        assert isinstance(result, int)
        assert result >= 0

def test_user_tier():
    result = user_tier("premium_user")
    assert result in ["free", "premium", "enterprise"]
```

### Testing with Fixtures

```python
@pytest.fixture
def feature_store():
    store = FeatureStore(offline_store="memory")
    yield store
    store.close()

def test_feature_integration(feature_store):
    @feature(entity=User, store=feature_store)
    def test_feature(user_id: str) -> int:
        return 42

    result = feature_store.get_feature("test_feature", "user_1")
    assert result == 42
```

## Composing Features

Features can depend on other features:

```python
@feature(entity=User, refresh="daily")
def total_purchases(user_id: str) -> float:
    return sum_purchases(user_id)

@feature(entity=User, refresh="daily")
def avg_purchase(user_id: str) -> float:
    return average_purchase(user_id)

@feature(entity=User, refresh="daily")
def purchase_score(user_id: str) -> float:
    total = store.get_feature("total_purchases", user_id)
    avg = store.get_feature("avg_purchase", user_id)
    return total * 0.7 + avg * 0.3
```

Fabra handles the dependency resolution and caching.

## Feature Groups

Organize related features:

```python
# features/user.py
@feature(entity=User, refresh="5m")
def login_count(user_id: str) -> int: ...

@feature(entity=User, refresh="daily")
def user_tier(user_id: str) -> str: ...

# features/transaction.py
@feature(entity=Transaction, refresh="realtime")
def amount(transaction_id: str) -> float: ...

@feature(entity=Transaction, refresh="5m")
def risk_score(transaction_id: str) -> float: ...
```

Import and register:

```python
# main.py
from features import user, transaction

fabra serve main.py  # All features available
```

## Hooks for Cross-Cutting Concerns

Add behavior to all features:

```python
from fabra.hooks import Hook

class LoggingHook(Hook):
    async def before_compute(self, feature_name: str, entity_id: str):
        logger.info(f"Computing {feature_name} for {entity_id}")

    async def after_compute(self, feature_name: str, entity_id: str, value: Any):
        logger.info(f"Computed {feature_name}: {value}")

store = FeatureStore(hooks=[LoggingHook()])
```

Use cases:

- Logging and monitoring
- Input validation
- Output transformation
- A/B testing

## Comparison: YAML vs Decorators

| Aspect | YAML | Decorators |
|--------|------|------------|
| Lines of code | 15-30 per feature | 3-5 per feature |
| IDE support | Limited | Full |
| Type checking | None | mypy/pyright |
| Testing | Difficult | pytest |
| Refactoring | Manual | Automated |
| Logic | Separate SQL files | Inline |
| Learning curve | New DSL | Just Python |

## Migration from YAML

If you're coming from Feast or similar:

**Before (Feast YAML):**

```yaml
feature_view:
  name: user_features
  entities:
    - user_id
  features:
    - name: transaction_count
      dtype: INT64
```

**After (Fabra):**

```python
@feature(entity=User, refresh="5m")
def transaction_count(user_id: str) -> int:
    return count_transactions(user_id)
```

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
def simple_feature(user_id: str) -> int:
    return hash(user_id) % 100

# Serve
# fabra serve features.py
```

[Quickstart guide →](../quickstart.md)

<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "BlogPosting",
  "headline": "Python Decorators for ML Feature Engineering",
  "description": "How to use Python decorators to define ML features. Replace YAML configuration with clean, testable Python code.",
  "author": {"@type": "Organization", "name": "Fabra Team"},
  "datePublished": "2025-01-07",
  "keywords": "python decorators ml, feature engineering python, ml feature definition, python feature store"
}
</script>
