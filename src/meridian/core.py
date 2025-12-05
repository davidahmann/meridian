from typing import Any, Callable, Dict, Optional, Type, Union, List, get_type_hints
from dataclasses import dataclass
from datetime import timedelta
import pandas as pd
from .store import (
    OfflineStore,
    DuckDBOfflineStore,
    OnlineStore,
    InMemoryOnlineStore,
    RedisOnlineStore,
)
from .scheduler import Scheduler
from .scheduler_dist import DistributedScheduler
import pybreaker
import structlog
from prometheus_client import Counter, Histogram
import time

# Circuit breaker for online store
# Fail fast after 5 failures, try again after 60 seconds
online_store_breaker = pybreaker.CircuitBreaker(fail_max=5, reset_timeout=60)

# Metrics
FEATURE_REQUESTS = Counter(
    "meridian_feature_requests_total", "Total feature requests", ["feature", "status"]
)
FEATURE_LATENCY = Histogram(
    "meridian_feature_latency_seconds",
    "Latency of feature retrieval",
    ["feature", "step"],
)

logger = structlog.get_logger()


async def async_breaker_call(
    breaker: pybreaker.CircuitBreaker,
    func: Callable[..., Any],
    *args: Any,
    **kwargs: Any,
) -> Any:
    return await breaker.call_async(func, *args, **kwargs)  # type: ignore[no-untyped-call]


@dataclass
class Entity:
    name: str
    id_column: str
    description: Optional[str] = None

    def _repr_html_(self) -> str:
        return f"""
        <div style="font-family: sans-serif; border: 1px solid #e0e0e0; border-radius: 4px; padding: 10px; max-width: 600px;">
            <h3 style="margin-top: 0; color: #333;">📦 Entity: {self.name}</h3>
            <p><strong>ID Column:</strong> <code>{self.id_column}</code></p>
            <p><strong>Description:</strong> {self.description or '<em>No description</em>'}</p>
        </div>
        """


@dataclass
class Feature:
    name: str
    entity_name: str
    func: Callable[..., Any]
    refresh: Optional[timedelta] = None
    ttl: Optional[timedelta] = None
    materialize: bool = False
    description: Optional[str] = None
    stale_tolerance: Optional[timedelta] = None
    default_value: Any = None


class FeatureRegistry:
    def __init__(self) -> None:
        self.entities: Dict[str, Entity] = {}
        self.features: Dict[str, Feature] = {}

    def register_entity(self, entity: Entity) -> None:
        self.entities[entity.name] = entity

    def register_feature(self, feature: Feature) -> None:
        self.features[feature.name] = feature

    def get_features_for_entity(self, entity_name: str) -> List[Feature]:
        return [f for f in self.features.values() if f.entity_name == entity_name]


