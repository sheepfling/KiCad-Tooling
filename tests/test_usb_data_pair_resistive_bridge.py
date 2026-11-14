"""Review direct fitted resistors across recognized USB 2.0 data pairs."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.design_lint_finding_models import (
    DesignLintIgnore,
    DesignLintRuleOverride,
)
from kicad_tooling.hwrepo.design_lint_policy_models import DesignLintPolicy
from kicad_tooling.hwrepo.design_lint_report_models import DesignLintReport
from kicad_tooling.hwrepo.models import NetlistContract
from kicad_tooling.hwrepo.usb_data_pair_resistive_bridge import (
    RULE_ID,
    usb_data_pair_resistive_bridge_candidates,
)
from tests.design_lint_fixtures import coach
from tests.design_lint_fixtures.usb_data_pair_resistive_bridge import (
    usb_data_pair_bridge_netlist,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint]


def _report(
    source: NetlistContract,
    *,
    mode: str | None = None,
    ignore: DesignLintIgnore | None = None,
) -> DesignLintReport:
    overrides = (
        ()
        if mode is None
        else (DesignLintRuleOverride(rule_id=RULE_ID, mode=mode, reason="Review USB termination"),)
    )
    return evaluate(
        "synthetic-usb-data-pair-resistive-bridge",
        coach(source),
        DesignLintPolicy(rules=overrides, ignores=() if ignore is None else (ignore,)),
    )


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_direct_resistor_across_separate_usb_data_nets_is_reviewed() -> None:
    source = usb_data_pair_bridge_netlist(value="90R")
    (candidate,) = usb_data_pair_resistive_bridge_candidates(source)
    report = _report(source)
    finding = next(item for item in report.findings if item.rule_id == RULE_ID)

    assert candidate.subject == (
        "U1: USB data port unindexed D+/D- nets USB_DP and USB_DM are bridged by R1"
    )
    assert candidate.evidence == {
        "component": ("U1",),
        "USB_port_group": ("unindexed",),
        "D+_pin": ("U1.1",),
        "D-_pin": ("U1.2",),
        "D+_net": ("USB_DP",),
        "D-_net": ("USB_DM",),
        "resistor": ("R1",),
        "resistance_ohms": ("90Ω",),
    }
    assert finding.mode == "review"
    assert finding.disposition == "OPEN"


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_intentional_and_inapplicable_passive_paths_are_controls() -> None:
    cases = (
        usb_data_pair_bridge_netlist(bridge="none"),
        usb_data_pair_bridge_netlist(bridge="resistor", resistor_dnp=True),
        usb_data_pair_bridge_netlist(bridge="capacitor"),
        usb_data_pair_bridge_netlist(bridge="series"),
    )
    assert all(not usb_data_pair_resistive_bridge_candidates(source) for source in cases)

    # Zero-ohm bridges remain visible because they still imply direct continuity.
    (zero_ohm,) = usb_data_pair_resistive_bridge_candidates(
        usb_data_pair_bridge_netlist(value="0R")
    )
    assert zero_ohm.evidence["resistance_ohms"] == ("0Ω",)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_incomplete_or_ambiguous_resistor_evidence_stays_quiet() -> None:
    source = usb_data_pair_bridge_netlist()
    extra_resistor_net = source.model_copy(update={"nets": {**source.nets, "OTHER": ("R1.1",)}})
    incomplete_resistor = source.model_copy(
        update={"component_pin_numbers": {**source.component_pin_numbers, "R1": ("1",)}}
    )
    unknown_value = source.model_copy(
        update={
            "components": {
                **source.components,
                "R1": source.components["R1"].model_copy(update={"value": "jumper"}),
            }
        }
    )
    missing_phy_inventory = source.model_copy(update={"component_pin_numbers": {"R1": ("1", "2")}})

    for control in (extra_resistor_net, incomplete_resistor, unknown_value, missing_phy_inventory):
        assert not usb_data_pair_resistive_bridge_candidates(control)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_rule_policy_can_block_disable_or_exact_ignore_review() -> None:
    source = usb_data_pair_bridge_netlist()
    default = next(item for item in _report(source).findings if item.rule_id == RULE_ID)
    assert _report(source, mode="block").status == "FAIL"
    off = next(item for item in _report(source, mode="off").findings if item.rule_id == RULE_ID)
    assert off.disposition == "RULE_OFF"

    ignore = DesignLintIgnore(
        rule_id=RULE_ID,
        fingerprint=default.fingerprint,
        reason="Synthetic intentional differential termination",
    )
    ignored = next(
        item for item in _report(source, ignore=ignore).findings if item.rule_id == RULE_ID
    )
    assert ignored.disposition == "IGNORED"


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_result_order_is_stable_under_net_and_component_reordering() -> None:
    source = usb_data_pair_bridge_netlist()
    reordered = source.model_copy(
        update={
            "components": dict(reversed(tuple(source.components.items()))),
            "nets": dict(reversed(tuple(source.nets.items()))),
            "component_symbols": dict(reversed(tuple(source.component_symbols.items()))),
            "pin_functions": dict(reversed(tuple(source.pin_functions.items()))),
            "component_pin_numbers": dict(reversed(tuple(source.component_pin_numbers.items()))),
        }
    )
    assert usb_data_pair_resistive_bridge_candidates(source) == (
        usb_data_pair_resistive_bridge_candidates(reordered)
    )
