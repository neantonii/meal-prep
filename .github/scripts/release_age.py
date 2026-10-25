"""Fail when a PR adds a package version published less than N days ago.

The list of added versions comes from GitHub's dependency graph (the same
comparison dependency-review-action uses), so no lock file is parsed here.
Only exact versions from lock files (``uv.lock``, ``package-lock.json``) are
checked; their release dates come from PyPI / the npm registry.

Environment: GITHUB_REPOSITORY, BASE_SHA, HEAD_SHA, optional GH_TOKEN and
MIN_AGE_DAYS (default 30).
"""

from __future__ import annotations

import datetime as dt
import json
import os
import urllib.parse
import urllib.request
from typing import Any

LOCK_FILES = ("uv.lock", "package-lock.json")


def fetch(url: str, token: str | None = None) -> Any:
    headers = {"Accept": "application/json", "User-Agent": "release-age-check"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers)) as r:
        return json.load(r)


def published(ecosystem: str, name: str, version: str) -> dt.datetime:
    if ecosystem == "pip":
        files = fetch(f"https://pypi.org/pypi/{name}/{version}/json")["urls"]
        stamp = min(f["upload_time_iso_8601"] for f in files)
    else:
        url = "https://registry.npmjs.org/" + urllib.parse.quote(name, safe="@")
        stamp = fetch(url)["time"][version]
    return dt.datetime.fromisoformat(stamp.replace("Z", "+00:00"))


def main() -> int:
    repo, base, head = (
        os.environ[k] for k in ("GITHUB_REPOSITORY", "BASE_SHA", "HEAD_SHA")
    )
    min_age = dt.timedelta(days=int(os.environ.get("MIN_AGE_DAYS", "30")))
    changes = fetch(
        f"https://api.github.com/repos/{repo}/dependency-graph/compare/{base}...{head}",
        os.environ.get("GH_TOKEN"),
    )
    added = sorted(
        (c["ecosystem"], c["name"], c["version"])
        for c in changes
        if c["change_type"] == "added"
        and c["ecosystem"] in ("pip", "npm")
        and c["manifest"].endswith(LOCK_FILES)
    )
    now = dt.datetime.now(dt.UTC)
    failed = False
    for ecosystem, name, version in added:
        try:
            age = now - published(ecosystem, name, version)
        except Exception as e:  # unknown version, non-registry source, network
            print(f"::error::{ecosystem} {name}=={version}: no release date ({e})")
            failed = True
            continue
        ok = age >= min_age
        failed |= not ok
        prefix = "ok " if ok else "::error::"
        print(f"{prefix}{ecosystem} {name}=={version}: published {age.days} days ago")
    print(f"{len(added)} added versions checked, minimum age {min_age.days} days")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
