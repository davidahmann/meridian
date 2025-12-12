"""Tests for Context Record (CRS-001) implementation."""

from datetime import datetime, timezone

from fabra.models import (
    ContextRecord,
    FeatureRecord,
    RetrievedItemRecord,
    AssemblyDecisions,
    DroppedItem,
    LineageMetadata,
    IntegrityMetadata,
    ContextLineage,
    FeatureLineage,
)
from fabra.context import (
    Context,
    generate_context_id,
    get_fabra_version,
    get_environment,
)
from fabra.utils.integrity import (
    compute_content_hash,
    compute_record_hash,
    verify_record_integrity,
    verify_content_integrity,
)


class TestContextIdGeneration:
    """Tests for context ID generation (Phase 1)."""

    def test_generate_context_id_format(self):
        """Context ID should have ctx_ prefix."""
        ctx_id = generate_context_id()
        assert ctx_id.startswith("ctx_")

    def test_generate_context_id_unique(self):
        """Each generated ID should be unique."""
        ids = [generate_context_id() for _ in range(100)]
        assert len(set(ids)) == 100

    def test_generate_context_id_contains_uuid(self):
        """Context ID should contain a valid UUID after prefix."""
        ctx_id = generate_context_id()
        uuid_part = ctx_id[4:]  # Remove 'ctx_' prefix
        # UUIDv7 is 36 characters with hyphens
        assert len(uuid_part) == 36


class TestContentHash:
    """Tests for content hashing."""

    def test_content_hash_deterministic(self):
        """Same content should always produce same hash."""
        content = "Hello, world!"
        hash1 = compute_content_hash(content)
        hash2 = compute_content_hash(content)
        assert hash1 == hash2

    def test_content_hash_has_prefix(self):
        """Content hash should have sha256: prefix."""
        content = "Test content"
        hash_result = compute_content_hash(content)
        assert hash_result.startswith("sha256:")

    def test_different_content_different_hash(self):
        """Different content should produce different hashes."""
        hash1 = compute_content_hash("Content A")
        hash2 = compute_content_hash("Content B")
        assert hash1 != hash2

    def test_empty_content_has_valid_hash(self):
        """Empty content should still produce a valid hash."""
        hash_result = compute_content_hash("")
        assert hash_result.startswith("sha256:")
        assert len(hash_result) == 71  # "sha256:" + 64 hex chars


class TestRecordHash:
    """Tests for record hashing."""

    def test_record_hash_deterministic(self):
        """Same record should always produce same hash."""
        record = _create_minimal_record()
        hash1 = compute_record_hash(record)
        hash2 = compute_record_hash(record)
        assert hash1 == hash2

    def test_record_hash_changes_on_content_change(self):
        """Changing content should change the record hash."""
        record1 = _create_minimal_record(content="Content A")
        record2 = _create_minimal_record(content="Content B")
        hash1 = compute_record_hash(record1)
        hash2 = compute_record_hash(record2)
        assert hash1 != hash2

    def test_record_hash_ignores_own_field(self):
        """Record hash should be computed without including itself."""
        record = _create_minimal_record()
        # The record_hash field should be empty when computing
        hash_result = compute_record_hash(record)
        assert hash_result.startswith("sha256:")


class TestIntegrityVerification:
    """Tests for integrity verification."""

    def test_verify_valid_record(self):
        """Valid record should pass integrity check."""
        # Create a record first, then compute hash with same timestamp
        base_record = _create_minimal_record()
        correct_hash = compute_record_hash(base_record)

        # Create a new record with the same data but correct hash
        record_with_hash = ContextRecord(
            context_id=base_record.context_id,
            created_at=base_record.created_at,  # Use same timestamp
            environment=base_record.environment,
            schema_version=base_record.schema_version,
            inputs=base_record.inputs,
            context_function=base_record.context_function,
            content=base_record.content,
            token_count=base_record.token_count,
            features=base_record.features,
            retrieved_items=base_record.retrieved_items,
            assembly=base_record.assembly,
            lineage=base_record.lineage,
            integrity=IntegrityMetadata(
                record_hash=correct_hash,
                content_hash=base_record.integrity.content_hash,
            ),
        )
        assert verify_record_integrity(record_with_hash)

    def test_verify_tampered_record(self):
        """Tampered record should fail integrity check."""
        record = _create_minimal_record(record_hash="sha256:invalid_hash")
        assert not verify_record_integrity(record)

    def test_verify_content_integrity_valid(self):
        """Valid content hash should pass verification."""
        content = "Test content"
        content_hash = compute_content_hash(content)
        record = _create_minimal_record(content=content, content_hash=content_hash)
        assert verify_content_integrity(record)

    def test_verify_content_integrity_tampered(self):
        """Tampered content should fail verification."""
        record = _create_minimal_record(
            content="Original content",
            content_hash="sha256:wrong_hash",
        )
        assert not verify_content_integrity(record)


