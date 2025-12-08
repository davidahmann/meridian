import pytest
from unittest.mock import MagicMock, patch
from meridian.ui import load_feature_store


def test_load_feature_store_fail() -> None:
    with patch("streamlit.error") as mock_err, patch(
        "streamlit.stop", side_effect=Exception("Stopped")
    ) as mock_stop, patch("importlib.util.spec_from_file_location", return_value=None):
        with pytest.raises(Exception, match="Stopped"):
            load_feature_store("non_existent_file.py")
        mock_err.assert_called()
        mock_stop.assert_called()


def test_load_feature_store_success() -> None:
    # We mock module loading to return a module with a store
    with patch("importlib.util.spec_from_file_location") as mock_spec:
        mock_mod = MagicMock()
        mock_spec.return_value.loader.exec_module.return_value = None

        # Use a real dummy class for isinstance check
        class DummyFeatureStore:
            pass

        with patch("meridian.ui.FeatureStore", DummyFeatureStore):
            # The object on the module:
            mock_store_instance = DummyFeatureStore()
            mock_mod.store = mock_store_instance

            # We configure module_from_spec
            with patch("importlib.util.module_from_spec", return_value=mock_mod):
                from typing import Any, cast

                # dir(module)
                mock_mod.__dir__ = MagicMock(return_value=["store"])  # type: ignore

                store = load_feature_store("features.py")
                # Fix Mypy overlap error
                assert cast(Any, store) is mock_store_instance
