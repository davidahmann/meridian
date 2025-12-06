import streamlit as st
import pandas as pd
import sys
import os
import importlib.util
from meridian.core import FeatureStore
from typing import Optional, List

st.set_page_config(page_title="Meridian UI", page_icon="🧭", layout="wide")


def load_feature_store(file_path: str) -> FeatureStore:
    """Load the FeatureStore from the given file path."""
    spec = importlib.util.spec_from_file_location("features", file_path)
    if not spec or not spec.loader:
        st.error(f"Could not load file: {file_path}")
        st.stop()

    module = importlib.util.module_from_spec(spec)
    sys.modules["features"] = module
    spec.loader.exec_module(module)

    # Find the FeatureStore instance
    for attr_name in dir(module):
        attr = getattr(module, attr_name)
        if isinstance(attr, FeatureStore):
            return attr

    st.error("No FeatureStore instance found in the provided file.")
    st.stop()


def main(args: Optional[List[str]] = None) -> None:
    st.title("🧭 Meridian Feature Store")

    if args is None:
        args = sys.argv

    # args will look like: ['streamlit', 'run', 'src/meridian/ui.py', '--', 'path/to/features.py']
    # Or if called directly: ['ui.py', 'features.py']

    if len(args) < 2:
        st.warning("Please provide the path to your feature definition file.")
        st.info("Usage: meridian ui <path_to_features.py>")
        return

    feature_file = args[1]

    if not os.path.exists(feature_file):
        st.error(f"File not found: {feature_file}")
        return

    store = load_feature_store(feature_file)

    # Sidebar
    st.sidebar.header("Configuration")
    st.sidebar.text(f"Loaded: {os.path.basename(feature_file)}")

    entities = list(store.registry.entities.keys())
    if not entities:
        st.warning("No entities found in the Feature Store.")
        return

    # Visual Eureka: Dependency Graph
    with st.expander("🗺️ Feature System Map", expanded=True):
        import streamlit.components.v1 as components

        # Build Mermaid Graph
        graph = ["graph LR"]
        graph.append(
            "    classDef entity fill:#e1f5fe,stroke:#01579b,stroke-width:2px;"
        )
        graph.append(
            "    classDef feature fill:#fff3e0,stroke:#ff6f00,stroke-width:1px;"
        )
        graph.append("    classDef store fill:#f3e5f5,stroke:#7b1fa2,stroke-width:2px;")

        # Online Store Node
        os_type = store.online_store.__class__.__name__
        graph.append(f"    OS[({os_type})]")
        graph.append("    class OS store;")

        for name, ent in store.registry.entities.items():
            safe_name = name.replace(" ", "_")
            ent_id = f"ENT_{safe_name}"
            graph.append(f"    subgraph {safe_name}")
            graph.append(f"        {ent_id}[{name}]")
            graph.append(f"        class {ent_id} entity;")

            # Find features for this entity
            feats = store.registry.get_features_for_entity(name)
            for f in feats:
                safe_feat = f.name.replace(" ", "_")
                feat_node = f"FEAT_{safe_feat}"
                graph.append(f"        {feat_node}({f.name})")
                graph.append(f"        class {feat_node} feature;")
                graph.append(f"        {ent_id} --> {feat_node}")

                if f.materialize:
                    graph.append(f"        {feat_node} -. Materialize .-> OS")

            graph.append("    end")

        mermaid_code = "\n".join(graph)

        html = f"""
        <script type="module">
        import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs';
        mermaid.initialize({{ startOnLoad: true, theme: 'default' }});
        </script>
        <div class="mermaid">
        {mermaid_code}
        </div>
        """
        components.html(html, height=300, scrolling=True)

    selected_entity_name = st.sidebar.selectbox("Select Entity", entities)
    entity = store.registry.entities[selected_entity_name]

    # Main Content
    st.header(f"Entity: {selected_entity_name}")
    st.markdown(f"**ID Column:** `{entity.id_column}`")
    if entity.description:
        st.markdown(f"_{entity.description}_")

    # Input ID
    entity_id = st.text_input(f"Enter {entity.id_column}", value="u1")

    if st.button("Fetch Features", type="primary"):
        with st.spinner("Fetching features..."):
            # Get all features for this entity
            features = store.registry.get_features_for_entity(selected_entity_name)
            feature_names = [f.name for f in features]

            if not feature_names:
                st.warning("No features defined for this entity.")
            else:
                # Fetch values
                import asyncio

                values = asyncio.run(
                    store.get_online_features(
                        entity_name=selected_entity_name,
                        entity_id=entity_id,
                        features=feature_names,
                    )
                )

                # Display as dataframe
                df = pd.DataFrame([values])
                st.dataframe(df, use_container_width=True)

                # Display detailed view
                st.subheader("Feature Details")
                for feat in features:
                    with st.expander(f"{feat.name}"):
                        st.write(f"**Refresh:** {feat.refresh}")
                        st.write(f"**TTL:** {feat.ttl}")
                        st.write(f"**Materialize:** {feat.materialize}")
                        st.code(f"Value: {values.get(feat.name)}")


if __name__ == "__main__":
    main()