class TestContextToRecord:
    """Tests for Context.to_record() conversion."""

    def test_basic_conversion(self):
        """Basic Context should convert to ContextRecord."""
        ctx = Context(
            id="test-uuid-1234",
            content="Test context content",
            meta={
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "name": "test_context",
                "freshness_status": "guaranteed",
                "token_usage": 100,
            },
            lineage=None,
        )
        record = ctx.to_record()

        assert record.context_id.startswith("ctx_")
        assert record.content == "Test context content"
        assert record.context_function == "test_context"
        assert record.schema_version == "1.0.0"

    def test_conversion_adds_ctx_prefix(self):
        """Conversion should add ctx_ prefix if not present."""
        ctx = Context(
            id="bare-uuid-5678",
            content="Content",
            meta={"name": "test"},
        )
        record = ctx.to_record()
        assert record.context_id == "ctx_bare-uuid-5678"

    def test_conversion_preserves_ctx_prefix(self):
        """Conversion should preserve existing ctx_ prefix."""
        ctx = Context(
            id="ctx_already-prefixed",
            content="Content",
            meta={"name": "test"},
        )
        record = ctx.to_record()
        assert record.context_id == "ctx_already-prefixed"

    def test_conversion_with_lineage(self):
        """Context with lineage should include features in record."""
        now = datetime.now(timezone.utc)
        lineage = ContextLineage(
            context_id="test-id",
            context_name="my_context",
            context_args={"user_id": "u123"},
            features_used=[
                FeatureLineage(
                    feature_name="user_tier",
                    entity_id="u123",
                    value="premium",
                    timestamp=now,
                    freshness_ms=100,
                    source="cache",
                )
            ],
            retrievers_used=[],
            items_provided=1,
            items_included=1,
            items_dropped=0,
        )

        ctx = Context(
            id="test-uuid",
            content="Context with features",
            meta={
                "name": "my_context",
                "token_usage": 50,
            },
            lineage=lineage,
        )
        record = ctx.to_record()

        assert len(record.features) == 1
        assert record.features[0].name == "user_tier"
        assert record.features[0].entity_id == "u123"
        assert record.features[0].value == "premium"
        assert record.features[0].source == "cache"

    def test_conversion_integrity_is_valid(self):
        """Converted record should have valid integrity hashes."""
        ctx = Context(
            id="test-uuid",
            content="Test content for hashing",
            meta={"name": "test"},
        )
        record = ctx.to_record()

        assert verify_record_integrity(record)
        assert verify_content_integrity(record)

    def test_conversion_without_content(self):
        """Conversion with include_content=False should clear content."""
        ctx = Context(
            id="test-uuid",
            content="Sensitive content",
            meta={"name": "test"},
        )
        record = ctx.to_record(include_content=False)

        assert record.content == ""


class TestFeatureRecord:
    """Tests for FeatureRecord model."""

    def test_feature_record_creation(self):
        """FeatureRecord should be creatable with valid data."""
        now = datetime.now(timezone.utc)
        feature = FeatureRecord(
            name="user_score",
            entity_id="user_123",
            value=0.95,
            source="compute",
            as_of=now,
            freshness_ms=500,
        )
        assert feature.name == "user_score"
        assert feature.value == 0.95
        assert feature.source == "compute"

    def test_feature_record_serialization(self):
        """FeatureRecord should serialize to JSON."""
        now = datetime.now(timezone.utc)
        feature = FeatureRecord(
            name="test_feature",
            entity_id="e1",
            value={"nested": "data"},
            source="cache",
            as_of=now,
            freshness_ms=100,
        )
        json_str = feature.model_dump_json()
        assert "test_feature" in json_str
        assert "nested" in json_str


