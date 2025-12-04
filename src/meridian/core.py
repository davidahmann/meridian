from typing import Any, Callable, Dict, Optional, Type, Union, List
from dataclasses import dataclass
from datetime import timedelta
import inspect
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


@dataclass
class Entity:
    name: str
    id_column: str
    description: Optional[str] = None


@dataclass
class Feature:
    name: str
    entity_name: str
    func: Callable[..., Any]
    refresh: Optional[timedelta] = None
    ttl: Optional[timedelta] = None
    materialize: bool = False
    description: Optional[str] = None


class FeatureRegistry:
    def __init__(self) -> None:
        self.entities: Dict[str, Entity] = {}
        self.features: Dict[str, Feature] = {}

    def register_entity(self, entity: Entity) -> None:
        self.entities[entity.name] = entity

    def register_feature(self, feature: Feature) -> None:
        self.features[feature.name] = feature


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
        if isinstance(self.online_store, RedisOnlineStore):
            self.scheduler = DistributedScheduler(self.online_store.client)
        else:
            self.scheduler = Scheduler()

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

    def get_training_data(
        self, entity_df: pd.DataFrame, features: List[str]
    ) -> pd.DataFrame:
        return self.offline_store.get_training_data(entity_df, features)

    def get_online_features(
        self, entity_name: str, entity_id: str, features: List[str]
    ) -> Dict[str, Any]:
        return self.online_store.get_online_features(entity_name, entity_id, features)

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
    ) -> Feature:
        feature = Feature(
            name=name,
            entity_name=entity_name,
            func=func,
            refresh=refresh,
            ttl=ttl,
            materialize=materialize,
            description=description,
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
            annotations = inspect.get_annotations(cls)
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
        )
        return func

    return decorator
