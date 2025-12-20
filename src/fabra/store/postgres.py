from datetime import datetime, timezone
import re
import os
from typing import List, Optional, Dict, Any, TYPE_CHECKING
import json
import hashlib
import pandas as pd
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine
from fabra.store.offline import OfflineStore

import structlog

if TYPE_CHECKING:
    from fabra.models import ContextRecord

logger = structlog.get_logger()


class PostgresOfflineStore(OfflineStore):
    def __init__(self, connection_string: str) -> None:
        # Ensure connection string uses asyncpg driver
        if "asyncpg" not in connection_string:
            if "postgresql+psycopg2://" in connection_string:
                connection_string = connection_string.replace(
                    "postgresql+psycopg2://", "postgresql+asyncpg://"
                )
            elif "postgresql://" in connection_string:
                connection_string = connection_string.replace(
                    "postgresql://", "postgresql+asyncpg://"
                )

        # Pool Configuration
        pool_size = int(os.getenv("FABRA_PG_POOL_SIZE", "5"))
        max_overflow = int(os.getenv("FABRA_PG_MAX_OVERFLOW", "10"))

        self.engine: AsyncEngine = create_async_engine(
            connection_string,
            pool_size=pool_size,
            max_overflow=max_overflow,
        )

    async def get_training_data(
        self,
        entity_df: pd.DataFrame,
        features: List[str],
        entity_id_col: str,
        timestamp_col: str = "timestamp",
    ) -> pd.DataFrame:
        # MVP: Similar to DuckDB, we assume features are accessible via SQL.
        # We upload the entity_df to a temporary table and join.

        # Normalize timestamps to UTC-Aware
        # If naive, assume UTC.
        # This ensures consistent behavior with asyncpg/Postgres which prefer Aware datetimes.
        entity_df_norm = entity_df.copy()
        if timestamp_col in entity_df_norm.columns:
            ts_series = entity_df_norm[timestamp_col]
            if (
                pd.api.types.is_datetime64_ns_dtype(ts_series)
                and getattr(ts_series.dtype, "tz", None) is None
            ):
                entity_df_norm[timestamp_col] = ts_series.dt.tz_localize("UTC")
            elif pd.api.types.is_datetime64_dtype(ts_series):
                # Already aware, enable conversion to UTC if mixed?
                # ideally convert to UTC for consistency
                entity_df_norm[timestamp_col] = ts_series.dt.tz_convert("UTC")

        async with self.engine.connect() as conn:  # type: ignore[no-untyped-call]
            # 1. Upload entity_df to temp table
            # Pandas to_sql is sync, so we can't use it directly with async engine easily
            # without running in executor or using a sync connection.
            # For MVP, we'll create the table manually and insert values.
            # This is slow but works for proof of concept.

            # Create temp table
            await conn.execute(
                text(
                    "CREATE TEMP TABLE IF NOT EXISTS temp_entity_lookup (entity_id VARCHAR, timestamp TIMESTAMPTZ)"
                )
            )
            await conn.execute(text("DELETE FROM temp_entity_lookup"))

            # Insert values
            # Insert values
            # Note: We use SQLAlchemy's parameter binding for batch insert (executemany).
            # This is efficient for moderate sizes but slower than Postgres COPY for massive datasets.
            # Production upgrade: Use asyncpg.copy_records_to_table().
            values = []
            for _, row in entity_df_norm.iterrows():
                # Timestamp is now guaranteed Aware UTC by our normalization above
                ts_val = row[timestamp_col].to_pydatetime()
                values.append(
                    {
                        "entity_id": str(row[entity_id_col]),
                        "timestamp": ts_val,
                    }
                )

            if values:
                await conn.execute(
                    text(
                        "INSERT INTO temp_entity_lookup (entity_id, timestamp) VALUES (:entity_id, :timestamp)"
                    ),
                    values,
                )

            await conn.commit()

            # 2. Execute join using LATERAL JOIN for Point-in-Time Correctness
            query_parts = ["SELECT e.*"]
            joins = ""

            import re

            for feature in features:
                if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", feature):
                    raise ValueError(f"Invalid feature name: {feature}")

                joins += (
                    f" LEFT JOIN LATERAL ("
                    f" SELECT {feature}"
                    f" FROM {feature} f"  # nosec
                    f" WHERE f.entity_id = e.entity_id"
                    f" AND f.timestamp <= e.timestamp"
                    f" ORDER BY f.timestamp DESC"
                    f" LIMIT 1"
                    f" ) {feature}_lat ON TRUE"
                )
                query_parts.append(f", {feature}_lat.{feature} AS {feature}")

            query = "".join(query_parts) + f" FROM temp_entity_lookup e {joins}"

            result = await conn.execute(text(query))  # nosec
            rows = result.fetchall()

            # Convert to DataFrame
            # Convert to DataFrame
            if rows:
                sql_df = pd.DataFrame(rows, columns=result.keys())
            else:
                sql_df = pd.DataFrame(columns=list(result.keys()))

            # Ensure sql_df has UTC timezone to match entity_df_norm
            # asyncpg returns aware datetimes, likely UTC.
            # We assume sql_df is already aware.

            # Merge back to original entity_df (using the normalized one for keys)
            # We merge on entity_id and timestamp.
            # Note: The temp table used 'entity_id' and 'timestamp' as column names.
            # We need to map them back if the original cols were different, but for now we assume standard names
            # or that the caller handles column mapping.
            # Actually, the simplest way is to merge on the index if we preserved order, but SQL doesn't guarantee order.
            # So we merge on the join keys.

            # Ensure join keys match types
            sql_df["entity_id"] = sql_df["entity_id"].astype(str)
            # timestamp might be datetime64[ns] in pandas and datetime in postgres

            # To be safe and simple:
            # 1. Rename sql_df columns to match entity_id_col and timestamp_col if they differ
            if "entity_id" in sql_df.columns and entity_id_col != "entity_id":
                sql_df = sql_df.rename(columns={"entity_id": entity_id_col})
            if "timestamp" in sql_df.columns and timestamp_col != "timestamp":
                sql_df = sql_df.rename(columns={"timestamp": timestamp_col})

            # 2. Merge
            # We use a left join to keep all rows from entity_df_norm
            # We use entity_df_norm for the merge to ensure TZs match (both Aware UTC)
            merged_df_norm = pd.merge(
                entity_df_norm,
                sql_df,
                on=[entity_id_col, timestamp_col],
                how="left",
                suffixes=("", "_sql"),
            )

            # 3. Restore original non-normalized entity_df structure?
            # The caller might expect strict preservation of the input dataframe.
            # But the features are attached. If we return the normalized timestamps (UTC), it's generally cleaner.
            # Let's return the merged result with normalized UTC timestamps.
            return merged_df_norm

    async def execute_sql(self, query: str) -> pd.DataFrame:
        async with self.engine.connect() as conn:  # type: ignore[no-untyped-call]
            result = await conn.execute(text(query))
            rows = result.fetchall()
            if rows:
                return pd.DataFrame(rows, columns=result.keys())
            else:
                return pd.DataFrame(columns=list(result.keys()))

    async def get_historical_features(
        self, entity_name: str, entity_id: str, features: List[str], timestamp: datetime
    ) -> Dict[str, Any]:
        """
        Retrieves feature values as they were at the specified timestamp.
        """
        if not features:
            return {}

        # Use LATERAL JOINs against a single-row virtual table
        selects = []
        joins = ""

        import re

        for feature in features:
            if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", feature):
                continue

            joins += (
                f" LEFT JOIN LATERAL ("
                f" SELECT {feature}"
                f" FROM {feature} f"  # nosec
                f" WHERE f.entity_id = e.entity_id"
                f" AND f.timestamp <= e.timestamp"
                f" ORDER BY f.timestamp DESC"
                f" LIMIT 1"
                f" ) {feature}_lat ON TRUE"
            )
            selects.append(f"{feature}_lat.{feature} AS {feature}")

        select_clause = ", ".join(selects)

        # Postgres VALUES syntax for virtual table: (VALUES ('id', 'ts'::timestamp)) as e(entity_id, timestamp)
        query = f"""
        SELECT {select_clause}
        FROM (VALUES (:entity_id, :ts::timestamp)) as e(entity_id, timestamp)
        {joins}
        """  # nosec

        async with self.engine.connect() as conn:  # type: ignore[no-untyped-call]
            result = await conn.execute(
                text(query), {"entity_id": str(entity_id), "ts": timestamp}
            )
            row = result.fetchone()
            if row:
                # Convert Row to dict
                return dict(row._mapping)
            return {}

    async def create_index_table(self, index_name: str, dimension: int = 1536) -> None:
        """
        Creates the vector index table if it doesn't exist.
        Schema: id (UUID), entity_id, chunk_index, content, embedding, metadata.
        STRICT SCHEMA: Adds content_hash for deduplication.
        """
        table_name = f"fabra_index_{index_name}"
        async with self.engine.begin() as conn:  # type: ignore[no-untyped-call]
            # Enable extension
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))

            # Create table
            await conn.execute(
                text(
                    f"""
                    CREATE TABLE IF NOT EXISTS {table_name} (
                        id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
                        entity_id TEXT NOT NULL,
                        chunk_index INTEGER NOT NULL,
                        content TEXT NOT NULL,
                        content_hash TEXT NOT NULL,
                        embedding vector({dimension}),
                        metadata JSONB DEFAULT '{{}}'::jsonb,
                        created_at TIMESTAMP DEFAULT NOW(),
                        UNIQUE (entity_id, content_hash)
                    )
                    """
                )
            )

            # Create HNSW index
            idx_name = f"idx_{index_name}_embedding"
            await conn.execute(
                text(
                    f"""
                    CREATE INDEX IF NOT EXISTS {idx_name}
                    ON {table_name}
                    USING hnsw (embedding vector_cosine_ops)
                    """
                )
            )

    async def add_documents(
        self,
        index_name: str,
        entity_id: str,
        chunks: List[str],
        embeddings: List[List[float]],
        metadatas: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        """
        Inserts documents into the index.
        Computes content_hash and adds mandatory metadata.
        """
        if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", index_name):
            raise ValueError(f"Invalid index name {index_name}. Must be alphanumeric.")

        table_name = f"fabra_index_{index_name}"

        values = []
        for i, (chunk, vec) in enumerate(zip(chunks, embeddings)):
            meta = metadatas[i] if metadatas and i < len(metadatas) else {}

            # Compute hash
            content_hash = hashlib.sha256(chunk.encode("utf-8")).hexdigest()

            # Add Mandatory Metadata
            meta["ingestion_timestamp"] = datetime.now(timezone.utc).isoformat()
            meta["content_hash"] = content_hash
            meta["indexer_version"] = "fabra-v1"

            vec_str = str(vec)

            values.append(
                {
                    "entity_id": entity_id,
                    "chunk_index": i,
                    "content": chunk,
                    "content_hash": content_hash,
                    "embedding": vec_str,
                    "metadata": json.dumps(meta),
                }
            )

        async with self.engine.begin() as conn:  # type: ignore[no-untyped-call]
            # Use ON CONFLICT DO NOTHING to satisfy "prevent duplication" constraint
            insert_query = f"""
                    INSERT INTO {table_name} (entity_id, chunk_index, content, content_hash, embedding, metadata)
                    VALUES (:entity_id, :chunk_index, :content, :content_hash, :embedding, :metadata)
                    ON CONFLICT (entity_id, content_hash) DO NOTHING
                    """  # nosec

            await conn.execute(
                text(insert_query),
                values,
            )

    async def search(
        self,
        index_name: str,
        query_embedding: List[float],
        top_k: int = 5,
        filter_timestamp: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """
        Performs vector similarity search (Cosine Distance via <=> operator).
        Returns list of dicts with content and metadata.
        """
        if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", index_name):
            raise ValueError(f"Invalid index name {index_name}. Must be alphanumeric.")

        table_name = f"fabra_index_{index_name}"
        vec_str = str(query_embedding)

        where_clause = ""
        params = {"query_vec": vec_str, "top_k": top_k}

        if filter_timestamp:
            # Filter by ingestion time (created_at)
            where_clause = "WHERE created_at <= :ts"
            params["ts"] = filter_timestamp

        query = f"""
        SELECT content, metadata, 1 - (embedding <=> :query_vec) as score
        FROM {table_name}
        {where_clause}
        ORDER BY embedding <=> :query_vec
        LIMIT :top_k
        """  # nosec

        async with self.engine.connect() as conn:  # type: ignore[no-untyped-call]
            result = await conn.execute(text(query), params)
            rows = result.fetchall()
            return [
                {"content": r.content, "metadata": r.metadata, "score": r.score}
                for r in rows
            ]

    async def _ensure_context_table(self) -> None:
        """Create context_log table if it doesn't exist."""
        async with self.engine.begin() as conn:  # type: ignore[no-untyped-call]
            await conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS context_log (
                        context_id VARCHAR(255) PRIMARY KEY,
                        timestamp TIMESTAMPTZ NOT NULL,
                        content TEXT NOT NULL,
                        lineage JSONB NOT NULL,
                        meta JSONB NOT NULL,
                        version VARCHAR(10) DEFAULT 'v1'
                    )
                    """
                )
            )
            # If the table already existed with a smaller varchar, widen it.
            try:
                await conn.execute(
                    text(
                        "ALTER TABLE context_log ALTER COLUMN context_id TYPE VARCHAR(255)"
                    )
                )
            except Exception as e:
                logger.debug("context_log_alter_skipped", error=str(e))
            # Create index for timestamp-based queries
            await conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS idx_context_log_timestamp ON context_log(timestamp)"
                )
            )

    async def log_context(
        self,
        context_id: str,
        timestamp: datetime,
        content: str,
        lineage: Dict[str, Any],
        meta: Dict[str, Any],
        version: str = "v1",
    ) -> None:
        """Persist context to Postgres for replay."""
        await self._ensure_context_table()

        def json_serializer(obj: Any) -> str:
            """Handle datetime and other non-serializable types."""
            if isinstance(obj, datetime):
                return obj.isoformat()
            raise TypeError(
                f"Object of type {type(obj).__name__} is not JSON serializable"
            )

        lineage_json = json.dumps(lineage, default=json_serializer)
        meta_json = json.dumps(meta, default=json_serializer)

        async with self.engine.begin() as conn:  # type: ignore[no-untyped-call]
            await conn.execute(
                text(
                    """
                    INSERT INTO context_log (context_id, timestamp, content, lineage, meta, version)
                    VALUES (:context_id, :timestamp, :content, :lineage, :meta, :version)
                    ON CONFLICT (context_id) DO UPDATE SET
                        timestamp = EXCLUDED.timestamp,
                        content = EXCLUDED.content,
                        lineage = EXCLUDED.lineage,
                        meta = EXCLUDED.meta,
                        version = EXCLUDED.version
                    """
                ),
                {
                    "context_id": context_id,
                    "timestamp": timestamp,
                    "content": content,
                    "lineage": lineage_json,
                    "meta": meta_json,
                    "version": version,
                },
            )

    async def get_context(self, context_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a context by ID."""
        await self._ensure_context_table()

        async with self.engine.connect() as conn:  # type: ignore[no-untyped-call]
            result = await conn.execute(
                text("SELECT * FROM context_log WHERE context_id = :context_id"),
                {"context_id": context_id},
            )
            row = result.fetchone()
            if row is None:
                return None

            return {
                "context_id": row.context_id,
                "timestamp": row.timestamp,
                "content": row.content,
                "lineage": row.lineage
                if isinstance(row.lineage, dict)
                else json.loads(row.lineage),
                "meta": row.meta
                if isinstance(row.meta, dict)
                else json.loads(row.meta),
                "version": row.version,
            }

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
        await self._ensure_context_table()

        conditions = []
        params: Dict[str, Any] = {"limit": limit}

        if start:
            conditions.append("timestamp >= :start")
            params["start"] = start
        if end:
            conditions.append("timestamp <= :end")
            params["end"] = end

        # Filter by name (stored in meta JSONB)
        if name:
            conditions.append("meta->>'name' = :name")
            params["name"] = name

        # Filter by freshness_status (stored in meta JSONB)
        if freshness_status:
            conditions.append("meta->>'freshness_status' = :freshness_status")
            params["freshness_status"] = freshness_status

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        query = f"""
            SELECT context_id, timestamp, meta, version
            FROM context_log
            {where_clause}
            ORDER BY timestamp DESC
            LIMIT :limit
        """  # nosec B608 - where_clause built from validated internal conditions

        async with self.engine.connect() as conn:  # type: ignore[no-untyped-call]
            result = await conn.execute(text(query), params)
            rows = result.fetchall()

            results = []
            for row in rows:
                meta = row.meta if isinstance(row.meta, dict) else json.loads(row.meta)
                results.append(
                    {
                        "context_id": row.context_id,
                        "timestamp": row.timestamp,
                        "name": meta.get("name", "unknown"),
                        "token_usage": meta.get("token_usage", 0),
                        "freshness_status": meta.get("freshness_status", "unknown"),
                        "version": row.version,
                    }
                )
            return results

    async def _ensure_records_table(self) -> None:
        """Create context_records table if it doesn't exist."""
        async with self.engine.begin() as conn:  # type: ignore[no-untyped-call]
            await conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS context_records (
                        context_id VARCHAR(255) PRIMARY KEY,
                        created_at TIMESTAMPTZ NOT NULL,
                        environment VARCHAR(50) NOT NULL,
                        schema_version VARCHAR(20) NOT NULL,
                        context_function VARCHAR(255),
                        inputs JSONB,
                        content TEXT,
                        token_count INTEGER,
                        features JSONB,
                        retrieved_items JSONB,
                        assembly JSONB,
                        lineage JSONB,
                        integrity JSONB,
                        record_hash VARCHAR(100) UNIQUE
                    )
                    """
                )
            )
            # Create indexes for common queries
            await conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS idx_records_created ON context_records(created_at)"
                )
            )
            await conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS idx_records_function ON context_records(context_function)"
                )
            )
            await conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS idx_records_env ON context_records(environment)"
                )
            )

    async def log_record(self, record: "ContextRecord") -> str:
        """Persist a ContextRecord to Postgres."""
        await self._ensure_records_table()
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

        async with self.engine.begin() as conn:  # type: ignore[no-untyped-call]
            params = {
                "context_id": record.context_id,
                "created_at": record.created_at,
                "environment": record.environment,
                "schema_version": record.schema_version,
                "context_function": record.context_function,
                "inputs": inputs_json,
                "content": record.content,
                "token_count": record.token_count,
                "features": features_json,
                "retrieved_items": retrieved_items_json,
                "assembly": assembly_json,
                "lineage": lineage_json,
                "integrity": integrity_json,
                "record_hash": record.integrity.record_hash,
            }

            result = await conn.execute(
                text(
                    """
                    INSERT INTO context_records
                    (context_id, created_at, environment, schema_version,
                     context_function, inputs, content, token_count,
                     features, retrieved_items, assembly, lineage, integrity, record_hash)
                    VALUES (:context_id, :created_at, :environment, :schema_version,
                            :context_function, :inputs, :content, :token_count,
                            :features, :retrieved_items, :assembly, :lineage, :integrity, :record_hash)
                    ON CONFLICT (context_id) DO NOTHING
                    """
                ),
                params,
            )

            if getattr(result, "rowcount", 0) == 0:
                existing = await conn.execute(
                    text(
                        "SELECT record_hash FROM context_records WHERE context_id = :context_id"
                    ),
                    {"context_id": record.context_id},
                )
                row = existing.fetchone()
                if row is None:
                    raise RuntimeError(
                        "Record insert conflict but no existing record found"
                    )
                existing_hash = row.record_hash
                attempted_hash = record.integrity.record_hash
                if existing_hash != attempted_hash:
                    raise ImmutableRecordError(
                        context_id=record.context_id,
                        existing_record_hash=existing_hash,
                        attempted_record_hash=attempted_hash,
                    )
            logger.info("record_logged", context_id=record.context_id)
            return record.context_id

    async def get_record(self, context_id: str) -> Optional["ContextRecord"]:
        """Retrieve a ContextRecord by ID."""
        from fabra.models import (
            ContextRecord,
            FeatureRecord,
            RetrievedItemRecord,
            AssemblyDecisions,
            LineageMetadata,
            IntegrityMetadata,
        )

        await self._ensure_records_table()

        async with self.engine.connect() as conn:  # type: ignore[no-untyped-call]
            result = await conn.execute(
                text("SELECT * FROM context_records WHERE context_id = :context_id"),
                {"context_id": context_id},
            )
            row = result.fetchone()
            if row is None:
                return None

            # Parse JSON fields - Postgres JSONB returns dict directly
            inputs = (
                row.inputs
                if isinstance(row.inputs, dict)
                else json.loads(row.inputs or "{}")
            )
            features_data = (
                row.features
                if isinstance(row.features, list)
                else json.loads(row.features or "[]")
            )
            retrieved_items_data = (
                row.retrieved_items
                if isinstance(row.retrieved_items, list)
                else json.loads(row.retrieved_items or "[]")
            )
            assembly_data = (
                row.assembly
                if isinstance(row.assembly, dict)
                else json.loads(row.assembly or "{}")
            )
            lineage_data = (
                row.lineage
                if isinstance(row.lineage, dict)
                else json.loads(row.lineage or "{}")
            )
            integrity_data = (
                row.integrity
                if isinstance(row.integrity, dict)
                else json.loads(row.integrity or "{}")
            )

            return ContextRecord(
                context_id=row.context_id,
                created_at=row.created_at,
                environment=row.environment,
                schema_version=row.schema_version,
                context_function=row.context_function,
                inputs=inputs or {},
                content=row.content,
                token_count=row.token_count,
                features=[FeatureRecord.model_validate(f) for f in features_data or []],
                retrieved_items=[
                    RetrievedItemRecord.model_validate(r)
                    for r in retrieved_items_data or []
                ],
                assembly=AssemblyDecisions.model_validate(assembly_data or {}),
                lineage=LineageMetadata.model_validate(lineage_data or {}),
                integrity=IntegrityMetadata.model_validate(integrity_data or {}),
            )

    async def get_record_by_hash(self, record_hash: str) -> Optional["ContextRecord"]:
        """Retrieve a ContextRecord by its record_hash."""
        from fabra.models import (
            ContextRecord,
            FeatureRecord,
            RetrievedItemRecord,
            AssemblyDecisions,
            LineageMetadata,
            IntegrityMetadata,
        )

        await self._ensure_records_table()

        async with self.engine.connect() as conn:  # type: ignore[no-untyped-call]
            result = await conn.execute(
                text("SELECT * FROM context_records WHERE record_hash = :record_hash"),
                {"record_hash": record_hash},
            )
            row = result.fetchone()
            if row is None:
                return None

            inputs = (
                row.inputs
                if isinstance(row.inputs, dict)
                else json.loads(row.inputs or "{}")
            )
            features_data = (
                row.features
                if isinstance(row.features, list)
                else json.loads(row.features or "[]")
            )
            retrieved_items_data = (
                row.retrieved_items
                if isinstance(row.retrieved_items, list)
                else json.loads(row.retrieved_items or "[]")
            )
            assembly_data = (
                row.assembly
                if isinstance(row.assembly, dict)
                else json.loads(row.assembly or "{}")
            )
            lineage_data = (
                row.lineage
                if isinstance(row.lineage, dict)
                else json.loads(row.lineage or "{}")
            )
            integrity_data = (
                row.integrity
                if isinstance(row.integrity, dict)
                else json.loads(row.integrity or "{}")
            )

            return ContextRecord(
                context_id=row.context_id,
                created_at=row.created_at,
                environment=row.environment,
                schema_version=row.schema_version,
                context_function=row.context_function,
                inputs=inputs or {},
                content=row.content,
                token_count=row.token_count,
                features=[FeatureRecord.model_validate(f) for f in features_data or []],
                retrieved_items=[
                    RetrievedItemRecord.model_validate(r)
                    for r in retrieved_items_data or []
                ],
                assembly=AssemblyDecisions.model_validate(assembly_data or {}),
                lineage=LineageMetadata.model_validate(lineage_data or {}),
                integrity=IntegrityMetadata.model_validate(integrity_data or {}),
            )

    async def list_records(
        self,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        limit: int = 100,
        context_function: Optional[str] = None,
        environment: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """List context records in time range with optional filters."""
        await self._ensure_records_table()

        conditions = []
        params: Dict[str, Any] = {"limit": limit}

        if start:
            conditions.append("created_at >= :start")
            params["start"] = start
        if end:
            conditions.append("created_at <= :end")
            params["end"] = end
        if context_function:
            conditions.append("context_function = :context_function")
            params["context_function"] = context_function
        if environment:
            conditions.append("environment = :environment")
            params["environment"] = environment

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        query = f"""
            SELECT context_id, created_at, environment, schema_version,
                   context_function, token_count, record_hash
            FROM context_records
            {where_clause}
            ORDER BY created_at DESC
            LIMIT :limit
        """  # nosec B608 - where_clause built from validated internal conditions

        async with self.engine.connect() as conn:  # type: ignore[no-untyped-call]
            result = await conn.execute(text(query), params)
            rows = result.fetchall()

            results = []
            for row in rows:
                results.append(
                    {
                        "context_id": row.context_id,
                        "created_at": row.created_at,
                        "environment": row.environment,
                        "schema_version": row.schema_version,
                        "context_function": row.context_function,
                        "token_count": row.token_count,
                        "record_hash": row.record_hash,
                    }
                )
            return results
