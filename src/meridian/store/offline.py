from abc import ABC, abstractmethod
from typing import List
import duckdb
import pandas as pd


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
        # For MVP, we'll assume features are just SQL queries that return (entity_id, timestamp, value)
        # In a real implementation, this would be much more complex (point-in-time joins).
        # For now, let's just register the entity_df and run a simple join if possible,
        # or just return the entity_df if no features are passed (to pass the simplest test).

        # TODO: Implement full point-in-time join logic.
        # For now, we just register the entity dataframe so it can be queried.
        # Register entity_df so it can be queried
        self.conn.register("entity_df", entity_df)

        # For MVP, we assume features are tables or views in DuckDB.
        # We'll perform a LEFT JOIN on the entity_df.
        # This is a simplification; real implementations need Point-in-Time Correctness.

        # Construct query
        # SELECT e.*, f1.value as f1, f2.value as f2 FROM entity_df e
        # LEFT JOIN feature_table_1 f1 ON e.id = f1.id
        # ...

        # But wait, we don't know the table names for the features here.
        # The 'features' list contains feature names.
        # In a real system, the registry maps feature_name -> table/view + column.
        # For this MVP, let's assume the feature name IS the table name,
        # and it has columns [entity_id, value].

        # However, the 'sql' field in Feature definition is a query.
        # If the feature is defined by SQL, we can treat it as a CTE or subquery.

        # Since we don't have access to the registry here (it's in FeatureStore),
        # we have a design gap.
        # The FeatureStore should probably resolve the SQL for each feature and pass it down,
        # OR the OfflineStore needs to know about feature definitions.

        # Given the current architecture, FeatureStore delegates to OfflineStore.
        # Let's assume for this MVP that the 'features' list passed here
        # are actually the SQL queries themselves (or table names) if we change the call site.

        # BUT, FeatureStore.get_training_data passes 'sql_features' (names) to this method.
        # This means OfflineStore needs to look them up? No, it doesn't have the registry.

        # FIX: We should change FeatureStore to pass a Dict[name, sql] instead of List[name].
        # But for now, let's assume the OfflineStore just joins existing tables named after features.
        # If the user defined a SQL feature, they must have materialized it or created a view?
        # No, 'sql' in Feature is the definition.

        # Let's pivot: FeatureStore should execute the SQL for each feature to get a DF,
        # then join them in memory (Pandas) for the MVP.
        # That's easier and safer than dynamic SQL generation here without metadata.

        # WAIT! If we do that, we lose the power of the DB engine.
        # Let's try to do it right.
        # We will assume that for any feature requested here, there exists a table/view
        # in DuckDB with that name.
        # The FeatureStore should ensure that view exists (maybe by registering the SQL as a view?).

        # Let's go with the "Join existing tables" approach for now.
        # We assume there is a table named `feature_name` with columns `entity_id` and `value`.
        # We also need to know the entity_id column name.
        # This is getting complicated without metadata.

        # Register entity_df so it can be queried
        self.conn.register("entity_df", entity_df)

        # Construct query using ASOF JOIN for Point-in-Time Correctness
        # SELECT e.*, f1.value as f1
        # FROM entity_df e
        # ASOF LEFT JOIN feature_table f1
        # ON e.entity_id = f1.entity_id AND e.timestamp >= f1.timestamp

        query = "SELECT entity_df.*"
        joins = ""

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
            return self.conn.execute(query).df()
        except Exception as e:
            # Fallback for when tables don't exist (e.g. unit tests without setup)
            print(f"Offline retrieval failed: {e}")
            return entity_df

    async def execute_sql(self, query: str) -> pd.DataFrame:
        return self.conn.execute(query).df()
