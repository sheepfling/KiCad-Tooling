"""Deterministic USB data-pin reviews for direct named-rail assignments."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.models import (
    ContractCoachReport,
    DesignLintIgnore,
    DesignLintPolicy,
    DesignLintRuleOverride,
    NetlistContract,
)
from tests.design_lint_fixtures.usb_signal_named_rail import usb_signal_on_named_rail_netlist

RULE_ID = "bus.usb_signal_on_named_rail"
pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint]


def _report(observed: NetlistContract, policy: DesignLintPolicy | None = None):
    project_id = "synthetic-usb-signal-named-rail"
    return evaluate(
        project_id,
        ContractCoachReport(status="READY_FOR_REVIEW", project_id=project_id, observed=observed),
        policy or DesignLintPolicy(),
    )


@pytest.mark.parametrize(
    ("function", "pin", "rail", "family", "side"),
    (
        ("USB_DP", "U1.1", "GND", "USB 2.0 data", "positive"),
        ("USB_DM", "U1.2", "+3V3", "USB 2.0 data", "negative"),
        ("DP1", "U1.1", "GND", "USB 2.0 data port 1", "positive"),
        ("DM1", "U1.2", "+5V", "USB 2.0 data port 1", "negative"),
        ("SSTX+", "U1.1", "GND", "USB SuperSpeed TX", "positive"),
        ("STDASSTX-", "U1.2", "+3V3", "USB SuperSpeed TX", "negative"),
        ("SSRX+", "U1.1", "GND", "USB SuperSpeed RX", "positive"),
        ("STDBSSRX-", "U1.2", "+5V", "USB SuperSpeed RX", "negative"),
    ),
)
def test_supported_usb_data_functions_on_named_rails_request_review(
    function: str, pin: str, rail: str, family: str, side: str
) -> None:
    report = _report(usb_signal_on_named_rail_netlist(function=function, pin=pin, rail_name=rail))
    findings = tuple(item for item in report.findings if item.rule_id == RULE_ID)

    assert report.status == "REVIEW"
    assert len(findings) == 1
    assert (
        findings[0].subject
        == f"{pin}: {function} on {'return-like' if rail == 'GND' else 'supply-like'} net {rail}"
    )
    assert findings[0].evidence["usb_signal_family"] == (family,)
    assert findings[0].evidence["usb_pair_side"] == (side,)


@pytest.mark.parametrize("function", ("VBUS", "CC1", "SBU1", "TXD", "USB_D0"))
def test_power_control_and_unrecognized_functions_are_quiet(function: str) -> None:
    report = _report(usb_signal_on_named_rail_netlist(function=function))

    assert not any(item.rule_id == RULE_ID for item in report.findings)


def test_neutral_net_labels_do_not_request_review() -> None:
    report = _report(usb_signal_on_named_rail_netlist(rail_name="USB_D+"))

    assert not any(item.rule_id == RULE_ID for item in report.findings)


def test_dnp_open_ambiguous_duplicate_connector_and_incomplete_cases_are_skipped() -> None:
    source = usb_signal_on_named_rail_netlist()
    controls = (
        source.model_copy(update={"dnp_components": ("U1",)}),
        source.model_copy(update={"nets": {"USB_DM_NET": ("U1.2",)}}),
        source.model_copy(update={"nets": {"GND": ("U1.1",), "+3V3": ("U1.1",)}}),
        source.model_copy(update={"pin_functions": {"U1.1": "USB_DP", "u1.1": "USB_DM"}}),
        source.model_copy(update={"component_pin_numbers": {"U1": ("2",)}}),
        source.model_copy(
            update={
                "components": {"J1": source.components["U1"]},
                "nets": {"GND": ("J1.1",), "USB_DM_NET": ("J1.2",)},
                "component_symbols": {"J1": "Connector:USB_A"},
                "pin_functions": {"J1.1": "USB_DP", "J1.2": "USB_DM"},
                "component_pin_numbers": {"J1": ("1", "2")},
            }
        ),
    )

    for control in controls:
        assert not any(item.rule_id == RULE_ID for item in _report(control).findings)


def test_project_policy_can_block_disable_or_ignore_a_reviewed_strap() -> None:
    source = usb_signal_on_named_rail_netlist()
    finding = next(item for item in _report(source).findings if item.rule_id == RULE_ID)
    blocked = _report(
        source,
        DesignLintPolicy(
            rules=(DesignLintRuleOverride(rule_id=RULE_ID, mode="block", reason="reviewed"),)
        ),
    )
    disabled = _report(
        source,
        DesignLintPolicy(
            rules=(DesignLintRuleOverride(rule_id=RULE_ID, mode="off", reason="reviewed"),)
        ),
    )
    ignored = _report(
        source,
        DesignLintPolicy(
            ignores=(
                DesignLintIgnore(
                    rule_id=RULE_ID,
                    fingerprint=finding.fingerprint,
                    reason="USB pin is intentionally strapped",
                ),
            )
        ),
    )

    assert blocked.status == "FAIL"
    assert (
        next(item for item in disabled.findings if item.rule_id == RULE_ID).disposition
        == "RULE_OFF"
    )
    assert (
        next(item for item in ignored.findings if item.rule_id == RULE_ID).disposition == "IGNORED"
    )


def test_assignment_order_is_stable_and_neutral_repair_clears_review() -> None:
    fault = usb_signal_on_named_rail_netlist()
    reordered = fault.model_copy(
        update={
            "nets": dict(reversed(tuple(fault.nets.items()))),
            "pin_functions": dict(reversed(tuple(fault.pin_functions.items()))),
        }
    )
    repaired = fault.model_copy(update={"nets": {"USB_DP_NET": ("U1.1",), "USB_DM_NET": ("U1.2",)}})

    findings = tuple(item for item in _report(fault).findings if item.rule_id == RULE_ID)
    reordered_findings = tuple(
        item for item in _report(reordered).findings if item.rule_id == RULE_ID
    )
    assert tuple(item.model_dump() for item in findings) == tuple(
        item.model_dump() for item in reordered_findings
    )
    assert not any(item.rule_id == RULE_ID for item in _report(repaired).findings)
