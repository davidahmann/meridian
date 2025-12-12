"""Tests for enhanced assembly tracking (Phase 2 of CRS-001)."""


from fabra.context import (
    AssemblyTracker,
    Context,
)
from fabra.models import (
    DroppedItem,
    ContextLineage,
)


class TestAssemblyTrackerDroppedItems:
    """Tests for dropped item tracking in AssemblyTracker."""

    def test_tracker_initializes_with_empty_dropped_items(self):
        """AssemblyTracker should start with empty dropped_items list."""
        tracker = AssemblyTracker(context_id="test-123")
        assert tracker.dropped_items == []

    def test_record_dropped_item_adds_to_list(self):
        """record_dropped_item should add DroppedItem to list."""
        tracker = AssemblyTracker(context_id="test-123")

        tracker.record_dropped_item(
            source_id="feature_abc",
            priority=2,
            token_count=150,
            reason="budget_exceeded",
        )

        assert len(tracker.dropped_items) == 1
        dropped = tracker.dropped_items[0]
        assert dropped.source_id == "feature_abc"
        assert dropped.priority == 2
        assert dropped.token_count == 150
        assert dropped.reason == "budget_exceeded"

    def test_record_multiple_dropped_items(self):
        """Multiple dropped items should be tracked in order."""
        tracker = AssemblyTracker(context_id="test-123")

        tracker.record_dropped_item(
            source_id="item_1",
            priority=1,
            token_count=100,
            reason="budget_exceeded",
        )
        tracker.record_dropped_item(
            source_id="item_2",
            priority=0,
            token_count=200,
            reason="priority_cutoff",
        )

        assert len(tracker.dropped_items) == 2
        assert tracker.dropped_items[0].source_id == "item_1"
        assert tracker.dropped_items[1].source_id == "item_2"


class TestContextLineageDroppedItems:
    """Tests for dropped items in ContextLineage."""

    def test_lineage_has_dropped_items_detail_field(self):
        """ContextLineage should have dropped_items_detail field."""
        lineage = ContextLineage(
            context_id="test-123",
            items_dropped=2,
            dropped_items_detail=[
                DroppedItem(
                    source_id="item_1",
                    priority=1,
                    token_count=100,
                    reason="budget_exceeded",
                ),
                DroppedItem(
                    source_id="item_2",
                    priority=0,
                    token_count=50,
                    reason="budget_exceeded",
                ),
            ],
        )

        assert len(lineage.dropped_items_detail) == 2
        assert lineage.items_dropped == 2

    def test_lineage_default_empty_dropped_items(self):
        """ContextLineage should default to empty dropped_items_detail."""
        lineage = ContextLineage(context_id="test-123")
        assert lineage.dropped_items_detail == []


class TestContextToRecordWithDroppedItems:
    """Tests for Context.to_record() with dropped items."""

    def test_to_record_includes_dropped_items_from_lineage(self):
        """to_record() should include dropped items from lineage."""
        dropped = [
            DroppedItem(
                source_id="extra_context",
                priority=3,
                token_count=500,
                reason="budget_exceeded",
            )
        ]

        lineage = ContextLineage(
            context_id="test-123",
            context_name="test_context",
            items_provided=5,
            items_included=4,
            items_dropped=1,
            dropped_items_detail=dropped,
        )

        ctx = Context(
            id="test-123",
            content="Test content",
            meta={
                "name": "test_context",
                "token_usage": 100,
                "max_tokens": 1000,
            },
            lineage=lineage,
        )

        record = ctx.to_record()

        assert len(record.assembly.dropped_items) == 1
        assert record.assembly.dropped_items[0].source_id == "extra_context"
        assert record.assembly.dropped_items[0].token_count == 500
        assert record.assembly.dropped_items[0].reason == "budget_exceeded"

    def test_to_record_empty_dropped_items_when_no_lineage(self):
        """to_record() should have empty dropped_items when no lineage."""
        ctx = Context(
            id="test-123",
            content="Test content",
            meta={"name": "test"},
            lineage=None,
        )

        record = ctx.to_record()
        assert record.assembly.dropped_items == []


class TestDroppedItemModel:
    """Tests for DroppedItem model."""

    def test_dropped_item_creation(self):
        """DroppedItem should be creatable with valid data."""
        item = DroppedItem(
            source_id="chunk_abc123",
            priority=2,
            token_count=350,
            reason="budget_exceeded",
        )
        assert item.source_id == "chunk_abc123"
        assert item.priority == 2
        assert item.token_count == 350
        assert item.reason == "budget_exceeded"

    def test_dropped_item_reason_validation(self):
        """DroppedItem should accept valid reason values."""
        item1 = DroppedItem(
            source_id="item_1",
            priority=1,
            token_count=100,
            reason="budget_exceeded",
        )
        item2 = DroppedItem(
            source_id="item_2",
            priority=1,
            token_count=100,
            reason="priority_cutoff",
        )
        assert item1.reason == "budget_exceeded"
        assert item2.reason == "priority_cutoff"

    def test_dropped_item_serialization(self):
        """DroppedItem should serialize to JSON."""
        item = DroppedItem(
            source_id="test_item",
            priority=5,
            token_count=999,
            reason="budget_exceeded",
        )
        json_str = item.model_dump_json()
        assert "test_item" in json_str
        assert "999" in json_str
        assert "budget_exceeded" in json_str
