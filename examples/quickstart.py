import pandas as pd
from datetime import timedelta
from meridian.core import FeatureStore, entity, feature
from meridian.store import DuckDBOfflineStore, InMemoryOnlineStore

# 1. Initialize the Feature Store
# We use DuckDB for offline (historical) data and In-Memory for online (serving) data.
store = FeatureStore(
    offline_store=DuckDBOfflineStore(), online_store=InMemoryOnlineStore()
)


# 2. Define an Entity
# Entities are the primary keys for your features (e.g., User, Product).
@entity(store)
class User:
    user_id: str


# 3. Define Features
# Features are defined as simple Python functions decorated with @feature.
@feature(entity=User, refresh=timedelta(minutes=5), materialize=True)
def user_click_count(user_id: str) -> int:
    """Calculates the total clicks for a user."""
    # In a real scenario, this would query a raw data source.
    # For this example, we return a mock value.
    return 42


@feature(entity=User)
def user_is_active(user_id: str) -> bool:
    """Determines if a user is currently active."""
    return True


# 4. Simulate Offline Data (Training)
# Create a DataFrame of entities to fetch historical features for.
entity_df = pd.DataFrame({"user_id": ["u1", "u2", "u3"]})

print("--- Offline Feature Retrieval (Training Data) ---")
# In a real scenario, this would join with historical data in DuckDB.
# Currently, our DuckDB store is a placeholder, so this will return the entity_df.
training_data = store.get_training_data(
    entity_df, features=["user_click_count", "user_is_active"]
)
print(training_data)

# 5. Simulate Online Data (Serving)
# Pre-load some data into the online store (usually done by the scheduler/materializer).
store.online_store.set_online_features(
    "User", "u1", {"user_click_count": 100, "user_is_active": True}
)

print("\n--- Online Feature Retrieval (Serving) ---")
online_features = store.get_online_features(
    entity_name="User", entity_id="u1", features=["user_click_count", "user_is_active"]
)
print(f"Features for User u1: {online_features}")

# 6. Start the Scheduler (Optional)
# This would start the background jobs to materialize features.
# store.start()
