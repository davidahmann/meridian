from typing import List, Optional, Dict, Any, Literal
from pydantic import BaseModel, Field
from datetime import datetime, timezone


class FeatureLineage(BaseModel):
    """Record of a feature used in context assembly."""

    feature_name: str = Field(..., description="Name of the feature")
    entity_id: str = Field(..., description="Entity ID for which feature was retrieved")
    value: Any = Field(..., description="The feature value used")
    timestamp: datetime = Field(
        ..., description="When this feature value was computed/retrieved"
    )
    freshness_ms: int = Field(
        ..., description="Age of the feature in milliseconds at assembly time"
    )
    source: Literal["cache", "compute", "fallback"] = Field(
        ..., description="Where the value came from"
    )


class DocumentChunkLineage(BaseModel):
    """Record of a document chunk used in context assembly with freshness tracking."""

    chunk_id: str = Field(..., description="Unique identifier for this chunk")
    document_id: str = Field(..., description="Parent document identifier")
    content_hash: str = Field(
        ..., description="Hash of chunk content for deduplication"
    )
    source_url: Optional[str] = Field(None, description="Original document URL/path")

    # Freshness tracking
    indexed_at: datetime = Field(
        ..., description="When this chunk was indexed into the vector store"
    )
    document_modified_at: Optional[datetime] = Field(
        None, description="Last modification time of the source document"
    )
    freshness_ms: int = Field(
        0, description="Age of the chunk in milliseconds at retrieval time"
    )
    is_stale: bool = Field(
        False, description="Whether this chunk exceeds freshness SLA"
    )

    # Retrieval metadata
    similarity_score: float = Field(
        0.0, description="Similarity score from vector search"
    )
    retriever_name: str = Field(..., description="Which retriever returned this chunk")
    position_in_results: int = Field(
        0, description="Position in search results (0-indexed)"
    )


class RetrieverLineage(BaseModel):
    """Record of a retriever call in context assembly."""

    retriever_name: str = Field(..., description="Name of the retriever")
    query: str = Field(..., description="Query string passed to retriever")
    results_count: int = Field(..., description="Number of results returned")
    latency_ms: float = Field(..., description="Time taken for retrieval in ms")
    index_name: Optional[str] = Field(None, description="Index/collection searched")

    # Document/chunk freshness tracking
    chunks_returned: List[DocumentChunkLineage] = Field(
        default_factory=list, description="Individual chunks with freshness info"
    )
    stale_chunks_count: int = Field(
        0, description="Number of chunks that exceeded freshness SLA"
    )
    oldest_chunk_ms: int = Field(
        0, description="Age in ms of the oldest chunk returned"
    )


class ContextLineage(BaseModel):
    """Full lineage for a context assembly - tracks exactly what data was used."""

    context_id: str = Field(..., description="The UUIDv7 of the parent context")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When assembly occurred",
    )

    # Context function info (for replay)
    context_name: Optional[str] = Field(
        None, description="Name of the context function for replay"
    )
    context_args: Optional[Dict[str, Any]] = Field(
        None, description="Arguments passed to context function for replay"
    )

    # What data sources were used
    features_used: List[FeatureLineage] = Field(
        default_factory=list, description="All features retrieved during assembly"
    )
    retrievers_used: List[RetrieverLineage] = Field(
        default_factory=list, description="All retriever calls made during assembly"
    )

    # Assembly statistics
    items_provided: int = Field(
        0, description="Total items returned by context function"
    )
    items_included: int = Field(0, description="Items that fit within token budget")
    items_dropped: int = Field(0, description="Items dropped due to budget constraints")
    dropped_items_detail: List["DroppedItem"] = Field(
        default_factory=list,
        description="Detailed list of dropped items with reasons (CRS-001)",
    )

    # Freshness tracking
    freshness_status: Literal["guaranteed", "degraded", "unknown"] = Field(
        "unknown", description="Overall freshness of the context"
    )
    stalest_feature_ms: int = Field(
        0, description="Age in ms of the oldest feature used"
    )
    freshness_violations: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Features that violated freshness SLA",
    )

    # Token economics
    token_usage: int = Field(0, description="Total tokens in final context")
    max_tokens: Optional[int] = Field(None, description="Token budget limit")
    estimated_cost_usd: float = Field(0.0, description="Estimated cost in USD")


