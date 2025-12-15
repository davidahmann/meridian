import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

from fabra.models import ContextLineage, FeatureLineage, RetrieverLineage, ContextRecord
from fabra.utils.compare import compare_contexts
from fabra.utils.integrity import (
    compute_content_hash,
    compute_record_hash,
    verify_content_integrity,
    verify_record_integrity,
)


FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures"


def _load_json(name: str) -> dict:
    return json.loads((FIXTURES_DIR / name).read_text())


def _normalize_diff(d: dict) -> dict:
    d = dict(d)
    d.pop("timestamp", None)
    # CRS-001 input diffs are not part of the legacy golden fixture.
    d.pop("input_diffs", None)
    d.pop("inputs_added", None)
    d.pop("inputs_removed", None)
    d.pop("inputs_modified", None)
    if isinstance(d.get("feature_diffs"), list):
        d["feature_diffs"] = sorted(
            d["feature_diffs"],
            key=lambda x: (
                x.get("change_type", ""),
                x.get("feature_name", ""),
                x.get("entity_id", ""),
            ),
        )
    if isinstance(d.get("retriever_diffs"), list):
        d["retriever_diffs"] = sorted(
            d["retriever_diffs"],
            key=lambda x: (x.get("retriever_name", ""), x.get("change_type", "")),
        )
    return d


def test_golden_context_record_hashes() -> None:
    data = _load_json("context_record_golden.json")
    record = ContextRecord.model_validate(data)

    assert verify_content_integrity(record)
    assert verify_record_integrity(record)

    assert record.integrity.content_hash == compute_content_hash(record.content)
    assert record.integrity.record_hash == compute_record_hash(record)


def test_golden_context_diff_output() -> None:
    fixture = _normalize_diff(_load_json("context_diff_golden.json"))

    base_ts = datetime(2025, 1, 1, tzinfo=timezone.utc)
    comp_ts = base_ts + timedelta(minutes=5)

    base = ContextLineage(
        context_id="ctx_a",
        timestamp=base_ts,
        context_name="chat_context",
        context_args={"user_id": "u1", "query": "test"},
        features_used=[
            FeatureLineage(
                feature_name="user_tier",
                entity_id="u1",
                value="free",
                timestamp=base_ts,
                freshness_ms=1000,
                source="cache",
            ),
        ],
        retrievers_used=[
            RetrieverLineage(
                retriever_name="demo_docs",
                query="test",
                results_count=2,
                latency_ms=10.0,
                index_name=None,
                chunks_returned=[],
                stale_chunks_count=0,
                oldest_chunk_ms=0,
            ),
        ],
        items_provided=2,
        items_included=2,
        items_dropped=0,
        dropped_items_detail=[],
        freshness_status="guaranteed",
        stalest_feature_ms=1000,
        freshness_violations=[],
        token_usage=50,
        max_tokens=4000,
        estimated_cost_usd=0.0001,
    )

    comp = ContextLineage(
        context_id="ctx_b",
        timestamp=comp_ts,
        context_name="chat_context",
        context_args={"user_id": "u1", "query": "test"},
        features_used=[
            FeatureLineage(
                feature_name="user_tier",
                entity_id="u1",
                value="premium",
                timestamp=comp_ts,
                freshness_ms=2000,
                source="cache",
            ),
            FeatureLineage(
                feature_name="purchase_count",
                entity_id="u1",
                value=3,
                timestamp=comp_ts,
                freshness_ms=2000,
                source="compute",
            ),
        ],
        retrievers_used=[
            RetrieverLineage(
                retriever_name="demo_docs",
                query="test",
                results_count=3,
                latency_ms=12.0,
                index_name=None,
                chunks_returned=[],
                stale_chunks_count=0,
                oldest_chunk_ms=0,
            ),
        ],
        items_provided=2,
        items_included=2,
        items_dropped=0,
        dropped_items_detail=[],
        freshness_status="degraded",
        stalest_feature_ms=2000,
        freshness_violations=[{"feature": "user_tier", "age_ms": 2000, "sla_ms": 1000}],
        token_usage=70,
        max_tokens=4000,
        estimated_cost_usd=0.0002,
    )

    diff = compare_contexts(base, comp, base_content="A", comparison_content="B")
    actual = _normalize_diff(diff.model_dump(mode="json"))

    assert actual == fixture
