"""Power-output peer-pin lint regression cases."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from kicad_tooling.hwrepo.models import (
    DesignLintIgnore,
    DesignLintPolicy,
    DesignLintRuleOverride,
    NetlistContract,
)
from tests.component_peer_pin_native_support import _run_native_peer_pin_assignment_lane
from tests.component_peer_pin_support import (
    RULE_ID,
    component_peer_coverage,
    lint_report,
    peer_power_output_netlist,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.component_lint, pytest.mark.power_lint]


def test_reports_an_open_native_power_output_pin_when_an_exact_peer_is_connected() -> None:
    report = lint_report(peer_power_output_netlist())
    findings = [item for item in report.findings if item.rule_id == RULE_ID]

    assert report.status == "REVIEW"
    assert len(findings) == 1
    finding = findings[0]
    assert finding.mode == "review"
    assert finding.evidence["symbol"] == ("Synthetic:PowerModule",)
    assert finding.evidence["pin_number"] == ("2",)
    assert finding.evidence["pin_electrical_type"] == ("power_out",)
    assert finding.evidence["unassigned_pins"] == ("U2.2",)
    assert finding.evidence["U1.2"] == ("VOUT",)
    assert finding.evidence["U2.2"] == ()
    assert "do not require peer pins to share a net" in finding.message
    assert "component.unconnected_power_input" not in {item.rule_id for item in report.findings}
    coverage = component_peer_coverage(report, RULE_ID)
    assert coverage.status == "EVALUATED"
    assert coverage.netlist_sha256 == report.netlist_sha256
    assert coverage.exact_symbol_peer_group_count == 1
    assert coverage.complete_pin_inventory_group_count == 1
    assert coverage.comparable_pin_group_count == 2
    assert coverage.matching_electrical_type_pin_group_count == 1
    assert coverage.compatible_function_pin_group_count == 1
    assert coverage.unambiguous_assignment_pin_group_count == 1
    assert coverage.candidate_group_count == coverage.finding_count == 1
    assert coverage.suppressed_candidate_count == 0


def test_reports_open_pin_across_native_symbol_aliases_with_the_same_part_id() -> None:
    observed = peer_power_output_netlist(
        symbols={"U1": "Synthetic:PowerModule", "U2": "Synthetic:PowerModuleAlias"},
        part_ids={"U1": "synthetic-power-module-001", "U2": "SYNTHETIC-POWER-MODULE-001"},
    )
    report = lint_report(observed)
    findings = [item for item in report.findings if item.rule_id == RULE_ID]

    assert len(findings) == 1
    finding = findings[0]
    assert finding.evidence["peer_group_basis"] == ("part_id",)
    assert finding.evidence["peer_group_identity"] == ("SYNTHETIC-POWER-MODULE-001",)
    assert finding.evidence["peer_group_symbols"] == (
        "Synthetic:PowerModule",
        "Synthetic:PowerModuleAlias",
    )
    assert finding.evidence["unassigned_pins"] == ("U2.2",)
    assert "same native PART_ID" in finding.message
    coverage = component_peer_coverage(report, RULE_ID)
    assert coverage.status == "EVALUATED"
    assert coverage.exact_symbol_peer_group_count == 0
    assert coverage.part_id_peer_group_count == 1
    assert coverage.candidate_group_count == coverage.finding_count == 1
    assert coverage.deduplicated_candidate_group_count == 0
    reordered = lint_report(
        observed.model_copy(
            update={
                "components": dict(reversed(tuple(observed.components.items()))),
                "nets": dict(reversed(tuple(observed.nets.items()))),
                "component_symbols": dict(reversed(tuple(observed.component_symbols.items()))),
                "pin_functions": dict(reversed(tuple(observed.pin_functions.items()))),
                "pin_electrical_types": dict(
                    reversed(tuple(observed.pin_electrical_types.items()))
                ),
                "component_pin_numbers": dict(
                    reversed(tuple(observed.component_pin_numbers.items()))
                ),
            }
        )
    )
    reordered_finding = next(item for item in reordered.findings if item.rule_id == RULE_ID)
    assert (reordered_finding.fingerprint, reordered_finding.evidence) == (
        finding.fingerprint,
        finding.evidence,
    )


@pytest.mark.parametrize(
    "output_nets",
    (("VOUT", "VOUT"), ("VOUT_A", "VOUT_B")),
)
def test_assigned_peer_outputs_are_valid_same_or_separate_net_controls(
    output_nets: tuple[str, str],
) -> None:
    report = lint_report(peer_power_output_netlist(output_nets=output_nets))

    assert RULE_ID not in {item.rule_id for item in report.findings}
    assert report.status == "PASS"


@pytest.mark.parametrize(
    "observed",
    (
        peer_power_output_netlist(output_nets=(None, None)),
        peer_power_output_netlist(output_nets=("VOUT", None), dnp=("U2",)),
        peer_power_output_netlist(
            output_nets=("VOUT", None),
            symbols={"U1": "Synthetic:SourceA", "U2": "Synthetic:SourceB"},
        ),
        peer_power_output_netlist(output_nets=("VOUT", None), missing_inventory=("U2",)),
        peer_power_output_netlist(output_nets=("VOUT", None), ambiguous_outputs=("U1",)),
        peer_power_output_netlist(
            output_nets=("VOUT", None), output_electrical_types=("power_in", "power_in")
        ),
    ),
)
def test_skips_open_all_dnp_different_symbol_incomplete_ambiguous_and_non_output_cases(
    observed: NetlistContract,
) -> None:
    assert RULE_ID not in {item.rule_id for item in lint_report(observed).findings}


@pytest.mark.parametrize("output_function", ("VDD", "GND"))
def test_named_supply_and_return_outputs_keep_their_specific_findings(
    output_function: str,
) -> None:
    report = lint_report(peer_power_output_netlist(output_function=output_function))
    findings = {item.rule_id: item for item in report.findings}

    assert RULE_ID not in findings
    specific_rule = (
        "component.unconnected_return_pin"
        if output_function == "GND"
        else "component.unconnected_supply_pin"
    )
    assert specific_rule in findings
    assert findings[specific_rule].evidence["U2.2"] == ()


def test_shield_named_power_output_remains_eligible_without_a_component_shield_rule() -> None:
    report = lint_report(peer_power_output_netlist(output_function="SHIELD"))
    findings = {item.rule_id: item for item in report.findings}

    assert RULE_ID in findings
    assert "component.unconnected_return_pin" not in findings
    assert findings[RULE_ID].evidence["unassigned_pins"] == ("U2.2",)


def test_rule_policy_and_exact_ignore_are_project_configurable() -> None:
    observed = peer_power_output_netlist()
    original = lint_report(observed)
    finding = next(item for item in original.findings if item.rule_id == RULE_ID)

    blocked = lint_report(
        observed,
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=RULE_ID,
                    mode="block",
                    reason="Synthetic project requires every peer output to be disposed",
                ),
            )
        ),
    )
    assert blocked.status == "FAIL"

    disabled = lint_report(
        observed,
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=RULE_ID,
                    mode="off",
                    reason="Synthetic project disables this peer-output prompt",
                ),
            )
        ),
    )
    assert disabled.status == "PASS"
    assert next(item for item in disabled.findings if item.rule_id == RULE_ID).disposition == (
        "RULE_OFF"
    )

    ignored = lint_report(
        observed,
        DesignLintPolicy(
            ignores=(
                DesignLintIgnore(
                    rule_id=RULE_ID,
                    fingerprint=finding.fingerprint,
                    reason="Synthetic project accepts the intentionally open peer output",
                ),
            )
        ),
    )
    ignored_finding = next(
        item for item in ignored.findings if item.fingerprint == finding.fingerprint
    )
    assert ignored_finding.disposition == "IGNORED"


def test_finding_is_stable_under_map_order_changes() -> None:
    source = peer_power_output_netlist()
    original = lint_report(source)
    reordered_source = source.model_copy(
        update={
            "components": dict(reversed(tuple(source.components.items()))),
            "nets": dict(reversed(tuple(source.nets.items()))),
            "component_symbols": dict(reversed(tuple(source.component_symbols.items()))),
            "pin_functions": dict(reversed(tuple(source.pin_functions.items()))),
            "pin_electrical_types": dict(reversed(tuple(source.pin_electrical_types.items()))),
            "component_pin_numbers": dict(reversed(tuple(source.component_pin_numbers.items()))),
        }
    )
    reordered = lint_report(reordered_source)
    original_findings = {
        item.subject: (item.fingerprint, item.evidence)
        for item in original.findings
        if item.rule_id == RULE_ID
    }
    reordered_findings = {
        item.subject: (item.fingerprint, item.evidence)
        for item in reordered.findings
        if item.rule_id == RULE_ID
    }

    assert reordered_findings == original_findings


@pytest.mark.native_kicad
@pytest.mark.slow
@pytest.mark.skipif(
    os.environ.get("KICAD_RUN_NATIVE_COMPONENT_PEER_PIN_FIXTURES") != "1",
    reason="pinned native fixtures run in package acceptance",
)
def test_peer_power_output_fault_and_control_on_pinned_native_versions(tmp_path: Path) -> None:
    _run_native_peer_pin_assignment_lane("power", tmp_path)
