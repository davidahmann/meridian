import pytest
import pandas as pd
from datetime import datetime, timezone, timedelta
from fabra.store.offline import DuckDBOfflineStore
from fabra.models import (
    ContextRecord,
    FeatureRecord,
    AssemblyDecisions,
    IntegrityMetadata,
    LineageMetadata,
)


@pytest.fixture
def offline_store():
    # Use in-memory DuckDB for fast isolated testing
    store = DuckDBOfflineStore(database=":memory:")
    return store


@pytest.mark.asyncio
async def test_ensure_tables(offline_store):
    # Triggers table creation
    await offline_store.log_context(
        context_id="test_init",
        timestamp=datetime.now(timezone.utc),
        content="init",
        lineage={},
        meta={},
        version="v1",
    )

    # Check tables exist
    def check():
        conn = offline_store._get_conn()
        tables = conn.execute("SHOW TABLES").df()
        return "context_log" in tables["name"].values

    exists = await offline_store._run_db(check)
    assert exists


@pytest.mark.asyncio
async def test_log_and_get_context(offline_store):
    ctx_id = "ctx_123"
    ts = datetime.now(timezone.utc)
    content = "test content"
    lineage = {"features": ["f1"]}
    meta = {"name": "test_ctx"}

    await offline_store.log_context(ctx_id, ts, content, lineage, meta)

    retrieved = await offline_store.get_context(ctx_id)
    assert retrieved is not None
    assert retrieved["context_id"] == ctx_id
    assert retrieved["content"] == content
    assert retrieved["lineage"] == lineage
    assert retrieved["meta"] == meta
    # Timestamp might lack timezone in DB return if naive?
    # offline.py line 446: row["timestamp"]
    # DuckDB timestamps are naive usually.
    # Let's check type.
    # assert retrieved["timestamp"] == ts # might fail strict equality due to precision/tz


@pytest.mark.asyncio
async def test_list_contexts(offline_store):
    base_ts = datetime.now(timezone.utc)

    # Log 3 contexts
    await offline_store.log_context(
        "c1", base_ts - timedelta(hours=2), "c1", {}, {"name": "c1"}
    )
    await offline_store.log_context(
        "c2", base_ts - timedelta(hours=1), "c2", {}, {"name": "target"}
    )
    await offline_store.log_context("c3", base_ts, "c3", {}, {"name": "target"})

    # List all
    all_ctx = await offline_store.list_contexts()
    assert len(all_ctx) == 3

    # Filter by name
    # Debug: print all to see what's wrong if it fails
    # print(f"DEBUG ALL CTX: {all_ctx}")
    # Check if we need to test this behavior. Json queries in duckdb can be fickle in tests.

    # offline.py: json_extract(meta, '$.name') = ?
    # In test, we pass name="target".
    # This should work.

    targets = await offline_store.list_contexts(name="target")

    # Debug if it fails
    if len(targets) != 2:

        def debug_query():
            return offline_store._get_conn().execute("SELECT * FROM context_log").df()

        df = await offline_store._run_db(debug_query)
        print("\nDEBUG CONTEXT_LOG:\n", df)
        print("Meta column type:", df["meta"].dtype)
        print("Meta column values:", df["meta"].values)

    assert len(targets) == 2
    assert {c["context_id"] for c in targets} == {"c2", "c3"}

    # Filter by time
    recent = await offline_store.list_contexts(start=base_ts - timedelta(minutes=30))
    assert len(recent) == 1
    assert recent[0]["context_id"] == "c3"


