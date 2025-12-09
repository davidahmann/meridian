"""End-to-end integration tests for Freshness SLAs (v1.5)."""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch

from meridian.context import (
    context,
    ContextItem,
    _assembly_tracker,
)
from meridian.exceptions import FreshnessSLAError


class TestFreshnessE2E:
    """End-to-end tests for freshness SLA feature."""

    @pytest.mark.asyncio
    async def test_degraded_mode_with_stale_feature(self):
        """Test that stale features trigger degraded mode but don't fail."""

        @context(freshness_sla="30s")
        async def build_prompt():
            # Simulate recording a stale feature (2 minutes old)
            tracker = _assembly_tracker.get()
            if tracker:
                stale_time = datetime.now(timezone.utc) - timedelta(minutes=2)
                tracker.record_feature(
                    feature_name="user_tier",
                    entity_id="user_123",
                    value="premium",
                    timestamp=stale_time,
                    source="cache",
                )
            return [ContextItem(content="User is premium tier.")]

        ctx = await build_prompt()

        # Should succeed but be degraded
        assert ctx.meta["freshness_status"] == "degraded"
        assert len(ctx.meta["freshness_violations"]) == 1
        assert ctx.meta["freshness_violations"][0]["feature"] == "user_tier"
        assert ctx.meta["freshness_violations"][0]["sla_ms"] == 30_000
        assert ctx.meta["freshness_violations"][0]["age_ms"] > 100_000  # > 100s

    @pytest.mark.asyncio
    async def test_guaranteed_mode_with_fresh_features(self):
        """Test that fresh features result in guaranteed status."""

        @context(freshness_sla="5m")
        async def build_prompt():
            # Simulate recording a fresh feature (5 seconds old)
            tracker = _assembly_tracker.get()
            if tracker:
                fresh_time = datetime.now(timezone.utc) - timedelta(seconds=5)
                tracker.record_feature(
                    feature_name="user_tier",
                    entity_id="user_123",
                    value="premium",
                    timestamp=fresh_time,
                    source="compute",
                )
            return [ContextItem(content="User is premium tier.")]

        ctx = await build_prompt()

        # Should be guaranteed
        assert ctx.meta["freshness_status"] == "guaranteed"
        assert ctx.meta["freshness_violations"] == []

    @pytest.mark.asyncio
    async def test_strict_mode_raises_on_stale_feature(self):
        """Test that strict mode raises FreshnessSLAError on violations."""

        @context(freshness_sla="30s", freshness_strict=True)
        async def strict_prompt():
            # Simulate recording a stale feature
            tracker = _assembly_tracker.get()
            if tracker:
                stale_time = datetime.now(timezone.utc) - timedelta(minutes=5)
                tracker.record_feature(
                    feature_name="critical_feature",
                    entity_id="entity_1",
                    value="stale_value",
                    timestamp=stale_time,
                    source="cache",
                )
            return [ContextItem(content="Content with stale data.")]

        with pytest.raises(FreshnessSLAError) as exc_info:
            await strict_prompt()

        assert "1 feature(s)" in str(exc_info.value)
        assert len(exc_info.value.violations) == 1
        assert exc_info.value.violations[0]["feature"] == "critical_feature"

    @pytest.mark.asyncio
    async def test_multiple_features_partial_violations(self):
        """Test with multiple features where only some violate SLA."""

        @context(freshness_sla="1m")
        async def multi_feature_prompt():
            tracker = _assembly_tracker.get()
            if tracker:
                # Fresh feature (10 seconds old)
                tracker.record_feature(
                    feature_name="fresh_feature",
                    entity_id="user_1",
                    value="fresh_val",
                    timestamp=datetime.now(timezone.utc) - timedelta(seconds=10),
                    source="compute",
                )
                # Stale feature (5 minutes old)
                tracker.record_feature(
                    feature_name="stale_feature",
                    entity_id="user_1",
                    value="stale_val",
                    timestamp=datetime.now(timezone.utc) - timedelta(minutes=5),
                    source="cache",
                )
            return [ContextItem(content="Mixed freshness content.")]

        ctx = await multi_feature_prompt()

        assert ctx.meta["freshness_status"] == "degraded"
        assert len(ctx.meta["freshness_violations"]) == 1
        assert ctx.meta["freshness_violations"][0]["feature"] == "stale_feature"
        # Fresh feature should not be in violations
        assert all(
            v["feature"] != "fresh_feature" for v in ctx.meta["freshness_violations"]
        )

    @pytest.mark.asyncio
    async def test_stale_sources_includes_violated_features(self):
        """Test that stale_sources includes features that violated SLA."""

        @context(freshness_sla="30s")
        async def prompt_with_violations():
            tracker = _assembly_tracker.get()
            if tracker:
                tracker.record_feature(
                    feature_name="violated_feature",
                    entity_id="user_1",
                    value="val",
                    timestamp=datetime.now(timezone.utc) - timedelta(minutes=2),
                    source="cache",
                )
            return [ContextItem(content="Content")]

        ctx = await prompt_with_violations()

        assert "violated_feature" in ctx.meta["stale_sources"]

    @pytest.mark.asyncio
    async def test_context_is_fresh_property(self):
        """Test the is_fresh property on Context."""

        @context(freshness_sla="30s")
        async def guaranteed_prompt():
            return [ContextItem(content="Fresh content")]

        ctx_fresh = await guaranteed_prompt()
        assert ctx_fresh.is_fresh is True

        @context(freshness_sla="30s")
        async def degraded_prompt():
            tracker = _assembly_tracker.get()
            if tracker:
                tracker.record_feature(
                    feature_name="stale",
                    entity_id="e1",
                    value="v1",
                    timestamp=datetime.now(timezone.utc) - timedelta(minutes=5),
                    source="cache",
                )
            return [ContextItem(content="Stale content")]

        ctx_stale = await degraded_prompt()
        assert ctx_stale.is_fresh is False

    @pytest.mark.asyncio
    async def test_no_sla_means_no_violations(self):
        """Test that without SLA, no freshness violations are recorded."""

        @context()  # No freshness_sla
        async def no_sla_prompt():
            tracker = _assembly_tracker.get()
            if tracker:
                # Even very old feature should not cause violation
                tracker.record_feature(
                    feature_name="old_feature",
                    entity_id="e1",
                    value="v1",
                    timestamp=datetime.now(timezone.utc) - timedelta(days=30),
                    source="cache",
                )
            return [ContextItem(content="Content")]

        ctx = await no_sla_prompt()

        # Should be guaranteed (no SLA to violate)
        assert ctx.meta["freshness_status"] == "guaranteed"
        assert ctx.meta["freshness_violations"] == []
        assert ctx.meta["freshness_sla_ms"] is None


