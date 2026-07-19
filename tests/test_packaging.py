"""Tests for the installable ``aet`` package skeleton."""

import importlib.metadata

import aet


def test_aet_package_is_importable():
    """The installed editable package can be imported."""
    assert aet is not None


def test_aet_version_is_declared():
    """`aet.__version__` matches the package metadata."""
    assert hasattr(aet, "__version__")
    assert aet.__version__ == "0.1.0"


def test_aet_console_entry_point_declared():
    """pyproject.toml declares a ``aet`` console script entry point."""
    eps = importlib.metadata.entry_points(group="console_scripts")
    aet_eps = [ep for ep in eps if ep.name == "aet"]
    assert len(aet_eps) == 1
    assert aet_eps[0].value.startswith("aet.")
