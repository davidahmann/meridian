"""Tests for Freshness SLA feature (v1.5)."""

import pytest
from datetime import datetime, timezone, timedelta

from meridian.utils.time import (
    parse_duration_to_ms,
    format_ms_to_human,
    validate_sla,
    InvalidSLAFormatError,
)
from meridian.exceptions import FreshnessSLAError
from meridian.context import context, ContextItem, AssemblyTracker


class TestSLAParsing:
    """Tests for SLA duration parsing (2.1)."""

    def test_parse_seconds(self):
        assert parse_duration_to_ms("30s") == 30_000
        assert parse_duration_to_ms("1s") == 1_000
        assert parse_duration_to_ms("120s") == 120_000

    def test_parse_minutes(self):
        assert parse_duration_to_ms("5m") == 300_000
        assert parse_duration_to_ms("1m") == 60_000
        assert parse_duration_to_ms("30m") == 1_800_000

    def test_parse_hours(self):
        assert parse_duration_to_ms("1h") == 3_600_000
        assert parse_duration_to_ms("24h") == 86_400_000

    def test_parse_days(self):
        assert parse_duration_to_ms("1d") == 86_400_000
        assert parse_duration_to_ms("7d") == 604_800_000

    def test_parse_milliseconds(self):
        assert parse_duration_to_ms("500ms") == 500
        assert parse_duration_to_ms("1000ms") == 1_000

    def test_parse_with_decimals(self):
        assert parse_duration_to_ms("1.5h") == 5_400_000
        assert parse_duration_to_ms("2.5m") == 150_000

    def test_parse_case_insensitive(self):
        assert parse_duration_to_ms("5M") == 300_000
        assert parse_duration_to_ms("1H") == 3_600_000

    def test_parse_with_whitespace(self):
        assert parse_duration_to_ms(" 5m ") == 300_000

    def test_invalid_format_raises(self):
        with pytest.raises(InvalidSLAFormatError):
            parse_duration_to_ms("invalid")

        with pytest.raises(InvalidSLAFormatError):
            parse_duration_to_ms("5x")

        with pytest.raises(InvalidSLAFormatError):
            parse_duration_to_ms("")

        with pytest.raises(InvalidSLAFormatError):
            parse_duration_to_ms("m5")

    def test_validate_sla_none(self):
        assert validate_sla(None) is None

    def test_validate_sla_valid(self):
        assert validate_sla("5m") == 300_000


class TestFormatMsToHuman:
    """Tests for human-readable duration formatting."""

    def test_format_milliseconds(self):
        assert format_ms_to_human(500) == "500ms"
        assert format_ms_to_human(999) == "999ms"

    def test_format_seconds(self):
        assert format_ms_to_human(1000) == "1s"
        assert format_ms_to_human(30000) == "30s"

    def test_format_minutes(self):
        assert format_ms_to_human(60000) == "1m"
        assert format_ms_to_human(90000) == "1m 30s"

    def test_format_hours(self):
        assert format_ms_to_human(3600000) == "1h"
        assert format_ms_to_human(5400000) == "1h 30m"

    def test_format_days(self):
        assert format_ms_to_human(86400000) == "1d"
        assert format_ms_to_human(90000000) == "1d 1h"


class TestFreshnessSLAError:
    """Tests for FreshnessSLAError exception."""

    def test_error_creation(self):
        violations = [
            {"feature": "user_tier", "age_ms": 360000, "sla_ms": 300000},
            {"feature": "purchase_count", "age_ms": 400000, "sla_ms": 300000},
        ]
        error = FreshnessSLAError("SLA breached", violations)

        assert error.message == "SLA breached"
        assert len(error.violations) == 2
        assert error.violations[0]["feature"] == "user_tier"

    def test_error_str(self):
        violations = [{"feature": "user_tier", "age_ms": 360000, "sla_ms": 300000}]
        error = FreshnessSLAError("SLA breached", violations)

        assert "user_tier" in str(error)
        assert "360000ms" in str(error)
        assert "300000ms" in str(error)

    def test_error_repr(self):
        violations = [{"feature": "user_tier", "age_ms": 360000, "sla_ms": 300000}]
        error = FreshnessSLAError("SLA breached", violations)

        assert "FreshnessSLAError" in repr(error)
        assert "user_tier" in repr(error)