class ContextTrace(BaseModel):
    """
    Metadata-only trace object for debugging context assembly.
    Does NOT contain the full text content to preserve privacy/log-size.
    """

    context_id: str = Field(
        ..., description="The unique UUIDv7 of the context assembly"
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Creation timestamp",
    )
    latency_ms: float = Field(..., description="Total assembly time in milliseconds")

    # Costs
    token_usage: int = Field(..., description="Total tokens used in the final context")
    cost_usd: Optional[float] = Field(None, description="Estimated cost in USD")

    # Freshness
    freshness_status: str = Field(..., description="'guaranteed' or 'degraded'")
    stale_sources: List[str] = Field(
        default_factory=list, description="List of source IDs that violated SLA"
    )

    # Lineage
    source_ids: List[str] = Field(
        default_factory=list, description="IDs of source items used"
    )
    cache_hit: bool = Field(False, description="Whether this was served from cache")

    # Missing Data (for debugging)
    missing_features: List[str] = Field(
        default_factory=list, description="Features that were requested but not found"
    )

    meta: Dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata"
    )


class FeatureDiff(BaseModel):
    """Represents a change in a feature value between two contexts."""

    feature_name: str = Field(..., description="Name of the feature that changed")
    entity_id: str = Field(..., description="Entity ID for the feature")
    old_value: Optional[Any] = Field(
        None, description="Value in the base context (None if added)"
    )
    new_value: Optional[Any] = Field(
        None, description="Value in the comparison context (None if removed)"
    )
    change_type: Literal["added", "removed", "modified", "unchanged"] = Field(
        ..., description="Type of change"
    )
    old_freshness_ms: Optional[int] = Field(
        None, description="Freshness in base context"
    )
    new_freshness_ms: Optional[int] = Field(
        None, description="Freshness in comparison context"
    )


class InputDiff(BaseModel):
    """Represents a change in a CRS-001 record input between two records."""

    key: str = Field(..., description="Input key that changed")
    old_value: Optional[Any] = Field(
        None, description="Value in the base record (None if added)"
    )
    new_value: Optional[Any] = Field(
        None, description="Value in the comparison record (None if removed)"
    )
    change_type: Literal["added", "removed", "modified", "unchanged"] = Field(
        ..., description="Type of change"
    )


class RetrieverDiff(BaseModel):
    """Represents a change in retriever results between two contexts."""

    retriever_name: str = Field(..., description="Name of the retriever")
    query_changed: bool = Field(False, description="Whether the query changed")
    old_query: Optional[str] = Field(None, description="Query in base context")
    new_query: Optional[str] = Field(None, description="Query in comparison context")
    old_results_count: int = Field(0, description="Results count in base context")
    new_results_count: int = Field(0, description="Results count in comparison context")
    chunks_added: List[str] = Field(
        default_factory=list, description="Chunk IDs that were added"
    )
    chunks_removed: List[str] = Field(
        default_factory=list, description="Chunk IDs that were removed"
    )
    change_type: Literal["added", "removed", "modified", "unchanged"] = Field(
        ..., description="Type of change"
    )


class ContentDiff(BaseModel):
    """Represents differences in content between two contexts."""

    lines_added: int = Field(0, description="Number of lines added")
    lines_removed: int = Field(0, description="Number of lines removed")
    lines_changed: int = Field(0, description="Number of lines modified")
    similarity_score: float = Field(0.0, description="Content similarity (0.0-1.0)")
    diff_summary: str = Field("", description="Human-readable diff summary")


class ContextDiff(BaseModel):
    """
    Comparison result between two context assemblies.
    Shows what features, retrievers, and content changed.
    """

    base_context_id: str = Field(..., description="ID of the base (older) context")
    comparison_context_id: str = Field(
        ..., description="ID of the comparison (newer) context"
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When this diff was computed",
    )

    # Time between contexts
    time_delta_ms: int = Field(0, description="Time difference in milliseconds")

    # Feature changes
    feature_diffs: List[FeatureDiff] = Field(
        default_factory=list, description="All feature changes"
    )
    features_added: int = Field(0, description="Count of features added")
    features_removed: int = Field(0, description="Count of features removed")
    features_modified: int = Field(
        0, description="Count of features with changed values"
    )

    # Retriever changes
    retriever_diffs: List[RetrieverDiff] = Field(
        default_factory=list, description="All retriever changes"
    )
    retrievers_added: int = Field(0, description="Count of retrievers added")
    retrievers_removed: int = Field(0, description="Count of retrievers removed")
    retrievers_modified: int = Field(
        0, description="Count of retrievers with changed results"
    )

    # Content changes
    content_diff: Optional[ContentDiff] = Field(
        None, description="Diff of the final content"
    )

    # CRS-001 input changes (record.inputs)
    input_diffs: List[InputDiff] = Field(
        default_factory=list, description="All CRS-001 input changes"
    )
    inputs_added: int = Field(0, description="Count of inputs added")
    inputs_removed: int = Field(0, description="Count of inputs removed")
    inputs_modified: int = Field(0, description="Count of inputs with changed values")

    # Token/cost changes
    token_delta: int = Field(0, description="Change in token usage (new - old)")
    cost_delta_usd: float = Field(0.0, description="Change in cost (new - old)")

    # Freshness changes
    base_freshness_status: str = Field(
        "unknown", description="Freshness status of base context"
    )
    comparison_freshness_status: str = Field(
        "unknown", description="Freshness status of comparison context"
    )
    freshness_improved: bool = Field(False, description="Whether freshness improved")

    # Dropped items changes (CRS-001)
    items_dropped_base: List["DroppedItem"] = Field(
        default_factory=list, description="Items dropped in base context"
    )
    items_dropped_comparison: List["DroppedItem"] = Field(
        default_factory=list, description="Items dropped in comparison context"
    )
    items_dropped_delta: int = Field(
        0, description="Change in number of dropped items (comparison - base)"
    )

    # Integrity status (CRS-001)
    base_content_hash: Optional[str] = Field(
        None, description="Content hash of base context"
    )
    comparison_content_hash: Optional[str] = Field(
        None, description="Content hash of comparison context"
    )

    # Summary
    has_changes: bool = Field(False, description="Whether any meaningful changes exist")
    change_summary: str = Field("", description="Human-readable change summary")


