from typing import Dict, Any, List, Optional
import redis.asyncio as redis
import json
from .online import OnlineStore, _wrap_feature_value
from datetime import datetime, timezone


class RedisOnlineStore(OnlineStore):
    def __init__(
        self,
        host: str = "localhost",
        port: int = 6379,
        db: int = 0,
        password: Optional[str] = None,
        redis_url: Optional[str] = None,
    ) -> None:
        # IMPORTANT: Do not create the asyncio Redis client in __init__.
        # Creating it eagerly can call asyncio.get_event_loop() on import/construct
        # (notably on Python 3.9), which raises when no loop is set yet.
        #
        # We lazily create the async client on first use inside an async method.
        # Allow passing a redis URL as the first positional arg for convenience,
        # e.g. RedisOnlineStore("redis://localhost:6379").
        if (
            redis_url is None
            and isinstance(host, str)
            and host.startswith(("redis://", "rediss://"))
        ):
            redis_url = host

        self.connection_kwargs: Dict[str, Any]
        self._client: Optional[Any] = None
        if redis_url:
            self.connection_kwargs = {"url": redis_url}
        else:
            self.connection_kwargs = {
                "host": host,
                "port": port,
                "db": db,
                "password": password,
                "decode_responses": True,
            }

    def _get_client(self) -> Any:
        if self._client is not None:
            return self._client

        # Ensure we're in an async context for Python versions where the redis client
        # constructor touches the event loop policy.
        import asyncio

        try:
            asyncio.get_running_loop()
        except RuntimeError as e:
            raise RuntimeError(
                "RedisOnlineStore client must be created inside an async context; "
                "call RedisOnlineStore methods from an event loop."
            ) from e

        if "url" in self.connection_kwargs:
            self._client = redis.Redis.from_url(
                self.connection_kwargs["url"], decode_responses=True
            )
        else:
            self._client = redis.Redis(**self.connection_kwargs)

        return self._client

    @property
    def client(self) -> Any:
        # Backwards-compatible accessor used in tests and in some internal call sites.
        return self._get_client()

    def get_sync_client(self) -> Any:
        """Returns a synchronous Redis client for the scheduler."""
        import redis as sync_redis

        if "url" in self.connection_kwargs:
            return sync_redis.Redis.from_url(
                self.connection_kwargs["url"], decode_responses=True
            )

        return sync_redis.Redis(
            host=self.connection_kwargs["host"],
            port=self.connection_kwargs["port"],
            db=self.connection_kwargs["db"],
            password=self.connection_kwargs["password"],
            decode_responses=True,
        )

    async def get_online_features(
        self, entity_name: str, entity_id: str, feature_names: List[str]
    ) -> Dict[str, Any]:
        # Key format: "entity_name:entity_id"
        key = f"{entity_name}:{entity_id}"

        # Use HMGET to fetch specific fields
        values = await self._get_client().hmget(key, feature_names)

        result: Dict[str, Any] = {}
        for name, value in zip(feature_names, values):
            if value is not None:
                # Redis stores strings, so we might need to infer types or store as JSON.
                # For MVP, we'll try to parse as JSON, fallback to string.
                try:
                    parsed = json.loads(value)
                    if (
                        isinstance(parsed, dict)
                        and parsed.get("__fabra_feature_value__") is True
                    ):
                        result[name] = parsed.get("value")
                    else:
                        result[name] = parsed
                except (json.JSONDecodeError, TypeError):
                    result[name] = value
        return result

    async def get_online_features_with_meta(
        self, entity_name: str, entity_id: str, feature_names: List[str]
    ) -> Dict[str, Dict[str, Any]]:
        key = f"{entity_name}:{entity_id}"
        values = await self._get_client().hmget(key, feature_names)
        result: Dict[str, Dict[str, Any]] = {}
        for name, value in zip(feature_names, values):
            if value is None:
                continue
            try:
                parsed = json.loads(value)
                if (
                    isinstance(parsed, dict)
                    and parsed.get("__fabra_feature_value__") is True
                ):
                    result[name] = parsed
                else:
                    result[name] = _wrap_feature_value(parsed)
            except (json.JSONDecodeError, TypeError):
                result[name] = _wrap_feature_value(value)
        return result

    async def set_online_features(
        self,
        entity_name: str,
        entity_id: str,
        features: Dict[str, Any],
        ttl: Optional[int] = None,
    ) -> None:
        key = f"{entity_name}:{entity_id}"

        # Convert values to JSON strings for storage
        serialized_features = {}
        for k, v in features.items():
            wrapped = _wrap_feature_value(v, as_of=datetime.now(timezone.utc))
            serialized_features[k] = json.dumps(wrapped)

        await self._get_client().hset(key, mapping=serialized_features)

        if ttl:
            await self._get_client().expire(key, ttl)

    async def set_online_features_bulk(
        self,
        entity_name: str,
        features_df: Any,
        feature_name: str,
        entity_id_col: str,
        ttl: Optional[int] = None,
    ) -> None:
        # Use a pipeline for bulk writes with batching
        BATCH_SIZE = 1000
        async with self._get_client().pipeline() as pipe:
            for i, (_, row) in enumerate(features_df.iterrows()):
                entity_id = str(row[entity_id_col])
                value = row[feature_name]
                key = f"{entity_name}:{entity_id}"

                # Serialize value
                wrapped = _wrap_feature_value(value, as_of=datetime.now(timezone.utc))
                serialized_value = json.dumps(wrapped)

                # Add to pipeline
                pipe.hset(key, feature_name, serialized_value)
                if ttl:
                    pipe.expire(key, ttl)

                # Execute batch
                if (i + 1) % BATCH_SIZE == 0:
                    await pipe.execute()

            # Execute remaining
            await pipe.execute()

    # --- Cache Primitives for Context API ---
    async def get(self, key: str) -> Any:
        return await self._get_client().get(key)

    async def set(self, key: str, value: Any, ex: Optional[int] = None) -> Any:
        return await self._get_client().set(key, value, ex=ex)

    async def delete(self, *keys: str) -> Any:
        return await self._get_client().delete(*keys)

    async def smembers(self, key: str) -> Any:
        return await self._get_client().smembers(key)

    def pipeline(self) -> Any:
        return self._get_client().pipeline()
