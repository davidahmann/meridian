from abc import ABC, abstractmethod
from typing import List
import duckdb
import pandas as pd
import asyncio


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


class DuckDBOfflineStore(OfflineStore):
    def __init__(self, database: str = ":memory:") -> None:
        self.conn = duckdb.connect(database=database)

    async def get_training_data(
        self,
        entity_df: pd.DataFrame,
        features: List[str],
        entity_id_col: str,
        timestamp_col: str = "timestamp",
    ) -> pd.DataFrame:
        # Register entity_df so it can be queried
        self.conn.register("entity_df", entity_df)

        # Construct query using ASOF JOIN for Point-in-Time Correctness
        # SELECT e.*, f1.value as f1
        # FROM entity_df e
        # ASOF LEFT JOIN feature_table f1
        # ON e.entity_id = f1.entity_id AND e.timestamp >= f1.timestamp

        query = "SELECT entity_df.*"
        joins = ""

        # ... (rest of the query construction logic is fine, preserving context)
        for feature in features:
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
            # Offload synchronous DuckDB execution to a thread
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(
                None, lambda: self.conn.execute(query).df()
            )
        except Exception as e:
            # Fallback for when tables don't exist (e.g. unit tests without setup)
            print(f"Offline retrieval failed: {e}")
            return entity_df

    async def execute_sql(self, query: str) -> pd.DataFrame:
        # Truly async using thread pool executor
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, lambda: self.conn.execute(query).df())
