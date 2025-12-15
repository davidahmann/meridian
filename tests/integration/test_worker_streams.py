from __future__ import annotations

import pytest
from redis.asyncio import Redis

from fabra.core import FeatureStore
from fabra.events import AxiomEvent
from fabra.store.offline import DuckDBOfflineStore
from fabra.store.redis import RedisOnlineStore
from fabra.worker import AxiomWorker


@pytest.mark.asyncio
async def test_worker_discovers_trigger_streams_and_updates_online_store(
    infrastructure: dict, redis_client: Redis[str]
) -> None:
    # Use real Redis for online store writes.
    online = RedisOnlineStore(redis_url=infrastructure["redis_url"])
    # Reuse the test container client to avoid extra connections.
    online.client = redis_client

    store = FeatureStore(
        offline_store=DuckDBOfflineStore(database=":memory:"),
        online_store=online,
    )

    def compute_purchase_total(entity_id: str, payload: dict) -> int:  # type: ignore[override]
        return int(payload["amount"])

    store.register_feature(
        name="purchase_total",
        entity_name="user",
        func=compute_purchase_total,
        trigger="purchase",
    )

    worker = AxiomWorker(store=store)
    await worker.setup()
    assert worker.streams == ["fabra:events:purchase"]

    event = AxiomEvent(event_type="purchase", entity_id="u1", payload={"amount": 42})
    await worker.process_message(
        "fabra:events:purchase",
        "0-1",
        {"data": event.model_dump_json()},
    )

    out = await store.online_store.get_online_features(
        "user",
        "u1",
        ["purchase_total"],
    )
    assert out["purchase_total"] == 42
