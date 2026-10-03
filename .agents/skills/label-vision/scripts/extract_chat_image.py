"""Extract the latest user-attached chat image to disk.

Chat attachments are embedded base64 in the conversation event history,
not files on disk. This script discovers the current conversation,
searches newest-first for the latest user message with an image block,
and decodes the first image to <out-path>.<fmt> (extension from the
data-URL MIME type).

Usage:
    python extract_chat_image.py <out-path-without-extension>

Prints the saved path on success; exits nonzero with a plain error when
no image is found (no photo dropped yet, key file missing, API error).
"""

from __future__ import annotations

import base64
import json
import os
import re
import sys
import urllib.request
from pathlib import Path

SERVER = "http://127.0.0.1:18000"
KEY_FILE = Path.home() / ".openhands" / "agent-canvas" / "api-key.txt"


def discover_conversation_id(convs_path: Path) -> str:
    """Newest conversation dir; names are dashless, reinsert at 8-4-4-4-12."""
    entries = sorted(
        (p for p in convs_path.iterdir() if p.is_dir()),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not entries:
        raise RuntimeError(f"no conversations under {convs_path}")
    dashless = entries[0].name
    m = re.fullmatch(r"(.{8})(.{4})(.{4})(.{4})(.{12})", dashless)
    if not m:
        raise RuntimeError(f"unexpected conversation dir name: {dashless}")
    return "-".join(m.groups())


def latest_user_image(conversation_id: str, session_key: str) -> tuple[str, bytes]:
    """Newest-first user event search; return (fmt, raw bytes)."""
    url = (
        f"{SERVER}/api/conversations/{conversation_id}/events/search"
        "?limit=5&sort_order=TIMESTAMP_DESC&source=user"
    )
    req = urllib.request.Request(url, headers={"X-Session-API-Key": session_key})
    with urllib.request.urlopen(req, timeout=30) as resp:
        payload = json.load(resp)
    events = payload.get("items", payload.get("events", []))
    for event in events:
        content = event.get("llm_message", {}).get("content", [])
        for block in content:
            if block.get("type") != "image":
                continue
            for data_url in block.get("image_urls", []):
                header, _, b64 = data_url.partition(",")
                fmt = header.split(";")[0].split("/")[-1]
                return fmt, base64.b64decode(b64)
    raise RuntimeError("no user-attached image in the 5 latest user messages")


def main() -> int:
    if len(sys.argv) != 2:
        print(
            "usage: extract_chat_image.py <out-path-without-extension>", file=sys.stderr
        )
        return 2
    try:
        convs = os.environ.get("OH_CONVERSATIONS_PATH")
        convs_path = (
            Path(convs)
            if convs
            else (Path.home() / ".openhands" / "agent-canvas" / "conversations")
        )
        conversation_id = discover_conversation_id(convs_path)
        session_key = KEY_FILE.read_text(encoding="utf-8").strip()
        fmt, raw = latest_user_image(conversation_id, session_key)
        dest = Path(sys.argv[1]).with_suffix(f".{fmt}")
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(raw)
    except Exception as e:
        print(f"extract_chat_image: {e}", file=sys.stderr)
        return 1
    print(f"{dest} ({len(raw)} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
