"""Recipe model.

Holds the schema for a parsed recipe: the YAML frontmatter and the Cooklang
body references. Parsing of .cook files lives in ``meal_prep.adapters.recipes``.
"""

from pydantic import BaseModel, ConfigDict, Field, field_validator

from meal_prep.dtos._normalize import normalize_slug
from meal_prep.enums import MealRole, RecipeCategory

_SLUG_RULE = (
    "a lowercase kebab-case slug (alphanumeric words separated by single "
    "hyphens; trimmed and lowercased on load)"
)


class RecipeYield(BaseModel):
    """What one batch makes: the portion count and the finished weight."""

    model_config = ConfigDict(extra="forbid")

    servings: float = Field(
        ..., gt=0, description="Number of portions produced by the batch"
    )
    cooked_g: float = Field(
        ..., gt=0, description="Total finished cooked batch weight in grams"
    )


class RecipeStorage(BaseModel):
    """How long the cooked batch keeps, and whether it freezes."""

    model_config = ConfigDict(extra="forbid")

    fridge_days: int = Field(
        ...,
        gt=0,
        description="Days the cooked batch keeps refrigerated (food-safety "
        "guidance for cooked leftovers); independent of the raw ingredients' "
        "shelf_life_days",
    )
    freezer_friendly: bool = Field(
        ..., description="Whether the cooked batch can be frozen"
    )


class RecipeFrontmatter(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    id: str = Field(
        ...,
        description=f"Recipe id, {_SLUG_RULE}; must equal the file stem",
    )
    title: str = Field(..., min_length=1, description="Human-readable recipe title")
    category: RecipeCategory = Field(
        ..., description="Recipe category; must equal the parent directory name"
    )
    yield_info: RecipeYield = Field(
        ..., alias="yield", description="Portion count and cooked batch weight"
    )
    storage_info: RecipeStorage = Field(
        ..., alias="storage", description="Fridge life and freezer suitability"
    )
    meal_role: MealRole | None = Field(
        default=None,
        description="The part of a meal it plays, for the planner's archetypes "
        "(breakfast and snack recipes); absent when the category says enough",
    )

    @field_validator("id")
    @classmethod
    def validate_id_format(cls, v: str) -> str:
        return normalize_slug(v, field="Recipe id")


class RecipeIngredientRef(BaseModel):
    """An ingredient declaration with an amount: ``@id{quantity%unit}`` in the
    Cooklang body. Repeated declarations of one id add up."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(
        ...,
        description="Ingredient id, as in the catalog (data/ingredients/*.yaml); "
        f"{_SLUG_RULE}",
    )
    quantity: float = Field(
        ...,
        gt=0,
        description="Amount used by one batch; fractions and mixed numbers are "
        "accepted in the body ('1/2', '1 1/2')",
    )
    unit: str = Field(
        "",
        description="Measurement unit; empty string means a count (resolved to the "
        "reserved 'count' node during enrichment). Must be gram-reachable on the "
        "ingredient's catalog entry (a standard unit, a custom unit, or 'package').",
    )

    @field_validator("id")
    @classmethod
    def validate_id_format(cls, v: str) -> str:
        return normalize_slug(v, field="Recipe ingredient id")


class RecipeIngredientMention(BaseModel):
    """An amount-less ingredient reference (``@name`` or ``@name{}``).

    Carries only an id. A mention contributes nothing to quantity and must be
    backed by a declaration elsewhere in the recipe; the recipe service enforces
    that invariant.
    """

    model_config = ConfigDict(extra="forbid")

    id: str = Field(
        ...,
        description="Ingredient id; must also be declared with an amount "
        "elsewhere in the recipe",
    )

    @field_validator("id")
    @classmethod
    def validate_id_format(cls, v: str) -> str:
        return normalize_slug(v, field="Recipe ingredient mention id")


class RecipeCookwareRef(BaseModel):
    """A piece of equipment: ``#id`` in the Cooklang body."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(
        ...,
        description=f"Equipment id, as in data/equipment.yaml; {_SLUG_RULE}",
    )

    @field_validator("id")
    @classmethod
    def validate_id_format(cls, v: str) -> str:
        return normalize_slug(v, field="Recipe cookware id")


class RecipeDTO(BaseModel):
    """A parsed recipe file, ``recipes/<category>/<id>.cook``.

    The file is YAML frontmatter (id, title, category, yield, storage,
    optional meal_role; no other keys) followed by a Cooklang body. Ingredients, mentions and
    cookware are parsed from the body, never authored as YAML: ``@id{1/2%cup}``
    declares an amount, ``@id`` or ``@id{}`` mentions an ingredient declared
    elsewhere, ``#id`` names equipment, and ``~name{10%min}`` is a timer (the
    name is required).
    """

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    id: str = Field(
        ...,
        description=f"Recipe id, {_SLUG_RULE}; must equal the file stem",
    )
    title: str = Field(..., min_length=1, description="Human-readable recipe title")
    category: RecipeCategory = Field(
        ..., description="Recipe category; must equal the parent directory name"
    )
    yield_info: RecipeYield = Field(
        ..., alias="yield", description="Portion count and cooked batch weight"
    )
    storage_info: RecipeStorage = Field(
        ..., alias="storage", description="Fridge life and freezer suitability"
    )
    meal_role: MealRole | None = Field(
        default=None,
        description="The part of a meal it plays, for the planner's archetypes "
        "(breakfast and snack recipes); absent when the category says enough",
    )
    ingredients: list[RecipeIngredientRef] = Field(
        ...,
        description="Ingredient declarations with amounts, parsed from the body "
        "in order of appearance",
    )
    mentions: list[RecipeIngredientMention] = Field(
        default_factory=list,
        description="Amount-less ingredient references (``@id`` or ``@id{}``) "
        "parsed from the body; each needs a declaration elsewhere",
    )
    cookware: list[RecipeCookwareRef] = Field(
        ..., description="Equipment referenced in the body (``#id``)"
    )
    instructions: str = Field(
        ..., description="The Cooklang body: one step per paragraph"
    )