class FeatureStore:
    def __init__(
        self,
        offline_store: Optional[OfflineStore] = None,
        online_store: Optional[OnlineStore] = None,
    ) -> None:
        self.registry = FeatureRegistry()
        self.offline_store = offline_store or DuckDBOfflineStore()
        self.online_store = online_store or InMemoryOnlineStore()

        self.scheduler: Union[Scheduler, DistributedScheduler]

        # Select scheduler based on online store type
        # Select scheduler based on online store type
        if isinstance(self.online_store, RedisOnlineStore):
            self.scheduler = DistributedScheduler(self.online_store.get_sync_client())
        else:
            self.scheduler = Scheduler()

    def _repr_html_(self) -> str:
        # Count entities and features
        n_entities = len(self.registry.entities)
        n_features = len(self.registry.features)

        # Build Entity Table
        entity_rows = ""
        for name, ent in self.registry.entities.items():
            entity_rows += f"<tr><td>{name}</td><td>{ent.id_column}</td><td>{ent.description or ''}</td></tr>"

        # Build Feature Table (Top 5)
        feature_rows = ""
        for i, (name, feat) in enumerate(self.registry.features.items()):
            if i >= 5:
                feature_rows += f"<tr><td colspan='4'><em>... and {n_features - 5} more</em></td></tr>"
                break
            feature_rows += f"<tr><td>{name}</td><td>{feat.entity_name}</td><td>{feat.refresh}</td><td>{feat.materialize}</td></tr>"

        return f"""
        <div style="font-family: sans-serif; border: 1px solid #e0e0e0; border-radius: 4px; padding: 10px;">
            <h2 style="margin-top: 0; color: #1f77b4;">🧭 Meridian Feature Store</h2>
            <div style="display: flex; gap: 20px; margin-bottom: 10px;">
                <div><strong>Entities:</strong> {n_entities}</div>
                <div><strong>Features:</strong> {n_features}</div>
                <div><strong>Offline:</strong> {self.offline_store.__class__.__name__}</div>
                <div><strong>Online:</strong> {self.online_store.__class__.__name__}</div>
            </div>

            <h4>Entities</h4>
            <table style="width: 100%; border-collapse: collapse; margin-bottom: 10px;">
                <thead style="background-color: #f8f9fa;">
                    <tr><th style="text-align: left; padding: 5px;">Name</th><th style="text-align: left; padding: 5px;">ID Column</th><th style="text-align: left; padding: 5px;">Description</th></tr>
                </thead>
                <tbody>
                    {entity_rows}
                </tbody>
            </table>

            <h4>Features</h4>
            <table style="width: 100%; border-collapse: collapse;">
                <thead style="background-color: #f8f9fa;">
                    <tr><th style="text-align: left; padding: 5px;">Name</th><th style="text-align: left; padding: 5px;">Entity</th><th style="text-align: left; padding: 5px;">Refresh</th><th style="text-align: left; padding: 5px;">Materialize</th></tr>
                </thead>
                <tbody>
                    {feature_rows}
                </tbody>
            </table>
        </div>
        """

    def start(self) -> None:
        """
        Starts the scheduler and registers jobs for all materialized features.
        """
        for name, feature in self.registry.features.items():
            if feature.materialize and feature.refresh:
                self.scheduler.schedule_job(
                    func=lambda: self._materialize_feature(name),
                    interval_seconds=int(feature.refresh.total_seconds()),
                    job_id=f"materialize_{name}",
                )

    def _materialize_feature(self, feature_name: str) -> None:
        # TODO: Implement actual materialization logic (query offline -> write online)
        # For now, just log that it ran.
        print(f"Materializing feature: {feature_name}")

    async def get_training_data(
        self, entity_df: pd.DataFrame, features: List[str]
    ) -> pd.DataFrame:
        return await self.offline_store.get_training_data(entity_df, features)

    async def get_online_features(
        self, entity_name: str, entity_id: str, features: List[str]
    ) -> Dict[str, Any]:
        log = logger.bind(
            entity_name=entity_name, entity_id=entity_id, features=features
        )
        start_time = time.perf_counter()

        # 1. Try Cache (Online Store)
        try:
            with FEATURE_LATENCY.labels(feature="all", step="cache").time():
                results = await async_breaker_call(
                    online_store_breaker,
                    self.online_store.get_online_features,
                    entity_name,
                    entity_id,
                    features,
                )
        except Exception as e:
            # If online store fails completely (e.g. Redis down) or BreakerOpen, treat all as missing
            log.warning("online_store_failed", error=str(e))
            results = {}

        final_results = {}
        missing_features = []

        for feature_name in features:
            if feature_name in results:
                final_results[feature_name] = results[feature_name]
                FEATURE_REQUESTS.labels(feature=feature_name, status="hit").inc()
            else:
                missing_features.append(feature_name)
                FEATURE_REQUESTS.labels(feature=feature_name, status="miss").inc()

        if missing_features:
            log.info("cache_miss", missing_features=missing_features)

        # 2. Try Compute (On-Demand)
        for feature_name in missing_features:
            feature_def = self.registry.features.get(feature_name)
            if not feature_def:
                FEATURE_REQUESTS.labels(feature=feature_name, status="unknown").inc()
                continue

            try:
                # Execute the feature function
                with FEATURE_LATENCY.labels(
                    feature=feature_name, step="compute"
                ).time():
                    val = feature_def.func(entity_id)

                final_results[feature_name] = val
                FEATURE_REQUESTS.labels(
                    feature=feature_name, status="compute_success"
                ).inc()

                # Optionally write back to cache?
                # await self.online_store.set_online_features(entity_name, entity_id, {feature_name: val})

            except Exception as e:
                log.error("compute_failed", feature=feature_name, error=str(e))
                FEATURE_REQUESTS.labels(
                    feature=feature_name, status="compute_failure"
                ).inc()

                # 3. Try Default Value
                if feature_def.default_value is not None:
                    final_results[feature_name] = feature_def.default_value
                    FEATURE_REQUESTS.labels(
                        feature=feature_name, status="default"
                    ).inc()
                    log.info(
                        "using_default",
                        feature=feature_name,
                        default_value=feature_def.default_value,
                    )
                else:
                    FEATURE_REQUESTS.labels(feature=feature_name, status="error").inc()
                    pass

        duration = time.perf_counter() - start_time
        log.info(
            "get_online_features_complete", duration=duration, found=len(final_results)
        )
        return final_results

    def register_entity(
        self, name: str, id_column: str, description: Optional[str] = None
    ) -> Entity:
        entity = Entity(name=name, id_column=id_column, description=description)
        self.registry.register_entity(entity)
        return entity

    def register_feature(
        self,
        name: str,
        entity_name: str,
        func: Callable[..., Any],
        refresh: Optional[timedelta] = None,
        ttl: Optional[timedelta] = None,
        materialize: bool = False,
        description: Optional[str] = None,
        stale_tolerance: Optional[timedelta] = None,
        default_value: Any = None,
    ) -> Feature:
        feature = Feature(
            name=name,
            entity_name=entity_name,
            func=func,
            refresh=refresh,
            ttl=ttl,
            materialize=materialize,
            description=description,
            stale_tolerance=stale_tolerance,
            default_value=default_value,
        )
        self.registry.register_feature(feature)
        return feature


