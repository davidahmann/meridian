import pytest
from datetime import timedelta
from meridian.core import _parse_timedelta, feature, FeatureStore, entity


def test_parse_timedelta_valid() -> None:
    assert _parse_timedelta("30s") == timedelta(seconds=30)
    assert _parse_timedelta("5m") == timedelta(minutes=5)
    assert _parse_timedelta("1h") == timedelta(hours=1)
    assert _parse_timedelta("2d") == timedelta(days=2)


def test_parse_timedelta_invalid() -> None:
    with pytest.raises(ValueError, match="Invalid duration format"):
        _parse_timedelta("five minutes")

    with pytest.raises(ValueError, match="Invalid duration format"):
        _parse_timedelta("5x")


def test_feature_decorator_with_strings() -> None:
    store = FeatureStore()

    @entity(store)
    class User:
        user_id: str

    @feature(User, refresh="10m", ttl="1h")
    def my_feature(user_id: str) -> int:
        return 1

    f = store.registry.features["my_feature"]
    assert f.refresh == timedelta(minutes=10)
    assert f.ttl == timedelta(hours=1)
