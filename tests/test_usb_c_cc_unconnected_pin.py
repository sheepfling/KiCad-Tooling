"""Focused regression coverage for unassigned USB-C CC signal pins."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.models import DesignLintPolicy
from tests.design_lint_fixtures import coach, unconnected_protocol_pins

RULE_ID = "bus.usb_c_unconnected_cc_pin"

pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint]


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_unassigned_usb_c_cc_pins_emit_review() -> None:
    source = unconnected_protocol_pins()
    report = evaluate("synthetic-usb-c-cc-open", coach(source), DesignLintPolicy())
    findings = {finding.subject for finding in report.findings if finding.rule_id == RULE_ID}

    assert findings == {"J1.1: CC1", "J1.2: CC2"}


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_assigned_usb_c_cc_pins_are_quiet_for_this_rule() -> None:
    source = unconnected_protocol_pins()
    assigned = source.model_copy(
        update={
            "nets": {
                **source.nets,
                "USB_CC1": ("J1.1",),
                "USB_CC2": ("J1.2",),
            }
        }
    )
    report = evaluate("synthetic-usb-c-cc-assigned", coach(assigned), DesignLintPolicy())

    assert not any(finding.rule_id == RULE_ID for finding in report.findings)
