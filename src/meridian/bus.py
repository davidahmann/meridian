from __future__ import annotations
from redis.asyncio import Redis
from meridian.events import AxiomEvent


class RedisEventBus:
    def __init__(self, redis: Redis[str], stream: str = "meridian_events"):
        self.redis = redis
        self.stream = stream

    async def publish(self, event: AxiomEvent) -> str:
        """
        Publishes an event to the Redis Stream.
        Returns the Redis Stream Message ID.
        """
        stream_key = f"meridian:events:{event.event_type}"
        # Serialize the event.
        # We store the entire object as JSON in a single 'data' field
        # OR we store specific fields.
        # To make it queryable and follow standard practices, we can just dump the whole JSON.
        # But dumping 'json' requires the consumer to parse it again.

        # Using model_dump_json() ensures UUIDs/Datetimes are serialized correctly.
        data = event.model_dump_json()

        # xadd returns the msg id
        msg_id = await self.redis.xadd(stream_key, {"data": data})
        return str(msg_id)
