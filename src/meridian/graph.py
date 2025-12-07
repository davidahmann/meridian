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
        2. Fetch deps from Store (Mocked/Stubbed for now).
        3. Render.
        """
        deps = self.parse_dependencies(template)
        if not deps:
            return template

        logger.debug("dag_resolving", entity_id=entity_id, dependencies=deps)

        # In a real implementation hooked to FeatureStore:
        # values = await self.store.get_features(list(deps), entity_id)
        # For now, we rely on a simulated fetch method for partial testing
        values = await self._fetch_features_stub(list(deps), entity_id)

        return await self.resolve(template, values)

    async def _fetch_features_stub(
        self, feature_names: List[str], entity_id: str
    ) -> Dict[str, Any]:
        """
        Placeholder for FeatureStore interaction.
        Should be replaced or mocked in integration.
        """
        if self.store and hasattr(self.store, "get_online_features"):
            # Future integration point
            # return await self.store.get_online_features(feature_names, entity_id)
            pass

        # Return dummy data for purely unit-testing this class without store
        return {name: f"mock_value_for_{name}" for name in feature_names}
