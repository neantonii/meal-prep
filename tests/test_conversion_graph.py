from pathlib import Path
import pytest
from meal_prep.adapters.units import load_units
from meal_prep.adapters.ingredients import load_all_ingredients
from meal_prep.models.ingredient import Ingredient
from meal_prep.engines.conversion_graph import ConversionEdge, ConversionError, build_graph
from meal_prep.services.pricing import container_weight_g


@pytest.fixture
def units():
    return load_units(Path("data/units.yaml"))


@pytest.fixture
def chicken(units):
    catalog = load_all_ingredients(Path("data/ingredients"), units=units)
    return catalog["boneless-chicken-breast"]


def test_chicken_breast_discrete_and_mass_conversions(chicken, units):
    graph = chicken.get_conversion_graph(units)

    # 1 piece = 237.5 g
    assert graph.convert(1, "piece", "g") == 237.5
    assert graph.convert(2, "piece", "g") == 475.0

    # 1 piece to kg (transitive: piece -> g -> kg)
    assert graph.convert(1, "piece", "kg") == pytest.approx(0.2375)

    # Reverse: 475 g to pieces
    assert graph.convert(475, "g", "piece") == 2.0


def test_chicken_breast_packaging_conversions(chicken, units):
    graph = chicken.get_conversion_graph(units)

    # 1 pack = 4 pieces
    assert graph.convert(1, "pack", "piece") == 4.0
    assert graph.convert(4, "piece", "pack") == 1.0

    # 1 pack = 950 g
    assert graph.convert(1, "pack", "g") == 950.0
    assert graph.convert(950, "g", "pack") == 1.0
    assert graph.convert(1900, "g", "pack") == 2.0

    # 1 pack to kg
    assert graph.convert(1, "pack", "kg") == pytest.approx(0.95)


def test_unreachable_conversion_raises_error(chicken, units):
    graph = chicken.get_conversion_graph(units)

    # Chicken has no volume/density bridge
    assert graph.can_convert("cup", "g") is False
    assert graph.can_convert("piece", "tbsp") is False

    with pytest.raises(ValueError, match="No conversion path exists"):
        graph.convert(1, "cup", "g")

    with pytest.raises(ValueError, match="No conversion path exists"):
        chicken.convert(2, "cup", "piece", units=units)


def test_alias_and_plural_normalization(chicken, units):
    # Testing alias "pieces" -> "piece", "grams" -> "g", "packs" -> "pack"
    assert chicken.convert(2, "pieces", "grams", units=units) == 475.0
    assert chicken.convert(1, "packs", "pieces", units=units) == 4.0


def test_ingredient_with_density_bridge(units):
    """Test ingredient that defines a volume-to-mass bridge (e.g. olive oil: 1 ml = 0.92 g)."""
    olive_oil = Ingredient.model_validate(
        {
            "id": "extra-virgin-olive-oil",
            "name": "Extra Virgin Olive Oil",
            "aisle": "pantry",
            "storage": "ambient",
            "shelf_life_days": 365,
            "package": {
                "container": "bottle",
                "unit": "ml",
                "amount": 1000,
            },
            "reference": {
                "brand": "Compliments",
                "product": "Extra Virgin Olive Oil 1L",
                "price": 14.99,
            },
            "macros_per_100g": {
                "calories_kcal": 884.0,
                "protein_g": 0.0,
                "fat_g": 100.0,
                "carbs_g": 0.0,
                "fiber_g": 0.0,
            },
            "conversions": [
                {"from": "ml", "to": "g", "factor": 0.92},  # Density bridge!
            ],
        }
    )

    graph = olive_oil.get_conversion_graph(units)

    # Volume can now convert to mass!
    assert graph.can_convert("tbsp", "g") is True
    assert graph.can_convert("cup", "g") is True

    # 1 tbsp = 15 ml * 0.92 g/ml = 13.8 g
    assert graph.convert(1, "tbsp", "g") == 13.8

    # 1 cup = 240 ml * 0.92 g/ml = 220.8 g
    assert graph.convert(1, "cup", "g") == 220.8

    # 1 bottle = 1000 ml = 920 g
    assert graph.convert(1, "bottle", "ml") == 1000.0
    assert graph.convert(1, "bottle", "g") == 920.0

