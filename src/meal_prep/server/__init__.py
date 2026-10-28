"""Self-hosted diary server (FastAPI).

Composes existing primitives (``load_library()``, the diary and prep-session
services and the file storage API) with serialization + HTTP + a static SPA.
No domain rules of its own: they live in ``meal_prep.services.prep``.
"""

from meal_prep.server.app import create_app

__all__ = ["create_app"]