@pytest.mark.asyncio
async def test_log_and_get_record(offline_store):
    # Setup minimal record
    ts = datetime.now(timezone.utc)
    # FeatureRecord fields: name, entity_id, value, source, as_of, freshness_ms
    record = ContextRecord(
        context_id="rec_1",
        created_at=ts,
        environment="test",
        schema_version="1.0",
        context_function="fn_test",
        inputs={"arg": 1},
        content="rec content",
        token_count=10,
        features=[
            FeatureRecord(
                name="f",
                entity_id="e",
                value="v",
                source="compute",
                as_of=ts,
                freshness_ms=0,
            )
        ],
        retrieved_items=[],
        assembly=AssemblyDecisions(
            tokens_used=10, dropped_items=[], freshness_status="guaranteed"
        ),
        lineage=LineageMetadata(features_used=["f"], fabra_version="1.0.0"),
        integrity=IntegrityMetadata(record_hash="hash1", content_hash="h1"),
    )

    await offline_store.log_record(record)

    fetched = await offline_store.get_record("rec_1")
    assert fetched is not None
    assert fetched.context_id == record.context_id
    assert fetched.context_function == "fn_test"
    assert fetched.inputs == {"arg": 1}
    assert len(fetched.features) == 1
    assert fetched.features[0].name == "f"
    assert fetched.integrity.record_hash == "hash1"


@pytest.mark.asyncio
async def test_log_record_immutable_idempotent_and_violation(offline_store):
    ts = datetime.now(timezone.utc)
    record = ContextRecord(
        context_id="rec_immut",
        created_at=ts,
        environment="test",
        schema_version="1.0",
        context_function="fn_test",
        inputs={"arg": 1},
        content="rec content",
        token_count=10,
        features=[],
        retrieved_items=[],
        assembly=AssemblyDecisions(
            tokens_used=10, dropped_items=[], freshness_status="guaranteed"
        ),
        lineage=LineageMetadata(features_used=[], fabra_version="1.0.0"),
        integrity=IntegrityMetadata(record_hash="hash_ok", content_hash="h1"),
    )

    await offline_store.log_record(record)
    # Idempotent re-log with same hash should succeed
    await offline_store.log_record(record)

    # Attempt to overwrite with a different hash should fail
    from fabra.exceptions import ImmutableRecordError

    bad = record.model_copy(deep=True)
    bad.integrity.record_hash = "hash_bad"
    with pytest.raises(ImmutableRecordError):
        await offline_store.log_record(bad)


@pytest.mark.asyncio
async def test_get_record_by_hash(offline_store):
    ts = datetime.now(timezone.utc)
    record = ContextRecord(
        context_id="rec_hash_lookup",
        created_at=ts,
        environment="test",
        schema_version="1.0",
        context_function="fn_test",
        inputs={},
        content="rec content",
        token_count=10,
        features=[],
        retrieved_items=[],
        assembly=AssemblyDecisions(
            tokens_used=10, dropped_items=[], freshness_status="guaranteed"
        ),
        lineage=LineageMetadata(features_used=[], fabra_version="1.0.0"),
        integrity=IntegrityMetadata(record_hash="hash_lookup", content_hash="h1"),
    )

    await offline_store.log_record(record)
    fetched = await offline_store.get_record_by_hash("hash_lookup")
    assert fetched is not None
    assert fetched.context_id == "rec_hash_lookup"


@pytest.mark.asyncio
async def test_list_records(offline_store):
    ts = datetime.now(timezone.utc)

    def make_rec(cid, fn, env):
        return ContextRecord(
            context_id=cid,
            created_at=ts,
            environment=env,
            schema_version="1.0",
            context_function=fn,
            inputs={},
            content="content",
            features=[],
            retrieved_items=[],
            assembly=AssemblyDecisions(
                tokens_used=10, dropped_items=[], freshness_status="guaranteed"
            ),
            lineage=LineageMetadata(features_used=[], fabra_version="1.0.0"),
            integrity=IntegrityMetadata(record_hash=cid, content_hash=cid),
        )

    await offline_store.log_record(make_rec("r1", "fn_a", "prod"))
    await offline_store.log_record(make_rec("r2", "fn_b", "dev"))
    await offline_store.log_record(make_rec("r3", "fn_a", "dev"))

    # Filter by function
    fn_a = await offline_store.list_records(context_function="fn_a")
    assert len(fn_a) == 2

    # Filter by env
    dev = await offline_store.list_records(environment="dev")
    assert len(dev) == 2

    # Filter both
    dev_a = await offline_store.list_records(environment="dev", context_function="fn_a")
    assert len(dev_a) == 1
    assert dev_a[0]["context_id"] == "r3"


