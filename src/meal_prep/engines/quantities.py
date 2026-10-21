"""Human-authored quantity parsing (stdlib only).

Accepts plain decimals (``0.5``), vulgar fractions (``1/2``), and mixed
numbers (``1 1/2``) — the forms cooks actually write. Returns a plain
``float``: the fraction is a parse-time convenience, and everything
downstream (DTOs, models, renderer) stays numeric.
"""

from __future__ import annotations

from fractions import Fraction


def parse_quantity(raw: str) -> float:
    """Parse an authored quantity to ``float``.

    Raises ``ValueError`` with the offending text when unparseable.
    """
    text = raw.strip()
    if not text:
        raise ValueError("Quantity is empty. Must be a numeric value.")
    try:
        if " " in text:
            whole_raw, _, frac_raw = text.partition(" ")
            value = float(int(whole_raw) + Fraction(frac_raw))
        elif "/" in text:
            value = float(Fraction(text))
        else:
            value = float(text)
    except (ValueError, ZeroDivisionError):
        raise ValueError(
            f"Invalid quantity '{raw}'. Must be a numeric value."
        ) from None
    return value
