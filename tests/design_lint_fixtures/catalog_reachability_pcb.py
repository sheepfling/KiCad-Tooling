"""Synthetic PCB design-lint rule reachability inputs."""

from __future__ import annotations

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.models import (
    ContractCoachReport,
    DesignLintPolicy,
    NetlistContract,
)
from kicad_tooling.hwrepo.pcb_component_inventory_models import (
    PcbComponentInventoryCoverageReport,
    PcbMissingFootprintPlacement,
)


def pcb_component_inventory_rule_ids() -> set[str]:
    """Emit the fitted schematic component placement finding through evaluation."""
    netlist_sha256 = "a" * 64
    observed = NetlistContract(components={}, nets={})
    coach = ContractCoachReport(
        status="READY_FOR_REVIEW",
        project_id="synthetic-pcb-inventory",
        netlist_sha256=netlist_sha256,
        observed=observed,
    )
    inventory = PcbComponentInventoryCoverageReport(
        status="COMPLETE",
        mode="review",
        netlist_sha256=netlist_sha256,
        board_path="projects/synthetic/kicad/controller.kicad_pcb",
        board_sha256="b" * 64,
        snapshot_path="build/design-lint/synthetic-pcb-inventory/snapshot.json",
        snapshot_sha256="c" * 64,
        snapshot_schema="12",
        kicad_version="10.0.5",
        image="registry.example/kicad:10.0.5@sha256:" + "d" * 64,
        probe_sha256="e" * 64,
        missing_placements=(
            PcbMissingFootprintPlacement(
                reference="U2",
                assigned_footprint="Package_SO:SOIC-8",
            ),
        ),
    )
    report = evaluate(
        coach.project_id,
        coach,
        DesignLintPolicy(),
        pcb_component_inventory_coverage=inventory,
    )
    return {finding.rule_id for finding in report.findings}
