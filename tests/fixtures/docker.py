"""Docker container fixtures for integration tests."""

import pytest
import redis
import os


@pytest.fixture(scope="session")
def postgres_url() -> str:
    """Get Postgres connection URL from environment or use local test DB."""
    return os.getenv(
        "FABRA_POSTGRES_URL",
        "postgresql://fabra:fabra_test_password@localhost:5433/fabra_test",  # pragma: allowlist secret
    )


@pytest.fixture(scope="session")
def redis_url() -> str:
    """Get Redis connection URL from environment or use local test instance."""
    return os.getenv("FABRA_REDIS_URL", "redis://localhost:6380/0")


@pytest.fixture
def redis_client(redis_url: str):
    """Create a Redis client for testing."""
    client = redis.from_url(redis_url)
    client.flushdb()  # Clean before test
    yield client
    client.flushdb()  # Clean after test
    client.close()
