import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from meridian.server import create_app
from meridian.core import FeatureStore
from meridian.hooks import WebhookHook
from fastapi.testclient import TestClient


@pytest.fixture
def mock_store() -> MagicMock:
    store = MagicMock(spec=FeatureStore)
    store.offline_store = MagicMock()
    # Mock online store for ingest endpoint (it checks for it)
    store.online_store = MagicMock()
    store.online_store.client = MagicMock()  # Redis client mock

    # We need real HookManager to test the triggering
    from meridian.hooks import HookManager

    store.hooks = HookManager()

    return store


@pytest.mark.asyncio
async def test_webhook_trigger(mock_store: MagicMock) -> None:
    # Mock httpx to intercept webhook call
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        # Return a sync MagicMock for the response, not an AsyncMock
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        # Register Webhook
        hook = WebhookHook(url="http://example.com/webhook")
        mock_store.hooks.register(hook)

        app = create_app(mock_store)
        client = TestClient(app)

        # Trigger Ingest
        # We need to mock RedisEventBus publish to avoid connecting to real Redis
        # The previous error "None object is not iterable" might be from mock_publish usage?
        # No, probably from how patch context manager is used or return value.
        with patch(
            "meridian.bus.RedisEventBus.publish", new_callable=AsyncMock
        ) as mock_publish:
            mock_publish.return_value = "msg-123"

            resp = client.post(
                "/v1/ingest/click_event?entity_id=user-123", json={"button": "signup"}
            )

            assert resp.status_code == 202

            # Verify Webhook was called
            mock_post.assert_awaited_once()
            args, kwargs = mock_post.await_args  # type: ignore
            assert args[0] == "http://example.com/webhook"
            assert kwargs["json"]["event"] == "click_event"
            assert kwargs["json"]["entity_id"] == "user-123"
            assert kwargs["json"]["payload"] == {"button": "signup"}