def entity(
    store: FeatureStore, id_column: Optional[str] = None
) -> Callable[[Type[Any]], Type[Any]]:
    def decorator(cls: Type[Any]) -> Type[Any]:
        # If id_column is not provided, try to infer from type hints
        nonlocal id_column
        if id_column is None:
            # Simple inference: look for the first annotated field
            annotations = get_type_hints(cls)
            if annotations:
                id_column = next(iter(annotations))
            else:
                raise ValueError(f"Could not infer id_column for entity {cls.__name__}")

        # Python's class docstring is in __doc__, but sometimes it needs to be stripped
        doc = cls.__doc__.strip() if cls.__doc__ else None
        store.register_entity(name=cls.__name__, id_column=id_column, description=doc)
        setattr(cls, "_meridian_entity_name", cls.__name__)
        setattr(cls, "_meridian_store", store)  # Link store to entity
        return cls

    return decorator


def feature(
    entity: Type[Any],
    store: Optional[FeatureStore] = None,
    refresh: Optional[Union[str, timedelta]] = None,
    ttl: Optional[Union[str, timedelta]] = None,
    materialize: bool = False,
    stale_tolerance: Optional[Union[str, timedelta]] = None,
    default_value: Any = None,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        # If store is not passed, we might need a way to find it.
        # For now, we'll assume the user passes it or we rely on a global context (which we want to avoid if possible).
        # Wait, the PRD example: @feature(entity=User, refresh="5m", materialize=True)
        # It doesn't pass 'store'.
        # This implies 'entity' (the class) might hold a reference to the store?
        # Or we rely on the fact that @entity registered it.

        # BUT, to register the feature, we need the store instance.
        # Option 1: Pass store to @feature.
        # Option 2: The Entity class knows its store.
        # Let's check if we can attach the store to the Entity class in @entity.

        nonlocal store
        if store is None:
            # Try to get store from the entity class
            store = getattr(entity, "_meridian_store", None)

        if store is None:
            raise ValueError(
                "FeatureStore instance must be provided or linked via the Entity."
            )

        # Parse refresh/ttl strings to timedelta if needed (TODO: Implement parsing logic)
        # For MVP, we'll just pass them through if they are timedeltas, or fail if strings for now until we add parsing.

        store.register_feature(
            name=func.__name__,
            entity_name=getattr(entity, "_meridian_entity_name"),
            func=func,
            refresh=refresh,  # type: ignore
            ttl=ttl,  # type: ignore
            materialize=materialize,
            description=func.__doc__,
            stale_tolerance=stale_tolerance,  # type: ignore
            default_value=default_value,
        )
        return func

    return decorator
