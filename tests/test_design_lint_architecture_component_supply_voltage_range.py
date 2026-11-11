"""Keep exact component supply-range lint in its power-owned modules."""

from __future__ import annotations

import inspect
from pathlib import Path

import pytest

from kicad_tooling.hwrepo.component_supply_range_models import (
    ComponentSupplyVoltageRangeMap,
)
from kicad_tooling.hwrepo.design_lint_catalog import rule_catalog
from kicad_tooling.hwrepo.models import ComponentSupplyVoltageRangeMap as PublicMap

pytestmark = [pytest.mark.catalog_lint, pytest.mark.architecture]

RULE_ID = "power.component_supply_voltage_outside_range"
OWNER = "kicad_tooling/hwrepo/power_component_supply_range.py#component_supply_voltage_range_issues"
PIN_COVERAGE_RULE_ID = "power.component_supply_range_pin_coverage"
PIN_COVERAGE_OWNER = (
    "kicad_tooling/hwrepo/power_component_supply_range_coverage.py#"
    "component_supply_range_pin_coverage_issues"
)
MAP_COVERAGE_RULE_ID = "power.component_supply_range_map_coverage"
MAP_COVERAGE_OWNER = (
    "kicad_tooling/hwrepo/power_component_supply_range_map_coverage.py#"
    "component_supply_range_map_coverage_issues"
)


def test_catalog_names_the_theme_owned_predicate_and_disabled_default() -> None:
    rule = next(item for item in rule_catalog().rules if item.rule_id == RULE_ID)

    assert rule.theme == "power"
    assert rule.default_mode == "off"
    assert rule.implementation_owner == OWNER
    assert OWNER in rule.implementation_refs
    assert "component_voltage_ratings.py" not in rule.implementation_owner


def test_catalog_names_the_theme_owned_supply_pin_coverage_predicate() -> None:
    rule = next(item for item in rule_catalog().rules if item.rule_id == PIN_COVERAGE_RULE_ID)

    assert rule.theme == "power"
    assert rule.default_mode == "off"
    assert rule.implementation_owner == PIN_COVERAGE_OWNER
    assert PIN_COVERAGE_OWNER in rule.implementation_refs


def test_catalog_names_the_theme_owned_supply_range_map_discovery_predicate() -> None:
    rule = next(item for item in rule_catalog().rules if item.rule_id == MAP_COVERAGE_RULE_ID)

    assert rule.theme == "power"
    assert rule.default_mode == "off"
    assert rule.implementation_owner == MAP_COVERAGE_OWNER
    assert MAP_COVERAGE_OWNER in rule.implementation_refs


def test_supply_range_model_has_a_direct_owner_and_public_compatibility_export() -> None:
    assert PublicMap is ComponentSupplyVoltageRangeMap
    assert inspect.getmodule(ComponentSupplyVoltageRangeMap).__name__ == (
        "kicad_tooling.hwrepo.component_supply_range_models"
    )


def test_supply_range_modules_and_lint_suite_stay_below_review_limits() -> None:
    root = Path(__file__).resolve().parents[1]
    paths = (
        "kicad_tooling/hwrepo/component_supply_range_models.py",
        "kicad_tooling/hwrepo/power_component_supply_range.py",
        "kicad_tooling/hwrepo/design_lint_power_supply_range.py",
        "kicad_tooling/hwrepo/power_component_supply_range_coverage.py",
        "kicad_tooling/hwrepo/design_lint_power_supply_range_coverage.py",
        "kicad_tooling/hwrepo/power_component_supply_range_map_coverage.py",
        "kicad_tooling/hwrepo/design_lint_power_supply_range_map_coverage.py",
        "tests/test_component_supply_voltage_range.py",
        "tests/test_component_supply_range_pin_coverage.py",
        "tests/test_component_supply_range_map_coverage.py",
        "tests/test_component_supply_voltage_range_parity.py",
        "tests/test_component_supply_range_map_coverage_parity.py",
        "tests/test_component_rating_native_fixture_lane.py",
    )

    for relative in paths:
        assert len((root / relative).read_text(encoding="utf-8").splitlines()) < 500, relative


def test_policy_imports_the_map_from_its_theme_owner() -> None:
    root = Path(__file__).resolve().parents[1]
    policy_source = (root / "kicad_tooling/hwrepo/design_lint_policy_models.py").read_text(
        encoding="utf-8"
    )

    assert "from .component_supply_range_models import ComponentSupplyVoltageRangeMap" in (
        policy_source
    )
    assert "from .models import ComponentSupplyVoltageRangeMap" not in policy_source
