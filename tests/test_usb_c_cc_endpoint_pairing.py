"""Deterministic USB-C connector/controller CC endpoint-pairing regressions."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.design_lint_finding_models import DesignLintIgnore
from kicad_tooling.hwrepo.design_lint_policy_models import DesignLintPolicy
from kicad_tooling.hwrepo.models import DesignLintRuleOverride
from kicad_tooling.hwrepo.usb_c_cc_endpoint_pairing import (
    RULE_ID,
    crossed_usb_c_cc_endpoint_candidates,
)
from tests.design_lint_fixtures import coach
from tests.design_lint_fixtures.usb_c_cc_endpoint_pairing import (
    usb_c_cc_endpoint_pairing_netlist,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint]


def _report(source, policy: DesignLintPolicy | None = None):
    return evaluate(
        "synthetic-usb-c-cc-endpoint-pairing",
        coach(source),
        DesignLintPolicy() if policy is None else policy,
    )


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_crossed_connector_controller_cc_assignments_request_review() -> None:
    report = _report(usb_c_cc_endpoint_pairing_netlist())
    findings = tuple(item for item in report.findings if item.rule_id == RULE_ID)

    assert report.status == "REVIEW"
    assert len(findings) == 1
    assert findings[0].subject == "J1/U1: USB-C CC1/CC2 endpoint nets appear crossed"
    assert findings[0].mode == "review"
    assert findings[0].evidence == {
        "connector": ("J1",),
        "controller": ("U1",),
        "connector_CC1_net": ("CC1_BUS",),
        "connector_CC2_net": ("CC2_BUS",),
        "controller_CC1_net": ("CC2_BUS",),
        "controller_CC2_net": ("CC1_BUS",),
        "nets": ("CC1_BUS", "CC2_BUS"),
    }
    assert "does not establish" not in findings[0].message
    assert "not proof" in findings[0].message


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_direct_mapping_and_other_incomplete_or_ambiguous_cases_are_controls() -> None:
    source = usb_c_cc_endpoint_pairing_netlist()
    cases = (
        usb_c_cc_endpoint_pairing_netlist(crossed=False),
        usb_c_cc_endpoint_pairing_netlist(same_net=True),
        usb_c_cc_endpoint_pairing_netlist(dnp=("J1",)),
        usb_c_cc_endpoint_pairing_netlist(dnp=("U1",)),
        usb_c_cc_endpoint_pairing_netlist(duplicate_controller_function=True),
        usb_c_cc_endpoint_pairing_netlist(incomplete_controller_inventory=True),
        usb_c_cc_endpoint_pairing_netlist(ambiguous_connector_assignment=True),
        source.model_copy(update={"components": {"J1": source.components["J1"]}}),
    )

    for case in cases:
        assert not crossed_usb_c_cc_endpoint_candidates(case)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_project_policy_can_block_disable_or_ignore_one_crossed_endpoint_finding() -> None:
    source = usb_c_cc_endpoint_pairing_netlist()
    initial = next(item for item in _report(source).findings if item.rule_id == RULE_ID)
    blocked = _report(
        source,
        DesignLintPolicy(
            rules=(DesignLintRuleOverride(rule_id=RULE_ID, mode="block", reason="Reviewed"),)
        ),
    )
    disabled = _report(
        source,
        DesignLintPolicy(
            rules=(DesignLintRuleOverride(rule_id=RULE_ID, mode="off", reason="Not applicable"),)
        ),
    )
    ignored = _report(
        source,
        DesignLintPolicy(
            ignores=(
                DesignLintIgnore(
                    rule_id=RULE_ID,
                    fingerprint=initial.fingerprint,
                    reason="Reviewed exact controller mapping",
                ),
            )
        ),
    )

    assert blocked.status == "FAIL"
    assert next(item for item in blocked.findings if item.rule_id == RULE_ID).mode == "block"
    assert (
        next(item for item in disabled.findings if item.rule_id == RULE_ID).disposition
        == "RULE_OFF"
    )
    assert (
        next(item for item in ignored.findings if item.rule_id == RULE_ID).disposition == "IGNORED"
    )


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_endpoint_order_is_stable_and_corrected_mapping_clears_the_finding() -> None:
    source = usb_c_cc_endpoint_pairing_netlist()
    reordered = source.model_copy(
        update={
            "nets": dict(reversed(tuple(source.nets.items()))),
            "pin_functions": dict(reversed(tuple(source.pin_functions.items()))),
        }
    )

    assert crossed_usb_c_cc_endpoint_candidates(source) == crossed_usb_c_cc_endpoint_candidates(
        reordered
    )
    assert not crossed_usb_c_cc_endpoint_candidates(
        usb_c_cc_endpoint_pairing_netlist(crossed=False)
    )
