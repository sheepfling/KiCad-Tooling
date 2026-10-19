"""Synthetic source-backed IC decoupling acceptance used by the native lane."""

from __future__ import annotations

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.ic_decoupling_models import (
    IcDecouplingCapacitorRequirement,
    IcDecouplingMap,
    IcDecouplingRequirement,
)
from kicad_tooling.hwrepo.models import ContractCoachReport, DesignLintPolicy, NetlistContract

RULE_ID = "power.ic_decoupling_below_project_minimum"


def source_backed_ic_decoupling_result(
    observed: NetlistContract,
    *,
    project_id: str,
    netlist_sha256: str,
) -> tuple[str, tuple[str, ...]]:
    """Evaluate the synthetic 100 nF boundary map against one native netlist."""
    requirement = IcDecouplingRequirement(
        id="synthetic-u1-vdd-decoupling",
        basis="Synthetic native fixture minimum: 100 nF nominal total",
        ic_reference="U1",
        expected_ic_value="Synthetic IC",
        expected_ic_symbol="Lint:PowerInput",
        expected_ic_footprint="Synthetic:QFN",
        power_pin="U1.1",
        power_net="+3V3",
        return_net="GND",
        minimum_total_capacitance_pf=100_000.0,
        capacitors=(
            IcDecouplingCapacitorRequirement(
                reference="C1",
                expected_symbol="Device:C",
                expected_footprint="Synthetic:0603",
                power_pin="C1.1",
                return_pin="C1.2",
            ),
        ),
    )
    report = evaluate(
        project_id,
        ContractCoachReport(
            status="READY_FOR_REVIEW",
            project_id=project_id,
            observed=observed,
            netlist_sha256=netlist_sha256,
        ),
        DesignLintPolicy(
            ic_decoupling_map=IcDecouplingMap(requirements=(requirement,))
        ),
    )
    subjects = tuple(
        sorted(item.subject for item in report.findings if item.rule_id == RULE_ID)
    )
    return report.status, subjects
