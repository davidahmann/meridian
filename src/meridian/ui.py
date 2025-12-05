import streamlit as st
import pandas as pd
import sys
import os
import importlib.util
from meridian.core import FeatureStore

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


def main() -> None:
    st.title("🧭 Meridian Feature Store")

    # Get file path from command line args (passed via st.session_state or env var if needed,
    # but for simplicity we'll assume it's passed as a command line arg to the script)
    # Streamlit args handling is a bit tricky, so we'll look at sys.argv
    # sys.argv will look like: ['streamlit', 'run', 'src/meridian/ui.py', '--', 'path/to/features.py']

    if len(sys.argv) < 2:
        st.warning("Please provide the path to your feature definition file.")
        st.info("Usage: meridian ui <path_to_features.py>")
        return

    feature_file = sys.argv[1]

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
                values = store.get_online_features(
                    entity_name=selected_entity_name,
                    entity_id=entity_id,
                    features=feature_names,
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
