"""Architecture checks for the project-mapped signal-divider rule owner."""

from __future__ import annotations

from pathlib import Path

import pytest

from kicad_tooling.hwrepo.design_lint_catalog import rule_catalog

pytestmark = [pytest.mark.design_lint, pytest.mark.catalog_lint, pytest.mark.architecture]

ROOT = Path(__file__).resolve().parents[1]
OWNER = "kicad_tooling/hwrepo/signal_dividers.py#scan_signal_divider_map"
RULE_ID = "interface.signal_divider_input_range_mismatch"


def test_signal_divider_rule_uses_its_theme_owned_predicate() -> None:
    rule = next(item for item in rule_catalog().rules if item.rule_id == RULE_ID)
    owner_path, owner_function = OWNER.split("#", maxsplit=1)
    owner_source = (ROOT / owner_path).read_text(encoding="utf-8")
    coverage_source = (ROOT / "kicad_tooling/hwrepo/design_lint_component_coverage.py").read_text(
        encoding="utf-8"
    )

    assert rule.theme == "interfaces"
    assert rule.implementation_owner == OWNER
    assert OWNER in rule.implementation_refs
    assert f"def {owner_function}(" in owner_source
    assert "from .signal_dividers import scan_signal_divider_map" in coverage_source


def test_signal_divider_sources_and_regression_suites_stay_reviewable() -> None:
    paths = (
        "kicad_tooling/hwrepo/signal_dividers.py",
        "kicad_tooling/hwrepo/signal_divider_models.py",
        "kicad_tooling/hwrepo/design_lint_signal_divider_candidates.py",
        "kicad_tooling/hwrepo/design_lint_signal_divider_evidence.py",
        "kicad_tooling/hwrepo/voltage_divider_math.py",
        "kicad_tooling/hwrepo/component_source_identity.py",
        "tests/design_lint_fixtures/signal_divider.py",
        "tests/test_signal_divider_contract.py",
        "tests/test_signal_divider_native_fixture_lane.py",
        "tests/test_design_lint_mcp_parity_signal_divider.py",
    )
    oversized = {
        path: len((ROOT / path).read_text(encoding="utf-8").splitlines())
        for path in paths
        if len((ROOT / path).read_text(encoding="utf-8").splitlines()) >= 500
    }

    assert not oversized
