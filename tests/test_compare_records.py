"""Tests for compare_records() function (Phase 5 of CRS-001)."""

from datetime import datetime, timezone, timedelta

from fabra.models import (
    ContextRecord,
    FeatureRecord,
    AssemblyDecisions,
    DroppedItem,
    LineageMetadata,
    IntegrityMetadata,
)
from fabra.utils.compare import compare_records, format_diff_report
from fabra.utils.integrity import compute_content_hash


def _create_test_record(
    context_id: str = "ctx_test-12345",
    content: str = "Test context content",
    created_at: datetime = None,
    features: list = None,
    dropped_items: list = None,
    inputs: dict = None,
    tokens_used: int = 100,
    freshness_status: str = "guaranteed",
) -> ContextRecord:
    """Create a ContextRecord for testing."""
    if created_at is None:
        created_at = datetime.now(timezone.utc)
    if features is None:
        features = []
    if dropped_items is None:
        dropped_items = []
    if inputs is None:
        inputs = {"user_id": "u123"}

    content_hash = compute_content_hash(content)

    return ContextRecord(
        context_id=context_id,
        created_at=created_at,
        environment="development",
        schema_version="1.0.0",
        inputs=inputs,
        context_function="test_context",
        content=content,
        token_count=len(content.split()),
        features=features,
        retrieved_items=[],
        assembly=AssemblyDecisions(
            max_tokens=1000,
            tokens_used=tokens_used,
            items_provided=3,
            items_included=3 - len(dropped_items),
            dropped_items=dropped_items,
            freshness_status=freshness_status,
        ),
        lineage=LineageMetadata(
            features_used=[f.name for f in features],
            retrievers_used=[],
            indexes_used=[],
            fabra_version="2.0.7",
            estimated_cost_usd=0.001,
        ),
        integrity=IntegrityMetadata(
            record_hash="",
            content_hash=content_hash,
        ),
    )


class TestCompareRecordsBasic:
    """Basic tests for compare_records()."""

    def test_identical_records_no_changes(self):
        """Identical records should show no changes."""
        now = datetime.now(timezone.utc)
        record1 = _create_test_record(
            context_id="ctx_base", content="Same content", created_at=now
        )
        record2 = _create_test_record(
            context_id="ctx_comp", content="Same content", created_at=now
        )

        diff = compare_records(record1, record2)

        assert not diff.has_changes
        assert diff.features_added == 0
        assert diff.features_removed == 0
        assert diff.features_modified == 0
        assert diff.content_diff.similarity_score == 1.0
        assert diff.items_dropped_delta == 0

    def test_different_content_detected(self):
        """Different content should be detected."""
        record1 = _create_test_record(content="Original content")
        record2 = _create_test_record(content="Modified content")

        diff = compare_records(record1, record2)

        assert diff.has_changes
        assert diff.content_diff.similarity_score < 1.0
        assert "content:" in diff.change_summary

    def test_time_delta_calculated(self):
        """Time delta should be calculated correctly."""
        now = datetime.now(timezone.utc)
        record1 = _create_test_record(created_at=now)
        record2 = _create_test_record(created_at=now + timedelta(seconds=5))

        diff = compare_records(record1, record2)

        assert diff.time_delta_ms == 5000

    def test_inputs_modified_detected(self):
        record1 = _create_test_record(inputs={"user_id": "u123", "answer": "a"})
        record2 = _create_test_record(inputs={"user_id": "u123", "answer": "b"})

        diff = compare_records(record1, record2)

        assert diff.has_changes
        assert diff.inputs_modified == 1
        assert "inputs:" in diff.change_summary


class TestCompareRecordsFeatures:
    """Tests for feature comparison in compare_records()."""

    def test_feature_added(self):
        """Added feature should be detected."""
        now = datetime.now(timezone.utc)
        record1 = _create_test_record(features=[])
        record2 = _create_test_record(
            features=[
                FeatureRecord(
                    name="user_tier",
                    entity_id="u123",
                    value="premium",
                    source="cache",
                    as_of=now,
                    freshness_ms=50,
                )
            ]
        )

        diff = compare_records(record1, record2)

        assert diff.has_changes
        assert diff.features_added == 1
        assert diff.features_removed == 0
        assert "1 features added" in diff.change_summary

    def test_feature_removed(self):
        """Removed feature should be detected."""
        now = datetime.now(timezone.utc)
        record1 = _create_test_record(
            features=[
                FeatureRecord(
                    name="user_tier",
                    entity_id="u123",
                    value="premium",
                    source="cache",
                    as_of=now,
                    freshness_ms=50,
                )
            ]
        )
        record2 = _create_test_record(features=[])

        diff = compare_records(record1, record2)

        assert diff.has_changes
        assert diff.features_added == 0
        assert diff.features_removed == 1
        assert "1 features removed" in diff.change_summary

    def test_feature_modified(self):
        """Modified feature value should be detected."""
        now = datetime.now(timezone.utc)
        record1 = _create_test_record(
            features=[
                FeatureRecord(
                    name="user_tier",
                    entity_id="u123",
                    value="free",
                    source="cache",
                    as_of=now,
                    freshness_ms=50,
                )
            ]
        )
        record2 = _create_test_record(
            features=[
                FeatureRecord(
                    name="user_tier",
                    entity_id="u123",
                    value="premium",
                    source="cache",
                    as_of=now,
                    freshness_ms=50,
                )
            ]
        )

        diff = compare_records(record1, record2)

        assert diff.has_changes
        assert diff.features_modified == 1
        assert "1 features modified" in diff.change_summary


