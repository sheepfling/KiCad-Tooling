"""Synthetic PCB design-lint rule reachability inputs."""

from __future__ import annotations

from kicad_tooling.hwrepo.design_lint import candidates, evaluate
from kicad_tooling.hwrepo.design_lint_types import Candidate
from kicad_tooling.hwrepo.models import (
    ContractCoachReport,
    DesignLintPolicy,
    NetlistContract,
    PcbRfModuleAntennaMap,
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
from kicad_tooling.hwrepo.pcb_touch_pad_clearance_models import (
    PcbTouchPadClearanceCoverageReport,
)
from tests import pcb_decoupling_support as _pcb_decoupling_support
from tests import pcb_rf_antenna_support as _pcb_rf_antenna_support
from tests.design_lint_fixtures import observed as observed_netlist
from tests.design_lint_fixtures import pcb_reference_planes as _pcb_reference_plane_fixtures
from tests.design_lint_fixtures import pcb_switching_loop as _pcb_switching_loop_fixtures
from tests.design_lint_fixtures.pcb_signal_path import incomplete_signal_report, path_map
from tests.test_pcb_drc_coverage import incomplete_report as incomplete_pair_report
from tests.test_pcb_drc_coverage import pair_map
from tests.test_pcb_keepouts import incomplete_report as incomplete_keepout_report
from tests.test_pcb_keepouts import mapping_for as keepout_mapping
from tests.test_pcb_protection_path import (
    coverage_report as protection_path_coverage,
)
from tests.test_pcb_protection_path import (
    mapping as protection_path_mapping,
)
from tests.test_pcb_protection_path import (
    snapshot as protection_path_snapshot,
)
from tests.test_pcb_track_width import (
    coverage as track_width_coverage,
)
from tests.test_pcb_track_width import (
    mapping as track_width_mapping,
)
from tests.test_pcb_track_width import (
    requirement as track_width_requirement,
)
from tests.test_pcb_track_width import (
    snapshot as track_width_snapshot,
)
from tests.test_pcb_track_width import (
    track as track_width_track,
)


def pcb_rule_ids() -> set[str]:
    """Emit representative PCB inventory and custom-rule candidates."""
    netlist_sha256 = "f" * 64
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
    ignored_dfm_check = Candidate(
        rule_id="pcb.dfm_drc_check_ignored",
        subject="projects/synthetic/controller.kicad_pro#hole_clearance",
        message="Synthetic Error-default DFM DRC check explicitly declares Ignore.",
        evidence={"source_path": ("projects/synthetic/controller.kicad_pro",)},
    )
    warning_core_check = Candidate(
        rule_id="pcb.core_drc_check_warning",
        subject="projects/synthetic/controller.kicad_pro#unconnected_items",
        message="Synthetic Error-default DRC check is configured as Warning.",
        evidence={"source_path": ("projects/synthetic/controller.kicad_pro",)},
    )
    warning_dfm_check = Candidate(
        rule_id="pcb.dfm_drc_check_warning",
        subject="projects/synthetic/controller.kicad_pro#track_width",
        message="Synthetic Error-default DFM DRC check is configured as Warning.",
        evidence={"source_path": ("projects/synthetic/controller.kicad_pro",)},
    )
    downgraded_signal_integrity_check = Candidate(
        rule_id="pcb.signal_integrity_drc_check_downgraded",
        subject="projects/synthetic/controller.kicad_pro#skew_out_of_range",
        message="Synthetic Error-default signal-integrity DRC check is configured below Error.",
        evidence={"source_path": ("projects/synthetic/controller.kicad_pro",)},
    )
    downgraded_electrical_check = Candidate(
        rule_id="pcb.electrical_drc_check_downgraded",
        subject="projects/synthetic/controller.kicad_pro#creepage",
        message="Synthetic Error-default electrical DRC check is configured below Error.",
        evidence={"source_path": ("projects/synthetic/controller.kicad_pro",)},
    )
    downgraded_miscellaneous_check = Candidate(
        rule_id="pcb.miscellaneous_drc_check_downgraded",
        subject="projects/synthetic/controller.kicad_pro#items_not_allowed",
        message="Synthetic Error-default miscellaneous DRC check is configured below Error.",
        evidence={"source_path": ("projects/synthetic/controller.kicad_pro",)},
    )
    ignored_warning_default_check = Candidate(
        rule_id="pcb.warning_default_drc_check_ignored",
        subject="projects/synthetic/controller.kicad_pro#via_dangling",
        message="Synthetic Warning-default native DRC check explicitly declares Ignore.",
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
    mechanical_edge_rule = Candidate(
        rule_id="pcb.mechanical_edge_clearance_rule_coverage",
        subject="projects/synthetic/controller.kicad_dru#front-edge",
        message="Synthetic source-bound courtyard-to-edge rule coverage is incomplete.",
        evidence={"source_path": ("projects/synthetic/controller.kicad_dru",)},
    )
    report = evaluate(
        coach.project_id,
        coach,
        DesignLintPolicy(),
        pcb_component_inventory_coverage=inventory,
        pcb_dru_rule_candidates=(ignored_rule, excluded_custom_rule, mechanical_edge_rule),
        pcb_native_drc_candidates=(
            ignored_core_check,
            ignored_dfm_check,
            warning_core_check,
            warning_dfm_check,
            downgraded_signal_integrity_check,
            downgraded_electrical_check,
            downgraded_miscellaneous_check,
            ignored_warning_default_check,
            persisted_drc_exclusion,
        ),
    )
    result = {finding.rule_id for finding in report.findings}
    empty_coach = coach
    decoupling_map = _pcb_decoupling_support.mapping(
        _pcb_decoupling_support.requirement(maximum_um=None)
    )
    decoupling_result = evaluate(
        "synthetic-decoupling",
        empty_coach,
        DesignLintPolicy(pcb_decoupling_map=decoupling_map),
        pcb_decoupling_coverage=_pcb_decoupling_support.coverage_report(
            decoupling_map, _pcb_decoupling_support.snapshot()
        ),
    )
    result.update(item.rule_id for item in decoupling_result.findings)

    protection_map = protection_path_mapping()
    protection_result = evaluate(
        "synthetic-protection-path",
        empty_coach,
        DesignLintPolicy(pcb_protection_path_map=protection_map),
        pcb_protection_path_coverage=protection_path_coverage(
            protection_map,
            protection_path_snapshot(entry_distance_nm=100001, via_offsets_nm=(2900000,)),
        ),
    )
    result.update(item.rule_id for item in protection_result.findings)

    track_map = track_width_mapping(track_width_requirement(minimum_um=251))
    track_result = evaluate(
        "synthetic-track-width",
        empty_coach,
        DesignLintPolicy(pcb_track_width_map=track_map),
        pcb_track_width_coverage=track_width_coverage(
            track_map,
            track_width_snapshot(track_width_track("001", "VDD", 250000)),
        ),
    )
    result.update(item.rule_id for item in track_result.findings)

    reference_hole = (
        (4000000, 4000000),
        (6000000, 4000000),
        (6000000, 6000000),
        (4000000, 6000000),
    )
    reference_map = _pcb_reference_plane_fixtures.mapping()
    reference_result = evaluate(
        "synthetic-reference-plane",
        empty_coach,
        DesignLintPolicy(pcb_reference_plane_map=reference_map),
        pcb_reference_plane_coverage=_pcb_reference_plane_fixtures.report(
            reference_map,
            _pcb_reference_plane_fixtures.snapshot(
                _pcb_reference_plane_fixtures.track(),
                zones=(
                    _pcb_reference_plane_fixtures.zone(
                        "00000000-0000-0000-0000-000000000001", holes=(reference_hole,)
                    ),
                ),
            ),
        ),
    )
    result.update(item.rule_id for item in reference_result.findings)

    switching_loop_map = _pcb_switching_loop_fixtures.mapping()
    switching_loop_result = evaluate(
        "synthetic-switching-loop",
        ContractCoachReport(
            status="READY_FOR_REVIEW",
            project_id="synthetic-switching-loop",
            netlist_sha256=netlist_sha256,
            observed=observed_netlist(),
        ),
        DesignLintPolicy(pcb_switching_loop_map=switching_loop_map),
        pcb_switching_loop_coverage=_pcb_switching_loop_fixtures.coverage(
            switching_loop_map, _pcb_switching_loop_fixtures.snapshot(expanded=True)
        ),
    )
    result.update(item.rule_id for item in switching_loop_result.findings)

    pair_result = evaluate(
        "synthetic-differential-pair",
        empty_coach,
        DesignLintPolicy(pcb_differential_pair_rule_map=pair_map()),
        pcb_differential_pair_coverage=incomplete_pair_report(),
    )
    result.update(item.rule_id for item in pair_result.findings)
    result.update(
        item.rule_id
        for item in candidates(
            observed_netlist(),
            pcb_signal_path_coverage=incomplete_signal_report(path_map()),
        )
    )

    keepout_map = keepout_mapping()
    keepout_coverage = incomplete_keepout_report(keepout_map)
    keepout_result = evaluate(
        "synthetic-keepout",
        empty_coach.model_copy(update={"netlist_sha256": keepout_coverage.netlist_sha256}),
        DesignLintPolicy(pcb_keepout_map=keepout_map),
        pcb_keepout_coverage=keepout_coverage,
    )
    result.update(item.rule_id for item in keepout_result.findings)

    rf_map = PcbRfModuleAntennaMap(
        basis="Synthetic catalog reachability requirement",
        requirements=(_pcb_rf_antenna_support.requirement(),),
    )
    rf_result = _pcb_rf_antenna_support.lint_report(
        policy=DesignLintPolicy(pcb_rf_module_antenna_map=rf_map),
        source_netlist=_pcb_rf_antenna_support.netlist(symbol="RF_Module:Other"),
        observed_board=_pcb_rf_antenna_support.snapshot(),
    )
    result.update(item.rule_id for item in rf_result.findings)

    touch_candidates = candidates(
        NetlistContract(components={}, nets={}),
        pcb_touch_pad_clearance_coverage=PcbTouchPadClearanceCoverageReport(
            status="BLOCKED",
            mode="review",
            issue="Synthetic native geometry evidence is unavailable",
        ),
    )
    result.update(item.rule_id for item in touch_candidates)
    return result
