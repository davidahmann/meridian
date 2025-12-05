import asyncio
import random
from datetime import timedelta
from meridian.core import FeatureStore, entity, feature

# 1. Initialize Feature Store (Auto-Configured)
# In production, this will pick up Postgres and Redis from env vars.
print("🚀 Initializing Meridian Feature Store...")
store = FeatureStore()


@entity(store)
class User:
    user_id: str


@feature(entity=User, refresh=timedelta(minutes=5), materialize=True)
def random_score(user_id: str) -> float:
    """A random score for the user."""
    return random.random() * 100  # nosec


async def main() -> None:
    print("✅ Store initialized with:")
    print(f"   Offline: {store.offline_store.__class__.__name__}")
    print(f"   Online:  {store.online_store.__class__.__name__}")

    # 2. Start Scheduler
    print("⏰ Starting scheduler...")
    store.start()

    # 3. Simulate Traffic
    users = ["u1", "u2", "u3", "u4", "u5"]

    print("🔄 Running simulation loop (Ctrl+C to stop)...")
    while True:
        try:
            # Pick a random user
            user_id = random.choice(users)  # nosec

            # Fetch online features
            features = await store.get_online_features(
                "User", user_id, ["random_score"]
            )

            score = features.get("random_score")
            status = "HIT" if score is not None else "MISS"
            print(f"[{status}] User {user_id}: score={score}")

            await asyncio.sleep(2)

        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"Error: {e}")
            await asyncio.sleep(1)


if __name__ == "__main__":
    asyncio.run(main())
