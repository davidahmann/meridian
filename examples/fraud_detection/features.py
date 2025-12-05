from datetime import timedelta
from meridian.core import FeatureStore, entity, feature
from meridian.store import DuckDBOfflineStore, InMemoryOnlineStore

# Initialize Store
store = FeatureStore(
    offline_store=DuckDBOfflineStore(), online_store=InMemoryOnlineStore()
)


# --- Entities ---
@entity(store)
class User:
    user_id: str


@entity(store)
class Merchant:
    merchant_id: str


# --- Features ---


@feature(entity=User, refresh=timedelta(minutes=10), materialize=True)
def user_transaction_count_1h(user_id: str) -> int:
    """Number of transactions by user in the last hour."""
    return 5  # Mock value


@feature(entity=User, refresh=timedelta(hours=24), materialize=True)
def user_avg_transaction_amount_7d(user_id: str) -> float:
    """Average transaction amount for user in last 7 days."""
    return 125.50  # Mock value


@feature(entity=Merchant, refresh=timedelta(hours=1), materialize=True)
def merchant_risk_score(merchant_id: str) -> float:
    """Risk score of the merchant (0.0 to 1.0)."""
    return 0.85  # Mock value


# Pre-load data for serving demo
# Pre-load data for serving demo
if __name__ == "__main__":
    import asyncio

    async def main() -> None:
        await store.online_store.set_online_features(
            "User",
            "u123",
            {"user_transaction_count_1h": 5, "user_avg_transaction_amount_7d": 125.50},
        )
        await store.online_store.set_online_features(
            "Merchant", "m999", {"merchant_risk_score": 0.85}
        )

    asyncio.run(main())
