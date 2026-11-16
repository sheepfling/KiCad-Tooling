"""Guard the RS-485 receiver-sharing rule's predicate ownership."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.design_lint import rule_catalog

RULE_ID = "bus.rs485_receiver_outputs_share_net"

pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint, pytest.mark.architecture]


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_receiver_output_sharing_uses_a_focused_predicate_owner() -> None:
    rule = next(item for item in rule_catalog().rules if item.rule_id == RULE_ID)

    assert rule.theme == "interfaces"
    assert rule.implementation_owner == (
        "kicad_tooling/hwrepo/rs485_receiver_output_sharing.py#"
        "rs485_receiver_output_sharing_candidates"
    )
    assert rule.implementation_owner in rule.implementation_refs
    assert "kicad_tooling/hwrepo/rs485_data_functions.py#rs485_data_pin_role" in (
        rule.implementation_refs
    )
