import pytest
from datetime import timedelta
from meridian.core import FeatureStore, entity, feature


def test_register_entity() -> None:
    store = FeatureStore()

    @entity(store)
    class User:
        """A user of the platform."""

        user_id: str

    assert "User" in store.registry.entities
    ent = store.registry.entities["User"]
    assert ent.name == "User"
    assert ent.id_column == "user_id"
    assert ent.description == "A user of the platform."


def test_register_feature() -> None:
    store = FeatureStore()

    @entity(store)
    class User:
        user_id: str

    @feature(entity=User, materialize=True, refresh=timedelta(minutes=5))
    def user_transaction_count(user_id: str) -> int:
        """Counts transactions."""
        return 5

    assert "user_transaction_count" in store.registry.features
    feat = store.registry.features["user_transaction_count"]
    assert feat.name == "user_transaction_count"
    assert feat.entity_name == "User"
    assert feat.materialize is True
    assert feat.refresh == timedelta(minutes=5)
    assert feat.description == "Counts transactions."


def test_entity_id_inference_failure() -> None:
    store = FeatureStore()
    with pytest.raises(ValueError, match="Could not infer id_column"):

        @entity(store)
        class BadEntity:
            pass
