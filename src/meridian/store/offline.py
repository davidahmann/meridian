from abc import ABC, abstractmethod
from typing import List
import duckdb
import pandas as pd


class OfflineStore(ABC):
    @abstractmethod
    def get_training_data(
        self, entity_df: pd.DataFrame, features: List[str]
    ) -> pd.DataFrame:
        """
        Generates training data by joining entity_df with feature data.
        """
        pass


class DuckDBOfflineStore(OfflineStore):
    def __init__(self, database: str = ":memory:") -> None:
        self.conn = duckdb.connect(database=database)

    def get_training_data(
        self, entity_df: pd.DataFrame, features: List[str]
    ) -> pd.DataFrame:
        # For MVP, we'll assume features are just SQL queries that return (entity_id, timestamp, value)
        # In a real implementation, this would be much more complex (point-in-time joins).
        # For now, let's just register the entity_df and run a simple join if possible,
        # or just return the entity_df if no features are passed (to pass the simplest test).

        # TODO: Implement full point-in-time join logic.
        # For now, we just register the entity dataframe so it can be queried.
        self.conn.register("entity_df", entity_df)

        # Placeholder return
        return entity_df

    def execute_sql(self, query: str) -> pd.DataFrame:
        return self.conn.execute(query).df()