class TestRetrievedItemRecord:
    """Tests for RetrievedItemRecord model."""

    def test_retrieved_item_creation(self):
        """RetrievedItemRecord should be creatable with valid data."""
        now = datetime.now(timezone.utc)
        item = RetrievedItemRecord(
            retriever="doc_search",
            chunk_id="chunk_001",
            document_id="doc_123",
            content_hash="sha256:abc123",
            similarity_score=0.89,
            as_of=now,
        )
        assert item.retriever == "doc_search"
        assert item.chunk_id == "chunk_001"
        assert item.similarity_score == 0.89


class TestAssemblyDecisions:
    """Tests for AssemblyDecisions model."""

    def test_assembly_decisions_defaults(self):
        """AssemblyDecisions should have sensible defaults."""
        assembly = AssemblyDecisions()
        assert assembly.max_tokens is None
        assert assembly.tokens_used == 0
        assert assembly.freshness_status == "unknown"
        assert assembly.dropped_items == []

    def test_assembly_with_dropped_items(self):
        """AssemblyDecisions should track dropped items."""
        assembly = AssemblyDecisions(
            max_tokens=1000,
            tokens_used=950,
            items_provided=5,
            items_included=3,
            dropped_items=[
                DroppedItem(
                    source_id="item_4",
                    priority=2,
                    token_count=100,
                    reason="budget_exceeded",
                ),
                DroppedItem(
                    source_id="item_5",
                    priority=1,
                    token_count=150,
                    reason="budget_exceeded",
                ),
            ],
        )
        assert len(assembly.dropped_items) == 2
        assert assembly.dropped_items[0].source_id == "item_4"


class TestContextRecordSerialization:
    """Tests for ContextRecord serialization."""

    def test_record_json_roundtrip(self):
        """ContextRecord should survive JSON serialization roundtrip."""
        record = _create_minimal_record()
        json_str = record.model_dump_json()
        restored = ContextRecord.model_validate_json(json_str)

        assert restored.context_id == record.context_id
        assert restored.content == record.content
        assert restored.schema_version == record.schema_version

    def test_record_dict_roundtrip(self):
        """ContextRecord should survive dict conversion roundtrip."""
        record = _create_minimal_record()
        record_dict = record.model_dump()
        restored = ContextRecord.model_validate(record_dict)

        assert restored.context_id == record.context_id


class TestEnvironmentAndVersion:
    """Tests for environment and version helpers."""

    def test_get_fabra_version(self):
        """Should return a version string."""
        version = get_fabra_version()
        assert isinstance(version, str)
        assert version != ""

    def test_get_environment_default(self):
        """Should return 'development' by default."""
        import os

        # Clear any existing FABRA_ENV
        original = os.environ.pop("FABRA_ENV", None)
        try:
            env = get_environment()
            assert env == "development"
        finally:
            if original:
                os.environ["FABRA_ENV"] = original


# Helper functions for creating test records


def _create_minimal_record(
    context_id: str = "ctx_test-123",
    content: str = "Test content",
    record_hash: str = "",
    content_hash: str | None = None,
) -> ContextRecord:
    """Create a minimal ContextRecord for testing."""
    now = datetime.now(timezone.utc)

    if content_hash is None:
        content_hash = compute_content_hash(content)

    return ContextRecord(
        context_id=context_id,
        created_at=now,
        environment="development",
        schema_version="1.0.0",
        inputs={"test": "input"},
        context_function="test_function",
        content=content,
        token_count=len(content.split()),
        features=[],
        retrieved_items=[],
        assembly=AssemblyDecisions(),
        lineage=LineageMetadata(
            features_used=[],
            retrievers_used=[],
            indexes_used=[],
            fabra_version="2.0.7",
        ),
        integrity=IntegrityMetadata(
            record_hash=record_hash,
            content_hash=content_hash,
        ),
    )
