from abc import ABC, abstractmethod
from typing import Dict, Any, List


class OnlineStore(ABC):
    @abstractmethod
    async def get_online_features(
        self, entity_name: str, entity_id: str, feature_names: List[str]
    ) -> Dict[str, Any]:
        """
        Retrieves feature values for a single entity from the online store.
        """
        pass

    @abstractmethod
    async def set_online_features(
        self, entity_name: str, entity_id: str, features: Dict[str, Any]
    ) -> None:
        """
        Writes feature values for a single entity to the online store.
        """
        pass


class InMemoryOnlineStore(OnlineStore):
    def __init__(self) -> None:
        # Structure: {entity_name: {entity_id: {feature_name: value}}}
        self._storage: Dict[str, Dict[str, Dict[str, Any]]] = {}

    async def get_online_features(
        self, entity_name: str, entity_id: str, feature_names: List[str]
    ) -> Dict[str, Any]:
        entity_storage = self._storage.get(entity_name, {})
        features = entity_storage.get(entity_id, {})
        return {name: features.get(name) for name in feature_names if name in features}

    async def set_online_features(
        self, entity_name: str, entity_id: str, features: Dict[str, Any]
    ) -> None:
        if entity_name not in self._storage:
            self._storage[entity_name] = {}
        if entity_id not in self._storage[entity_name]:
            self._storage[entity_name][entity_id] = {}

        self._storage[entity_name][entity_id].update(features)
