from importlib.metadata import version

from fabra import __version__


def test_version() -> None:
    assert __version__ == version("fabra-ai")
