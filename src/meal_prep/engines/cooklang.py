"""Pure Cooklang tokenizer and parser.

This module is a dependency-free engine. It owns the Cooklang micro-syntax
(the ``@ingredient`` and ``#cookware`` markup, plus the ``~timer`` markup it
validates in place) and turns raw instruction text into plain data records. It
imports nothing from the rest of the codebase (stdlib only) and must stay that
way — enforced by ``test_engines_package_has_no_domain_imports``.

Timers are validated here but deliberately not surfaced: a recipe is about
ingredients and cookware, and a timer duration is an instruction-text detail,
not a data record the system reasons about.

The compiled patterns are the single source of truth for Cooklang syntax,
shared by the recipe adapter (parsing into DTOs) and the renderer (formatting
instructions back to HTML).
"""

from dataclasses import dataclass
import re

# Cooklang element patterns. Kept at module scope so the renderer can reuse the
# exact same compiled objects rather than re-declaring them.
INGREDIENT_PATTERN = re.compile(
    r"@(?:([a-zA-Z0-9_-]+|\b[a-zA-Z0-9_ -]+?)\s*\{\s*([^}%]*?)\s*(?:%\s*([^}]+?)\s*)?\}|([a-zA-Z0-9_-]+))"
)
COOKWARE_PATTERN = re.compile(
    r"#([a-zA-Z0-9_-]+|\b[a-zA-Z0-9_ -]+?)\s*\{\}|#([a-zA-Z0-9_-]+)"
)
TIMER_PATTERN = re.compile(
    r"~([a-zA-Z0-9_-]+)?\s*\{\s*([^}%]+)\s*%\s*([^}]+)\s*\}"
)

# Valid timer duration units. Self-contained: the `time` dimension has been
# removed from units.yaml, so this engine carries its own canonical set rather
# than depending on an external registry.
_TIME_UNITS = {
    "s", "sec", "second", "seconds",
    "min", "mins", "minute", "minutes",
    "hr", "hrs", "hour", "hours",
}


@dataclass(frozen=True)
class CooklangIngredient:
    name: str
    quantity: float
    unit: str


@dataclass(frozen=True)
class CooklangMention:
    """An ingredient reference without an amount (``@name`` or ``@name{}``).

    A mention contributes nothing to quantity; it only triggers highlighting and
    must be backed by a declaration elsewhere in the same recipe.
    """

    name: str


@dataclass(frozen=True)
class CooklangCookware:
    id: str


@dataclass(frozen=True)
class CooklangDocument:
    ingredients: tuple[CooklangIngredient, ...]
    mentions: tuple[CooklangMention, ...]
    cookware: tuple[CooklangCookware, ...]


def parse_cooklang(text: str) -> CooklangDocument:
    """Tokenize Cooklang instruction text into ingredient, mention, and cookware records.

    An ingredient *declaration* carries a quantity and an optional unit: the
    unit may be omitted (``@name{qty}``) and is recorded as the empty string,
    which the recipe service later interprets as a count. A *mention*
    (``@name`` or ``@name{}``) carries no amount and is returned separately so
    callers can validate that every mention has a declaration.

    Raises ``ValueError`` on syntax errors: a quantity-less declaration with a
    unit (``@name{%unit}``), a non-numeric/non-positive quantity, or a malformed
    timer (non-numeric or non-positive duration, or an unrecognized time unit).
    Timers are validated but not returned.
    """
    ingredients: list[CooklangIngredient] = []
    mentions: list[CooklangMention] = []

    for match in INGREDIENT_PATTERN.finditer(text):
        if match.group(1):
            name = match.group(1).strip().lower()
            qty_raw = match.group(2).strip() if match.group(2) else ""
            unit_raw = match.group(3).strip().lower() if match.group(3) else ""
        else:
            name = match.group(4).strip().lower()
            mentions.append(CooklangMention(name=name))
            continue

        if qty_raw == "" and unit_raw == "":
            mentions.append(CooklangMention(name=name))
            continue

        if qty_raw == "":
            raise ValueError(
                f"Ingredient '@{name}' in recipe missing quantity. "
                "A unit requires a quantity, e.g. '{quantity%unit}'."
            )

        try:
            qty = float(qty_raw)
        except ValueError:
            raise ValueError(f"Invalid quantity '{qty_raw}' for ingredient '@{name}'. Must be a numeric value.")

        if qty <= 0:
            raise ValueError(f"Quantity for ingredient '@{name}' must be positive, got {qty}.")

        ingredients.append(CooklangIngredient(name=name, quantity=qty, unit=unit_raw))

    cookware: list[CooklangCookware] = []
    seen_cookware: set[str] = set()
    for match in COOKWARE_PATTERN.finditer(text):
        item_id = (match.group(1) or match.group(2)).strip().lower()
        if item_id not in seen_cookware:
            seen_cookware.add(item_id)
            cookware.append(CooklangCookware(id=item_id))

    _validate_timers(text)

    return CooklangDocument(
        ingredients=tuple(ingredients),
        mentions=tuple(mentions),
        cookware=tuple(cookware),
    )


def _validate_timers(text: str) -> None:
    """Validate ``~name{duration%unit}`` markup without surfacing timer records."""
    for match in TIMER_PATTERN.finditer(text):
        name = (match.group(1) or "timer").strip()
        duration_raw = match.group(2).strip()
        unit_raw = match.group(3).strip().lower()

        try:
            duration = float(duration_raw)
        except ValueError:
            raise ValueError(
                f"Invalid timer duration '{duration_raw}' for timer '{name}'. Must be a numeric value."
            )

        if duration <= 0:
            raise ValueError(f"Timer duration for '{name}' must be positive, got {duration}.")

        if unit_raw not in _TIME_UNITS:
            raise ValueError(
                f"Timer '{name}' uses unknown time unit '{unit_raw}'. "
                f"Must be one of: {', '.join(sorted(_TIME_UNITS))}."
            )
