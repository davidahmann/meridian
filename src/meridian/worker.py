import asyncio
import logging
from typing import Optional, Dict, Any
from redis.asyncio import Redis
from meridian.events import AxiomEvent
from meridian.core import FeatureStore

logger = logging.getLogger(__name__)


class AxiomWorker:
    def __init__(
        self, redis_url: Optional[str] = None, store: Optional[FeatureStore] = None
    ):
        self.store: Optional[FeatureStore] = None
        if store:
            self.store = store
            # Prefer store's redis if available
            if hasattr(store.online_store, "client"):
                self.redis = store.online_store.client
            elif hasattr(store.online_store, "redis"):
                self.redis = store.online_store.redis
            elif redis_url:
                self.redis = Redis.from_url(redis_url, decode_responses=True)
            else:
                # Fallback if store doesn't expose redis directly?
                # ideally we have it.
                pass

        # If no store provided, or store didn't give redis, look at redis_url
        if not hasattr(self, "redis"):
            if redis_url:
                self.redis = Redis.from_url(redis_url, decode_responses=True)
            else:
                from meridian.config import get_store_factory

                _, online_store = get_store_factory()
                if hasattr(online_store, "client"):
                    self.redis = online_store.client
                elif hasattr(online_store, "redis"):
                    self.redis = online_store.redis
                else:
                    from meridian.config import get_redis_url

                    url = get_redis_url()
                    self.redis = Redis.from_url(url, decode_responses=True)

        self.store = store
        self.group_name = "axiom_workers"
        from uuid import uuid4

        self.consumer_name = f"worker_{uuid4().hex[:8]}"

    async def setup(self) -> None:
        """Ensure consumer group exists for all known event types."""
        # For Phase 1, we only know about 'transaction' or generic events.
        # We need to decide: do we listen to ALL streams? Redis Streams doesn't support wildcard XREAD nicely.
        # We usually listen to specific streams.
        # Let's assume a fixed list or discovery.
        # For Story 1.1.1, we have `meridian:events:{event_type}`.
        # We'll listen to `meridian:events:transaction` as a default for now, or just `meridian:events:all`?
        # The RedisEventBus publishes to `meridian:events:{event_type}`.
        # Let's listen to `meridian:events:transaction` for the demo scenario.
        self.streams = ["meridian:events:transaction"]

        for stream in self.streams:
            try:
                # 0-0 means create group pointing to start, mkstream=True creates stream if missing
                await self.redis.xgroup_create(
                    stream, self.group_name, id="0", mkstream=True
                )
            except Exception as e:
                # Ignore if group already exists
                if "BUSYGROUP" not in str(e):
                    logger.warning(f"Error creating group for {stream}: {e}")

    async def run(self) -> None:
        await self.setup()
        logger.info(f"AxiomWorker started. Listening on {self.streams}")

        try:
            while True:
                # Block for 1 second
                streams_dict = {s: ">" for s in self.streams}
                results = await self.redis.xreadgroup(
                    self.group_name,
                    self.consumer_name,
                    streams_dict,
                    count=10,
                    block=1000,
                )

                if not results:
                    continue

                for stream_name, messages in results:
                    for message_id, fields in messages:
                        await self.process_message(stream_name, message_id, fields)

        except asyncio.CancelledError:
            logger.info("Worker stopping...")
        finally:
            await self.redis.aclose()

    async def process_message(
        self, stream: str, msg_id: str, fields: Dict[str, Any]
    ) -> None:
        try:
            data_str = fields.get("data")
            if not data_str:
                logger.warning(f"Missing data in message {msg_id}")
                await self.ack(stream, msg_id)
                return

            # Parse Event
            event = AxiomEvent.model_validate_json(data_str)
            logger.info(f"Processing event from {stream}: {msg_id}")

            # TRIGGER LOGIC
            if self.store:
                triggered_features = self.store.registry.get_features_by_trigger(
                    event.event_type
                )

                if not triggered_features:
                    logger.info(f"No features triggered by {event.event_type}")

                for feature in triggered_features:
                    logger.info(
                        f"Triggering feature {feature.name} for entity {event.entity_id}"
                    )
                    try:
                        # 1. Compute Result
                        import inspect

                        sig = inspect.signature(feature.func)
                        kwargs: Dict[str, Any] = {}
                        if "event" in sig.parameters:
                            kwargs["event"] = event
                        if "payload" in sig.parameters:
                            kwargs["payload"] = event.payload

                        val = feature.func(event.entity_id, **kwargs)

                        # 2. Write to Online Store
                        await self.store.online_store.set_online_features(
                            entity_name=feature.entity_name,
                            entity_id=event.entity_id,
                            features={feature.name: val},
                        )
                        logger.info(f"Updated {feature.name}:{event.entity_id} = {val}")

                    except Exception as e:
                        logger.error(f"Error computing feature {feature.name}: {e}")
            else:
                logger.warning("No Store provided to worker. Cannot look up triggers.")

            await self.ack(stream, msg_id)

        except Exception as e:
            logger.error(f"Failed to process message {msg_id}: {e}")
            pass

    async def ack(self, stream: str, msg_id: str) -> None:
        await self.redis.xack(stream, self.group_name, msg_id)

    def stop(self) -> None:
        # Since run() loop checks cancelled error, we rely on task cancellation
        pass
