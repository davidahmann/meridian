from abc import ABC, abstractmethod
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from typing import List, Optional, TYPE_CHECKING, TypeVar, cast
import duckdb
import pandas as pd
import asyncio
from typing import Dict, Any
from datetime import datetime, timezone
import os
from pathlib import Path


import structlog

if TYPE_CHECKING:
    from fabra.models import ContextRecord

logger = structlog.get_logger()

T = TypeVar("T")


class OfflineStore(ABC):
    @abstractmethod
    async def get_training_data(
        self,
        entity_df: pd.DataFrame,
        features: List[str],
        entity_id_col: str,
        timestamp_col: str = "timestamp",
    ) -> pd.DataFrame:
        """
        Generates training data by joining entity_df with feature data.
        """

    @abstractmethod
    async def execute_sql(self, query: str) -> pd.DataFrame:
        """
        Executes a SQL query against the offline store and returns a DataFrame.
        """
        pass

    @abstractmethod
    async def get_historical_features(
        self, entity_name: str, entity_id: str, features: List[str], timestamp: datetime
    ) -> Dict[str, Any]:
        """
        Retrieves feature values as they were at the specified timestamp.
        """
        pass

    @abstractmethod
    async def log_context(
        self,
        context_id: str,
        timestamp: datetime,
        content: str,
        lineage: Dict[str, Any],
        meta: Dict[str, Any],
        version: str = "v1",
    ) -> None:
        """
        Persists a context assembly for replay and audit.

        Args:
            context_id: UUIDv7 identifier for the context
            timestamp: When the context was assembled
            content: The full assembled context text
            lineage: Serialized ContextLineage as dict
            meta: Additional metadata
            version: Schema version
        """
        pass

    @abstractmethod
    async def get_context(self, context_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieves a historical context by ID.

        Returns:
            Dict with keys: context_id, timestamp, content, lineage, meta, version
            Or None if not found.
        """
        pass

    @abstractmethod
    async def list_contexts(
        self,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        limit: int = 100,
        name: Optional[str] = None,
        freshness_status: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Lists contexts in a time range for debugging.

        Args:
            start: Filter contexts created after this time
            end: Filter contexts created before this time
            limit: Maximum number of results
            name: Filter by context name (from meta.name)
            freshness_status: Filter by freshness status ("guaranteed" or "degraded")

        Returns:
            List of context summaries (without full content for efficiency)
        """
        pass

    @abstractmethod
    async def log_record(self, record: "ContextRecord") -> str:
        """
        Persists a ContextRecord to the store.

        Args:
            record: The ContextRecord to persist.

        Returns:
            The context_id of the stored record.
        """
        pass

    @abstractmethod
    async def get_record(self, context_id: str) -> Optional["ContextRecord"]:
        """
        Retrieves a ContextRecord by ID.

        Args:
            context_id: The context ID (with ctx_ prefix).

        Returns:
            The ContextRecord if found, None otherwise.
        """
        pass

    @abstractmethod
    async def get_record_by_hash(self, record_hash: str) -> Optional["ContextRecord"]:
        """
        Retrieves a ContextRecord by its record_hash.

        Args:
            record_hash: The CRS-001 record_hash (sha256:...).

        Returns:
            The ContextRecord if found, None otherwise.
        """
        pass

    @abstractmethod
    async def list_records(
        self,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        limit: int = 100,
        context_function: Optional[str] = None,
        environment: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Lists context records in a time range.

        Args:
            start: Filter records created after this time
            end: Filter records created before this time
            limit: Maximum number of results
            context_function: Filter by context function name
            environment: Filter by environment (development, staging, production)

        Returns:
            List of record summaries (without full content).
        """
        pass


class DuckDBOfflineStore(OfflineStore):
    def __init__(self, database: Optional[str] = None) -> None:
        if database is None:
            database = os.getenv("FABRA_DUCKDB_PATH")
            if not database:
                database = str(Path.home() / ".fabra" / "fabra.duckdb")

        if database != ":memory:":
            db_path = Path(database).expanduser()
            db_path.parent.mkdir(parents=True, exist_ok=True)
            database = str(db_path)

        self._database = database
        self._executor = ThreadPoolExecutor(
            max_workers=1, thread_name_prefix="fabra-duckdb"
        )
        self._conn: Optional[duckdb.DuckDBPyConnection] = None

    def _get_conn(self) -> duckdb.DuckDBPyConnection:
        if self._conn is None:
            self._conn = duckdb.connect(database=self._database)
        return self._conn

    async def _run_db(self, fn: Callable[[], T]) -> T:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(self._executor, fn)

    def _ensure_context_table_sync(self) -> None:
        """Create context_log table if it doesn't exist.

        DuckDB connections are not thread-safe; this must only be called on the
        store's single DB thread (via `_run_db`).
        """
        conn = self._get_conn()
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS context_log (
                context_id VARCHAR PRIMARY KEY,
                timestamp TIMESTAMP NOT NULL,
                content TEXT NOT NULL,
                lineage JSON NOT NULL,
                meta JSON NOT NULL,
                version VARCHAR DEFAULT 'v1'
            )
        """
        )
        try:
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_context_log_timestamp ON context_log(timestamp)"
            )
        except Exception:  # nosec B110 - Index may already exist, safe to ignore
            pass

    def _ensure_records_table_sync(self) -> None:
        """Create context_records table if it doesn't exist.

        DuckDB connections are not thread-safe; this must only be called on the
        store's single DB thread (via `_run_db`).
        """
        conn = self._get_conn()
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS context_records (
                context_id VARCHAR PRIMARY KEY,
                created_at TIMESTAMP NOT NULL,
                environment VARCHAR NOT NULL,
                schema_version VARCHAR NOT NULL,
                context_function VARCHAR,
                inputs JSON,
                content TEXT,
                token_count INTEGER,
                features JSON,
                retrieved_items JSON,
                assembly JSON,
                lineage JSON,
                integrity JSON,
                record_hash VARCHAR UNIQUE
            )
        """
        )
        try:
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_records_created ON context_records(created_at)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_records_function ON context_records(context_function)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_records_env ON context_records(environment)"
            )
        except Exception:  # nosec B110 - Index may already exist, safe to ignore
            pass

    async def get_training_data(
        self,
        entity_df: pd.DataFrame,
        features: List[str],
        entity_id_col: str,
        timestamp_col: str = "timestamp",
    ) -> pd.DataFrame:
        # Construct query using ASOF JOIN for Point-in-Time Correctness
        # SELECT e.*, f1.value as f1
        # FROM entity_df e
        # ASOF LEFT JOIN feature_table f1
        # ON e.entity_id = f1.entity_id AND e.timestamp >= f1.timestamp

        query = "SELECT entity_df.*"
        joins = ""

        # ... (rest of the query construction logic is fine, preserving context)
        import re

        for feature in features:
            if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", feature):
                raise ValueError(f"Invalid feature name: {feature}")

            # MVP Assumption: Feature table has columns [entity_id, timestamp, feature_name]
            # We alias the feature table to its name for clarity

            # Note: DuckDB ASOF JOIN syntax:
            # FROM A ASOF LEFT JOIN B ON A.id = B.id AND A.ts >= B.ts
            # The inequality MUST be >= for ASOF behavior (find latest B where B.ts <= A.ts)

            joins += f"""
            ASOF LEFT JOIN {feature}
            ON entity_df.{entity_id_col} = {feature}.entity_id
            AND entity_df.{timestamp_col} >= {feature}.timestamp
            """

            query += f", {feature}.{feature} AS {feature}"

        query += f" FROM entity_df {joins}"

        try:

            def _run() -> pd.DataFrame:
                conn = self._get_conn()
                conn.register("entity_df", entity_df)
                return conn.execute(query).df()

            return await self._run_db(_run)
        except Exception as e:
            # Fallback for when tables don't exist (e.g. unit tests without setup)
            logger.warning("offline_retrieval_failed", error=str(e))
            return entity_df

    async def execute_sql(self, query: str) -> pd.DataFrame:
        def _run() -> pd.DataFrame:
            conn = self._get_conn()
            result = conn.execute(query)
            try:
                return result.df()
            except Exception:
                return pd.DataFrame()

        return await self._run_db(_run)

    async def get_historical_features(
        self, entity_name: str, entity_id: str, features: List[str], timestamp: datetime
    ) -> Dict[str, Any]:
        """
        Retrieves historical features using DuckDB ASOF JOIN.
        """
        # 1. Create temporary context for the lookup
        ts_str = timestamp.isoformat()

        # Using parameterized query for safety if possible, or careful string construction
        # entity_id usually safe-ish, but let's be careful.
        # But for view creation, params are tricky. We'll use string interpolation for MVP
        # assuming internal entity_ids.

        setup_query = f"CREATE OR REPLACE TEMP VIEW request_ctx AS SELECT '{entity_id}' as entity_id, CAST('{ts_str}' AS TIMESTAMP) as timestamp"

        # 2. Build Query
        # We select the feature values.
        # Handle case where features list is empty?
        if not features:
            return {}

        selects = ", ".join([f"{f}.{f} as {f}" for f in features])
        query = f"SELECT {selects} FROM request_ctx"  # nosec

        joins = ""
        import re

        for feature in features:
            if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", feature):
                logger.warning("invalid_feature_name", feature=feature)
                continue

            # ASOF JOIN assumes tables named after features exist and have (entity_id, timestamp, {feature_name})
            # This is a strong assumption of the default schema.
            joins += f"""
            ASOF LEFT JOIN {feature}
            ON request_ctx.entity_id = {feature}.entity_id
            AND request_ctx.timestamp >= {feature}.timestamp
            """

        query += joins

        try:

            def _run() -> pd.DataFrame:
                conn = self._get_conn()
                conn.execute(setup_query)
                return conn.execute(query).df()

            df = await self._run_db(_run)
            if not df.empty:
                # Convert first row to dict
                return cast(Dict[str, Any], df.iloc[0].to_dict())
            return {}
        except Exception as e:
            # Table missing likely
            logger.warning("historical_retrieval_failed", error=str(e))
            return {}

    async def log_context(
        self,
        context_id: str,
        timestamp: datetime,
        content: str,
        lineage: Dict[str, Any],
        meta: Dict[str, Any],
        version: str = "v1",
    ) -> None:
        """Persist context to DuckDB for replay."""
        import json

        def json_serializer(obj: Any) -> str:
            """Handle datetime and other non-serializable types."""
            if isinstance(obj, datetime):
                return obj.isoformat()
            raise TypeError(
                f"Object of type {type(obj).__name__} is not JSON serializable"
            )

        lineage_json = json.dumps(lineage, default=json_serializer)
        meta_json = json.dumps(meta, default=json_serializer)
        ts_str = timestamp.isoformat()

        # Use parameterized query to prevent injection
        try:

            def _run() -> None:
                self._ensure_context_table_sync()
                self._get_conn().execute(
                    """
                    INSERT OR REPLACE INTO context_log
                    (context_id, timestamp, content, lineage, meta, version)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    [context_id, ts_str, content, lineage_json, meta_json, version],
                )

            await self._run_db(_run)
            logger.info("context_logged", context_id=context_id)
        except Exception as e:
            logger.error("context_log_failed", context_id=context_id, error=str(e))
            raise

    async def get_context(self, context_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a context by ID."""
        import json

        try:

            def _run() -> pd.DataFrame:
                self._ensure_context_table_sync()
                return (
                    self._get_conn()
                    .execute(
                        "SELECT * FROM context_log WHERE context_id = ?", [context_id]
                    )
                    .df()
                )

            df = await self._run_db(_run)
            if df.empty:
                return None

            row = df.iloc[0]
            return {
                "context_id": row["context_id"],
                "timestamp": row["timestamp"],
                "content": row["content"],
                "lineage": json.loads(row["lineage"])
                if isinstance(row["lineage"], str)
                else row["lineage"],
                "meta": json.loads(row["meta"])
                if isinstance(row["meta"], str)
                else row["meta"],
                "version": row["version"],
            }
        except Exception as e:
            logger.error(
                "context_retrieval_failed", context_id=context_id, error=str(e)
            )
            return None

    async def list_contexts(
        self,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        limit: int = 100,
        name: Optional[str] = None,
        freshness_status: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """List contexts in time range with optional filters.

        Args:
            start: Filter contexts created after this time
            end: Filter contexts created before this time
            limit: Maximum number of results
            name: Filter by context name (from meta.name)
            freshness_status: Filter by freshness status ("guaranteed" or "degraded")
        """
        import json

        # Build query with optional time filters
        conditions = []
        params: List[Any] = []

        if start:
            conditions.append("timestamp >= ?")
            params.append(start.isoformat())
        if end:
            conditions.append("timestamp <= ?")
            params.append(end.isoformat())

        # Filter by name (stored in meta JSON)
        if name:
            conditions.append("json_extract_string(meta, '$.name') = ?")
            params.append(name)

        # Filter by freshness_status (stored in meta JSON)
        if freshness_status:
            conditions.append("json_extract_string(meta, '$.freshness_status') = ?")
            params.append(freshness_status)

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        params.append(limit)

        query = f"""
            SELECT context_id, timestamp, meta, version
            FROM context_log
            {where_clause}
            ORDER BY timestamp DESC
            LIMIT ?
        """  # nosec B608 - where_clause built from validated internal conditions

        try:

            def _run() -> pd.DataFrame:
                self._ensure_context_table_sync()
                return self._get_conn().execute(query, params).df()

            df = await self._run_db(_run)
            results = []
            for _, row in df.iterrows():
                meta = (
                    json.loads(row["meta"])
                    if isinstance(row["meta"], str)
                    else row["meta"]
                )
                results.append(
                    {
                        "context_id": row["context_id"],
                        "timestamp": row["timestamp"],
                        "name": meta.get("name", "unknown"),
                        "token_usage": meta.get("token_usage", 0),
                        "freshness_status": meta.get("freshness_status", "unknown"),
                        "version": row["version"],
                    }
                )
            return results
        except Exception as e:
            logger.error("context_list_failed", error=str(e))
            return []

    async def log_record(self, record: "ContextRecord") -> str:
        """Persist a ContextRecord to DuckDB."""
        import json
        from fabra.exceptions import ImmutableRecordError

        def json_serializer(obj: Any) -> str:
            """Handle datetime and other non-serializable types."""
            if isinstance(obj, datetime):
                return obj.isoformat()
            raise TypeError(
                f"Object of type {type(obj).__name__} is not JSON serializable"
            )

        # Serialize complex fields to JSON
        inputs_json = json.dumps(record.inputs, default=json_serializer)
        features_json = json.dumps(
            [f.model_dump(mode="json") for f in record.features],
            default=json_serializer,
        )
        retrieved_items_json = json.dumps(
            [r.model_dump(mode="json") for r in record.retrieved_items],
            default=json_serializer,
        )
        assembly_json = json.dumps(
            record.assembly.model_dump(mode="json"), default=json_serializer
        )
        lineage_json = json.dumps(
            record.lineage.model_dump(mode="json"), default=json_serializer
        )
        integrity_json = json.dumps(
            record.integrity.model_dump(mode="json"), default=json_serializer
        )

        try:

            def _run() -> None:
                self._ensure_records_table_sync()
                existing = (
                    self._get_conn()
                    .execute(
                        "SELECT record_hash FROM context_records WHERE context_id = ?",
                        [record.context_id],
                    )
                    .fetchone()
                )
                if existing is not None:
                    existing_hash = existing[0]
                    attempted_hash = record.integrity.record_hash
                    if existing_hash == attempted_hash:
                        return
                    raise ImmutableRecordError(
                        context_id=record.context_id,
                        existing_record_hash=existing_hash,
                        attempted_record_hash=attempted_hash,
                    )

                self._get_conn().execute(
                    """
                    INSERT INTO context_records
                    (context_id, created_at, environment, schema_version,
                     context_function, inputs, content, token_count,
                     features, retrieved_items, assembly, lineage, integrity, record_hash)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        record.context_id,
                        record.created_at.isoformat(),
                        record.environment,
                        record.schema_version,
                        record.context_function,
                        inputs_json,
                        record.content,
                        record.token_count,
                        features_json,
                        retrieved_items_json,
                        assembly_json,
                        lineage_json,
                        integrity_json,
                        record.integrity.record_hash,
                    ],
                )

            await self._run_db(_run)
            logger.info("record_logged", context_id=record.context_id)
            return record.context_id
        except Exception as e:
            logger.error(
                "record_log_failed", context_id=record.context_id, error=str(e)
            )
            raise

    async def get_record(self, context_id: str) -> Optional["ContextRecord"]:
        """Retrieve a ContextRecord by ID."""
        import json
        from fabra.models import (
            ContextRecord,
            FeatureRecord,
            RetrievedItemRecord,
            AssemblyDecisions,
            LineageMetadata,
            IntegrityMetadata,
        )

        try:

            def _run() -> pd.DataFrame:
                self._ensure_records_table_sync()
                return (
                    self._get_conn()
                    .execute(
                        "SELECT * FROM context_records WHERE context_id = ?",
                        [context_id],
                    )
                    .df()
                )

            df = await self._run_db(_run)
            if df.empty:
                return None

            row = df.iloc[0]

            # Parse JSON fields
            inputs = (
                json.loads(row["inputs"])
                if isinstance(row["inputs"], str)
                else row["inputs"]
            )
            features_data = (
                json.loads(row["features"])
                if isinstance(row["features"], str)
                else row["features"]
            )
            retrieved_items_data = (
                json.loads(row["retrieved_items"])
                if isinstance(row["retrieved_items"], str)
                else row["retrieved_items"]
            )
            assembly_data = (
                json.loads(row["assembly"])
                if isinstance(row["assembly"], str)
                else row["assembly"]
            )
            lineage_data = (
                json.loads(row["lineage"])
                if isinstance(row["lineage"], str)
                else row["lineage"]
            )
            integrity_data = (
                json.loads(row["integrity"])
                if isinstance(row["integrity"], str)
                else row["integrity"]
            )

            # Parse created_at timestamp
            created_at = row["created_at"]
            if isinstance(created_at, str):
                created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            elif isinstance(created_at, datetime) and created_at.tzinfo is None:
                # DuckDB TIMESTAMP is timezone-naive; records are always authored in UTC.
                created_at = created_at.replace(tzinfo=timezone.utc)

            return ContextRecord(
                context_id=row["context_id"],
                created_at=created_at,
                environment=row["environment"],
                schema_version=row["schema_version"],
                context_function=row["context_function"],
                inputs=inputs or {},
                content=row["content"],
                token_count=row["token_count"],
                features=[FeatureRecord.model_validate(f) for f in features_data or []],
                retrieved_items=[
                    RetrievedItemRecord.model_validate(r)
                    for r in retrieved_items_data or []
                ],
                assembly=AssemblyDecisions.model_validate(assembly_data or {}),
                lineage=LineageMetadata.model_validate(lineage_data or {}),
                integrity=IntegrityMetadata.model_validate(integrity_data or {}),
            )
        except Exception as e:
            logger.error("record_retrieval_failed", context_id=context_id, error=str(e))
            return None

    async def get_record_by_hash(self, record_hash: str) -> Optional["ContextRecord"]:
        """Retrieve a ContextRecord by its record_hash."""
        import json
        from fabra.models import (
            ContextRecord,
            FeatureRecord,
            RetrievedItemRecord,
            AssemblyDecisions,
            LineageMetadata,
            IntegrityMetadata,
        )

        try:

            def _run() -> pd.DataFrame:
                self._ensure_records_table_sync()
                return (
                    self._get_conn()
                    .execute(
                        "SELECT * FROM context_records WHERE record_hash = ?",
                        [record_hash],
                    )
                    .df()
                )

            df = await self._run_db(_run)
            if df.empty:
                return None

            row = df.iloc[0]

            inputs = (
                json.loads(row["inputs"])
                if isinstance(row["inputs"], str)
                else row["inputs"]
            )
            features_data = (
                json.loads(row["features"])
                if isinstance(row["features"], str)
                else row["features"]
            )
            retrieved_items_data = (
                json.loads(row["retrieved_items"])
                if isinstance(row["retrieved_items"], str)
                else row["retrieved_items"]
            )
            assembly_data = (
                json.loads(row["assembly"])
                if isinstance(row["assembly"], str)
                else row["assembly"]
            )
            lineage_data = (
                json.loads(row["lineage"])
                if isinstance(row["lineage"], str)
                else row["lineage"]
            )
            integrity_data = (
                json.loads(row["integrity"])
                if isinstance(row["integrity"], str)
                else row["integrity"]
            )

            created_at = row["created_at"]
            if isinstance(created_at, str):
                created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            elif isinstance(created_at, datetime) and created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=timezone.utc)

            return ContextRecord(
                context_id=row["context_id"],
                created_at=created_at,
                environment=row["environment"],
                schema_version=row["schema_version"],
                context_function=row["context_function"],
                inputs=inputs or {},
                content=row["content"],
                token_count=row["token_count"],
                features=[FeatureRecord.model_validate(f) for f in features_data or []],
                retrieved_items=[
                    RetrievedItemRecord.model_validate(r)
                    for r in retrieved_items_data or []
                ],
                assembly=AssemblyDecisions.model_validate(assembly_data or {}),
                lineage=LineageMetadata.model_validate(lineage_data or {}),
                integrity=IntegrityMetadata.model_validate(integrity_data or {}),
            )
        except Exception as e:
            logger.error(
                "record_retrieval_failed", record_hash=record_hash, error=str(e)
            )
            return None

    async def list_records(
        self,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        limit: int = 100,
        context_function: Optional[str] = None,
        environment: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """List context records in time range with optional filters."""
        conditions = []
        params: List[Any] = []

        if start:
            conditions.append("created_at >= ?")
            params.append(start.isoformat())
        if end:
            conditions.append("created_at <= ?")
            params.append(end.isoformat())
        if context_function:
            conditions.append("context_function = ?")
            params.append(context_function)
        if environment:
            conditions.append("environment = ?")
            params.append(environment)

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        params.append(limit)

        query = f"""
            SELECT context_id, created_at, environment, schema_version,
                   context_function, token_count, record_hash
            FROM context_records
            {where_clause}
            ORDER BY created_at DESC
            LIMIT ?
        """  # nosec B608 - where_clause built from validated internal conditions

        try:

            def _run() -> pd.DataFrame:
                self._ensure_records_table_sync()
                return self._get_conn().execute(query, params).df()

            df = await self._run_db(_run)
            results = []
            for _, row in df.iterrows():
                results.append(
                    {
                        "context_id": row["context_id"],
                        "created_at": row["created_at"],
                        "environment": row["environment"],
                        "schema_version": row["schema_version"],
                        "context_function": row["context_function"],
                        "token_count": row["token_count"],
                        "record_hash": row["record_hash"],
                    }
                )
            return results
        except Exception as e:
            logger.error("record_list_failed", error=str(e))
            return []
