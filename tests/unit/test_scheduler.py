from unittest.mock import MagicMock
from meridian.core import FeatureStore, entity, feature
from datetime import timedelta


def test_scheduler_integration() -> None:
    store = FeatureStore()
    store.scheduler = MagicMock()

    @entity(store)
    class User:
        user_id: str

    @feature(entity=User, materialize=True, refresh=timedelta(seconds=1))
    def user_transaction_count(user_id: str) -> int:
        return 5

    store.start()

    # Verify schedule_job was called
    store.scheduler.schedule_job.assert_called_once()
    call_args = store.scheduler.schedule_job.call_args[1]
    assert call_args["interval_seconds"] == 1
    assert call_args["job_id"] == "materialize_user_transaction_count"


def test_scheduler_no_materialize() -> None:
    store = FeatureStore()
    store.scheduler = MagicMock()

    @entity(store)
    class User:
        user_id: str

    @feature(entity=User, materialize=False, refresh=timedelta(seconds=1))
    def user_transaction_count(user_id: str) -> int:
        return 5

    store.start()

    # Should not schedule if materialize=False
    store.scheduler.schedule_job.assert_not_called()
