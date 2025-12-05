from datetime import timedelta
from meridian.core import FeatureStore, entity, feature
from meridian.store import DuckDBOfflineStore, InMemoryOnlineStore

# Initialize the store
# For serving, we typically want a persistent offline store and a fast online store.
# Here we use defaults for simplicity.
store = FeatureStore(
    offline_store=DuckDBOfflineStore(), online_store=InMemoryOnlineStore()
)


@entity(store)
class User:
    user_id: str


@feature(entity=User, refresh=timedelta(minutes=5), materialize=True)
def user_click_count(user_id: str) -> int:
    """Calculates the total clicks for a user."""
    return 42


@feature(entity=User)
def user_is_active(user_id: str) -> bool:
    """Determines if a user is currently active."""
    return True


# Pre-load some data for demonstration purposes
# In production, this would be done by the materialization scheduler.
if __name__ == "__main__":
    import asyncio

    async def main() -> None:
        await store.online_store.set_online_features(
            "User", "u1", {"user_click_count": 100, "user_is_active": True}
        )

    asyncio.run(main())