class RetrieverSnapshot(BaseModel):
    """
    Snapshot of retriever results for replay functionality.
    Stores the complete retriever state at a point in time.
    """

    snapshot_id: str = Field(..., description="Unique identifier for this snapshot")
    retriever_name: str = Field(..., description="Name of the retriever")
    query: str = Field(..., description="Query string that was executed")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When this snapshot was captured",
    )

    # Results
    results: List[Dict[str, Any]] = Field(
        default_factory=list, description="Raw retriever results"
    )
    results_count: int = Field(0, description="Number of results returned")

    # Chunk details with content
    chunks: List[DocumentChunkLineage] = Field(
        default_factory=list, description="Chunk lineage with metadata"
    )
    chunk_contents: Dict[str, str] = Field(
        default_factory=dict, description="Mapping of chunk_id to full content"
    )

    # Retrieval metadata
    latency_ms: float = Field(0.0, description="Time taken for retrieval")
    index_name: Optional[str] = Field(None, description="Index/collection searched")
    embedding_model: Optional[str] = Field(None, description="Embedding model used")
    search_params: Dict[str, Any] = Field(
        default_factory=dict, description="Search parameters (top_k, threshold, etc.)"
    )

    # Context linkage
    context_id: Optional[str] = Field(
        None, description="Context ID this snapshot belongs to"
    )


class RetrieverReplayResult(BaseModel):
    """Result from replaying a retriever snapshot."""

    snapshot_id: str = Field(..., description="The snapshot that was replayed")
    replayed_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When the replay occurred",
    )

    # Comparison with live results
    live_results_count: int = Field(0, description="Results from live retrieval")
    snapshot_results_count: int = Field(0, description="Results from snapshot")

    # Drift detection
    chunks_added: List[str] = Field(
        default_factory=list, description="Chunks in live but not snapshot"
    )
    chunks_removed: List[str] = Field(
        default_factory=list, description="Chunks in snapshot but not live"
    )
    chunks_modified: List[str] = Field(
        default_factory=list, description="Chunks with changed content"
    )

    # Score drift
    score_drift: Dict[str, float] = Field(
        default_factory=dict,
        description="Change in similarity scores per chunk (chunk_id -> delta)",
    )
    max_score_drift: float = Field(0.0, description="Maximum absolute score change")
    avg_score_drift: float = Field(0.0, description="Average score change")

    # Summary
    has_drift: bool = Field(False, description="Whether results have drifted")
    drift_summary: str = Field("", description="Human-readable drift summary")


# =============================================================================
# Context Record Types (CRS-001)
# =============================================================================


class FeatureRecord(BaseModel):
    """A feature value used in a context assembly - part of the Context Record."""

    name: str = Field(..., description="Name of the feature")
    entity_id: str = Field(..., description="Entity ID for which feature was retrieved")
    value: Any = Field(..., description="The feature value used")
    source: Literal["cache", "compute", "fallback"] = Field(
        ..., description="Where the value came from"
    )
    as_of: datetime = Field(..., description="When this value was computed/retrieved")
    freshness_ms: int = Field(
        ..., description="Age of the feature in milliseconds at assembly time"
    )


class RetrievedItemRecord(BaseModel):
    """A retrieved document/chunk used in a context assembly - part of the Context Record."""

    retriever: str = Field(
        ..., description="Name of the retriever that returned this item"
    )
    chunk_id: str = Field(..., description="Unique identifier for this chunk")
    document_id: str = Field(..., description="Parent document identifier")
    content_hash: str = Field(..., description="SHA256 hash of chunk content")
    content: Optional[str] = Field(
        None, description="Full content (optional, for replay)"
    )
    token_count: int = Field(0, description="Number of tokens in this chunk")
    priority: int = Field(0, description="Priority in context assembly")
    similarity_score: float = Field(
        0.0, description="Similarity score from vector search"
    )
    source_url: Optional[str] = Field(None, description="Original document URL/path")
    as_of: datetime = Field(..., description="When this chunk was indexed")
    freshness_ms: int = Field(0, description="Age in milliseconds at retrieval time")
    is_stale: bool = Field(
        False, description="Whether this chunk exceeds freshness SLA"
    )


