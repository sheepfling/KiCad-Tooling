"""Architecture guard for the RS-485 open A/B line rule owner."""

from __future__ import annotations

from pathlib import Path

import pytest

from kicad_tooling.hwrepo.design_lint_catalog import rule_catalog
from kicad_tooling.hwrepo.rs485_unconnected_line_pin import (
    rs485_unconnected_line_pin_candidates,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint, pytest.mark.architecture]

ROOT = Path(__file__).resolve().parents[1]
OWNER = "kicad_tooling/hwrepo/rs485_unconnected_line_pin.py#rs485_unconnected_line_pin_candidates"


@pytest.mark.design_lint_rule(rule_id="bus.rs485_unconnected_line_pin")
def test_rule_catalog_points_to_its_small_theme_owned_predicate() -> None:
    rule = next(
        item for item in rule_catalog().rules if item.rule_id == "bus.rs485_unconnected_line_pin"
    )
    module = ROOT / "kicad_tooling/hwrepo/rs485_unconnected_line_pin.py"

    assert len(module.read_text(encoding="utf-8").splitlines()) < 500
    assert rule.theme == "interfaces"
    assert rule.implementation_owner == OWNER
    assert OWNER in rule.implementation_refs
    assert rs485_unconnected_line_pin_candidates.__module__.endswith("rs485_unconnected_line_pin")
