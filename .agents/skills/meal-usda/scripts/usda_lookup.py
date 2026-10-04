"""Pull raw FoodData Central records for agent-side reasoning.

Thin wrapper over the FDC REST API — it fetches data only. It performs no
nutrient mapping, no DTO shaping, no plausibility checks: the agent picks
the match and reasons about the nutrients itself.

Usage:
    python usda_lookup.py search <query> [--limit N] [--data-types ...]
    python usda_lookup.py fetch <fdcId> [--out PATH]

Reads the API key from the USDA_KEY environment variable. Run from the
repo root so relative --out paths land under .agent_tmp/ as usual.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

BASE = "https://api.nal.usda.gov/fdc/v1"
TIMEOUT = 30


def _key() -> str:
    key = os.environ.get("USDA_KEY")
    if not key:
        raise RuntimeError("USDA_KEY is not set in the environment")
    return key


def _read_response(resp: urllib.request.addinfourl) -> dict:
    return json.load(resp)


def search(query: str, limit: int, data_types: list[str]) -> dict:
    """POST /foods/search; return totalHits plus identity fields per hit."""
    payload: dict[str, object] = {"query": query, "pageSize": limit}
    if data_types:
        payload["dataType"] = data_types
    req = urllib.request.Request(
        f"{BASE}/foods/search?api_key={_key()}",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        body = _read_response(resp)
    candidates = [
        {
            "fdcId": food.get("fdcId"),
            "description": food.get("description"),
            "dataType": food.get("dataType"),
            "brandOwner": food.get("brandOwner"),
        }
        for food in body.get("foods", [])
    ]
    return {"totalHits": body.get("totalHits"), "candidates": candidates}


def fetch(fdc_id: int) -> dict:
    """GET /food/{fdcId}; return the full record verbatim."""
    params = urllib.parse.urlencode({"api_key": _key()})
    with urllib.request.urlopen(
        f"{BASE}/food/{fdc_id}?{params}", timeout=TIMEOUT
    ) as resp:
        return _read_response(resp)


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch raw FDC records.")
    sub = parser.add_subparsers(dest="command", required=True)

    p_search = sub.add_parser("search", help="Search foods by keyword.")
    p_search.add_argument("query", help="Free-text query, e.g. 'chicken breast raw'")
    p_search.add_argument("--limit", type=int, default=10)
    p_search.add_argument(
        "--data-types",
        nargs="*",
        default=["Foundation", "SR Legacy"],
        help="FDC data types to include; pass empty to search all types.",
    )

    p_fetch = sub.add_parser("fetch", help="Fetch one record by FDC ID.")
    p_fetch.add_argument("fdc_id", type=int)
    p_fetch.add_argument("--out", help="Write the record JSON here instead of stdout.")

    args = parser.parse_args()
    try:
        if args.command == "search":
            print(json.dumps(search(args.query, args.limit, args.data_types), indent=2))
        else:
            record = fetch(args.fdc_id)
            text = json.dumps(record, indent=2)
            if args.out:
                with open(args.out, "w", encoding="utf-8") as f:
                    f.write(text + "\n")
                print(f"record {args.fdc_id} written to {args.out}")
            else:
                print(text)
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")[:500]
        print(f"usda_lookup: HTTP {e.code}: {detail}", file=sys.stderr)
        return 1
    except RuntimeError as e:
        print(f"usda_lookup: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
