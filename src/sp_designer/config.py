"""Paths and settings.

Public reference data ships with the package (``sp_designer/data``).
User data (manual overrides, own materials, fetched prices) lives in a user
directory outside the repository, because it may contain confidential values.
"""

from __future__ import annotations

import os
from pathlib import Path

PACKAGE_DATA_DIR = Path(__file__).parent / "data"


def user_data_dir() -> Path:
    """Directory for user data; override with the ``SPD_DATA_DIR`` environment variable."""
    path = Path(os.environ.get("SPD_DATA_DIR", Path.home() / ".sp-designer"))
    path.mkdir(parents=True, exist_ok=True)
    return path
