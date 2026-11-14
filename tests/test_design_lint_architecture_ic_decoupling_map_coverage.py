"""Keep IC decoupling-map coverage owned by focused power-lint modules."""

from __future__ import annotations

import inspect

import pytest

from kicad_tooling.hwrepo.design_lint_catalog import rule_catalog
from kicad_tooling.hwrepo.power_ic_decoupling_map_coverage import (
    ic_decoupling_map_coverage_issues,
)
from tests.lint_architecture_support import REPO_ROOT

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.power_lint,
    pytest.mark.catalog_lint,
    pytest.mark.architecture,
]

RULE_ID = "power.ic_decoupling_map_pin_coverage"
OWNER = "kicad_tooling/hwrepo/power_ic_decoupling_map_coverage.py#ic_decoupling_map_coverage_issues"


def test_catalog_names_opt_in_power_owner_and_native_fixture() -> None:
    rule = next(item for item in rule_catalog().rules if item.rule_id == RULE_ID)

    assert rule.theme == "power"
    assert rule.default_mode == "off"
    assert rule.implementation_owner == OWNER
    assert OWNER in rule.implementation_refs
    assert rule.required_native_fixtures == ("KICAD_RUN_NATIVE_IC_RAIL_CAPACITOR_FIXTURES",)
    assert inspect.getmodule(ic_decoupling_map_coverage_issues).__name__ == (
        "kicad_tooling.hwrepo.power_ic_decoupling_map_coverage"
    )


def test_ic_decoupling_map_coverage_modules_and_suites_stay_below_review_limit() -> None:
    paths = (
        "kicad_tooling/hwrepo/power_ic_decoupling_map_coverage.py",
        "kicad_tooling/hwrepo/design_lint_power_ic_decoupling_map_coverage.py",
        "kicad_tooling/ci_hosted_ic_decoupling_map_coverage.py",
        "kicad_tooling/ci_hosted_ic_rail_capacitors.py",
        "kicad_tooling/hwrepo/design_lint_power_candidate_evidence.py",
        "kicad_tooling/hwrepo/design_lint_power_candidates.py",
        "tests/test_ic_decoupling_map_pin_coverage.py",
        "tests/test_ic_decoupling_map_pin_coverage_parity.py",
        "tests/test_ic_rail_capacitor_native_fixture_lane.py",
        "tests/test_design_lint_architecture_ic_decoupling_map_coverage.py",
    )
    oversized = {
        relative: len((REPO_ROOT / relative).read_text(encoding="utf-8").splitlines())
        for relative in paths
        if len((REPO_ROOT / relative).read_text(encoding="utf-8").splitlines()) >= 500
    }

    assert not oversized, f"IC map-coverage owners must remain below 500 lines: {oversized}"
