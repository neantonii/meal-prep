"""Shared token normalization for DTO shape validation.

These are the *only* token cleanups permitted anywhere: case-folding and
whitespace trimming, plus the canonical identifier convention. No inference,
no plural stripping, no alias resolution — those concerns belong to services.
"""

import re

_SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def normalize_slug(value: str, *, field: str) -> str:
    """Return ``value`` trimmed and lowercased, or raise if not a kebab-case slug.

    The canonical identifier convention: lowercase alphanumeric words separated
    by single hyphens (``boneless-chicken-breast``, ``air-fryer``). Enforced for
    ingredient, recipe, aisle, equipment, and custom-unit identifiers.
    """
    clean = value.strip().lower()
    if not _SLUG_RE.match(clean):
        raise ValueError(
            f"{field} '{value}' must be a lowercase kebab-case slug "
            "(alphanumeric words separated by single hyphens)"
        )
    return clean


def clean_token(value: str, *, field: str) -> str:
    """Return ``value`` trimmed and lowercased, or raise if empty.

    For unit names, container nouns, and alias tokens: case-folding and
    whitespace trimming are the only allowed cleanups.
    """
    clean = value.strip().lower()
    if not clean:
        raise ValueError(f"{field} cannot be empty")
    return clean