def test_conversion_for_tsp_works_with_only_tbsp_supplied(units):
    """Test that an ingredient with only tbsp supplied can convert tsp via standard intermediate units."""
    butter = Ingredient.model_validate(
        {
            "id": "unsalted-butter",
            "name": "Unsalted Butter",
            "aisle": "dairy",
            "storage": "refrigerated",
            "shelf_life_days": 90,
            "package": {
                "container": "pack",
                "unit": "g",
                "amount": 454,
            },
            "reference": {
                "brand": "Compliments",
                "product": "Compliments Butter Unsalted 454 g",
                "price": 6.69,
            },
            "macros_per_100g": {
                "calories_kcal": 700.0,
                "protein_g": 1.0,
                "fat_g": 80.0,
                "carbs_g": 0.0,
                "fiber_g": 0.0,
            },
            "conversions": [
                {"from": "tbsp", "to": "g", "factor": 14.2},
            ],
        }
    )

    graph = butter.get_conversion_graph(units)

    # Invariant units: 1 tbsp = 15 ml, 1 tsp = 5 ml -> 1 tbsp = 3 tsp
    assert graph.can_convert("tsp", "g") is True
    assert graph.can_convert("tbsp", "g") is True

    # 1 tbsp = 14.2 g
    assert graph.convert(1, "tbsp", "g") == 14.2
    # 1 tsp = 14.2 / 3 = 4.733333 g
    assert graph.convert(1, "tsp", "g") == pytest.approx(14.2 / 3.0, rel=1e-4)
    # 3 tsp = 14.2 g
    assert graph.convert(3, "tsp", "g") == pytest.approx(14.2, rel=1e-4)
    # Reverse conversion: 14.2 g to tsp = 3 tsp
    assert graph.convert(14.2, "g", "tsp") == pytest.approx(3.0, rel=1e-4)


def test_arbitrary_edges_and_reverse_transformations(units):
    """Test arbitrary edge between discrete unit and volume, and automatic reverse transformation."""
    protein_powder = Ingredient.model_validate(
        {
            "id": "whey-protein",
            "name": "Whey Protein Powder",
            "aisle": "pantry",
            "storage": "ambient",
            "shelf_life_days": 365,
            "package": {
                "container": "tub",
                "unit": "scoop",
                "amount": 30,
            },
            "reference": {
                "brand": "Optimum Nutrition",
                "product": "Gold Standard 100% Whey 900g",
                "price": 45.99,
            },
            "macros_per_100g": {
                "calories_kcal": 400.0,
                "protein_g": 80.0,
                "fat_g": 5.0,
                "carbs_g": 10.0,
                "fiber_g": 0.0,
            },
            "conversions": [
                # Arbitrary edge: 1 scoop = 2 tbsp (discrete count to volume, no grams directly)
                {"from": "scoop", "to": "tbsp", "factor": 2.0},
            ],
        }
    )

    graph = protein_powder.get_conversion_graph(units)

    # 1 scoop = 2 tbsp
    assert graph.convert(1, "scoop", "tbsp") == 2.0
    # Automatic reverse: 2 tbsp = 1 scoop (inverse coefficient 1/2)
    assert graph.convert(2, "tbsp", "scoop") == 1.0

    # Transitive via volume units: 1 tbsp = 15 ml, 1 tsp = 5 ml
    # 1 scoop = 2 tbsp = 30 ml
    assert graph.convert(1, "scoop", "ml") == 30.0
    assert graph.convert(30, "ml", "scoop") == 1.0

    # 1 scoop = 6 tsp
    assert graph.convert(1, "scoop", "tsp") == 6.0
    assert graph.convert(6, "tsp", "scoop") == 1.0


def make_ingredient(**overrides):
    """Build a valid ingredient payload, overridable per test."""
    data = {
        "id": "test-item",
        "name": "Test Item",
        "aisle": "pantry",
        "storage": "ambient",
        "shelf_life_days": 30,
        "package": {"container": "pack", "unit": "piece", "amount": 4},
        "reference": {"brand": "Test", "product": "Test", "price": 5.0},
        "macros_per_100g": {
            "calories_kcal": 100,
            "protein_g": 20,
            "fat_g": 1,
            "carbs_g": 0,
            "fiber_g": 0,
        },
        "conversions": [{"from": "piece", "to": "g", "factor": 237.5}],
    }
    data.update(overrides)
    return data


