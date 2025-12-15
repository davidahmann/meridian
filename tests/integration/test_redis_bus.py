from __future__ import annotations
import pytest
import json
from fabra.bus import RedisEventBus
from fabra.events import AxiomEvent
from redis.asyncio import Redis


@pytest.mark.asyncio
async def test_redis_bus_publish(redis_client: Redis[str]) -> None:
    bus = RedisEventBus(redis_client)
    event = AxiomEvent(event_type="integration_test", entity_id="u1", payload={"a": 1})

    msg_id = await bus.publish(event)
    assert msg_id is not None

    # Read back to verify
    stream_key = "fabra:events:integration_test"
    # xread returns [[key, [(msg_id, fields)]]]
    result = await redis_client.xread({stream_key: "0-0"}, count=1)
    assert result

    # result structure: [ [stream_key, [ (msg_id, {field: value}) ]] ]
    entry = result[0][1][0]
    fields = entry[1]

    data_str = fields["data"]
    data = json.loads(data_str)
    assert data["entity_id"] == "u1"
    assert data["payload"]["a"] == 1
    assert data["id"] == str(event.id)

    # Also published to the shared all-events stream.
    all_stream_key = "fabra:events:all"
    result_all = await redis_client.xread({all_stream_key: "0-0"}, count=1)
    assert result_all