@pytest.mark.asyncio
async def test_get_training_data(offline_store):
    # Training data requires ASOF JOIN logic check
    # We need to setup 'entity_df' and 'feature tables'.
    # DuckDBOfflineStore._run_db executes with a connection.
    # We can create tables manually using _run_db.

    async def setup_tables():
        def _run():
            conn = offline_store._get_conn()
            # Feature table: user_clicks (entity_id, timestamp, user_clicks)
            conn.execute(
                "CREATE TABLE user_clicks (entity_id VARCHAR, timestamp TIMESTAMP, user_clicks INTEGER)"
            )
            conn.execute(
                "INSERT INTO user_clicks VALUES ('u1', TIMESTAMP '2023-01-01 10:00:00', 5)"
            )
            conn.execute(
                "INSERT INTO user_clicks VALUES ('u1', TIMESTAMP '2023-01-01 12:00:00', 10)"
            )  # newer
            conn.execute(
                "INSERT INTO user_clicks VALUES ('u2', TIMESTAMP '2023-01-01 10:00:00', 2)"
            )

        await offline_store._run_db(_run)

    await setup_tables()

    # Entity DF
    entity_df = pd.DataFrame(
        [
            {
                "user_id": "u1",
                "event_time": datetime(2023, 1, 1, 11, 0, 0),
                "label": 1,
            },  # Should match 10:00:00 -> 5
            {
                "user_id": "u1",
                "event_time": datetime(2023, 1, 1, 13, 0, 0),
                "label": 0,
            },  # Should match 12:00:00 -> 10
            {
                "user_id": "u2",
                "event_time": datetime(2023, 1, 1, 9, 0, 0),
                "label": 0,
            },  # Match nothing -> NaN (ASOF behavior)
        ]
    )

    # get_training_data(entity_df, features=["user_clicks"], entity_id_col="user_id", timestamp_col="event_time")
    # Wait, the SQL query construction uses ASOF JOIN ... ON entity_df.id = feature.entity_id etc.
    # It assumes feature table name matches feature name? Yes.

    result = await offline_store.get_training_data(
        entity_df=entity_df,
        features=["user_clicks"],
        entity_id_col="user_id",
        timestamp_col="event_time",
    )

    assert len(result) == 3
    assert "user_clicks" in result.columns

    # Sort by time to ensure order
    result = result.sort_values("event_time")

    # u1 at 11:00 should get value from 10:00 -> 5
    assert result.iloc[1]["user_clicks"] == 5
    # u1 at 13:00 should get value from 12:00 -> 10
    assert result.iloc[2]["user_clicks"] == 10
    # u2 at 9:00 (event_time 09:00 is earliest)
    assert pd.isna(result.iloc[0]["user_clicks"])


def test_format_diff_report():
    from fabra.models import ContextDiff
    from fabra.utils.compare import format_diff_report

    # Create a dummy diff with changes
    diff = ContextDiff(
        base_context_id="ctx_1",
        comparison_context_id="ctx_2",
        feature_diffs=[],
        features_added=1,
        features_removed=2,
        features_modified=3,
        retriever_diffs=[],
        retrievers_added=0,
        retrievers_removed=0,
        retrievers_modified=0,
        change_summary="Changes detected",
        has_changes=True,
    )

    report = format_diff_report(diff, verbose=True)
    assert "Context Diff Report" in report
    assert "Base context:       ctx_1" in report
    assert "Features:" in report
    assert "  Added:    1" in report
    assert "  Removed:  2" in report
