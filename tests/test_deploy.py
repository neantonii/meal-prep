"""Guards for the single-source toolchain: the Dockerfile owns all versions."""

from __future__ import annotations

import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]


def test_dockerfile_images_are_pinned_by_digest():
    dockerfile = (_ROOT / "Dockerfile").read_text(encoding="utf-8")
    images = re.findall(r"^FROM (\S+)", dockerfile, flags=re.MULTILINE)
    external = [image for image in images if "/" in image or ":" in image]
    assert external
    unpinned = [image for image in external if "@sha256:" not in image]
    assert not unpinned, f"images must be pinned by digest: {unpinned}"


def test_uv_image_comes_from_docker_hub():
    """Astral publishes the same uv image on GHCR and Docker Hub, but only
    Docker Hub gives Dependabot a push date, so only there does its cooldown
    apply (on ghcr.io every update arrives without the wait)."""
    dockerfile = (_ROOT / "Dockerfile").read_text(encoding="utf-8")
    uv = re.findall(r"^FROM (\S*/uv[:@]\S*)", dockerfile, flags=re.MULTILINE)
    assert uv, "no uv image in the Dockerfile"
    assert all(image.startswith("astral/uv:") for image in uv), (
        f"use Docker Hub's astral/uv, not {uv}"
    )


def test_workflows_install_no_toolchains():
    """CI runs through the Dockerfile; workflows must not pin their own
    Python/Node/uv (a second copy Dependabot can't keep in step)."""
    offenders = [
        f"{path.name}: {action}"
        for path in sorted((_ROOT / ".github" / "workflows").glob("*.yml"))
        for action in re.findall(
            r"uses:\s*(\S*setup-(?:python|node|uv)\S*)", path.read_text("utf-8")
        )
    ]
    assert not offenders, f"use the Dockerfile toolchain instead: {offenders}"


def test_compose_example_uses_the_host_time_zone():
    """The server's "today" (Plan vs Log) is the container's local date; with
    no zone it is UTC and turns over hours early in the evening."""
    compose = (_ROOT / "compose.example.yml").read_text(encoding="utf-8")
    assert re.search(
        r"^\s*- /etc/localtime:/etc/localtime:ro$", compose, re.MULTILINE
    ), "mount the host's /etc/localtime read-only"
