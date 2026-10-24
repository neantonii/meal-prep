"""Serve the diary web UI.

Usage (run from the repo root):
    python scripts/serve_diary.py --data-dir data --recipes-dir recipes --diary-dir diary
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

import uvicorn

from meal_prep.server import create_app
from meal_prep.server.logging import configure_logging

logger = logging.getLogger("meal_prep.server")


def main() -> None:
    parser = argparse.ArgumentParser(description="Serve the meal-prep diary UI.")
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--recipes-dir", type=Path, required=True)
    parser.add_argument("--diary-dir", type=Path, required=True)
    parser.add_argument("--log-dir", type=Path, default=Path("logs"))
    parser.add_argument("--log-level", default="INFO")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    log_file = configure_logging(args.log_dir, args.log_level)
    app = create_app(args.data_dir, args.recipes_dir, args.diary_dir)
    logger.info(
        "serving data=%s recipes=%s diary=%s log=%s",
        args.data_dir,
        args.recipes_dir,
        args.diary_dir,
        log_file,
    )
    uvicorn.run(app, host=args.host, port=args.port, log_level=args.log_level.lower())


if __name__ == "__main__":
    main()
