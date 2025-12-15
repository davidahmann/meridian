import functools
from typing import (
    Any,
    Callable,
    Dict,
    Optional,
    Type,
    Union,
    List,
    get_type_hints,
    cast,
)
from dataclasses import dataclass
from datetime import timedelta, datetime, timezone
import pandas as pd
from .store import (
    InMemoryOnlineStore,
    RedisOnlineStore,
)
from .scheduler import Scheduler
from .scheduler_dist import DistributedScheduler
from .hooks import Hook, HookManager
from .context import record_feature_usage

import structlog
from prometheus_client import Counter, Histogram
import time

from .store import (
    OfflineStore,
    OnlineStore,
)
from .retrieval import RetrieverRegistry
from .index import Index, IndexRegistry
from .embeddings import OpenAIEmbedding

# Metrics
FEATURE_REQUESTS = Counter(
    "fabra_feature_requests_total", "Total feature requests", ["feature", "status"]
)
FEATURE_LATENCY = Histogram(
    "fabra_feature_latency_seconds",
    "Latency of feature retrieval",
    ["feature", "step"],
)
FEATURE_MATERIALIZE_FAILURES = Counter(
    "fabra_feature_materialize_failures_total",
    "Total feature materialization failures",
    ["feature"],
)

logger = structlog.get_logger()


def get_current_timestamp() -> Optional[datetime]:
    """Returns the current Time Travel timestamp, or None if real-time."""
    # Single source of truth: time travel is controlled by fabra.context.
    from fabra.context import get_time_travel_timestamp

    return get_time_travel_timestamp()


async def get_context(
    func: Callable[..., Any], metadata: Optional[Dict[str, Any]] = None, **kwargs: Any
) -> Any:
    """
    Executes a context assembly function with Time Travel support.

    Args:
        func: The context function (decorated with @context).
        timestamp: (kwarg) The point-in-time to travel to.
        **kwargs: Arguments for the context function.
    """
    timestamp = kwargs.pop("timestamp", None)

    if timestamp:
        from fabra.context import set_time_travel_context, clear_time_travel_context

        set_time_travel_context(timestamp)
        try:
            return await func(**kwargs)
        finally:
            clear_time_travel_context()
    else:
        return await func(**kwargs)


@dataclass
class Entity:
    name: str
    id_column: str
    description: Optional[str] = None

    def _repr_html_(self) -> str:
        return f"""
        <div style="font-family: sans-serif; border: 1px solid #e0e0e0; border-radius: 4px; padding: 10px; max-width: 600px;">
            <h3 style="margin-top: 0; color: #333;">📦 Entity: {self.name}</h3>
            <p><strong>ID Column:</strong> <code>{self.id_column}</code></p>
            <p><strong>Description:</strong> {self.description or "<em>No description</em>"}</p>
        </div>
        """


@dataclass
class Feature:
    name: str
    entity_name: str
    func: Callable[..., Any]
    refresh: Optional[timedelta] = None
    ttl: Optional[timedelta] = None
    materialize: bool = False
    description: Optional[str] = None
    stale_tolerance: Optional[timedelta] = None
    default_value: Any = None
    sql: Optional[str] = None
    trigger: Optional[str] = None


class FeatureRegistry:
    def __init__(self) -> None:
        self.entities: Dict[str, Entity] = {}
        self.features: Dict[str, Feature] = {}
        self.contexts: Dict[str, Callable[..., Any]] = {}

    def register_entity(self, entity: Entity) -> None:
        self.entities[entity.name] = entity

    def register_feature(self, feature: Feature) -> None:
        self.features[feature.name] = feature

    def get_features_for_entity(self, entity_name: str) -> List[Feature]:
        return [f for f in self.features.values() if f.entity_name == entity_name]

    def get_features_by_trigger(self, trigger: str) -> List[Feature]:
        return [f for f in self.features.values() if f.trigger == trigger]

    def get_triggers(self) -> List[str]:
        triggers = {f.trigger for f in self.features.values() if f.trigger}
        return sorted(triggers)

    def register_context(self, name: str, func: Callable[..., Any]) -> None:
        """Register a context function for replay support."""
        self.contexts[name] = func


