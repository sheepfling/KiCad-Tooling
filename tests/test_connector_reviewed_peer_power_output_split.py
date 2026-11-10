"""Review split mapped named power outputs across reviewed connector peers."""

from __future__ import annotations

from typing import Any

import pytest

from kicad_tooling.hwrepo.connector_coverage_models import ConnectorCoverageReport
from kicad_tooling.hwrepo.models import DesignLintIgnore, DesignLintPolicy, DesignLintRuleOverride
from kicad_tooling.hwrepo.netlist_contract_models import NetlistContract
from tests.design_lint_fixtures.connector_reviewed_peer_power_input import (
    lint_report,
    power_input_coverage,
    power_input_netlist,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.connector_lint, pytest.mark.power_lint]

RULE_ID = "connector.reviewed_peer_power_output_split"


def _output_coverage(observed: NetlistContract, **kwargs: Any) -> ConnectorCoverageReport:
    """Build current synthetic output maps with the requested adjustments."""
    parameters = {
        "interface_signals": ("POWER_OUTPUT", "POWER_OUTPUT"),
        "roles": ("supply", "supply"),
        "directions": ("output", "output"),
        **kwargs,
    }
    return power_input_coverage(observed, **parameters)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_different_named_supply_outputs_split_across_reviewed_peers_need_review() -> None:
    observed = power_input_netlist(functions=("VBUS", "VDD_OUT"), electrical_type="power_out")

    report = lint_report(observed, _output_coverage(observed))
    findings = tuple(item for item in report.findings if item.rule_id == RULE_ID)

    assert report.status == "REVIEW"
    assert len(findings) == 1
    finding = findings[0]
    assert finding.subject == (
        "reviewed-synthetic-power-peers: POWER_OUTPUT (external-5v) "
        "named power outputs use separate nets"
    )
    assert finding.evidence["assignments"] == ("J1.1=USB_5V", "J2.1=SERIAL_5V")
    assert finding.evidence["native_pin_functions"] == ("J1.1=VBUS", "J2.1=VDD_OUT")
    assert finding.evidence["power_role_categories"] == ("vbus", "vdd")
    assert finding.evidence["interface_directions"] == ("output", "output")
    assert "does not prove these nets should be joined" in finding.message
    assert {item.rule_id for item in report.findings} == {RULE_ID}


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_common_same_function_and_nonoutput_directions_stay_quiet() -> None:
    controls = (
        (
            power_input_netlist(
                functions=("VBUS", "VDD_OUT"),
                electrical_type="power_out",
                power_assignments=("COMMON_5V", "COMMON_5V"),
            ),
            ("output", "output"),
        ),
        (
            power_input_netlist(functions=("VBUS", "VBUS"), electrical_type="power_out"),
            ("output", "output"),
        ),
        (
            power_input_netlist(functions=("VBUS", "VDD_OUT"), electrical_type="power_out"),
            ("input", "input"),
        ),
    )
    for observed, directions in controls:
        coverage = power_input_coverage(
            observed,
            interface_signals=("POWER_OUTPUT", "POWER_OUTPUT"),
            roles=("supply", "supply"),
            directions=directions,
        )
        assert RULE_ID not in {item.rule_id for item in lint_report(observed, coverage).findings}


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_role_domain_peer_identity_and_native_type_boundaries_stay_quiet() -> None:
    default = {"functions": ("VBUS", "VDD_OUT"), "electrical_type": "power_out"}
    controls = (
        (power_input_netlist(**default), {"peer_groups": ("usb", "serial")}),
        (power_input_netlist(**default), {"interface_signals": ("VBUS", "VDD_OUT")}),
        (power_input_netlist(**default), {"voltage_domains": ("usb-5v", "serial-5v")}),
        (power_input_netlist(**default), {"roles": ("signal", "signal")}),
        (power_input_netlist(functions=default["functions"], electrical_type="power_in"), {}),
        (
            power_input_netlist(**default, symbols=("Synthetic:SamePort", "Synthetic:SamePort")),
            {},
        ),
        (
            power_input_netlist(
                **default,
                values=("same connector", "same connector"),
                footprints=("Synthetic:Port", "Synthetic:Port"),
            ),
            {},
        ),
        (power_input_netlist(**default, part_ids=("PART-A", "PART-B")), {}),
        (power_input_netlist(**default, dnp=("J2",)), {}),
    )
    for observed, coverage_kwargs in controls:
        coverage = _output_coverage(observed, **coverage_kwargs)
        assert RULE_ID not in {item.rule_id for item in lint_report(observed, coverage).findings}


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_stale_incomplete_open_and_ambiguous_evidence_stay_quiet() -> None:
    observed = power_input_netlist(functions=("VBUS", "VDD_OUT"), electrical_type="power_out")
    current = _output_coverage(observed)
    changed = power_input_netlist(
        functions=("VBUS", "VDD_OUT"),
        electrical_type="power_out",
        power_assignments=("USB_5V_CHANGED", "SERIAL_5V"),
    )
    open_contact = power_input_netlist(
        functions=("VBUS", "VDD_OUT"),
        electrical_type="power_out",
        power_assignments=("USB_5V", None),
    )
    ambiguous = observed.model_copy(
        update={"nets": {**observed.nets, "SYNTHETIC_AMBIGUOUS": ("J1.1",)}}
    )
    cases = (
        (changed, current),
        (observed, _output_coverage(observed, complete_maps=False)),
        (open_contact, _output_coverage(open_contact)),
        (ambiguous, _output_coverage(ambiguous)),
    )
    for candidate, coverage in cases:
        assert RULE_ID not in {item.rule_id for item in lint_report(candidate, coverage).findings}


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_policy_exact_ignore_and_netlist_order_are_deterministic() -> None:
    observed = power_input_netlist(functions=("VBUS", "VDD_OUT"), electrical_type="power_out")
    coverage = _output_coverage(observed)
    baseline = lint_report(observed, coverage)
    finding = next(item for item in baseline.findings if item.rule_id == RULE_ID)
    blocked = lint_report(
        observed,
        coverage,
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=RULE_ID,
                    mode="block",
                    reason="Synthetic policy blocks review of split supply outputs.",
                ),
            )
        ),
    )
    ignored = lint_report(
        observed,
        coverage,
        DesignLintPolicy(
            ignores=(
                DesignLintIgnore(
                    rule_id=RULE_ID,
                    fingerprint=finding.fingerprint,
                    reason="Synthetic review approves intentionally separate sources.",
                ),
            )
        ),
    )
    reordered = observed.model_copy(update={"nets": dict(reversed(tuple(observed.nets.items())))})
    reordered_finding = next(
        item
        for item in lint_report(reordered, _output_coverage(reordered)).findings
        if item.rule_id == RULE_ID
    )

    assert blocked.status == "FAIL"
    assert any(
        item.rule_id == RULE_ID and item.disposition == "IGNORED" for item in ignored.findings
    )
    assert finding.fingerprint == reordered_finding.fingerprint
    assert finding.evidence == reordered_finding.evidence
