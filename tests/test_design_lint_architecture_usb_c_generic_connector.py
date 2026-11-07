"""Keep USB-C generic connector review in focused interface-owned modules."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo import usb_c_generic_connector
from kicad_tooling.hwrepo.design_lint import rule_catalog
from tests.lint_architecture_support import HWREPO, IMPLEMENTATION_MAX_LINES, line_count

pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint, pytest.mark.architecture]

RULE_ID = "bus.usb_c_generic_connector_cc_pair_review"
MODULES = (
    "usb_c_generic_connector.py",
    "design_lint_usb_c_generic_connector_candidate_evidence.py",
    "design_lint_usb_c_generic_connector_candidates.py",
)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_predicate_and_catalog_owner_stay_in_the_usb_c_theme_module() -> None:
    owner = "kicad_tooling/hwrepo/usb_c_generic_connector.py#usb_c_generic_connector_pairs"
    rule = next(item for item in rule_catalog().rules if item.rule_id == RULE_ID)

    assert rule.theme == "interfaces"
    assert rule.implementation_owner == owner
    assert owner in rule.implementation_refs
    assert usb_c_generic_connector.usb_c_generic_connector_pairs.__module__.endswith(
        "usb_c_generic_connector"
    )


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_usb_c_generic_connector_modules_stay_below_review_limit() -> None:
    counts = {name: line_count(HWREPO / name) for name in MODULES}

    assert all(count < IMPLEMENTATION_MAX_LINES for count in counts.values()), counts
