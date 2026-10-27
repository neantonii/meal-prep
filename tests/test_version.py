"""The VERSION file holds MAJOR.MINOR; CI appends its run number as PATCH."""

from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def test_version_file_is_major_minor():
    major, minor = (REPO / "VERSION").read_text().strip().split(".")
    assert major.isdigit()
    assert minor.isdigit()
