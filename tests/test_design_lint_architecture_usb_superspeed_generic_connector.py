"""Guard USB SuperSpeed generic-connector rule ownership and module scope."""

from __future__ import annotations

from pathlib import Path

import pytest

from kicad_tooling.hwrepo.design_lint import rule_catalog

pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint, pytest.mark.architecture]

RULE_ID = "bus.usb_superspeed_generic_connector_pair_review"
REPOSITORY = Path(__file__).resolve().parents[1]


def test_rule_owner_and_mapping_support_are_theme_owned() -> None:
    rule = next(item for item in rule_catalog().rules if item.rule_id == RULE_ID)

    assert rule.theme == "interfaces"
    assert rule.implementation_owner == (
        "kicad_tooling/hwrepo/usb_peer_generic_connector_candidates.py"
        "#generic_usb_connector_superspeed_pair_candidates"
    )
    assert rule.implementation_owner in rule.implementation_refs
    assert (
        "kicad_tooling/hwrepo/usb_peer_generic_connector_candidates.py"
        "#mapped_generic_usb_superspeed_connector_endpoints"
    ) in rule.implementation_refs


def test_usb_superspeed_generic_connector_modules_stay_below_review_limit() -> None:
    modules = (
        "kicad_tooling/hwrepo/usb_peer_generic_connector_candidates.py",
        "kicad_tooling/hwrepo/usb_peer_generic_connector_models.py",
        "kicad_tooling/hwrepo/design_lint_usb_superspeed_generic_connector_candidates.py",
        "kicad_tooling/hwrepo/design_lint_usb_superspeed_generic_connector_candidate_evidence.py",
        "kicad_tooling/hwrepo/usb_peer_reference_scan.py",
    )
    for relative in modules:
        path = REPOSITORY / relative
        assert len(path.read_text(encoding="utf-8").splitlines()) < 500, relative
