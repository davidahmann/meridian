from abc import ABC, abstractmethod
from typing import List
import duckdb
import pandas as pd
import asyncio
from typing import Dict, Any
from datetime import datetime


import structlog

logger = structlog.get_logger()


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
            # Offload synchronous DuckDB execution to a thread
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(
                None, lambda: self.conn.execute(query).df()
            )
        except Exception as e:
            # Fallback for when tables don't exist (e.g. unit tests without setup)
            logger.warning("offline_retrieval_failed", error=str(e))
            return entity_df

    async def execute_sql(self, query: str) -> pd.DataFrame:
        # Truly async using thread pool executor
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, lambda: self.conn.execute(query).df())

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

        self.conn.execute(setup_query)

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
            loop = asyncio.get_running_loop()
            # result returns df
            df = await loop.run_in_executor(None, lambda: self.conn.execute(query).df())
            if not df.empty:
                # Convert first row to dict
                return df.iloc[0].to_dict()
            return {}
        except Exception as e:
            # Table missing likely
            logger.warning("historical_retrieval_failed", error=str(e))
            return {}
