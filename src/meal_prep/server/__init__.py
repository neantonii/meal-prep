"""Self-hosted diary server (FastAPI).

Composes existing primitives — ``MealPrepLibrary.load()``,
``prepare_recipe()``, ``prepare_log_week()``, and the week-file storage API —
with serialization + HTTP + a static SPA. No new domain services.
"""

from meal_prep.server.app import create_app

__all__ = ["create_app"]
