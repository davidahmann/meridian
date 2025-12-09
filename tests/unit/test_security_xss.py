import pytest
from unittest.mock import AsyncMock, MagicMock
from meridian.server import create_app
from meridian.models import ContextTrace
from fastapi.testclient import TestClient


@pytest.mark.asyncio
async def test_xss_prevention() -> None:
    # Safe mocked store
    store_mock = MagicMock()
    store_mock.online_store.get = AsyncMock()

    # Trace with Malicious Payload
    # Use a payload without "/" to avoid routing 404s with encoded slashes in TestClient
    malicious_id = "<img src=x onerror=alert(1)>"
    malicious_src = "<script>alert('src')</script>"

    fake_trace = ContextTrace(
        context_id=malicious_id,
        latency_ms=10.0,
        token_usage=100,
        freshness_status="guaranteed",
        # Source ID also containing XSS
        source_ids=[malicious_src],
        stale_sources=[],
        cost_usd=0.01,
        cache_hit=False,
    )

    store_mock.online_store.get.return_value = fake_trace.model_dump_json()

    app = create_app(store_mock)
    client = TestClient(app)

    # Request with malicious ID in URL (reflected in page)
    # Note: FastAPI/Starlette URL encoding handles the path param, but we check if it is reflected in body unsafely.
    # The vulnerability report said context_id is reflected.

    # We pass a safe URL structure but the ID *inside the trace* (which we mocked above) contains the attack
    # We also use the ID in the URL to see if *that* is reflected safely.

    # Case 1: Reflected XSS (ID in URL)
    # We pass the malicious ID in the URL.
    # Note: TestClient/FastAPI might url-decodes it.
    import urllib.parse

    encoded_id = urllib.parse.quote(malicious_id, safe="")

    response = client.get(f"/context/{encoded_id}/visualize")
    assert response.status_code == 200
    html_content = response.text

    # Verify Reflected ID is escaped
    # malicious_id <img src=x onerror=alert(1)> should become &lt;img src=x onerror=alert(1)&gt;
    assert "&lt;img src=x onerror=alert(1)&gt;" in html_content
    assert "<img" not in html_content

    # Case 2: Stored XSS (Source ID in Trace)
    # malicious_src <script>alert('src')</script> should become &lt;script&gt;

    # Verify Stored Source ID is escaped
    # html.escape escapes ' as &#x27; by default
    assert "&lt;script&gt;alert(&#x27;src&#x27;)&lt;/script&gt;" in html_content
    assert "<script>" not in html_content