class TestContextDecoratorWithFreshnessSLA:
    """Tests for @context decorator with freshness_sla parameter."""

    @pytest.mark.asyncio
    async def test_invalid_sla_format_raises_at_decoration(self):
        """Invalid SLA format should raise immediately when decorator is applied."""
        with pytest.raises(InvalidSLAFormatError):

            @context(freshness_sla="invalid")
            async def bad_context():
                return [ContextItem(content="test")]

    @pytest.mark.asyncio
    async def test_valid_sla_format_accepted(self):
        """Valid SLA formats should be accepted."""

        @context(freshness_sla="5m")
        async def good_context():
            return [ContextItem(content="test")]

        # Should not raise
        assert good_context is not None

    @pytest.mark.asyncio
    async def test_context_freshness_guaranteed_when_all_fresh(self):
        """Context should be 'guaranteed' when all features are within SLA."""

        @context(freshness_sla="5m")
        async def fresh_context():
            return [ContextItem(content="test")]

        ctx = await fresh_context()
        assert ctx.meta["freshness_status"] == "guaranteed"
        assert ctx.meta["freshness_violations"] == []

    @pytest.mark.asyncio
    async def test_context_without_sla_is_guaranteed(self):
        """Context without SLA should default to 'guaranteed'."""

        @context()
        async def no_sla_context():
            return [ContextItem(content="test")]

        ctx = await no_sla_context()
        assert ctx.meta["freshness_status"] == "guaranteed"


class TestContextDecoratorStrictMode:
    """Tests for strict mode with FreshnessSLAError."""

    @pytest.mark.asyncio
    async def test_strict_mode_default_is_false(self):
        """Default freshness_strict should be False."""

        @context(freshness_sla="5m")
        async def context_func():
            return [ContextItem(content="test")]

        # Should not raise even if violations exist (mock would be needed)
        ctx = await context_func()
        assert ctx is not None

    @pytest.mark.asyncio
    async def test_strict_mode_no_error_when_fresh(self):
        """Strict mode should not raise when all features are fresh."""

        @context(freshness_sla="5m", freshness_strict=True)
        async def strict_context():
            return [ContextItem(content="test")]

        ctx = await strict_context()
        assert ctx.meta["freshness_status"] == "guaranteed"


class TestAssemblyTrackerFreshness:
    """Tests for AssemblyTracker freshness tracking."""

    def test_get_stalest_feature_ms_empty(self):
        """Empty tracker should return 0 for stalest feature."""
        tracker = AssemblyTracker(context_id="test-id")
        assert tracker.get_stalest_feature_ms() == 0

    def test_get_stalest_feature_ms_with_features(self):
        """Tracker should return max freshness_ms."""
        tracker = AssemblyTracker(context_id="test-id")

        # Record features with different ages
        now = datetime.now(timezone.utc)
        tracker.record_feature(
            feature_name="feature1",
            entity_id="user_1",
            value="val1",
            timestamp=now - timedelta(seconds=30),
            source="compute",
        )
        tracker.record_feature(
            feature_name="feature2",
            entity_id="user_1",
            value="val2",
            timestamp=now - timedelta(seconds=60),
            source="compute",
        )

        stalest = tracker.get_stalest_feature_ms()
        # Should be approximately 60 seconds = 60000ms
        assert stalest > 55000
        assert stalest < 65000

    def test_record_feature_calculates_freshness(self):
        """record_feature should calculate freshness_ms from timestamp."""
        tracker = AssemblyTracker(context_id="test-id")

        # Record a feature that's 5 seconds old
        old_time = datetime.now(timezone.utc) - timedelta(seconds=5)
        tracker.record_feature(
            feature_name="test_feature",
            entity_id="entity_1",
            value="value",
            timestamp=old_time,
            source="cache",
        )

        assert len(tracker.features) == 1
        assert tracker.features[0].feature_name == "test_feature"
        assert tracker.features[0].freshness_ms > 4000
        assert tracker.features[0].freshness_ms < 6000


class TestContextMetaFreshnessFields:
    """Tests for context meta freshness fields."""

    @pytest.mark.asyncio
    async def test_context_includes_freshness_violations_field(self):
        """Context meta should include freshness_violations list."""

        @context(freshness_sla="5m")
        async def context_func():
            return [ContextItem(content="test")]

        ctx = await context_func()
        assert "freshness_violations" in ctx.meta
        assert isinstance(ctx.meta["freshness_violations"], list)

    @pytest.mark.asyncio
    async def test_context_includes_freshness_sla_ms_field(self):
        """Context meta should include freshness_sla_ms when SLA is set."""

        @context(freshness_sla="5m")
        async def context_func():
            return [ContextItem(content="test")]

        ctx = await context_func()
        assert ctx.meta["freshness_sla_ms"] == 300_000

    @pytest.mark.asyncio
    async def test_context_freshness_sla_ms_none_when_not_set(self):
        """Context meta should have freshness_sla_ms=None when no SLA."""

        @context()
        async def context_func():
            return [ContextItem(content="test")]

        ctx = await context_func()
        assert ctx.meta["freshness_sla_ms"] is None
