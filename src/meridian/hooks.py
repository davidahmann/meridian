from abc import ABC
from typing import Dict, Any, List, Optional
import structlog

logger = structlog.get_logger()


class Hook(ABC):
    """
    Abstract base class for Meridian hooks.
    Subclasses can implement methods to intercept lifecycle events.
    """

    @property
    def name(self) -> str:
        return self.__class__.__name__

    async def before_feature_retrieval(
        self, entity_name: str, entity_id: str, features: List[str]
    ) -> None:
        """
        Called before fetching features from the online store.
        Can be used for validation, logging, or modifying the request (if mutable).
        """
        pass

    async def after_feature_retrieval(
        self,
        entity_name: str,
        entity_id: str,
        features: List[str],
        result: Dict[str, Any],
    ) -> None:
        """
        Called after fetching features.
        Can be used for auditing, post-processing, or enhancing the result.
        """

    async def after_ingest(
        self, event_type: str, entity_id: str, payload: Dict[str, Any]
    ) -> None:
        """
        Called after an event is ingested.
        """
        pass


class WebhookHook(Hook):
    """
    Hook that sends a webhook POST request on event ingestion.
    """

    def __init__(self, url: str, headers: Optional[Dict[str, str]] = None):
        self.url = url
        self.headers = headers or {}

    async def after_ingest(
        self, event_type: str, entity_id: str, payload: Dict[str, Any]
    ) -> None:
        import httpx

        try:
            async with httpx.AsyncClient() as client:
                data = {
                    "event": event_type,
                    "entity_id": entity_id,
                    "payload": payload,
                    "timestamp": 0,  # TODO: add timestamp if needed
                }
                resp = await client.post(self.url, json=data, headers=self.headers)
                resp.raise_for_status()
                logger.info("webhook_sent", url=self.url, status=resp.status_code)
        except Exception as e:
            # We log but don't raise, to avoid breaking the ingest flow
            logger.error("webhook_failed", url=self.url, error=str(e))


class HookManager:
    """
    Manages registration and execution of hooks.
    """

    def __init__(self, hooks: Optional[List[Hook]] = None):
        self.hooks: List[Hook] = hooks or []

    def register(self, hook: Hook) -> None:
        """Register a new hook."""
        self.hooks.append(hook)
        logger.info("hook_registered", hook_name=hook.name)

    async def trigger_before_retrieval(
        self, entity_name: str, entity_id: str, features: List[str]
    ) -> None:
        for hook in self.hooks:
            try:
                await hook.before_feature_retrieval(entity_name, entity_id, features)
            except Exception as e:
                logger.error(
                    "hook_execution_failed",
                    hook=hook.name,
                    stage="before_retrieval",
                    error=str(e),
                )

    async def trigger_after_retrieval(
        self,
        entity_name: str,
        entity_id: str,
        features: List[str],
        result: Dict[str, Any],
    ) -> None:
        for hook in self.hooks:
            try:
                await hook.after_feature_retrieval(
                    entity_name, entity_id, features, result
                )
            except Exception as e:
                logger.error(
                    "hook_execution_failed",
                    hook=hook.name,
                    stage="after_retrieval",
                    error=str(e),
                )

    async def trigger_after_ingest(
        self, event_type: str, entity_id: str, payload: Dict[str, Any]
    ) -> None:
        for hook in self.hooks:
            try:
                await hook.after_ingest(event_type, entity_id, payload)
            except Exception as e:
                logger.error(
                    "hook_execution_failed",
                    hook=hook.name,
                    stage="after_ingest",
                    error=str(e),
                )
