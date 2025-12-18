from __future__ import annotations
import pytest
import os
from typing import AsyncGenerator, Generator, Dict, Any
from testcontainers.redis import RedisContainer
from testcontainers.postgres import PostgresContainer
from redis.asyncio import Redis as AsyncRedis
import pytest_asyncio

# Ensure hermetic defaults during test *collection* (module import time).
# Some tests instantiate stores at import time, before fixtures run.
os.environ.setdefault("FABRA_DUCKDB_PATH", ":memory:")

# NOTE: We will import AxiomWorker later once we create it.
# For now, we mock the worker start/stop or use a placeholder if the file implies it needs to be there.
# Since we are doing TDD, we might need to create a dummy worker class or just comment it out
# until Step 3. However, the plan says "Harness first".
# To make the harness compile, we need the worker class to exist or be mocked.
# I will assume we create a skeleton Worker in Step 3, but for Step 1
# we can just setup the containers.


@pytest.fixture(scope="session")
def infrastructure() -> Generator[Dict[str, Any], None, None]:
    """
    Spins up the real world: Redis and Postgres.
    """
    # 1. Spin up Containers
    with (
        RedisContainer() as redis,
        PostgresContainer("pgvector/pgvector:pg16") as postgres,
    ):
        # Get URLs
        # testcontainers-python RedisContainer might not implement get_connection_url in all versions
        redis_host = redis.get_container_host_ip()
        redis_port = redis.get_exposed_port(6379)
        redis_url = f"redis://{redis_host}:{redis_port}"

        # Fix for some testcontainers versions returning psycopg2 url
        # We want postgresql+asyncpg://...
        postgres_url = postgres.get_connection_url().replace(
            "postgresql+psycopg2://", "postgresql+asyncpg://"
        )

        # 2. Override Config via Environment Variables
        os.environ["FABRA_ENV"] = "production"
        os.environ["FABRA_REDIS_URL"] = redis_url
        os.environ["FABRA_POSTGRES_URL"] = postgres_url

        yield {"redis_url": redis_url, "postgres_url": postgres_url}


@pytest.fixture(scope="session", autouse=True)
def _isolate_duckdb_path() -> None:
    """
    Keep unit tests hermetic by default.

    DevConfig now defaults to a durable DuckDB file; tests should not write to
    a developer's home directory unless explicitly requested.
    """
    os.environ.setdefault("FABRA_DUCKDB_PATH", ":memory:")


@pytest_asyncio.fixture
async def redis_client(
    infrastructure: Dict[str, Any],
) -> AsyncGenerator[AsyncRedis[str], None]:
    """
    Provides an async redis client connected to the container.
    """
    client = AsyncRedis.from_url(infrastructure["redis_url"], decode_responses=True)
    yield client
    await client.close()


@pytest.fixture(scope="session")
def postgres_url(infrastructure: Dict[str, Any]) -> str:
    """Provide postgres_url string to tests."""
    return infrastructure["postgres_url"]
