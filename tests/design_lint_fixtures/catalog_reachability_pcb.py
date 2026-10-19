"""Synthetic PCB design-lint rule reachability inputs."""

from __future__ import annotations

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.design_lint_types import Candidate
from kicad_tooling.hwrepo.models import (
    ContractCoachReport,
    DesignLintPolicy,
    NetlistContract,
)
from kicad_tooling.hwrepo.pcb_board_only_footprint_models import (
    PcbBoardOnlyFootprint,
    PcbBoardOnlyFootprintCoverage,
)
from kicad_tooling.hwrepo.pcb_component_inventory_models import (
    PcbComponentInventoryCoverageReport,
    PcbComponentValueMismatch,
    PcbMissingFootprintPlacement,
    PcbPopulationMismatch,
)
from kicad_tooling.hwrepo.pcb_pad_net_models import PcbSchematicBoardPadNetMismatch
from kicad_tooling.hwrepo.pcb_required_fitted_reference_models import (
    PcbRequiredFittedReferenceCoverage,
    PcbRequiredFittedReferenceMismatch,
)


def pcb_rule_ids() -> set[str]:
    """Emit representative PCB inventory and custom-rule candidates."""
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
        snapshot_schema="13",
        kicad_version="10.0.5",
        image="registry.example/kicad:10.0.5@sha256:" + "d" * 64,
        probe_sha256="e" * 64,
        missing_placements=(
            PcbMissingFootprintPlacement(
                reference="U2",
                assigned_footprint="Package_SO:SOIC-8",
            ),
        ),
        population_mismatches=(
            PcbPopulationMismatch(reference="U1", schematic_dnp=False, board_dnp=True),
        ),
        value_comparison_status="COMPLETE",
        value_mismatches=(
            PcbComponentValueMismatch(
                reference="U3",
                schematic_value="Synthetic schematic value",
                board_value="Synthetic board value",
            ),
        ),
        pad_net_comparison_status="COMPLETE",
        pad_net_mismatches=(
            PcbSchematicBoardPadNetMismatch(
                reference="U4",
                pin="1",
                mismatch="net_assignment_differs",
                schematic_net="SYNTHETIC_SIGNAL",
                board_net="SYNTHETIC_OTHER",
            ),
        ),
        board_only_footprint_coverage=PcbBoardOnlyFootprintCoverage(
            status="COMPLETE",
            mode="review",
            footprints=(
                PcbBoardOnlyFootprint(
                    reference="J6",
                    footprint="Synthetic:Board_Only_Connector",
                ),
            ),
        ),
        required_fitted_reference_coverage=PcbRequiredFittedReferenceCoverage(
            status="COMPLETE",
            mode="block",
            map_sha256="f" * 64,
            requirement_count=1,
            mismatches=(
                PcbRequiredFittedReferenceMismatch(
                    reference="U5",
                    basis="synthetic assembly requirement",
                    expected_footprint="Package_QFP:TQFP-48",
                    schematic_footprint="Package_QFP:TQFP-48",
                    board_footprint="Package_QFP:TQFP-48",
                    schematic_dnp=True,
                    board_dnp=True,
                    violations=("schematic_component_dnp", "board_footprint_dnp"),
                ),
            ),
        ),
    )
    ignored_rule = Candidate(
        rule_id="pcb.custom_drc_rule_ignored",
        subject="projects/synthetic/controller.kicad_dru#rule[1] SyntheticIgnoredRule",
        message="Synthetic custom DRC rule explicitly declares Ignore.",
        evidence={"source_path": ("projects/synthetic/controller.kicad_dru",)},
    )
    ignored_core_check = Candidate(
        rule_id="pcb.core_drc_check_ignored",
        subject="projects/synthetic/controller.kicad_pro#unconnected_items",
        message="Synthetic native DRC check explicitly declares Ignore.",
        evidence={"source_path": ("projects/synthetic/controller.kicad_pro",)},
    )
    persisted_drc_exclusion = Candidate(
        rule_id="pcb.drc_exclusion_present",
        subject="projects/synthetic/controller.kicad_pro#drc-exclusion/" + "a" * 64,
        message="Synthetic saved PCB DRC exclusion requires review.",
        evidence={"source_path": ("projects/synthetic/controller.kicad_pro",)},
    )
    excluded_custom_rule = Candidate(
        rule_id="pcb.custom_drc_rule_excluded",
        subject="projects/synthetic/controller.kicad_dru#rule[2] SyntheticExcludedRule",
        message="Synthetic custom DRC rule assigns exclusion severity.",
        evidence={"source_path": ("projects/synthetic/controller.kicad_dru",)},
    )
    report = evaluate(
        coach.project_id,
        coach,
        DesignLintPolicy(),
        pcb_component_inventory_coverage=inventory,
        pcb_dru_rule_candidates=(ignored_rule, excluded_custom_rule),
        pcb_native_drc_candidates=(ignored_core_check, persisted_drc_exclusion),
    )
    return {finding.rule_id for finding in report.findings}
