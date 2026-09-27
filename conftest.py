"""Test bootstrap: make the ``src``-layout package importable without installing it.

Pytest imports test modules before ``sys.path`` is otherwise arranged, so this
single hook at the repository root is enough for every test under ``tests/`` to
``import meal_prep``.
"""

from __future__ import annotations

import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))
