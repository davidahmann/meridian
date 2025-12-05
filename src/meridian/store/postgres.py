from typing import List
import pandas as pd
from sqlalchemy import create_engine, text
from .offline import OfflineStore


class PostgresOfflineStore(OfflineStore):
    def __init__(self, connection_string: str) -> None:
        self.engine = create_engine(connection_string)

    async def get_training_data(
        self, entity_df: pd.DataFrame, features: List[str]
    ) -> pd.DataFrame:
        # MVP: Similar to DuckDB, we assume features are accessible via SQL.
        # We upload the entity_df to a temporary table and join.

        # TODO: Use async driver (e.g. asyncpg) for true async I/O.
        # For now, we wrap the sync call.
        with self.engine.connect() as conn:
            # 1. Write entity_df to temp table
            entity_df.to_sql(
                "temp_entity_lookup", conn, if_exists="replace", index=False
            )

            # 2. Execute join (Placeholder logic)
            # In a real system, we'd construct a complex query.
            # Here we just return the entity_df to verify connectivity.
            query = text("SELECT * FROM temp_entity_lookup")
            result = pd.read_sql(query, conn)

            return result
