"""Look up a store product's label data with Gemini, from what the user dropped.

The user's own input goes to Gemini as-is: screenshots of the product page
(title, pack size, price) and/or a typed query. Gemini reads the product off
that input, searches for its Nutrition Facts on brand or retailer pages and
reads them with its URL tool. Grocery sites block scripts, but not Google's
fetchers, which is why the lookup goes through Gemini.

Usage (run from the repo root):
    python .agents/skills/meal-ingredient/scripts/fetch_product.py \\
        [--query "compliments croutons cheese garlic"] [--store voila.ca] \\
        [--out .agent_tmp/fetched-<slug>.json] [screenshot ...]

Prints (and with ``--out`` saves) one JSON object:
    from_input  brand, product, pack size and prices as the input shows them
    nutrition   serving line verbatim plus the nutrients, from opened pages
    retrieval   Gemini's status for every URL it tried to open
    zeros       nutrients reported as 0: check each against USDA (Gemini
                turns a blank panel row into 0 even when told not to)
    missing     nutrients not found: fill from USDA as for a label photo

Exits 3 when no page was retrieved or no nutrition came back; the label
photo flow takes over then. The API key comes from the environment's network
secret (the proxy adds ``x-goog-api-key``); outside such an environment, set
``GEMINI_API_KEY``.
"""

from __future__ import annotations

import argparse
import base64
import json
import mimetypes
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

API = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
DEFAULT_MODEL = "gemini-4-hydrogen"
NUTRIENTS = (
    "calories_kcal",
    "fat_g",
    "saturated_fat_g",
    "carbs_g",
    "fiber_g",
    "sugars_g",
    "protein_g",
    "sodium_mg",
    "potassium_mg",
)
NO_DATA = 3

PROMPT = """The user shops at {store} and dropped the attached input to name a
product they buy.{query}

1. From the user's input itself: brand, product title, pack size, and every
   price shown (current, regular, sale dates) exactly as printed. Null where
   the input does not show it; never look prices up.
2. Search for this exact product's official Nutrition Facts (the brand's own
   site or a grocery retailer's product page), open the pages and read them.

Nutrition values must be printed on a page you actually opened: no outside
knowledge, no estimates. A panel row with no amount next to it is null, not
zero; report 0 only where the page prints "0 g" or "0 mg". Reply with ONLY a
JSON object, no fences:
{{"from_input": {{"brand": str|null, "product": str|null,
  "pack_size": str|null, "price_current": str|null, "price_regular": str|null,
  "sale_note": str|null}},
 "nutrition": {{"source_title": str|null, "serving_text": str|null (verbatim),
  {fields}}}}}"""


def _parts(images: list[Path], prompt: str) -> list[dict[str, object]]:
    parts: list[dict[str, object]] = []
    for image in images:
        mime = mimetypes.guess_type(image.name)[0] or "image/png"
        data = base64.b64encode(image.read_bytes()).decode()
        parts.append({"inline_data": {"mime_type": mime, "data": data}})
    parts.append({"text": prompt})
    return parts


def _call(model: str, parts: list[dict[str, object]]) -> dict[str, object]:
    body = {
        "contents": [{"role": "user", "parts": parts}],
        "tools": [{"google_search": {}}, {"url_context": {}}],
        "generationConfig": {"temperature": 0},
    }
    headers = {"Content-Type": "application/json"}
    if key := os.environ.get("GEMINI_API_KEY"):
        headers["x-goog-api-key"] = key
    request = urllib.request.Request(
        API.format(model=model), data=json.dumps(body).encode(), headers=headers
    )
    for attempt in (1, 2):
        try:
            with urllib.request.urlopen(request, timeout=180) as response:
                result: dict[str, object] = json.load(response)
                return result
        except urllib.error.HTTPError as e:
            if e.code < 500 or attempt == 2:
                raise
        except urllib.error.URLError:
            if attempt == 2:
                raise
        time.sleep(5)
    raise AssertionError("unreachable")


def _json_object(text: str) -> dict[str, object]:
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end < start:
        raise ValueError(f"no JSON object in the reply: {text[:200]!r}")
    parsed: dict[str, object] = json.loads(text[start : end + 1])
    return parsed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("images", nargs="*", type=Path, help="screenshots")
    parser.add_argument("--query", default="", help="what the user typed")
    parser.add_argument("--store", default="voila.ca (Sobeys' online grocery)")
    parser.add_argument(
        "--model", default=os.environ.get("MEAL_PREP_FETCH_MODEL", DEFAULT_MODEL)
    )
    parser.add_argument("--out", type=Path, help="also save the JSON here")
    args = parser.parse_args()
    if not args.images and not args.query:
        parser.error("give at least one screenshot or --query")

    query = f'\nThe user typed: "{args.query}".' if args.query else ""
    fields = ", ".join(f'"{n}": num|null' for n in NUTRIENTS)
    prompt = PROMPT.format(store=args.store, query=query, fields=fields)
    response = _call(args.model, _parts(args.images, prompt))

    candidates = response.get("candidates")
    candidate = candidates[0] if isinstance(candidates, list) and candidates else {}
    meta = candidate.get("urlContextMetadata", {}).get("urlMetadata", [])
    retrieval = [m.get("urlRetrievalStatus", "") for m in meta]
    text = "".join(
        p.get("text", "") for p in candidate.get("content", {}).get("parts", [])
    )
    result = _json_object(text)
    nutrition = result.get("nutrition")
    nutrition = nutrition if isinstance(nutrition, dict) else {}
    result["model"] = args.model
    result["retrieval"] = retrieval
    result["zeros"] = [n for n in NUTRIENTS if nutrition.get(n) == 0]
    result["missing"] = [n for n in NUTRIENTS if nutrition.get(n) is None]

    output = json.dumps(result, indent=2, ensure_ascii=False)
    print(output)
    if args.out:
        args.out.write_text(output + "\n", encoding="utf-8")

    if "URL_RETRIEVAL_STATUS_SUCCESS" not in retrieval:
        print("no page was retrieved: use the label photo flow", file=sys.stderr)
        return NO_DATA
    if len(result["missing"]) == len(NUTRIENTS):
        print("no nutrition found: use the label photo flow", file=sys.stderr)
        return NO_DATA
    return 0


if __name__ == "__main__":
    sys.exit(main())
