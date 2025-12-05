from typing import List
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

            for feature in features:
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
