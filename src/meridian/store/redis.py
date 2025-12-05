from typing import Dict, Any, List, Optional, cast
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
    ) -> None:
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

        return sync_redis.Redis(
            host=cast(str, self.connection_kwargs["host"]),
            port=cast(int, self.connection_kwargs["port"]),
            db=cast(int, self.connection_kwargs["db"]),
            password=cast(Optional[str], self.connection_kwargs["password"]),
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
        self, entity_name: str, entity_id: str, features: Dict[str, Any]
    ) -> None:
        key = f"{entity_name}:{entity_id}"

        # Convert values to JSON strings for storage
        serialized_features = {}
        for k, v in features.items():
            serialized_features[k] = json.dumps(v)

        # Cast to Any to satisfy mypy's strict check on hset mapping
        await self.client.hset(key, mapping=serialized_features)  # type: ignore
