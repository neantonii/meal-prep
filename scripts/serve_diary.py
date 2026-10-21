"""Serve the diary web UI.

Usage (run from the repo root):
    python scripts/serve_diary.py --data-dir data --recipes-dir recipes --diary-dir diary
"""

from __future__ import annotations

import argparse
from pathlib import Path

import uvicorn

from meal_prep.server import create_app


def main() -> None:
    parser = argparse.ArgumentParser(description="Serve the meal-prep diary UI.")
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--recipes-dir", type=Path, required=True)
    parser.add_argument("--diary-dir", type=Path, required=True)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    app = create_app(args.data_dir, args.recipes_dir, args.diary_dir)
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
