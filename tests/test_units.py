from pathlib import Path
import pytest
from meal_prep.models.units import load_units


@pytest.fixture
def registry():
    return load_units(Path("data/units.yaml"))


def test_load_units_yaml(registry):
    assert registry.schema_data is not None
    assert registry.schema_data.mass.base == "g"
    assert registry.schema_data.volume.base == "ml"
    assert registry.schema_data.count.base == "item"


def test_normalize_aliases(registry):
    # Mass
    assert registry.normalize("g") == "g"
    assert registry.normalize("gram") == "g"
    assert registry.normalize("Grams") == "g"
    assert registry.normalize("kg") == "kg"
    assert registry.normalize("kilograms") == "kg"
    assert registry.normalize("lb") == "lb"
    assert registry.normalize("lbs") == "lb"

    # Volume
    assert registry.normalize("ml") == "ml"
    assert registry.normalize("milliliters") == "ml"
    assert registry.normalize("l") == "l"
    assert registry.normalize("liters") == "l"
    assert registry.normalize("tbsp") == "tbsp"
    assert registry.normalize("tablespoon") == "tbsp"
    assert registry.normalize("cup") == "cup"
    assert registry.normalize("cups") == "cup"

    # Count
    assert registry.normalize("item") == "item"
    assert registry.normalize("count") == "item"
    assert registry.normalize("slice") == "slice"
    assert registry.normalize("slices") == "slice"
    assert registry.normalize("clove") == "clove"
    assert registry.normalize("cloves") == "clove"

    # Time
    assert registry.normalize("s") == "s"
    assert registry.normalize("seconds") == "s"
    assert registry.normalize("min") == "min"
    assert registry.normalize("minutes") == "min"
    assert registry.normalize("hr") == "hr"
    assert registry.normalize("hours") == "hr"


def test_unknown_unit_raises_error(registry):
    with pytest.raises(ValueError, match="Unknown unit: 'football'"):
        registry.normalize("football")


def test_dimension_detection(registry):
    assert registry.dimension_of("grams") == "mass"
    assert registry.dimension_of("kg") == "mass"
    assert registry.dimension_of("cup") == "volume"
    assert registry.dimension_of("tbsp") == "volume"
    assert registry.dimension_of("slice") == "count"
    assert registry.dimension_of("item") == "count"


def test_universal_conversions_mass(registry):
    assert registry.convert(1, "kg", "g") == 1000.0
    assert registry.convert(500, "g", "kg") == 0.5
    assert registry.convert(1, "lb", "g") == pytest.approx(453.59)


def test_universal_conversions_volume(registry):
    assert registry.convert(1, "l", "ml") == 1000.0
    assert registry.convert(1, "tbsp", "ml") == 15.0
    assert registry.convert(1, "cup", "ml") == 240.0
    # 1 cup = 240 ml; 1 tbsp = 15 ml -> 240 / 15 = 16 tbsp!
    assert registry.convert(1, "cup", "tbsp") == 16.0


def test_cross_dimensional_conversion_rejected(registry):
    with pytest.raises(ValueError, match="Cannot convert between different dimensions"):
        registry.convert(1, "cup", "g")

    with pytest.raises(ValueError, match="Cannot convert between different dimensions"):
        registry.convert(2, "slice", "g")


def test_packaging_containers(registry):
    assert registry.is_valid_container("loaf") is True
    assert registry.is_valid_container("carton") is True
    assert registry.is_valid_container("bottle") is True
    assert registry.is_valid_container("bag") is True
    assert registry.is_valid_container("pack") is True
    assert registry.is_valid_container("alien_capsule") is False


def test_universal_conversions_time(registry):
    assert registry.dimension_of("min") == "time"
    assert registry.dimension_of("hr") == "time"
    assert registry.dimension_of("s") == "time"

    assert registry.convert(1, "hr", "min") == 60.0
    assert registry.convert(30, "min", "s") == 1800.0
    assert registry.convert(120, "s", "min") == 2.0


def test_valid_time_units(registry):
    assert registry.is_valid_time_unit("min") is True
    assert registry.is_valid_time_unit("minute") is True
    assert registry.is_valid_time_unit("hr") is True
    assert registry.is_valid_time_unit("hours") is True
    assert registry.is_valid_time_unit("s") is True
    assert registry.is_valid_time_unit("seconds") is True

    assert registry.is_valid_time_unit("g") is False
    assert registry.is_valid_time_unit("cup") is False
    assert registry.is_valid_time_unit("slice") is False