def test_container_equal_to_unit_is_rejected(units):
    """The KI-02 corruption: container == unit must fail loudly, not silently overwrite.

    'bunch' is the taxonomy's only noun that is both a container and a count unit (KI-11),
    so it is the collision this guard exists for.
    """
    payload = make_ingredient(
        package={"container": "bunch", "unit": "bunch", "amount": 1},
        conversions=[{"from": "piece", "to": "g", "factor": 237.5}],
    )
    ingredient = Ingredient.model_validate(payload)
    with pytest.raises(ValueError, match="self-reference"):
        ingredient.get_conversion_graph(units)


def test_implicit_package_edge_conflicting_with_authored_conversion_is_rejected(units):
    """The implicit container -> unit edge must not silently clash with an authored conversion.

    This is the KI-02 failure mode: the package edge implies 1 bunch = 3 piece while the
    authored data says 1 bunch = 5 piece. Before the fix the implicit edge overwrote the
    authored one with no error.
    """
    payload = make_ingredient(
        package={"container": "bunch", "unit": "piece", "amount": 3},
        conversions=[
            {"from": "bunch", "to": "piece", "factor": 5.0},
            {"from": "piece", "to": "g", "factor": 237.5},
        ],
    )
    ingredient = Ingredient.model_validate(payload)
    with pytest.raises(ValueError, match="redefines 'bunch' -> 'piece'"):
        ingredient.get_conversion_graph(units)


def test_authored_conversion_restating_the_package_edge_is_rejected(units):
    """Re-adding an edge that already exists is a no-op, so it is an error, not tolerated.

    The package block already yields `bunch -> piece = 3`, so authoring the identical
    conversion changes nothing and must be reported.
    """
    payload = make_ingredient(
        package={"container": "bunch", "unit": "piece", "amount": 3},
        conversions=[
            {"from": "bunch", "to": "piece", "factor": 3.0},
            {"from": "piece", "to": "g", "factor": 237.5},
        ],
    )
    ingredient = Ingredient.model_validate(payload)
    with pytest.raises(ValueError, match="redefines 'bunch' -> 'piece'"):
        ingredient.get_conversion_graph(units)


def test_authoring_the_reverse_of_the_package_edge_is_rejected(units):
    """Authoring the reverse of the implicit package edge is redundant, so it is an error.

    The package block already yields `bunch -> piece = 3` and the reverse is derived
    automatically, so authoring `piece -> bunch` adds nothing.
    """
    payload = make_ingredient(
        package={"container": "bunch", "unit": "piece", "amount": 3},
        conversions=[{"from": "piece", "to": "bunch", "factor": 1 / 3.0}],
    )
    ingredient = Ingredient.model_validate(payload)
    with pytest.raises(ValueError, match="defines both 'piece' -> 'bunch'"):
        ingredient.get_conversion_graph(units)


def test_package_unit_grams_needs_no_authored_conversions(units):
    """When the package unit IS grams, an empty conversions list is sufficient."""
    payload = make_ingredient(
        package={"container": "bag", "unit": "g", "amount": 454},
        conversions=[],
    )
    ingredient = Ingredient.model_validate(payload)
    graph = ingredient.get_conversion_graph(units)
    assert container_weight_g(ingredient, units) == 454.0
    assert graph.convert(1, "bag", "g") == 454.0


def test_directed_cycle_is_rejected(units):
    """A three-node cycle that the pair and dimension checks cannot see is caught."""
    payload = make_ingredient(
        package={"container": "bag", "unit": "cup", "amount": 8},
        conversions=[
            {"from": "cup", "to": "g", "factor": 240.0},
            {"from": "g", "to": "bag", "factor": 0.001},
        ],
    )
    ingredient = Ingredient.model_validate(payload)
    with pytest.raises(ValueError, match="conversion cycle"):
        ingredient.get_conversion_graph(units)


def test_unregistered_container_is_rejected(units):
    payload = make_ingredient(package={"container": "sack", "unit": "piece", "amount": 4})
    ingredient = Ingredient.model_validate(payload)
    with pytest.raises(ValueError, match="not a registered packaging container"):
        ingredient.get_conversion_graph(units)


def test_unbridged_custom_unit_is_rejected(units):
    """A package unit outside the taxonomy is only legal when an authored conversion bridges it."""
    payload = make_ingredient(
        package={"container": "tub", "unit": "scoop", "amount": 30},
        conversions=[{"from": "piece", "to": "g", "factor": 237.5}],
    )
    ingredient = Ingredient.model_validate(payload)
    with pytest.raises(ValueError, match="neither a registered unit"):
        ingredient.get_conversion_graph(units)


