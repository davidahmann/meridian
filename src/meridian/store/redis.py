from typing import Dict, Any, List, Optional
import redis.asyncio as redis
import json
from .online import OnlineStore


class RedisOnlineStore(OnlineStore):
    def __init__(
        self,
        host: str = "localhost",
        port: int = 6379,
        db: int = 0,
        password: Optional[str] = None,
        redis_url: Optional[str] = None,
    ) -> None:
        self.connection_kwargs: Dict[str, Any]
        if redis_url:
            self.client = redis.Redis.from_url(redis_url, decode_responses=True)
            # Parse URL for sync client recreation if needed, or store URL
            self.connection_kwargs = {"url": redis_url}
        else:
            self.connection_kwargs = {
                "host": host,
                "port": port,
                "db": db,
                "password": password,
                "decode_responses": True,
            }
            self.client = redis.Redis(
                host=host, port=port, db=db, password=password, decode_responses=True
            )

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
        values = await self.client.hmget(key, feature_names)

        result = {}
        for name, value in zip(feature_names, values):
            if value is not None:
                # Redis stores strings, so we might need to infer types or store as JSON.
                # For MVP, we'll try to parse as JSON, fallback to string.
                try:
                    result[name] = json.loads(value)
                except (json.JSONDecodeError, TypeError):
                    result[name] = value
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
            serialized_features[k] = json.dumps(v)

        # Cast to Any to satisfy mypy's strict check on hset mapping
        await self.client.hset(key, mapping=serialized_features)  # type: ignore

        if ttl:
            await self.client.expire(key, ttl)

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
        async with self.client.pipeline() as pipe:
            for i, (_, row) in enumerate(features_df.iterrows()):
                entity_id = str(row[entity_id_col])
                value = row[feature_name]
                key = f"{entity_name}:{entity_id}"

                # Serialize value
                serialized_value = json.dumps(value)

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
        return await self.client.get(key)

    async def set(self, key: str, value: Any, ex: Optional[int] = None) -> Any:
        return await self.client.set(key, value, ex=ex)

    async def delete(self, *keys: str) -> Any:
        return await self.client.delete(*keys)

    async def smembers(self, key: str) -> Any:
        return await self.client.smembers(key)

    def pipeline(self) -> Any:
        return self.client.pipeline()
