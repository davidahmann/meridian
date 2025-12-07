from __future__ import annotations
import pytest
import asyncio
from httpx import AsyncClient, ASGITransport
from redis.asyncio import Redis
from typing import Dict, Any
from meridian.server import create_app
from meridian.core import FeatureStore
from meridian.worker import AxiomWorker


@pytest.mark.asyncio
async def test_event_triggers_refresh(redis_client: Redis[str]) -> None:
    """
    Scenario:
    1. Ingest Event -> 2. Worker Processes -> 3. Redis Updated.
    """
    from meridian.core import entity, feature
    from dataclasses import dataclass

    # 1. Setup App & Store
    store = FeatureStore()

    @entity(store=store)
    @dataclass
    class User:
        id: str

    # Define a feature that uses the trigger
    @feature(entity=User, store=store, trigger="transaction", materialize=True)
    def user_spend(id: str, payload: Dict[str, Any]) -> int:
        return int(payload.get("amount", 0))

    app = create_app(store)

    # 2. Start Worker in Background (WITH STORE)
    worker = AxiomWorker(store=store)
    worker_task = asyncio.create_task(worker.run())

    # Allow worker to startup (group creation)
    await asyncio.sleep(0.5)

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # 3. Assert Initial State
            initial_val = await redis_client.hget("User:u1", "user_spend")
            assert initial_val is None

            # 4. Ingest Event
            payload = {"amount": 500}
            resp = await client.post(
                "/ingest/transaction", json=payload, params={"entity_id": "u1"}
            )
            assert resp.status_code == 202, f"Response: {resp.text}"

            # 5. Wait for Worker Processing
            val = None
            for i in range(20):  # Wait up to 2 seconds
                val = await redis_client.hget("User:u1", "user_spend")
                if val:
                    break
                await asyncio.sleep(0.1)

            # 6. Assert Final State
            assert val == "500"

    finally:
        # Stop worker
        worker_task.cancel()
        try:
            await worker_task
        except asyncio.CancelledError:
            pass