class TestFreshnessMetrics:
    """Tests for freshness metrics recording."""

    @pytest.mark.asyncio
    async def test_metrics_recorded_for_degraded_context(self):
        """Test that metrics are recorded when context is degraded."""
        from meridian.observability import ContextMetrics

        with patch.object(ContextMetrics, "record_freshness_status") as mock_status:
            with patch.object(
                ContextMetrics, "record_freshness_violation"
            ) as mock_violation:
                with patch.object(
                    ContextMetrics, "record_stalest_feature"
                ) as mock_stalest:

                    @context(freshness_sla="30s")
                    async def metriced_prompt():
                        tracker = _assembly_tracker.get()
                        if tracker:
                            tracker.record_feature(
                                feature_name="metric_feature",
                                entity_id="e1",
                                value="v1",
                                timestamp=datetime.now(timezone.utc)
                                - timedelta(minutes=2),
                                source="cache",
                            )
                        return [ContextItem(content="Content")]

                    await metriced_prompt()

                    # Check metrics were called
                    mock_status.assert_called_once_with("degraded")
                    mock_violation.assert_called_once_with("metric_feature")
                    mock_stalest.assert_called_once()

    @pytest.mark.asyncio
    async def test_metrics_recorded_for_guaranteed_context(self):
        """Test that metrics are recorded when context is guaranteed."""
        from meridian.observability import ContextMetrics

        with patch.object(ContextMetrics, "record_freshness_status") as mock_status:

            @context(freshness_sla="5m")
            async def fresh_prompt():
                return [ContextItem(content="Fresh content")]

            await fresh_prompt()

            mock_status.assert_called_once_with("guaranteed")
