from datetime import timedelta
from meridian.core import FeatureStore, entity, feature
from meridian.store import DuckDBOfflineStore, InMemoryOnlineStore
import random

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


# User Features
@feature(entity=User, refresh=timedelta(minutes=10), materialize=True)
def user_transaction_count_1h(user_id: str) -> int:
    """Number of transactions by user in the last hour."""
    # Mock logic
    return random.randint(0, 50)  # nosec


@feature(entity=User, refresh=timedelta(hours=24), materialize=True)
def user_avg_transaction_amount_7d(user_id: str) -> float:
    """Average transaction amount for user in last 7 days."""
    return random.uniform(10.0, 500.0)  # nosec


# Merchant Features
@feature(entity=Merchant, refresh=timedelta(hours=1), materialize=True)
def merchant_risk_score(merchant_id: str) -> float:
    """Risk score of the merchant (0.0 to 1.0)."""
    return random.random()  # nosec


# --- Simulation ---
# --- Simulation ---
if __name__ == "__main__":
    import asyncio

    async def main() -> None:
        print("--- Fraud Detection Feature Store Example ---")

        # Simulate materialization (populating online store)
        print("Materializing features...")
        await store.online_store.set_online_features(
            "User",
            "u123",
            {"user_transaction_count_1h": 5, "user_avg_transaction_amount_7d": 125.50},
        )
        await store.online_store.set_online_features(
            "Merchant", "m999", {"merchant_risk_score": 0.85}
        )

        # Online Retrieval for a Transaction
        print("\n--- Processing Transaction ---")
        user_id = "u123"
        merchant_id = "m999"

        user_features = await store.get_online_features(
            entity_name="User",
            entity_id=user_id,
            features=["user_transaction_count_1h", "user_avg_transaction_amount_7d"],
        )

        merchant_features = await store.get_online_features(
            entity_name="Merchant",
            entity_id=merchant_id,
            features=["merchant_risk_score"],
        )

        print(f"User Features ({user_id}): {user_features}")
        print(f"Merchant Features ({merchant_id}): {merchant_features}")

        # Simple Fraud Logic
        risk = 0.0
        if user_features["user_transaction_count_1h"] > 10:
            risk += 0.3
        if merchant_features["merchant_risk_score"] > 0.7:
            risk += 0.5

        print(f"\nCalculated Transaction Risk: {risk}")
        if risk > 0.6:
            print("🚨 TRANSACTION FLAGGED AS FRAUDULENT")
        else:
            print("✅ Transaction Approved")

    asyncio.run(main())
