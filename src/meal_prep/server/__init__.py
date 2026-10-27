"""Self-hosted diary server (FastAPI).

Composes existing primitives (``load_library()``, the diary services and the
week-file storage API) with serialization + HTTP + a static SPA. No new
domain services.
"""

from meal_prep.server.app import create_app

__all__ = ["create_app"]
