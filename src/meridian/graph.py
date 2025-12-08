from __future__ import annotations
import re
from typing import Set, Dict, Any, List
import structlog

logger = structlog.get_logger()


class DependencyResolver:
    """
    Resolves implicit dependencies in template strings.
    Example: "Hello {user.first_name}" -> depends on feature "user.first_name".
    """

    def __init__(self, store: Any = None):
        # Store passed in dynamically to avoid circular imports
        self.store = store

    def parse_dependencies(self, template: str) -> Set[str]:
        """
        Extracts variable names from a format string.
        Matches {var_name} or {entity.var_name}.
        """
        # Regex to find text inside curly braces, non-nested
        matches = re.findall(r"\{([\w\.]+)\}", template)
        return set(matches)

    async def resolve(self, template: str, context_data: Dict[str, Any]) -> str:
        """
        Renders the template using provided context data.
        Does NOT fetch from store yet (Stage 1).
        """
        try:
            return template.format(**context_data)
        except KeyError as e:
            logger.warning("dependency_missing", missing_key=str(e), template=template)
            # Return original string or partial?
            # Ideally verify strictness. For now, let it raise or handle gracefully.
            raise e

    async def execute_dag(self, template: str, entity_id: str) -> str:
        """
        Orchestrates the fetch -> render flow.
        1. Parse deps.
        2. Fetch deps from Store.
        3. Render.
        """
        deps = self.parse_dependencies(template)
        if not deps:
            return template

        logger.debug("dag_resolving", entity_id=entity_id, dependencies=deps)

        if not self.store:
            logger.warning(
                "dag_resolution_failed", reason="No store attached to Resolver"
            )
            # Fail safe: return template unresolved or raise?
            # For now, return as-is or partial. Let's return as-is to let downstream fail or handle.
            return template

        # Fetch features
        # Note: We assume all features belong to the same entity_id for now (V1 Simplification)
        # If deps encompass multiple entities, we'd need complex routing.
        # "FR-3.2 Implicit DAG Resolution" -> likely single entity context.
        try:
            # Group features by entity_name
            feature_map: Dict[str, List[str]] = {}
            resolved_values: Dict[str, Any] = {}

            # Inspect registry to map features to entities
            if not getattr(self.store, "registry", None):
                logger.warning("dag_registry_missing", reason="Store has no registry")
                return template

            for feat_name in deps:
                feat_def = self.store.registry.features.get(feat_name)
                if not feat_def:
                    logger.warning("feature_not_found_in_registry", feature=feat_name)
                    continue

                e_name = feat_def.entity_name
                if e_name not in feature_map:
                    feature_map[e_name] = []
                feature_map[e_name].append(feat_name)

            # Fetch for each entity
            for e_name, feats in feature_map.items():
                res = await self.store.get_online_features(e_name, entity_id, feats)
                resolved_values.update(res)

            # Fallback if self.store doesn't support registry lookups?
            # We assume it's the `FeatureStore` class from `core.py`.
        except Exception as e:
            logger.error("dag_fetch_error", error=str(e))
            return template

        try:
            return await self.resolve(template, resolved_values)
        except Exception:
            return template
