"""
Fabra Demo: Self-contained feature store example.

Run:
    fabra demo --mode features

Test (while demo is running):
    curl localhost:8000/features/user_engagement?entity_id=user_123
    curl localhost:8000/features/user_tier?entity_id=user_123
    curl localhost:8000/features/purchase_count?entity_id=user_123

Expected Response:
    {"value": 87.5, "freshness_ms": 0, "served_from": "online"}
"""

from datetime import timedelta

from fabra.core import FeatureStore, entity, feature
from fabra.store import DuckDBOfflineStore, InMemoryOnlineStore

# Initialize the store with in-memory backends for instant startup
store = FeatureStore(
    offline_store=DuckDBOfflineStore(),
    online_store=InMemoryOnlineStore(),
)


@entity(store)
class User:
    """User entity for ML features."""

    user_id: str


@feature(entity=User, refresh=timedelta(minutes=1), materialize=True)
def user_engagement(user_id: str) -> float:
    """Engagement score (0-100) based on user ID hash.

    This is a deterministic feature - same user_id always returns same score.
    """
    h = abs(hash(user_id + "engagement"))
    return round((h % 10000) / 100, 2)


@feature(entity=User, refresh=timedelta(hours=1))
def user_tier(user_id: str) -> str:
    """Premium/free tier based on user ID.

    Deterministic: same user_id always returns same tier.
    """
    return "premium" if hash(user_id) % 2 == 0 else "free"


@feature(entity=User, refresh=timedelta(minutes=5), materialize=True)
def purchase_count(user_id: str) -> int:
    """Simulated purchase count based on user ID.

    Deterministic: same user_id always returns same count.
    """
    return abs(hash(user_id + "purchases")) % 50


@feature(entity=User, refresh=timedelta(minutes=10))
def days_since_signup(user_id: str) -> int:
    """Days since user signed up (simulated)."""
    return abs(hash(user_id + "signup")) % 365


@feature(entity=User)
def is_active(user_id: str) -> bool:
    """Whether user is currently active."""
    return hash(user_id) % 3 != 0


async def _seed_demo_data() -> None:
    demo_users = ["user_123", "user_456", "user_789", "alice", "bob"]

    for uid in demo_users:
        features = {
            "user_engagement": user_engagement(uid),
            "user_tier": user_tier(uid),
            "purchase_count": purchase_count(uid),
            "days_since_signup": days_since_signup(uid),
            "is_active": is_active(uid),
        }
        await store.online_store.set_online_features("User", uid, features)


def _run_seed() -> None:
    import asyncio

    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_seed_demo_data())
    except RuntimeError:
        asyncio.run(_seed_demo_data())


_run_seed()
