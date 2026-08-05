"""Shared fixture for the app-compile tests."""

import tempfile

from gws_core import File


def create_empty_config_file() -> File:
    """Create a File resource containing an empty JSON object."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tmp:
        tmp.write("{}")
        tmp_path = tmp.name
    return File(tmp_path)
