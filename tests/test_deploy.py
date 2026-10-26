"""Keep the container image's runtimes in step with the rest of the repo."""

from __future__ import annotations

import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]


def test_dockerfile_node_major_matches_nvmrc():
    nvmrc = (_ROOT / "ui" / ".nvmrc").read_text(encoding="utf-8").strip()
    dockerfile = (_ROOT / "Dockerfile").read_text(encoding="utf-8")
    match = re.search(r"^FROM node:(\d+)-", dockerfile, flags=re.MULTILINE)
    assert match is not None, "Dockerfile has no node build stage"
    assert match.group(1) == nvmrc, (
        f"Dockerfile builds the UI on Node {match.group(1)}, ui/.nvmrc says {nvmrc}"
    )


def test_dockerfile_base_images_are_pinned_by_digest():
    dockerfile = (_ROOT / "Dockerfile").read_text(encoding="utf-8")
    images = re.findall(r"^FROM (\S+)", dockerfile, flags=re.MULTILINE)
    assert images
    unpinned = [image for image in images if "@sha256:" not in image]
    assert not unpinned, f"base images must be pinned by digest: {unpinned}"


def test_dockerfile_python_matches_ci():
    dockerfile = (_ROOT / "Dockerfile").read_text(encoding="utf-8")
    ci = (_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    image = re.search(r"^FROM python:(\d+\.\d+)-", dockerfile, flags=re.MULTILINE)
    workflow = re.search(r'python-version: "(\d+\.\d+)"', ci)
    assert image is not None and workflow is not None
    assert image.group(1) == workflow.group(1), (
        f"Dockerfile runs Python {image.group(1)}, CI tests on {workflow.group(1)}"
    )


def test_dockerfile_uv_matches_ci():
    dockerfile = (_ROOT / "Dockerfile").read_text(encoding="utf-8")
    ci = (_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    image = re.search(
        r"^FROM ghcr\.io/astral-sh/uv:([\d.]+)@", dockerfile, re.MULTILINE
    )
    workflow = re.search(r"setup-uv@\S+\s+with:\s+version: \"([\d.]+)\"", ci)
    assert image is not None and workflow is not None
    assert image.group(1) == workflow.group(1), (
        f"Dockerfile uses uv {image.group(1)}, CI uses {workflow.group(1)}"
    )
