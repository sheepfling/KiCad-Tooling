"""Focused regressions for USB 2.0 D+/D- assigned to one net."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.design_lint_finding_models import (
    DesignLintFinding,
    DesignLintIgnore,
    DesignLintRuleOverride,
)
from kicad_tooling.hwrepo.design_lint_policy_models import DesignLintPolicy
from kicad_tooling.hwrepo.design_lint_report_models import DesignLintReport
from kicad_tooling.hwrepo.models import NetlistContract
from kicad_tooling.hwrepo.usb_data_same_net import (
    RULE_ID,
    usb_data_same_net_candidates,
)
from tests.design_lint_fixtures import coach
from tests.design_lint_fixtures.usb_data_same_net import usb_data_same_net_netlist

pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint]


def _findings(source: NetlistContract) -> tuple[DesignLintFinding, ...]:
    report = evaluate("synthetic-usb-data-same-net", coach(source), DesignLintPolicy())
    return tuple(item for item in report.findings if item.rule_id == RULE_ID)


def _report(
    source: NetlistContract,
    *,
    mode: str | None = None,
    ignore: DesignLintIgnore | None = None,
) -> DesignLintReport:
    overrides = (
        ()
        if mode is None
        else (
            DesignLintRuleOverride(
                rule_id=RULE_ID,
                mode=mode,
                reason="Review the synthetic USB data pair",
            ),
        )
    )
    return evaluate(
        "synthetic-usb-data-same-net",
        coach(source),
        DesignLintPolicy(rules=overrides, ignores=() if ignore is None else (ignore,)),
    )


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_usb_data_pins_on_same_net_are_reviewed_and_separate_lines_are_control() -> None:
    fault = usb_data_same_net_netlist()
    findings = _findings(fault)

    assert len(findings) == 1
    assert findings[0].subject == "U1: USB data port unindexed D+/D- pins share USB_SHARED"
    assert findings[0].evidence == {
        "component": ("U1",),
        "USB_port_group": ("unindexed",),
        "D+_pin": ("U1.1",),
        "D-_pin": ("U1.2",),
        "D+_electrical_type": ("bidirectional",),
        "D-_electrical_type": ("bidirectional",),
        "net": ("USB_SHARED",),
    }
    assert not _findings(usb_data_same_net_netlist(shared=False))


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_numbered_ports_are_independent_and_function_aliases_are_bounded() -> None:
    source = usb_data_same_net_netlist(
        positive_function="USB1_D+",
        negative_function="USB1_D-",
    )
    assert _findings(source)[0].evidence["USB_port_group"] == ("1",)

    mismatched = source.model_copy(update={"pin_functions": {"U1.1": "USB1_D+", "U1.2": "USB2_D-"}})
    unsupported = source.model_copy(
        update={"pin_functions": {"U1.1": "USB_AUX+", "U1.2": "USB_AUX-"}}
    )
    assert not _findings(mismatched)
    assert not usb_data_same_net_candidates(unsupported)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_dnp_open_duplicate_ambiguous_and_incomplete_evidence_are_skipped() -> None:
    source = usb_data_same_net_netlist()
    dnp = source.model_copy(update={"dnp_components": ("U1",)})
    open_negative = source.model_copy(update={"nets": {"USB_SHARED": ("U1.1",)}})
    multiply_assigned = source.model_copy(update={"nets": {**source.nets, "OTHER": ("U1.1",)}})
    duplicate_positive = source.model_copy(
        update={
            "pin_functions": {**source.pin_functions, "U1.3": "USB D+"},
            "component_pin_numbers": {"U1": ("1", "2", "3")},
            "nets": {"USB_SHARED": ("U1.1", "U1.2", "U1.3")},
        }
    )
    missing_inventory = source.model_copy(update={"component_pin_numbers": {}})
    stale_inventory = source.model_copy(
        update={"pin_functions": {**source.pin_functions, "U1.3": "USB D+"}}
    )
    output_pair = usb_data_same_net_netlist(positive_type="output", negative_type="output")

    for control in (
        dnp,
        open_negative,
        multiply_assigned,
        duplicate_positive,
        missing_inventory,
        stale_inventory,
        output_pair,
    ):
        assert not _findings(control)
        assert not usb_data_same_net_candidates(control)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_two_output_pins_are_left_to_native_erc() -> None:
    outputs = usb_data_same_net_netlist(positive_type="output", negative_type="output")
    assert not _findings(outputs)
    assert not usb_data_same_net_candidates(outputs)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_policy_override_and_exact_ignore_control_review() -> None:
    source = usb_data_same_net_netlist()
    default_report = _report(source)
    default = next(item for item in default_report.findings if item.rule_id == RULE_ID)
    assert default.mode == "review"

    blocked = _report(source, mode="block")
    assert blocked.status == "FAIL"

    disabled = _report(source, mode="off")
    disabled_finding = next(item for item in disabled.findings if item.rule_id == RULE_ID)
    assert disabled_finding.disposition == "RULE_OFF"

    ignore = DesignLintIgnore(
        rule_id=RULE_ID,
        fingerprint=default.fingerprint,
        reason="Synthetic intentional single-line test configuration",
    )
    ignored = _report(source, ignore=ignore)
    ignored_finding = next(item for item in ignored.findings if item.rule_id == RULE_ID)
    assert ignored_finding.disposition == "IGNORED"