class FeatureStore:
    def __init__(
        self,
        offline_store: Optional[OfflineStore] = None,
        online_store: Optional[OnlineStore] = None,
        hooks: Optional[List[Hook]] = None,
    ) -> None:
        self.registry = FeatureRegistry()
        self.retriever_registry = RetrieverRegistry()
        self.index_registry = IndexRegistry()
        self.hooks = HookManager(hooks or [])

        # Auto-configure stores if not provided
        if offline_store is None or online_store is None:
            from fabra.config import get_store_factory

            default_offline, default_online = get_store_factory()
            self.offline_store = offline_store or default_offline
            self.online_store = online_store or default_online
        else:
            self.offline_store = offline_store
            self.online_store = online_store or InMemoryOnlineStore()

        self.scheduler: Union[Scheduler, DistributedScheduler]

        # Select scheduler based on online store type
        if isinstance(self.online_store, RedisOnlineStore):
            self.scheduler = DistributedScheduler(self.online_store.get_sync_client())
        else:
            self.scheduler = Scheduler()

    def _repr_html_(self) -> str:
        # Count entities and features
        n_entities = len(self.registry.entities)
        n_features = len(self.registry.features)

        # Build Entity Table
        entity_rows = ""
        for name, ent in self.registry.entities.items():
            entity_rows += f"<tr><td style='padding: 8px; border-bottom: 1px solid #eee;'>{name}</td><td style='padding: 8px; border-bottom: 1px solid #eee;'><code>{ent.id_column}</code></td><td style='padding: 8px; border-bottom: 1px solid #eee;'>{ent.description or ''}</td></tr>"

        # Build Feature Table (Top 5)
        feature_rows = ""
        for i, (name, feat) in enumerate(self.registry.features.items()):
            if i >= 5:
                feature_rows += f"<tr><td colspan='4' style='padding: 8px; text-align: center; color: #666;'><em>... and {n_features - 5} more</em></td></tr>"
                break
            feature_rows += f"<tr><td style='padding: 8px; border-bottom: 1px solid #eee;'>{name}</td><td style='padding: 8px; border-bottom: 1px solid #eee;'>{feat.entity_name}</td><td style='padding: 8px; border-bottom: 1px solid #eee;'><code>{feat.refresh}</code></td><td style='padding: 8px; border-bottom: 1px solid #eee;'>{feat.materialize}</td></tr>"

        return f"""
        <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; border: 1px solid #e0e0e0; border-radius: 8px; padding: 20px; max-width: 800px; box-shadow: 0 4px 6px rgba(0,0,0,0.05);">
            <div style="display: flex; align-items: center; margin-bottom: 20px;">
                <div style="font-size: 24px; margin-right: 10px;">🧭</div>
                <div>
                    <h2 style="margin: 0; color: #1a73e8; font-size: 20px;">Fabra Feature Store</h2>
                    <div style="color: #666; font-size: 13px;">Version: 1.2.5</div>
                </div>
            </div>

            <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 15px; margin-bottom: 25px;">
                <div style="background: #f8f9fa; padding: 10px; border-radius: 6px; text-align: center;">
                    <div style="font-size: 24px; font-weight: bold; color: #333;">{n_entities}</div>
                    <div style="color: #666; font-size: 12px; text-transform: uppercase;">Entities</div>
                </div>
                <div style="background: #f8f9fa; padding: 10px; border-radius: 6px; text-align: center;">
                    <div style="font-size: 24px; font-weight: bold; color: #333;">{n_features}</div>
                    <div style="color: #666; font-size: 12px; text-transform: uppercase;">Features</div>
                </div>
                <div style="background: #e8f0fe; padding: 10px; border-radius: 6px; text-align: center;">
                    <div style="font-weight: bold; color: #1a73e8; font-size: 14px; margin-bottom: 4px;">{self.offline_store.__class__.__name__}</div>
                    <div style="color: #1a73e8; font-size: 10px; text-transform: uppercase;">Offline</div>
                </div>
                <div style="background: #e6f4ea; padding: 10px; border-radius: 6px; text-align: center;">
                    <div style="font-weight: bold; color: #1e8e3e; font-size: 14px; margin-bottom: 4px;">{self.online_store.__class__.__name__}</div>
                    <div style="color: #1e8e3e; font-size: 10px; text-transform: uppercase;">Online</div>
                </div>
            </div>

            <h4 style="margin: 0 0 10px 0; color: #333;">Entities</h4>
            <div style="overflow-x: auto; margin-bottom: 20px;">
                <table style="width: 100%; border-collapse: collapse; font-size: 14px;">
                    <thead style="background-color: #f1f3f4; color: #5f6368;">
                        <tr><th style="text-align: left; padding: 8px; border-radius: 4px 0 0 4px;">Name</th><th style="text-align: left; padding: 8px;">ID Column</th><th style="text-align: left; padding: 8px; border-radius: 0 4px 4px 0;">Description</th></tr>
                    </thead>
                    <tbody>
                        {entity_rows}
                    </tbody>
                </table>
            </div>

            <h4 style="margin: 0 0 10px 0; color: #333;">Features</h4>
            <div style="overflow-x: auto;">
                <table style="width: 100%; border-collapse: collapse; font-size: 14px;">
                    <thead style="background-color: #f1f3f4; color: #5f6368;">
                        <tr><th style="text-align: left; padding: 8px; border-radius: 4px 0 0 4px;">Name</th><th style="text-align: left; padding: 8px;">Entity</th><th style="text-align: left; padding: 8px;">Refresh</th><th style="text-align: left; padding: 8px; border-radius: 0 4px 4px 0;">Materialize</th></tr>
                    </thead>
                    <tbody>
                        {feature_rows}
                    </tbody>
                </table>
            </div>
        </div>
        """

    def start(self) -> None:
        """
        Starts the scheduler and registers jobs for all materialized features.
        """
        # Start the scheduler
        self.scheduler.start()

        for name, feature in self.registry.features.items():
            if feature.materialize and feature.refresh:
                self.scheduler.schedule_job(
                    func=functools.partial(self._materialize_feature, name),
                    interval_seconds=int(feature.refresh.total_seconds()),
                    job_id=f"materialize_{name}",
                )

    def stop(self) -> None:
        """
        Stops the scheduler.
        """
        if hasattr(self.scheduler, "shutdown"):
            self.scheduler.shutdown()

    def _materialize_feature(self, feature_name: str) -> None:
        """Sync wrapper for scheduler."""
        import asyncio

        asyncio.run(self._materialize_feature_async(feature_name))

    async def _materialize_feature_async(self, feature_name: str) -> None:
        feature_def = self.registry.features.get(feature_name)
        if not feature_def:
            logger.error(
                "materialize_failed", error=f"Feature {feature_name} not found"
            )
            return

        if not feature_def.sql:
            logger.warning(
                "materialize_skipped",
                feature=feature_name,
                reason="No SQL definition. Cannot materialize pure Python feature without batch source.",
            )
            return

        logger.info("materialize_start", feature=feature_name)
        try:
            # 1. Execute SQL against Offline Store
            df = await self.offline_store.execute_sql(feature_def.sql)

            # 2. Write to Online Store
            # We assume the SQL returns [entity_id, feature_value] or similar.
            # We need to know the entity_id column name to map it correctly.
            entity_def = self.registry.entities.get(feature_def.entity_name)
            if not entity_def:
                raise ValueError(f"Entity '{feature_def.entity_name}' not found")

            # 3. Bulk Write
            await self.online_store.set_online_features_bulk(
                entity_name=feature_def.entity_name,
                features_df=df,
                feature_name=feature_name,
                entity_id_col=entity_def.id_column,
            )

            logger.info("materialize_success", feature=feature_name, rows=len(df))

        except Exception as e:
            logger.error("materialize_failed", feature=feature_name, error=str(e))
            FEATURE_MATERIALIZE_FAILURES.labels(feature=feature_name).inc()

    async def get_training_data(
        self, entity_df: pd.DataFrame, features: List[str]
    ) -> pd.DataFrame:
        # 1. Separate Python vs SQL features
        python_features = []
        sql_features = []

        for feature_name in features:
            feature_def = self.registry.features.get(feature_name)
            if not feature_def:
                import difflib

                matches = difflib.get_close_matches(
                    feature_name, self.registry.features.keys(), n=3, cutoff=0.6
                )
                msg = f"Feature '{feature_name}' not found in registry."
                if matches:
                    msg += f" Did you mean: {', '.join(matches)}?"
                raise ValueError(msg)

            if feature_def.sql:
                sql_features.append(feature_name)
            else:
                python_features.append(feature_name)

        # 2. Process Python Features (Row-by-Row Apply)
        # Copy df to avoid side effects
        result_df = entity_df.copy()

        # Ensure ID column is present for lookups if needed, though apply passes the row
        # We assume the entity_df has the necessary columns for the feature function.
        # Ideally, feature functions take an entity_id.

        for feature_name in python_features:
            feature_def = self.registry.features[feature_name]
            # Assuming feature function takes entity_id as first argument
            # We need to know which column in entity_df corresponds to the entity_id
            # The feature definition knows its entity_name, and the registry knows the entity definition
            entity_def = self.registry.entities.get(feature_def.entity_name)
            if not entity_def:
                raise ValueError(
                    f"Entity '{feature_def.entity_name}' not found for feature '{feature_name}'"
                )

            id_col = entity_def.id_column
            if id_col not in result_df.columns:
                raise ValueError(
                    f"Entity ID column '{id_col}' missing from input dataframe."
                )

            # Apply function
            # Note: This is slow for large dataframes, but correct for MVP "Python" path.
            result_df[feature_name] = result_df[id_col].apply(feature_def.func)

        # 3. Process SQL Features (Delegate to Offline Store)
        if sql_features:
            # Resolve entity_id_col from the first feature
            # Assuming all features belong to the same entity for this call
            first_feature = self.registry.features[features[0]]
            entity_def = self.registry.entities[first_feature.entity_name]
            entity_id_col = entity_def.id_column

            # Pass the partially enriched dataframe (result_df) to offline store
            # so it can join SQL features onto it.
            # We assume entity_df has a timestamp column named 'timestamp' or 'event_timestamp'
            timestamp_col = (
                "event_timestamp"
                if "event_timestamp" in result_df.columns
                else "timestamp"
            )

            result_df = await self.offline_store.get_training_data(
                result_df, sql_features, entity_id_col, timestamp_col
            )

        return result_df

    async def get_online_features(
        self, entity_name: str, entity_id: str, features: List[str]
    ) -> Dict[str, Any]:
        log = logger.bind(
            entity_name=entity_name, entity_id=entity_id, features=features
        )

        # Trigger Before Hooks
        await self.hooks.trigger_before_retrieval(entity_name, entity_id, features)

        start_time = time.perf_counter()

        # 0. Time Travel Check
        timestamp = get_current_timestamp()
        if timestamp:
            log.info("time_travel_request", timestamp=timestamp.isoformat())
            try:
                # We assume features belong to the same entity/table structure in offline store logic
                # get_historical_features returns Dict[feature_name, value]
                if not hasattr(self.offline_store, "get_historical_features"):
                    log.warning(
                        "offline_store_no_history",
                        reason="Method get_historical_features missing",
                    )
                    return {}  # Or raise?

                historical = await self.offline_store.get_historical_features(
                    entity_name=entity_name,
                    entity_id=entity_id,
                    features=features,
                    timestamp=timestamp,
                )
                # Record lineage (best-effort): values are "as of" the replay timestamp.
                for feature_name in features:
                    if feature_name in historical:
                        record_feature_usage(
                            feature_name=feature_name,
                            entity_id=entity_id,
                            value=historical[feature_name],
                            timestamp=timestamp,
                            source="cache",
                        )
                return historical
            except Exception as e:
                log.error("time_travel_failed", error=str(e))
                return {}  # Fallback to empty (missing)

        # 1. Try Cache (Online Store)
        results: Dict[str, Any] = {}
        meta_results: Dict[str, Dict[str, Any]] = {}
        try:
            with FEATURE_LATENCY.labels(feature="all", step="cache").time():
                from fabra.store.online import OnlineStore

                use_meta = (
                    isinstance(self.online_store, OnlineStore)
                    and self.online_store.__class__.get_online_features_with_meta
                    is not OnlineStore.get_online_features_with_meta
                )

                if use_meta:
                    meta_results = (
                        await self.online_store.get_online_features_with_meta(
                            entity_name,
                            entity_id,
                            features,
                        )
                    )
                    results = {
                        k: v.get("value") for k, v in (meta_results or {}).items()
                    }
                else:
                    results = await self.online_store.get_online_features(
                        entity_name,
                        entity_id,
                        features,
                    )
        except Exception as e:
            # If online store fails completely (e.g. Redis down), treat all as missing
            log.warning("online_store_failed", error=str(e))
            results = {}
            meta_results = {}

        final_results = {}
        missing_features = []

        for feature_name in features:
            if feature_name in results:
                val = results[feature_name]
                as_of = None
                if feature_name in meta_results:
                    as_of_raw = meta_results[feature_name].get("as_of")
                    if isinstance(as_of_raw, str):
                        try:
                            as_of = datetime.fromisoformat(
                                as_of_raw.replace("Z", "+00:00")
                            )
                        except Exception:
                            as_of = None
                final_results[feature_name] = val
                FEATURE_REQUESTS.labels(feature=feature_name, status="hit").inc()
                # Record for lineage tracking (cache hit)
                record_feature_usage(
                    feature_name=feature_name,
                    entity_id=entity_id,
                    value=val,
                    timestamp=as_of,
                    source="cache",
                )
            else:
                missing_features.append(feature_name)
                FEATURE_REQUESTS.labels(feature=feature_name, status="miss").inc()

        if missing_features:
            log.info("cache_miss", missing_features=missing_features)

        # 2. Try Compute (On-Demand)
        for feature_name in missing_features:
            feature_def = self.registry.features.get(feature_name)
            if not feature_def:
                FEATURE_REQUESTS.labels(feature=feature_name, status="unknown").inc()
                continue

            try:
                # Execute the feature function
                with FEATURE_LATENCY.labels(
                    feature=feature_name, step="compute"
                ).time():
                    val = feature_def.func(entity_id)

                final_results[feature_name] = val
                FEATURE_REQUESTS.labels(
                    feature=feature_name, status="compute_success"
                ).inc()
                # Record for lineage tracking (computed)
                record_feature_usage(
                    feature_name=feature_name,
                    entity_id=entity_id,
                    value=val,
                    timestamp=datetime.now(timezone.utc),
                    source="compute",
                )

                # Optionally write back to cache?
                try:
                    await self.online_store.set_online_features(
                        entity_name, entity_id, {feature_name: val}
                    )
                except Exception as e:
                    log.debug(
                        "online_store_writeback_failed",
                        feature=feature_name,
                        error=str(e),
                    )

            except Exception as e:
                log.error("compute_failed", feature=feature_name, error=str(e))
                FEATURE_REQUESTS.labels(
                    feature=feature_name, status="compute_failure"
                ).inc()

                # 3. Try Default Value
                if feature_def.default_value is not None:
                    final_results[feature_name] = feature_def.default_value
                    FEATURE_REQUESTS.labels(
                        feature=feature_name, status="default"
                    ).inc()
                    # Record for lineage tracking (fallback)
                    record_feature_usage(
                        feature_name=feature_name,
                        entity_id=entity_id,
                        value=feature_def.default_value,
                        timestamp=datetime.now(timezone.utc),
                        source="fallback",
                    )
                    log.info(
                        "using_default",
                        feature=feature_name,
                        default_value=feature_def.default_value,
                    )
                else:
                    FEATURE_REQUESTS.labels(feature=feature_name, status="error").inc()
                    pass

        duration = time.perf_counter() - start_time
        log.info(
            "get_online_features_complete", duration=duration, found=len(final_results)
        )

        # Trigger After Hooks
        await self.hooks.trigger_after_retrieval(
            entity_name, entity_id, features, final_results
        )

        return final_results

    async def get_feature(self, feature_name: str, entity_id: str) -> Any:
        """
        Convenience method to get a single feature value.
        """
        feature_def = self.registry.features.get(feature_name)
        if not feature_def:
            import difflib

            matches = difflib.get_close_matches(
                feature_name, self.registry.features.keys(), n=3, cutoff=0.6
            )
            msg = f"Feature '{feature_name}' not found."
            if matches:
                msg += f" Did you mean: {', '.join(matches)}?"
            raise ValueError(msg)

        results = await self.get_online_features(
            feature_def.entity_name, entity_id, [feature_name]
        )
        return results.get(feature_name)

    def register_entity(
        self, name: str, id_column: str, description: Optional[str] = None
    ) -> Entity:
        entity = Entity(name=name, id_column=id_column, description=description)
        self.registry.register_entity(entity)
        return entity

    def register_feature(
        self,
        name: str,
        entity_name: str,
        func: Callable[..., Any],
        refresh: Optional[timedelta] = None,
        ttl: Optional[timedelta] = None,
        materialize: bool = False,
        description: Optional[str] = None,
        stale_tolerance: Optional[timedelta] = None,
        default_value: Any = None,
        sql: Optional[str] = None,
        trigger: Optional[str] = None,
    ) -> Feature:
        feature = Feature(
            name=name,
            entity_name=entity_name,
            func=func,
            refresh=refresh,
            ttl=ttl,
            materialize=materialize,
            description=description,
            stale_tolerance=stale_tolerance,
            default_value=default_value,
            sql=sql,
            trigger=trigger,
        )
        self.registry.register_feature(feature)
        return feature

    def register_retriever(self, retriever_or_func: Any) -> None:
        """Registers a retriever with the store."""
        if hasattr(retriever_or_func, "_fabra_retriever"):
            retriever = getattr(retriever_or_func, "_fabra_retriever")
        else:
            retriever = retriever_or_func

        self.retriever_registry.register(retriever)
        # Inject Store Reference for DAG Resolution
        setattr(retriever, "_fabra_store_ref", self)

        # Inject Cache Backend if available
        # We use online_store.redis for caching
        if hasattr(self.online_store, "redis"):
            # Use setattr to bypass frozen dataclass if frozen (it's not frozen by default)
            setattr(retriever, "_cache_backend", self.online_store.redis)
        elif hasattr(self.online_store, "client"):
            setattr(retriever, "_cache_backend", self.online_store.client)

    def register_index(self, index_obj: Index) -> None:
        """Registers an index definition."""
        self.index_registry.register(index_obj)

    async def index(
        self,
        index_name: str,
        entity_id: str,
        text: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Ingests text into the specified index.
        1. Retrieve Index definition.
        2. Chunk text.
        3. Embed chunks.
        4. Store in Vector Store.
        """
        idx = self.index_registry.get(index_name)
        if not idx:
            raise ValueError(f"Index '{index_name}' not found.")

        # 1. Chunk
        chunks = idx.chunk_text(text)
        logger.info(f"Indexing {len(chunks)} chunks for {index_name}:{entity_id}")

        # 2. Embed
        # We need an embedding provider. For MVP, we use OpenAIEmbedding default or configured on store?
        # Ideally store has it. If not, we instantiate default.
        if not hasattr(self, "embedding_provider"):
            # Lazy init default
            self.embedding_provider = OpenAIEmbedding()

        embeddings = await self.embedding_provider.embed_documents(chunks)

        # 3. Store
        # We need the OfflineStore (which is now PostgresOfflineStore with vector caps)
        if not self.offline_store:
            raise ValueError("Offline store not configured. Cannot save index.")

        # Check capability
        if not hasattr(self.offline_store, "add_documents"):
            raise ValueError(
                "Configured offline store does not support vector indexing."
            )

            # We assume dimension matches embedding model. OpenAI small is 1536.
            await self.offline_store.create_index_table(index_name, dimension=1536)

        if hasattr(self.offline_store, "add_documents"):
            await self.offline_store.add_documents(
                index_name=index_name,
                entity_id=entity_id,
                chunks=chunks,
                embeddings=embeddings,
                metadatas=[metadata or {}]
                * len(
                    chunks
                ),  # Original line, assuming chunk_metadatas was a typo in the instruction
            )
        else:
            logger.warning("Offline store does not support vector indexing.")

    async def search(
        self,
        index_name: str,
        query: str,
        top_k: int = 5,
        filter_timestamp: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """
        Performs semantic search on the specified index.
        1. Embed query.
        2. Search Offline Store.
        """
        if not hasattr(self, "embedding_provider"):
            from fabra.embeddings import OpenAIEmbedding

            self.embedding_provider = OpenAIEmbedding()

        # 1. Embed
        # Embed single query
        # Since embed_documents takes list, we wrap it.
        # But maybe provider has embed_query?
        # Assuming embed_documents for now as generic interface.
        embeddings = await self.embedding_provider.embed_documents([query])
        query_vec = embeddings[0]

        # 2. Search
        if not hasattr(self.offline_store, "search"):
            raise NotImplementedError(
                "Configured offline store does not support search."
            )

        results = await self.offline_store.search(
            index_name=index_name,
            query_embedding=query_vec,
            top_k=top_k,
            filter_timestamp=filter_timestamp,
        )
        return cast(List[Dict[str, Any]], results)

    def register_context(self, context_func: Any) -> None:
        """
        Registers a context assembly function and injects the cache backend.
        """
        if hasattr(context_func, "_is_context"):
            # Inject the online store as the cache backend
            setattr(context_func, "_cache_backend", self.online_store)
            logger.info(f"Registered Context: {context_func.__name__}")

    async def get_context_at(self, context_id: str) -> Optional[Any]:
        """
        Retrieve a historical context by ID for replay/audit.

        Args:
            context_id: The UUIDv7 identifier from a previous context assembly.

        Returns:
            The exact Context object that was assembled, or None if not found.
        """
        from fabra.context import Context
        from fabra.models import ContextLineage

        row = await self.offline_store.get_context(context_id)
        if row is None:
            return None

        # Reconstruct Context object from stored data
        lineage = None
        if row.get("lineage"):
            try:
                lineage = ContextLineage(**row["lineage"])
            except Exception as e:
                logger.warning(
                    "lineage_parse_failed", context_id=context_id, error=str(e)
                )

        return Context(
            id=row["context_id"],
            content=row["content"],
            lineage=lineage,
            meta=row.get("meta", {}),
            version=row.get("version", "v1"),
        )

    async def replay_context(
        self,
        context_id: str,
        timestamp: Optional[datetime] = None,
    ) -> Optional[Any]:
        """
        Replay a context assembly, optionally with time-travel to historical feature values.

        If timestamp is None, returns the stored context as-is.
        If timestamp is provided, re-executes the context function with feature values
        as they existed at that point in time.

        Args:
            context_id: The UUIDv7 identifier from a previous context assembly.
            timestamp: Optional historical timestamp to replay with time-traveled features.

        Returns:
            The replayed Context object, or None if not found or replay not possible.
        """

        # Get the original context
        stored = await self.get_context_at(context_id)
        if not stored:
            return None

        # If no timestamp, just return stored context
        if not timestamp:
            return stored

        # Check if we have enough info to replay
        if not stored.lineage:
            logger.warning(
                "replay_no_lineage",
                context_id=context_id,
                message="Cannot replay: no lineage information stored",
            )
            return stored

        context_name = stored.lineage.context_name
        context_args = stored.lineage.context_args

        if not context_name or not context_args:
            logger.warning(
                "replay_missing_info",
                context_id=context_id,
                message="Cannot replay: context_name or context_args not stored",
            )
            return stored

        # Find the registered context function
        if context_name not in self.registry.contexts:
            logger.warning(
                "replay_context_not_found",
                context_id=context_id,
                context_name=context_name,
                message="Cannot replay: context function not registered",
            )
            return stored

        context_func = self.registry.contexts[context_name]

        # Re-execute with time travel
        # The context function will use the timestamp for point-in-time feature retrieval
        try:
            from fabra.context import set_time_travel_context, clear_time_travel_context

            set_time_travel_context(timestamp)
            try:
                replayed = await context_func(**context_args)
                # Mark as replayed in meta
                if hasattr(replayed, "meta"):
                    replayed.meta["replayed_from"] = context_id
                    replayed.meta["replay_timestamp"] = timestamp.isoformat()
                return replayed
            finally:
                clear_time_travel_context()

        except Exception as e:
            logger.error(
                "replay_failed",
                context_id=context_id,
                error=str(e),
            )
            return stored

    async def list_contexts(
        self,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        limit: int = 100,
        name: Optional[str] = None,
        freshness_status: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        List contexts in a time range for debugging/audit.

        Args:
            start: Start of time range (inclusive)
            end: End of time range (inclusive)
            limit: Maximum number of contexts to return
            name: Filter by context name (from meta.name)
            freshness_status: Filter by status - "guaranteed" or "degraded"

        Returns:
            List of context summaries (without full content)
        """
        return await self.offline_store.list_contexts(
            start=start,
            end=end,
            limit=limit,
            name=name,
            freshness_status=freshness_status,
        )

    async def invalidate_contexts_for_feature(self, feature_id: str) -> int:
        """
        Invalidates all cached contexts that depend on the given feature_id.
        Returns number of contexts invalidated.
        """
        if not self.online_store:
            return 0

        dep_key = f"dependency:{feature_id}"
        count = 0
        try:
            # 1. Get dependent cache keys
            cache_keys = await self.online_store.smembers(dep_key)
            if cache_keys:
                keys_to_delete = [k for k in cache_keys]  # ensure str
                # 2. Delete contexts
                if keys_to_delete:
                    await self.online_store.delete(*keys_to_delete)
                    count = len(keys_to_delete)
                    logger.info(
                        "context_invalidation", feature_id=feature_id, count=count
                    )

            # 3. Clean up the dependency mapping
            await self.online_store.delete(dep_key)

        except Exception as e:
            logger.error("invalidation_failed", feature_id=feature_id, error=str(e))

        return count


def entity(
    store: FeatureStore, id_column: Optional[str] = None
) -> Callable[[Type[Any]], Type[Any]]:
    def decorator(cls: Type[Any]) -> Type[Any]:
        # If id_column is not provided, try to infer from type hints
        nonlocal id_column
        if id_column is None:
            # Simple inference: look for the first annotated field
            annotations = get_type_hints(cls)
            if annotations:
                id_column = next(iter(annotations))
            else:
                raise ValueError(f"Could not infer id_column for entity {cls.__name__}")

        # Python's class docstring is in __doc__, but sometimes it needs to be stripped
        doc = cls.__doc__.strip() if cls.__doc__ else None
        store.register_entity(name=cls.__name__, id_column=id_column, description=doc)
        setattr(cls, "_fabra_entity_name", cls.__name__)
        setattr(cls, "_fabra_store", store)  # Link store to entity
        return cls

    return decorator


def feature(
    entity: Type[Any],
    store: Optional[FeatureStore] = None,
    refresh: Optional[Union[str, timedelta]] = None,
    ttl: Optional[Union[str, timedelta]] = None,
    materialize: bool = False,
    stale_tolerance: Optional[Union[str, timedelta]] = None,
    default_value: Any = None,
    sql: Optional[str] = None,
    trigger: Optional[str] = None,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        # If store is not passed, we might need a way to find it.
        # For now, we'll assume the user passes it or we rely on a global context (which we want to avoid if possible).
        # Wait, the PRD example: @feature(entity=User, refresh="5m", materialize=True)
        # It doesn't pass 'store'.
        # This implies 'entity' (the class) might hold a reference to the store?
        # Or we rely on the fact that @entity registered it.

        # BUT, to register the feature, we need the store instance.
        # Option 1: Pass store to @feature.
        # Option 2: The Entity class knows its store.
        # Let's check if we can attach the store to the Entity class in @entity.

        nonlocal store
        if store is None:
            # Try to get store from the entity class
            store = getattr(entity, "_fabra_store", None)

        if store is None:
            raise ValueError(
                "FeatureStore instance must be provided or linked via the Entity."
            )

        # Parse refresh/ttl strings to timedelta
        parsed_refresh: Optional[timedelta] = refresh  # type: ignore
        if isinstance(refresh, str):
            parsed_refresh = _parse_timedelta(refresh)

        parsed_ttl: Optional[timedelta] = ttl  # type: ignore
        if isinstance(ttl, str):
            parsed_ttl = _parse_timedelta(ttl)

        parsed_stale_tolerance: Optional[timedelta] = stale_tolerance  # type: ignore
        if isinstance(stale_tolerance, str):
            parsed_stale_tolerance = _parse_timedelta(stale_tolerance)

        store.register_feature(
            name=func.__name__,
            entity_name=getattr(entity, "_fabra_entity_name"),
            func=func,
            refresh=parsed_refresh,
            ttl=parsed_ttl,
            materialize=materialize,
            description=func.__doc__,
            stale_tolerance=parsed_stale_tolerance,
            default_value=default_value,
            sql=sql,
            trigger=trigger,
        )
        return func

    return decorator


def _parse_timedelta(duration: str) -> timedelta:
    """Parses a duration string (e.g. '5m', '1h') into a timedelta."""
    import re

    # Simple regex for parsing: 5m, 1h, 30s, 1d
    match = re.match(r"^(\d+)([smhd])$", duration)
    if not match:
        raise ValueError(
            f"Invalid duration format: '{duration}'. Use format like '5m', '1h', '30s'."
        )

    value = int(match.group(1))
    unit = match.group(2)

    if unit == "s":
        return timedelta(seconds=value)
    elif unit == "m":
        return timedelta(minutes=value)
    elif unit == "h":
        return timedelta(hours=value)
    elif unit == "d":
        return timedelta(days=value)

    raise ValueError(f"Unknown time unit: {unit}")