class DroppedItem(BaseModel):
    """Record of an item dropped due to budget constraints."""

    source_id: str = Field(..., description="Identifier of the dropped item")
    priority: int = Field(..., description="Priority of the dropped item")
    token_count: int = Field(..., description="Token count of the dropped item")
    reason: Literal["budget_exceeded", "priority_cutoff"] = Field(
        ..., description="Why the item was dropped"
    )


class AssemblyDecisions(BaseModel):
    """How context was assembled under constraints - part of the Context Record."""

    max_tokens: Optional[int] = Field(None, description="Token budget limit")
    tokens_used: int = Field(0, description="Total tokens in final context")
    items_provided: int = Field(
        0, description="Total items returned by context function"
    )
    items_included: int = Field(0, description="Items that fit within token budget")
    dropped_items: List[DroppedItem] = Field(
        default_factory=list, description="Full list of dropped items with reasons"
    )
    required_items_included: bool = Field(
        True, description="Whether all required items were included"
    )
    freshness_sla_ms: Optional[int] = Field(
        None, description="Freshness SLA in milliseconds"
    )
    freshness_status: Literal["guaranteed", "degraded", "unknown"] = Field(
        "unknown", description="Overall freshness of the context"
    )
    freshness_violations: List[str] = Field(
        default_factory=list, description="Feature names that violated freshness SLA"
    )


class LineageMetadata(BaseModel):
    """Complete dependency graph for audit and replay - part of the Context Record."""

    features_used: List[str] = Field(
        default_factory=list, description="Names of features used"
    )
    retrievers_used: List[str] = Field(
        default_factory=list, description="Names of retrievers used"
    )
    indexes_used: List[str] = Field(
        default_factory=list, description="Names of indexes/collections searched"
    )
    code_version: Optional[str] = Field(None, description="Git SHA of the codebase")
    fabra_version: str = Field(..., description="Version of Fabra used")
    assembly_latency_ms: float = Field(
        0.0, description="Time taken to assemble context"
    )
    estimated_cost_usd: float = Field(0.0, description="Estimated cost in USD")


class IntegrityMetadata(BaseModel):
    """Cryptographic guarantees for the Context Record."""

    record_hash: str = Field(
        ..., description="SHA256 hash of canonical JSON (excluding this field)"
    )
    content_hash: str = Field(..., description="SHA256 hash of just the content field")
    previous_context_id: Optional[str] = Field(
        None, description="Chain linking to previous context (optional)"
    )
    signed_at: Optional[datetime] = Field(
        None, description="When the record was signed"
    )
    signature: Optional[str] = Field(
        None, description="Optional cryptographic signature"
    )


class ContextRecord(BaseModel):
    """
    Immutable, replayable snapshot of all data used to assemble AI context.
    The atomic unit of the Inference Context Ledger.

    This is the canonical CRS-001 format for context records, combining:
    - Identity and metadata
    - Input arguments for replay
    - Final assembled content
    - All features and retrieved items used
    - Assembly decisions (what was included/dropped)
    - Full lineage metadata
    - Cryptographic integrity
    """

    # Identity
    context_id: str = Field(..., description="Unique identifier in format ctx_<uuid7>")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When this context was assembled",
    )
    environment: str = Field(
        "development", description="Environment: development, staging, production"
    )
    schema_version: str = Field("1.0.0", description="CRS schema version")

    # Inputs (for replay)
    inputs: Dict[str, Any] = Field(
        default_factory=dict, description="Arguments passed to context function"
    )
    context_function: str = Field(..., description="Name of the context function")

    # Final Output
    content: str = Field(..., description="The final assembled text content")
    token_count: int = Field(0, description="Total tokens in final context")

    # Features Used
    features: List[FeatureRecord] = Field(
        default_factory=list, description="All features retrieved during assembly"
    )

    # Retrieved Content
    retrieved_items: List[RetrievedItemRecord] = Field(
        default_factory=list, description="All chunks/documents retrieved"
    )

    # Assembly Decisions
    assembly: AssemblyDecisions = Field(
        default_factory=AssemblyDecisions,
        description="How context was assembled under constraints",
    )

    # Full Lineage
    lineage: LineageMetadata = Field(
        ..., description="Complete dependency graph for audit and replay"
    )

    # Cryptographic Integrity
    integrity: IntegrityMetadata = Field(..., description="Cryptographic guarantees")