def test_bridged_custom_unit_is_accepted(units):
    payload = make_ingredient(
        package={"container": "tub", "unit": "scoop", "amount": 30},
        conversions=[
            {"from": "scoop", "to": "tbsp", "factor": 2.0},
            {"from": "tbsp", "to": "g", "factor": 8.0},
        ],
    )
    ingredient = Ingredient.model_validate(payload)
    ingredient.get_conversion_graph(units)
    assert container_weight_g(ingredient, units) == 480.0


def test_container_weight_derived_from_conversions(units):
    """Net weight is derived from the container reaching grams, not declared."""
    payload = make_ingredient(
        package={"container": "pack", "unit": "piece", "amount": 4},
        conversions=[{"from": "piece", "to": "g", "factor": 237.5}],
    )
    ingredient = Ingredient.model_validate(payload)
    ingredient.get_conversion_graph(units)
    assert container_weight_g(ingredient, units) == 950.0


def test_container_weight_zero_when_grams_unreachable(units):
    """An unbridgeable container yields 0.0 so the loader can report it."""
    payload = make_ingredient(
        package={"container": "pack", "unit": "item", "amount": 1},
        conversions=[
            {"from": "item", "to": "serving", "factor": 2.0},
        ],
    )
    ingredient = Ingredient.model_validate(payload)
    ingredient.get_conversion_graph(units)
    assert container_weight_g(ingredient, units) == 0.0


def test_build_graph_is_pure_and_immutable():
    """The graph is constructible from raw edges alone and exposes no mutable state."""
    g = build_graph([
        ConversionEdge("bag", "piece", 4.0),
        ConversionEdge("piece", "g", 237.5),
    ])
    assert g.convert(1, "bag", "g") == 950.0
    assert g.factor("piece", "g") == 237.5
    assert g.factor("g", "piece") == pytest.approx(1 / 237.5)

    # `factors` is a read-only view; mutation must fail loudly.
    with pytest.raises(TypeError):
        g.factors[("bag", "piece")] = 999.0  # type: ignore[index]

    # `units` is an immutable frozenset.
    assert isinstance(g.units, frozenset)
    assert g.units == {"bag", "piece", "g"}

    assert g.reachable("bag") == {"bag", "piece", "g"}


def test_convert_does_not_round():
    """The graph returns the raw product; rounding is the presentation layer's job."""
    g = build_graph([ConversionEdge("a", "b", 3.0)])
    raw = g.convert(1.0, "b", "a")  # reverse edge: 1/3
    assert raw == 1.0 / 3.0
    assert raw != round(1.0 / 3.0, 6)  # the old engine rounded to 6 dp


def test_build_graph_enforces_invariants_without_domain():
    """Duplicate, reverse, and cycle rules are enforced by the graph alone."""
    with pytest.raises(ValueError, match="redefines"):
        build_graph([ConversionEdge("a", "b", 2.0), ConversionEdge("a", "b", 3.0)])
    with pytest.raises(ValueError, match="defines both"):
        build_graph([ConversionEdge("a", "b", 2.0), ConversionEdge("b", "a", 0.5)])
    with pytest.raises(ValueError, match="conversion cycle"):
        build_graph([
            ConversionEdge("a", "b", 2.0),
            ConversionEdge("b", "c", 3.0),
            ConversionEdge("c", "a", 4.0),
        ])


def test_conversion_edge_validates_at_construction():
    with pytest.raises(ValueError, match="self-reference"):
        ConversionEdge("x", "x", 1.0)
    with pytest.raises(ValueError, match="positive finite"):
        ConversionEdge("x", "y", 0.0)
    with pytest.raises(ValueError, match="positive finite"):
        ConversionEdge("x", "y", float("inf"))
    with pytest.raises(ValueError, match="non-empty"):
        ConversionEdge("", "y", 1.0)


def test_engines_package_has_no_domain_imports():
    """Drift guard: every ``engines`` module must stay 100% independent of the rest of the codebase."""
    import inspect
    import pkgutil
    import meal_prep.engines as engines

    for module in pkgutil.iter_modules(engines.__path__):
        mod = __import__(f"meal_prep.engines.{module.name}", fromlist=["x"])
        src = inspect.getsource(mod)
        assert "meal_prep" not in src, f"engines.{module.name} must not import from meal_prep"

