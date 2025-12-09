---
title: "Unit Testing ML Features with Fabra | Testing Guide"
description: "How to unit test your ML features with Fabra. Use the local in-memory store to mock data and test logic without external dependencies."
keywords: unit testing features, mlops testing, testing feature store, python ml testing
---

# Unit Testing with Fabra

Fabra is designed to be **testable by default**. You don't need to spin up Docker containers or mock complex database interactions to test your feature logic.

By using the default configuration (DuckDB + In-Memory), you can treat Fabra as a library rather than a service during your test suite execution.

## The Strategy: "Trojan Horse" Testing

Instead of asking your infra team for a Kubernetes cluster, start by using Fabra to mock feature data in your local unit tests. This gives you immediate value (cleaner tests) with zero operational overhead.

## Example: Testing a Fraud Model

Imagine you have a `FraudDetector` class that relies on features.

```python
# fraud.py
from fabra import FeatureStore
import pandas as pd

class FraudDetector:
    def __init__(self, store: FeatureStore):
        self.store = store

    async def predict_risk(self, user_id: str) -> float:
        # Fetch features purely from Python/Mock data
        features = await self.store.get_online_features(
            "User", user_id, ["transaction_count_1h", "last_login_country"]
        )

        # Simple heuristic
        if features.get("transaction_count_1h", 0) > 10:
            return 0.9
        return 0.1
```

### Writing the Test

You can write a standard `pytest` test that populates the in-memory store before running the logic.

```python
# test_fraud.py
import pytest
from fabra import FeatureStore, entity, feature
from fraud import FraudDetector

@pytest.fixture
def store():
    # 1. Initialize ephemeral store (In-Memory by default)
    store = FeatureStore()

    # 2. Define entities/features inline for the test
    @entity(store)
    class User:
        user_id: str

    @feature(User)
    def transaction_count_1h(uid: str) -> int:
        return 0 # Default, or we override via set_online_features

    @feature(User)
    def last_login_country(uid: str) -> str:
        return "US"

    return store

@pytest.mark.asyncio
async def test_high_risk_scenario(store):
    # 3. Seed the "Online Store" with mock data
    # No Redis required! Just a Python dict under the hood.
    await store.online_store.set_online_features(
        entity_name="User",
        entity_id="u1",
        features={"transaction_count_1h": 15, "last_login_country": "US"}
    )

    detector = FraudDetector(store)
    risk = await detector.predict_risk("u1")

    assert risk == 0.9
```

## Why this matters?

1.  **Speed**: Tests run in milliseconds.
2.  **Isolation**: No network calls to external DBs.
3.  **Portability**: Runs in any CI environment (GitHub Actions) with just `pip install fabra`.

Start small by using Fabra to organize your test data. When you're ready, the exact same code deploys to production with Redis.

<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "TechArticle",
  "headline": "Unit Testing ML Features with Fabra",
  "description": "How to unit test your ML features with Fabra. Use the local in-memory store to mock data and test logic without external dependencies.",
  "author": {"@type": "Organization", "name": "Fabra Team"},
  "keywords": "unit testing features, mlops testing, testing feature store, python ml testing",
  "articleSection": "Testing"
}
</script>
