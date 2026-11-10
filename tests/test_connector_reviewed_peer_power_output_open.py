"""Review an open mapped named power output beside an unlike peer."""

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

RULE_ID = "connector.reviewed_peer_power_output_open"


def _output_coverage(
    observed: NetlistContract,
    **kwargs: Any,
) -> ConnectorCoverageReport:
    """Build source-matched output maps for two synthetic connector peers."""
    parameters: dict[str, Any] = {
        "interface_signals": ("POWER_OUTPUT", "POWER_OUTPUT"),
        "roles": ("supply", "supply"),
        "directions": ("output", "output"),
        **kwargs,
    }
    return power_input_coverage(observed, **parameters)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_open_named_supply_output_beside_assigned_reviewed_peer_needs_review() -> None:
    observed = power_input_netlist(
        functions=("VBUS", "VDD_OUT"),
        electrical_type="power_out",
        power_assignments=(None, "SERIAL_5V"),
    )
    coverage = _output_coverage(observed)

    report = lint_report(observed, coverage)
    findings = tuple(item for item in report.findings if item.rule_id == RULE_ID)

    assert report.status == "REVIEW"
    assert len(findings) == 1
    assert findings[0].evidence["assignments"] == (
        "J1.1=<unassigned>",
        "J2.1=SERIAL_5V",
    )
    assert findings[0].evidence["native_pin_functions"] == ("J1.1=VBUS", "J2.1=VDD_OUT")
    assert findings[0].evidence["interface_directions"] == ("output", "output")
    assert "does not require connecting the contacts" in findings[0].message


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_open_output_is_symmetric_and_documented_or_two_sided_opens_stay_quiet() -> None:
    reversed_open = power_input_netlist(
        functions=("VBUS", "VDD_OUT"),
        electrical_type="power_out",
        power_assignments=("USB_5V", None),
    )
    reversed_findings = tuple(
        item
        for item in lint_report(reversed_open, _output_coverage(reversed_open)).findings
        if item.rule_id == RULE_ID
    )
    assert len(reversed_findings) == 1
    assert reversed_findings[0].evidence["assignments"] == (
        "J1.1=USB_5V",
        "J2.1=<unassigned>",
    )

    both_open = power_input_netlist(
        functions=("VBUS", "VDD_OUT"),
        electrical_type="power_out",
        power_assignments=(None, None),
    )
    documented = power_input_netlist(
        functions=("VBUS", "VDD_OUT"),
        electrical_type="power_out",
        power_assignments=(None, "SERIAL_5V"),
    )
    controls = (
        (both_open, _output_coverage(both_open)),
        (
            documented,
            _output_coverage(
                documented,
                unconnected_pin_reasons=("Synthetic intentionally unused output", None),
            ),
        ),
    )
    for observed, coverage in controls:
        assert RULE_ID not in {item.rule_id for item in lint_report(observed, coverage).findings}


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_open_output_requires_current_unambiguous_matching_peer_evidence() -> None:
    observed = power_input_netlist(
        functions=("VBUS", "VDD_OUT"),
        electrical_type="power_out",
        power_assignments=(None, "SERIAL_5V"),
    )
    stale = power_input_netlist(
        functions=("VBUS", "VDD_OUT"),
        electrical_type="power_out",
        power_assignments=(None, "SERIAL_5V_CHANGED"),
    )
    ambiguous = observed.model_copy(
        update={"nets": {**observed.nets, "SYNTHETIC_AMBIGUOUS": ("J2.1",)}}
    )
    same_symbol = power_input_netlist(
        functions=("VBUS", "VDD_OUT"),
        electrical_type="power_out",
        power_assignments=(None, "SERIAL_5V"),
        symbols=("Synthetic:SamePort", "Synthetic:SamePort"),
    )
    same_identity = power_input_netlist(
        functions=("VBUS", "VDD_OUT"),
        electrical_type="power_out",
        power_assignments=(None, "SERIAL_5V"),
        values=("same connector", "same connector"),
        footprints=("Synthetic:Port", "Synthetic:Port"),
    )
    part_id = power_input_netlist(
        functions=("VBUS", "VDD_OUT"),
        electrical_type="power_out",
        power_assignments=(None, "SERIAL_5V"),
        part_ids=("PART-A", "PART-B"),
    )
    dnp = power_input_netlist(
        functions=("VBUS", "VDD_OUT"),
        electrical_type="power_out",
        power_assignments=(None, "SERIAL_5V"),
        dnp=("J2",),
    )
    wrong_electrical_type = power_input_netlist(
        functions=("VBUS", "VDD_OUT"),
        electrical_type="power_in",
        power_assignments=(None, "SERIAL_5V"),
    )
    generic_functions = power_input_netlist(
        functions=("Pin_1", "Pin_1"),
        electrical_type="power_out",
        power_assignments=(None, "SERIAL_5V"),
    )
    cases = (
        (
            "different signals",
            observed,
            _output_coverage(observed, interface_signals=("USB_VBUS", "SERIAL_VDD")),
        ),
        (
            "different domains",
            observed,
            _output_coverage(observed, voltage_domains=("usb-5v", "serial-5v")),
        ),
        ("wrong role", observed, _output_coverage(observed, roles=("signal", "signal"))),
        ("wrong direction", observed, _output_coverage(observed, directions=("input", "input"))),
        (
            "different peer groups",
            observed,
            _output_coverage(observed, peer_groups=("usb", "serial")),
        ),
        ("incomplete map", observed, _output_coverage(observed, complete_maps=False)),
        ("unreviewed inventory", observed, _output_coverage(observed, inventory_reviewed=False)),
        ("stale map", stale, _output_coverage(observed)),
        ("ambiguous net", ambiguous, _output_coverage(ambiguous)),
        ("same symbols", same_symbol, _output_coverage(same_symbol)),
        ("same value and footprint", same_identity, _output_coverage(same_identity)),
        ("part ID", part_id, _output_coverage(part_id)),
        ("DNP peer", dnp, _output_coverage(dnp)),
        ("wrong electrical type", wrong_electrical_type, _output_coverage(wrong_electrical_type)),
        ("generic function", generic_functions, _output_coverage(generic_functions)),
    )
    for case_name, candidate, coverage in cases:
        findings = lint_report(candidate, coverage).findings
        assert RULE_ID not in {item.rule_id for item in findings}, case_name

    same_category = power_input_netlist(
        functions=("VBUS", "VBUS"),
        electrical_type="power_out",
        power_assignments=(None, "SERIAL_5V"),
    )
    assert RULE_ID not in {
        item.rule_id
        for item in lint_report(same_category, _output_coverage(same_category)).findings
    }


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_open_output_obeys_policy_exact_ignore_and_stable_net_order() -> None:
    observed = power_input_netlist(
        functions=("VBUS", "VDD_OUT"),
        electrical_type="power_out",
        power_assignments=(None, "SERIAL_5V"),
    )
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
                    reason="Synthetic policy blocks an unexplained open peer output.",
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
                    reason="Synthetic review accepts the intentional open output.",
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
    reordered_coverage = coverage.model_copy(update={"entries": tuple(reversed(coverage.entries))})
    reordered_map_finding = next(
        item
        for item in lint_report(observed, reordered_coverage).findings
        if item.rule_id == RULE_ID
    )

    assert blocked.status == "FAIL"
    assert any(
        item.rule_id == RULE_ID and item.disposition == "IGNORED" for item in ignored.findings
    )
    assert finding.fingerprint == reordered_finding.fingerprint
    assert finding.evidence == reordered_finding.evidence
    assert finding.fingerprint == reordered_map_finding.fingerprint
    assert finding.evidence == reordered_map_finding.evidence
