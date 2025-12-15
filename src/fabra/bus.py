from __future__ import annotations
from redis.asyncio import Redis
from fabra.events import AxiomEvent
import structlog

logger = structlog.get_logger()


class RedisEventBus:
    def __init__(self, redis: Redis[str], stream: str = "fabra_events"):
        self.redis = redis
        self.stream = stream

    async def publish(self, event: AxiomEvent) -> str:
        """
        Publishes an event to the Redis Stream.
        Returns the Redis Stream Message ID.
        """
        stream_key = f"fabra:events:{event.event_type}"
        all_stream_key = "fabra:events:all"
        # Serialize the event.
        # We store the entire object as JSON in a single 'data' field
        # OR we store specific fields.
        # To make it queryable and follow standard practices, we can just dump the whole JSON.
        # But dumping 'json' requires the consumer to parse it again.

        # Using model_dump_json() ensures UUIDs/Datetimes are serialized correctly.
        data = event.model_dump_json()

        # xadd returns the msg id
        msg_id = await self.redis.xadd(stream_key, {"data": data})
        # Also publish to an "all events" stream for simpler worker setups.
        # This is additive (does not change existing per-event streams).
        try:
            await self.redis.xadd(all_stream_key, {"data": data})
        except Exception as e:
            # Don't fail the main publish if the secondary stream fails.
            logger.debug("publish_all_stream_failed", error=str(e))
        return str(msg_id)