class TestCompareRecordsDroppedItems:
    """Tests for dropped items comparison."""

    def test_dropped_items_increase(self):
        """Increase in dropped items should be detected."""
        record1 = _create_test_record(dropped_items=[])
        record2 = _create_test_record(
            dropped_items=[
                DroppedItem(
                    source_id="extra_context",
                    priority=0,
                    token_count=100,
                    reason="budget_exceeded",
                )
            ]
        )

        diff = compare_records(record1, record2)

        assert diff.has_changes
        assert len(diff.items_dropped_base) == 0
        assert len(diff.items_dropped_comparison) == 1
        assert diff.items_dropped_delta == 1
        assert "dropped items: +1" in diff.change_summary

    def test_dropped_items_decrease(self):
        """Decrease in dropped items should be detected."""
        record1 = _create_test_record(
            dropped_items=[
                DroppedItem(
                    source_id="item_a",
                    priority=0,
                    token_count=50,
                    reason="budget_exceeded",
                ),
                DroppedItem(
                    source_id="item_b",
                    priority=1,
                    token_count=100,
                    reason="priority_cutoff",
                ),
            ]
        )
        record2 = _create_test_record(dropped_items=[])

        diff = compare_records(record1, record2)

        assert diff.has_changes
        assert len(diff.items_dropped_base) == 2
        assert len(diff.items_dropped_comparison) == 0
        assert diff.items_dropped_delta == -2

    def test_dropped_items_preserved_in_diff(self):
        """Dropped item details should be preserved in diff."""
        dropped = DroppedItem(
            source_id="chunk_xyz",
            priority=2,
            token_count=250,
            reason="budget_exceeded",
        )
        record1 = _create_test_record(dropped_items=[])
        record2 = _create_test_record(dropped_items=[dropped])

        diff = compare_records(record1, record2)

        assert len(diff.items_dropped_comparison) == 1
        assert diff.items_dropped_comparison[0].source_id == "chunk_xyz"
        assert diff.items_dropped_comparison[0].token_count == 250


class TestCompareRecordsFreshness:
    """Tests for freshness comparison."""

    def test_freshness_improved(self):
        """Freshness improvement should be detected."""
        record1 = _create_test_record(freshness_status="degraded")
        record2 = _create_test_record(freshness_status="guaranteed")

        diff = compare_records(record1, record2)

        assert diff.freshness_improved
        assert diff.base_freshness_status == "degraded"
        assert diff.comparison_freshness_status == "guaranteed"

    def test_freshness_degraded(self):
        """Freshness degradation should be detected."""
        record1 = _create_test_record(freshness_status="guaranteed")
        record2 = _create_test_record(freshness_status="degraded")

        diff = compare_records(record1, record2)

        assert not diff.freshness_improved


class TestCompareRecordsIntegrity:
    """Tests for integrity hash tracking in diff."""

    def test_content_hashes_included(self):
        """Content hashes should be included in diff."""
        record1 = _create_test_record(content="Content A")
        record2 = _create_test_record(content="Content B")

        diff = compare_records(record1, record2)

        assert diff.base_content_hash is not None
        assert diff.comparison_content_hash is not None
        assert diff.base_content_hash != diff.comparison_content_hash

    def test_same_content_same_hash(self):
        """Same content should have same hash."""
        record1 = _create_test_record(content="Same content")
        record2 = _create_test_record(content="Same content")

        diff = compare_records(record1, record2)

        assert diff.base_content_hash == diff.comparison_content_hash


class TestCompareRecordsTokens:
    """Tests for token delta calculation."""

    def test_token_delta_positive(self):
        """Increased token usage should show positive delta."""
        record1 = _create_test_record(tokens_used=100)
        record2 = _create_test_record(tokens_used=150)

        diff = compare_records(record1, record2)

        assert diff.token_delta == 50
        assert "tokens: +50" in diff.change_summary

    def test_token_delta_negative(self):
        """Decreased token usage should show negative delta."""
        record1 = _create_test_record(tokens_used=200)
        record2 = _create_test_record(tokens_used=100)

        diff = compare_records(record1, record2)

        assert diff.token_delta == -100


class TestFormatDiffReport:
    """Tests for format_diff_report() with CRS-001 fields."""

    def test_dropped_items_in_report(self):
        """Dropped items should appear in report."""
        record1 = _create_test_record(dropped_items=[])
        record2 = _create_test_record(
            dropped_items=[
                DroppedItem(
                    source_id="chunk_1",
                    priority=1,
                    token_count=100,
                    reason="budget_exceeded",
                )
            ]
        )

        diff = compare_records(record1, record2)
        report = format_diff_report(diff)

        assert "Dropped Items:" in report
        assert "Base:       0 items" in report
        assert "Comparison: 1 items" in report

    def test_verbose_shows_dropped_details(self):
        """Verbose mode should show dropped item details."""
        record1 = _create_test_record(dropped_items=[])
        record2 = _create_test_record(
            dropped_items=[
                DroppedItem(
                    source_id="chunk_xyz",
                    priority=2,
                    token_count=250,
                    reason="budget_exceeded",
                )
            ]
        )

        diff = compare_records(record1, record2)
        report = format_diff_report(diff, verbose=True)

        assert "chunk_xyz" in report
        assert "priority=2" in report
        assert "tokens=250" in report
        assert "budget_exceeded" in report

    def test_content_hashes_in_report(self):
        """Content hashes should appear in report."""
        record1 = _create_test_record(content="Content A")
        record2 = _create_test_record(content="Content B")

        diff = compare_records(record1, record2)
        report = format_diff_report(diff)

        assert "Content Integrity:" in report
        assert "Base hash:" in report
        assert "Comparison hash:" in report
