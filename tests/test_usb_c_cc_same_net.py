"""Focused regressions for USB-C connector CC1/CC2 pins sharing one net."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.design_lint import candidates, evaluate
from kicad_tooling.hwrepo.design_lint_finding_models import DesignLintIgnore
from kicad_tooling.hwrepo.design_lint_policy_models import DesignLintPolicy
from kicad_tooling.hwrepo.models import DesignLintRuleOverride, NetlistContract
from kicad_tooling.hwrepo.usb_c_cc_same_net import (
    RULE_ID,
    usb_c_cc_same_net_candidates,
)
from tests.design_lint_fixtures import coach
from tests.design_lint_fixtures.usb_c_cc_same_net import usb_c_cc_same_net_netlist

pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint]


def _report(
    source: NetlistContract,
    *,
    mode: str | None = None,
    ignore: DesignLintIgnore | None = None,
):
    overrides = ()
    if mode is not None:
        overrides = (
            DesignLintRuleOverride(rule_id=RULE_ID, mode=mode, reason="Reviewed test policy"),
        )
    policy = DesignLintPolicy(rules=overrides, ignores=() if ignore is None else (ignore,))
    return evaluate("synthetic-usb-c-cc-same-net", coach(source), policy)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_unique_connector_cc1_cc2_pins_on_one_net_request_review() -> None:
    source = usb_c_cc_same_net_netlist()
    report = _report(source)
    findings = tuple(item for item in report.findings if item.rule_id == RULE_ID)

    assert len(findings) == 1
    finding = findings[0]
    assert report.status == "REVIEW"
    assert finding.subject == "J1: USB-C CC1/CC2 pins share CC_SHARED"
    assert finding.mode == "review"
    assert finding.evidence == {
        "connector": ("J1",),
        "CC1_pin": ("J1.1",),
        "CC1_function": ("CC1",),
        "CC2_pin": ("J1.2",),
        "CC2_function": ("CC2",),
        "net": ("CC_SHARED",),
    }
    assert "does not establish the exact connector behavior" in finding.message
    assert "USB-C compliance" in finding.message


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_distinct_cc_nets_and_unreviewed_non_connector_are_controls() -> None:
    separated = usb_c_cc_same_net_netlist(shared=False)
    controller = usb_c_cc_same_net_netlist(reference="U1", symbol="Synthetic:USB_C_Controller")

    assert not any(item.rule_id == RULE_ID for item in _report(separated).findings)
    assert not any(item.rule_id == RULE_ID for item in usb_c_cc_same_net_candidates(controller))


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_aliases_need_reviewed_connector_identity_when_reference_is_custom() -> None:
    custom = usb_c_cc_same_net_netlist(
        reference="PORT_A",
        symbol="Synthetic:USB_C_Port",
        cc1_function="CC-1",
        cc2_function="cc_2",
    )

    assert not usb_c_cc_same_net_candidates(custom)
    findings = usb_c_cc_same_net_candidates(custom, ("PORT_A",))
    assert len(findings) == 1
    assert findings[0].evidence["CC1_function"] == ("CC-1",)
    assert findings[0].evidence["CC2_function"] == ("cc_2",)
    assert (
        tuple(
            item.rule_id for item in candidates(custom, reviewed_connector_references=("PORT_A",))
        ).count(RULE_ID)
        == 1
    )


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_dnp_open_ambiguous_duplicate_and_incomplete_evidence_is_skipped() -> None:
    source = usb_c_cc_same_net_netlist()
    unsupported = (
        usb_c_cc_same_net_netlist(dnp=True),
        source.model_copy(update={"nets": {"CC2_BUS": ("J1.2",)}}),
        source.model_copy(update={"nets": {"CC_SHARED": ("J1.1", "J1.2"), "OTHER": ("J1.1",)}}),
        source.model_copy(update={"component_pin_numbers": {}}),
        source.model_copy(update={"component_pin_numbers": {"J1": ("1",)}}),
        source.model_copy(
            update={
                "pin_functions": {"J1.1": "CC1", "J1.2": "CC2", "J1.3": "CC1"},
                "component_pin_numbers": {"J1": ("1", "2", "3")},
                "nets": {"CC_SHARED": ("J1.1", "J1.2", "J1.3")},
            }
        ),
    )

    for case in unsupported:
        assert not usb_c_cc_same_net_candidates(case)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_policy_can_block_disable_or_exactly_ignore_shared_cc_assignment() -> None:
    source = usb_c_cc_same_net_netlist()
    initial = next(item for item in _report(source).findings if item.rule_id == RULE_ID)
    blocked = _report(source, mode="block")
    disabled = _report(source, mode="off")
    ignored = _report(
        source,
        ignore=DesignLintIgnore(
            rule_id=RULE_ID,
            fingerprint=initial.fingerprint,
            reason="Reviewed USB-C connector assignment for this port mode",
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
def test_finding_order_is_stable_and_separating_cc_nets_clears_it() -> None:
    source = usb_c_cc_same_net_netlist()
    reordered = source.model_copy(
        update={
            "nets": dict(reversed(tuple(source.nets.items()))),
            "pin_functions": dict(reversed(tuple(source.pin_functions.items()))),
        }
    )

    assert tuple(
        item.model_dump() for item in _report(source).findings if item.rule_id == RULE_ID
    ) == tuple(item.model_dump() for item in _report(reordered).findings if item.rule_id == RULE_ID)
    assert not usb_c_cc_same_net_candidates(usb_c_cc_same_net_netlist(shared=False))
