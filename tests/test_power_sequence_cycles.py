"""Synthetic regressions for declared and observed power-sequence cycles."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.power_sequences import (
    power_sequence_graph_has_cycle,
    power_sequence_mismatches,
    power_sequence_observed_enable_cycles,
)
from tests.power_sequence_support import (
    RULE_ID,
    lint_report,
    power_sequence_map,
    power_sequence_netlist,
    power_sequence_output_cycle_map,
    power_sequence_output_cycle_netlist,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.power_lint]


def test_cycle_in_explicit_requirement_is_reported() -> None:
    sequence_map = power_sequence_map(cycle=True)
    report = lint_report(power_sequence_netlist(cycle=True), sequence_map)
    finding = next(item for item in report.findings if item.rule_id == RULE_ID)

    assert any("graph is cyclic" in issue for issue in finding.evidence["issues"])
    assert power_sequence_graph_has_cycle(sequence_map)


def test_mapped_output_to_enable_cycle_is_detected_with_acyclic_requirement_graph() -> None:
    sequence_map = power_sequence_output_cycle_map(cycle=True)
    observed = power_sequence_output_cycle_netlist(cycle=True)
    assert not power_sequence_graph_has_cycle(sequence_map)
    assert power_sequence_mismatches(sequence_map, observed) == ()

    cycles = power_sequence_observed_enable_cycles(sequence_map, observed)
    assert len(cycles) == 1
    assert cycles[0].stage_ids == ("rail-a", "rail-b")
    assert cycles[0].edges == (
        "rail-a output U1.2 on RAIL_A → rail-b enable U2.1",
        "rail-b output U2.2 on RAIL_B → rail-a enable U1.1",
    )

    report = lint_report(observed, sequence_map)
    assert report.status == "REVIEW"
    finding = next(item for item in report.findings if item.rule_id == RULE_ID)
    assert finding.evidence["declared_dependency_cycle"] == ("false",)
    assert finding.evidence["observed_output_to_enable_cycle_stages"] == ("rail-a, rail-b",)
    assert finding.evidence["observed_output_to_enable_cycle_edges"] == cycles[0].edges

    dnp_stage = observed.model_copy(update={"dnp_components": ("U2",)})
    assert not power_sequence_observed_enable_cycles(sequence_map, dnp_stage)

    wrong_enable_nets = dict(observed.nets)
    wrong_enable_nets["RAIL_A"] = ("U1.2",)
    wrong_enable_nets["UNEXPECTED"] = ("U2.1",)
    mismapped_stage = observed.model_copy(update={"nets": wrong_enable_nets})
    assert not power_sequence_observed_enable_cycles(sequence_map, mismapped_stage)

    reordered = observed.model_copy(
        update={
            "nets": dict(reversed(tuple(observed.nets.items()))),
            "components": dict(reversed(tuple(observed.components.items()))),
            "component_symbols": dict(reversed(tuple(observed.component_symbols.items()))),
            "component_pin_numbers": dict(reversed(tuple(observed.component_pin_numbers.items()))),
        }
    )
    reordered_finding = next(
        item for item in lint_report(reordered, sequence_map).findings if item.rule_id == RULE_ID
    )
    assert (reordered_finding.fingerprint, reordered_finding.evidence) == (
        finding.fingerprint,
        finding.evidence,
    )

    valid_map = power_sequence_output_cycle_map(cycle=False)
    valid_netlist = power_sequence_output_cycle_netlist(cycle=False)
    assert not power_sequence_observed_enable_cycles(valid_map, valid_netlist)
    assert RULE_ID not in {item.rule_id for item in lint_report(valid_netlist, valid_map).findings}
