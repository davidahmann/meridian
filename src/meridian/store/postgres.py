from datetime import datetime
from typing import List, Optional, Dict, Any
import json
import pandas as pd
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine
from meridian.store.offline import OfflineStore


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

        self.engine: AsyncEngine = create_async_engine(connection_string)

    async def get_training_data(
        self,
        entity_df: pd.DataFrame,
        features: List[str],
        entity_id_col: str,
        timestamp_col: str = "timestamp",
    ) -> pd.DataFrame:
        # MVP: Similar to DuckDB, we assume features are accessible via SQL.
        # We upload the entity_df to a temporary table and join.

        async with self.engine.connect() as conn:  # type: ignore[no-untyped-call]
            # 1. Upload entity_df to temp table
            # Pandas to_sql is sync, so we can't use it directly with async engine easily
            # without running in executor or using a sync connection.
            # For MVP, we'll create the table manually and insert values.
            # This is slow but works for proof of concept.

            # Create temp table
            await conn.execute(
                text(
                    "CREATE TEMP TABLE IF NOT EXISTS temp_entity_lookup (entity_id VARCHAR, timestamp TIMESTAMP)"
                )
            )
            await conn.execute(text("DELETE FROM temp_entity_lookup"))

            # Insert values
            # Insert values
            # Note: We use SQLAlchemy's parameter binding for batch insert (executemany).
            # This is efficient for moderate sizes but slower than Postgres COPY for massive datasets.
            # Production upgrade: Use asyncpg.copy_records_to_table().
            values = []
            for _, row in entity_df.iterrows():
                values.append(
                    {
                        "entity_id": str(row[entity_id_col]),
                        "timestamp": row[timestamp_col],
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

            # Merge back to original entity_df to preserve other columns (e.g. Python features)
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
            # We use a left join to keep all rows from entity_df
            merged_df = pd.merge(
                entity_df,
                sql_df,
                on=[entity_id_col, timestamp_col],
                how="left",
                suffixes=("", "_sql"),
            )

            return merged_df

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
        table_name = f"meridian_index_{index_name}"
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
        import hashlib
        import datetime

        table_name = f"meridian_index_{index_name}"

        values = []
        for i, (chunk, vec) in enumerate(zip(chunks, embeddings)):
            meta = metadatas[i] if metadatas and i < len(metadatas) else {}

            # Compute hash
            content_hash = hashlib.sha256(chunk.encode("utf-8")).hexdigest()

            # Add Mandatory Metadata
            meta["ingestion_timestamp"] = datetime.datetime.utcnow().isoformat()
            meta["content_hash"] = content_hash
            meta["indexer_version"] = "meridian-v1"

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
        table_name = f"meridian_index_{index_name}"
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
