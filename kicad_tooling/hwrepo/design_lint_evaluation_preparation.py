"""Normalize project evidence and policy before theme-specific lint scans."""

from __future__ import annotations

import hashlib
from typing import Literal

from .bus_signal_pairs import (
    resolve_complementary_pin_function_aliases,
)
from .component_roles import resolve_component_role_map
from .control_input_bias import (
    ControlInputBiasCoverageRequest,
    resolve_control_input_bias_coverage,
)
from .design_lint_bus_inputs import BusCandidateInputs
from .design_lint_candidate_inputs import (
    ComponentCandidateInputs,
    ConnectorCandidateInputs,
    DesignLintCandidateInputs,
    MappedCandidateInputs,
)
from .design_lint_catalog import rule_catalog
from .design_lint_component_coverage import (
    ComponentMapCoverageRequest,
    resolve_component_map_coverage,
)
from .design_lint_control_inputs import ControlCandidateInputs
from .design_lint_evaluation_types import (
    DesignLintEvaluationPreparation,
    DesignLintEvaluationPreparationResult,
    DesignLintEvaluationRequest,
    DesignLintResolvedCoverage,
)
from .design_lint_missing_evidence import (
    DesignLintMissingEvidenceInput,
    missing_evidence_report,
)
from .design_lint_pcb_coverage_policy import (
    normalize_pcb_mapped_coverage_policy,
)
from .design_lint_pcb_geometry_coverage_policy import normalize_pcb_input_coverage_policy
from .design_lint_pcb_inputs import PcbCandidateInputs
from .design_lint_peer_evaluation import scan_peer_design_lint_evidence
from .design_lint_peer_inputs import PeerCandidateInputs
from .design_lint_power_inputs import PowerCandidateInputs
from .design_lint_report_models import DesignLintReport
from .design_lint_rule_types import DesignLintRuleId
from .design_lint_schematic_coverage import (
    SCHEMATIC_GEOMETRY_RULE_IDS,
    schematic_geometry_coverage,
)
from .design_lint_stm32_coverage import resolve_stm32_pin_map_coverage
from .design_lint_usb_data_path_inputs import UsbDataPathCandidateInputs
from .external_protection import (
    ExternalProtectionCoverageRequest,
    resolve_external_protection_coverage,
)
from .i2c_address_inputs import I2cAddressCandidateInput
from .i2c_pullup_heuristics import I2cPullupCoverageRequest, resolve_i2c_pullup_coverage
from .i2c_pullup_inputs import I2cPullupSnifferInput
from .pcb_component_inventory_models import PcbComponentInventoryCoverageReport
from .pcb_decoupling_models import PcbDecouplingCoverageReport
from .pcb_drc_models import PcbDifferentialPairRuleCoverageReport
from .pcb_switching_loop_models import (
    PcbSwitchingLoopCoverageReport,
)
from .pcb_track_width_models import PcbTrackWidthCoverageReport
from .schematic_geometry_models import SchematicGeometryCoverage, SchematicGeometryRuleId


def prepare_evaluation(
    request: DesignLintEvaluationRequest,
) -> DesignLintEvaluationPreparationResult:
    """Resolve coverage states, reject stale inputs, and validate required evidence."""
    coach = request.coach
    policy = request.policy
    catalog = rule_catalog()
    coach_has_source_identity = bool(coach.source_hashes) or coach.native_summary is not None
    if coach_has_source_identity and coach.project_id != request.project_id:
        issue = (
            f"Contract coach evidence belongs to project {coach.project_id!r}, "
            f"not requested project {request.project_id!r}"
        )
        return DesignLintEvaluationPreparationResult(
            report=DesignLintReport(
                status="BLOCKED",
                project_id=request.project_id,
                rule_catalog=catalog,
                issues=(issue,),
                next_actions=(
                    "Capture contract-coach evidence for the requested project and rerun design lint.",
                ),
            )
        )
    input_pcb_coverage = normalize_pcb_input_coverage_policy(
        policy,
        source_hashes=coach.source_hashes,
        inputs=request.pcb_input_coverage,
    )
    protection_resolution = resolve_external_protection_coverage(
        ExternalProtectionCoverageRequest(
            coverage=request.external_protection_coverage,
            current_netlist_sha256=coach.netlist_sha256,
        )
    )
    external_protection_coverage = protection_resolution.coverage
    protection_issue = protection_resolution.binding_issue
    control_resolution = resolve_control_input_bias_coverage(
        ControlInputBiasCoverageRequest(
            coverage=request.control_input_bias_coverage,
            current_netlist_sha256=coach.netlist_sha256,
        )
    )
    control_coverage = control_resolution.coverage
    control_issue = control_resolution.binding_issue
    if control_issue is not None:
        if control_coverage is None:
            raise RuntimeError(
                "Control-input coverage binding issue requires its blocked coverage report."
            )
        return DesignLintEvaluationPreparationResult(
            report=DesignLintReport(
                status="BLOCKED",
                project_id=request.project_id,
                source_hashes=coach.source_hashes,
                netlist_sha256=coach.netlist_sha256,
                native_summary=coach.native_summary,
                native_status=coach.native_status,
                rule_catalog=catalog,
                control_input_bias_coverage=control_coverage,
                external_protection_coverage=external_protection_coverage,
                pcb_signal_path_rules=input_pcb_coverage.signal_path,
                pcb_keepout_coverage=input_pcb_coverage.keepout,
                pcb_rf_module_antenna_coverage=input_pcb_coverage.rf_antenna,
                pcb_touch_pad_clearance_coverage=input_pcb_coverage.touch_pad_clearance,
                issues=(control_issue,) + (() if protection_issue is None else (protection_issue,)),
                next_actions=(
                    "Recreate control-input bias coverage from the current native netlist and contract.",
                ),
            )
        )
    i2c_resolution = resolve_i2c_pullup_coverage(
        I2cPullupCoverageRequest(
            coverage=request.i2c_pullup_heuristic_coverage,
            current_netlist_sha256=coach.netlist_sha256,
        )
    )
    i2c_coverage = i2c_resolution.coverage
    i2c_issue = i2c_resolution.binding_issue
    if i2c_issue is not None:
        if i2c_coverage is None:
            raise RuntimeError("I2C pull-up binding issue requires its blocked coverage report.")
        return DesignLintEvaluationPreparationResult(
            report=DesignLintReport(
                status="BLOCKED",
                project_id=request.project_id,
                source_hashes=coach.source_hashes,
                netlist_sha256=coach.netlist_sha256,
                native_summary=coach.native_summary,
                native_status=coach.native_status,
                rule_catalog=catalog,
                i2c_pullup_heuristic_coverage=i2c_coverage,
                external_protection_coverage=external_protection_coverage,
                pcb_signal_path_rules=input_pcb_coverage.signal_path,
                pcb_keepout_coverage=input_pcb_coverage.keepout,
                pcb_rf_module_antenna_coverage=input_pcb_coverage.rf_antenna,
                pcb_touch_pad_clearance_coverage=input_pcb_coverage.touch_pad_clearance,
                issues=(i2c_issue,) + (() if protection_issue is None else (protection_issue,)),
                next_actions=(
                    "Recreate I2C pull-up coverage from the current native netlist and contract.",
                ),
            )
        )

    stm32_pin_map_coverage, source_hashes = resolve_stm32_pin_map_coverage(
        coach,
        policy,
        request.stm32_pin_map_coverage,
    )
    mapped_pcb_coverage = normalize_pcb_mapped_coverage_policy(
        policy,
        source_hashes=coach.source_hashes,
        inputs=request.pcb_mapped_coverage,
    )
    if coach.status != "READY_FOR_REVIEW" or coach.observed is None:
        return DesignLintEvaluationPreparationResult(
            report=missing_evidence_report(
                DesignLintMissingEvidenceInput(
                    project_id=request.project_id,
                    coach=coach,
                    policy=policy,
                    catalog=catalog,
                    stm32_pin_map_coverage=stm32_pin_map_coverage,
                    pcb_input_coverage=input_pcb_coverage,
                    pcb_mapped_coverage=mapped_pcb_coverage,
                    external_protection_coverage=external_protection_coverage,
                )
            )
        )

    component_role_resolution = resolve_component_role_map(
        coach.observed, policy.component_role_map
    )
    complementary_alias_resolution = resolve_complementary_pin_function_aliases(
        coach.observed, policy.complementary_pin_function_alias_map
    )
    geometry_coverage = request.geometry_coverage
    if geometry_coverage is None and request.schematic_geometry is not None:
        overrides = {item.rule_id: item for item in policy.rules}
        rule_modes: dict[SchematicGeometryRuleId, Literal["review", "block", "off"]]
        rule_modes = {
            rule_id: overrides[rule_id].mode if rule_id in overrides else "off"
            for rule_id in SCHEMATIC_GEOMETRY_RULE_IDS
        }
        geometry_coverage = schematic_geometry_coverage(
            request.schematic_geometry, coach.netlist_sha256, rule_modes
        )
    if geometry_coverage is None:
        geometry_coverage = SchematicGeometryCoverage()

    component_map_coverage = resolve_component_map_coverage(
        ComponentMapCoverageRequest(
            policy=policy,
            observed=coach.observed,
            netlist_sha256=coach.netlist_sha256,
            inputs=request.component_map_coverage,
        )
    )
    loop_map = mapped_pcb_coverage.switching_loop_map
    loop_mode = mapped_pcb_coverage.switching_loop_mode
    pair_map = mapped_pcb_coverage.differential_pair_map
    pair_mode = mapped_pcb_coverage.differential_pair_mode
    pair_map_sha256 = mapped_pcb_coverage.differential_pair_map_sha256

    pcb_decoupling_coverage = request.pcb_decoupling_coverage
    if pcb_decoupling_coverage is None:
        pcb_decoupling_coverage = (
            PcbDecouplingCoverageReport(
                status="BLOCKED",
                issue="Native PCB geometry evidence was not supplied for the configured decoupling map",
            )
            if policy.pcb_decoupling_map is not None
            else PcbDecouplingCoverageReport()
        )
    pcb_component_inventory_coverage = (
        request.pcb_component_inventory_coverage or PcbComponentInventoryCoverageReport()
    )
    pcb_track_width_coverage = request.pcb_track_width_coverage
    if pcb_track_width_coverage is None:
        pcb_track_width_coverage = (
            PcbTrackWidthCoverageReport(
                status="BLOCKED",
                issue="Native PCB geometry evidence was not supplied for the configured track-width map",
            )
            if policy.pcb_track_width_map is not None
            else PcbTrackWidthCoverageReport()
        )
    pcb_switching_loop_coverage = mapped_pcb_coverage.switching_loop
    if pcb_switching_loop_coverage is None:
        pcb_switching_loop_coverage = (
            PcbSwitchingLoopCoverageReport(
                status="BLOCKED",
                mode=loop_mode,
                map_sha256=hashlib.sha256(loop_map.model_dump_json().encode("utf-8")).hexdigest(),
                issue="Native PCB geometry evidence was not supplied for the configured switching-loop map",
            )
            if loop_map is not None and loop_mode != "off"
            else PcbSwitchingLoopCoverageReport(status="DISABLED", mode=loop_mode)
            if loop_map is not None
            else PcbSwitchingLoopCoverageReport()
        )
    pcb_differential_pair_coverage = mapped_pcb_coverage.differential_pair
    if pcb_differential_pair_coverage is None:
        pair_map = policy.pcb_differential_pair_rule_map
        if pair_map is None:
            pcb_differential_pair_coverage = PcbDifferentialPairRuleCoverageReport()
        elif pair_mode == "off":
            pcb_differential_pair_coverage = PcbDifferentialPairRuleCoverageReport(
                status="DISABLED", mode=pair_mode, map_sha256=pair_map_sha256
            )
        else:
            pcb_differential_pair_coverage = PcbDifferentialPairRuleCoverageReport(
                status="BLOCKED",
                mode=pair_mode,
                map_sha256=pair_map_sha256,
                issue="Source-bound native DRC rule evidence was not supplied for the configured pair map",
            )

    overrides = {str(item.rule_id): item for item in policy.rules}
    default_modes: dict[DesignLintRuleId, Literal["review", "block", "off"]] = {
        item.rule_id: item.default_mode for item in catalog.rules
    }
    coverage = DesignLintResolvedCoverage(
        geometry=geometry_coverage,
        i2c_address=component_map_coverage.i2c_address,
        external_protection=external_protection_coverage,
        crystal_network=component_map_coverage.crystal_network,
        regulator_feedback=component_map_coverage.regulator_feedback,
        signal_divider=component_map_coverage.signal_divider,
        rc_filter=component_map_coverage.rc_filter,
        connector_return_distribution=component_map_coverage.connector_return_distribution,
        pcb_decoupling=pcb_decoupling_coverage,
        pcb_component_inventory=pcb_component_inventory_coverage,
        pcb_protection_path=mapped_pcb_coverage.protection_path,
        pcb_track_width=pcb_track_width_coverage,
        pcb_reference_plane=mapped_pcb_coverage.reference_plane,
        pcb_switching_loop=pcb_switching_loop_coverage,
        pcb_differential_pair=pcb_differential_pair_coverage,
        pcb_signal_path=input_pcb_coverage.signal_path,
        pcb_keepout=input_pcb_coverage.keepout,
        pcb_rf_module_antenna=input_pcb_coverage.rf_antenna,
        pcb_touch_pad_clearance=input_pcb_coverage.touch_pad_clearance,
        stm32_pin_map=stm32_pin_map_coverage,
        control_input_bias=control_coverage,
        i2c_pullup_heuristic=i2c_coverage,
    )
    pcb_candidate_inputs = PcbCandidateInputs(
        component_inventory=coverage.pcb_component_inventory,
        decoupling=coverage.pcb_decoupling,
        protection_path=coverage.pcb_protection_path,
        track_width=coverage.pcb_track_width,
        reference_plane=coverage.pcb_reference_plane,
        switching_loop=coverage.pcb_switching_loop,
        differential_pair=coverage.pcb_differential_pair,
        signal_path=coverage.pcb_signal_path,
        keepout=coverage.pcb_keepout,
        rf_antenna=coverage.pcb_rf_module_antenna,
        touch_pad_clearance=coverage.pcb_touch_pad_clearance,
        stm32_pin_map=coverage.stm32_pin_map,
        dru_rule_candidates=request.pcb_dru_rule_candidates,
        native_drc_candidates=request.pcb_native_drc_candidates,
    )
    peer_evidence = scan_peer_design_lint_evidence(
        observed=coach.observed,
        netlist_sha256=coach.netlist_sha256,
        connector_coverage=request.component_map_coverage.connector_coverage,
        inputs=request.peer_scan_inputs,
        usb_data_path_map=policy.usb_data_path_map,
        default_modes=default_modes,
        overrides=overrides,
    )
    peer_power_output_override = overrides.get("component.peer_power_output_unconnected")
    peer_power_output_mode = (
        peer_power_output_override.mode
        if peer_power_output_override is not None
        else default_modes["component.peer_power_output_unconnected"]
    )
    connector_power_output_override = overrides.get("connector.unconnected_power_output")
    connector_power_output_mode = (
        connector_power_output_override.mode
        if connector_power_output_override is not None
        else default_modes["connector.unconnected_power_output"]
    )
    candidate_inputs = DesignLintCandidateInputs(
        observed=coach.observed,
        catalog=catalog,
        schematic_geometry=request.schematic_geometry,
        reviewed_connector_references=peer_evidence.reviewed_connector_references,
        connector=ConnectorCandidateInputs(
            coverage=request.component_map_coverage.connector_coverage,
            return_distribution=coverage.connector_return_distribution,
            stateful_contact_map=policy.connector_stateful_contact_map,
            power_output_review_enabled=connector_power_output_mode != "off",
        ),
        component=ComponentCandidateInputs(
            peer_pin_assignment_scans=peer_evidence.peer_pin_assignment_scans,
            peer_power_output_review_enabled=peer_power_output_mode != "off",
        ),
        control=ControlCandidateInputs.from_legacy_arguments(
            coach.observed,
            coverage.control_input_bias,
        ),
        power=PowerCandidateInputs(
            component_role_map=policy.component_role_map,
            power_path_map=policy.power_path_map,
            power_sequence_map=policy.power_sequence_map,
            oscillator_output_path_map=policy.oscillator_output_path_map,
            ic_decoupling_map=policy.ic_decoupling_map,
            regulator_passive_topology_map=policy.regulator_passive_topology_map,
        ),
        bus=BusCandidateInputs(
            observed=coach.observed,
            i2c_address=I2cAddressCandidateInput.from_candidate_arguments(
                coach.observed, policy.i2c_address_map, coverage.i2c_address
            ),
            i2c_pullup=I2cPullupSnifferInput.from_legacy_arguments(
                coach.observed, coverage.i2c_pullup_heuristic
            ),
            complementary_alias_resolution=complementary_alias_resolution,
            i2c_peer_reference_scan=peer_evidence.i2c_peer_reference_scan,
            spi_roster=request.spi_roster,
            spi_peer_reference_scan=peer_evidence.spi_peer_reference_scan,
            can_peer_reference_scan=peer_evidence.can_peer_reference_scan,
            rs485_peer_reference_scan=peer_evidence.rs485_peer_reference_scan,
            pcb_differential_pair_rule_map=policy.pcb_differential_pair_rule_map,
            reviewed_connector_references=peer_evidence.reviewed_connector_references,
        ),
        peer=PeerCandidateInputs(
            digital_voltage_context=request.peer_scan_inputs.digital_peer_voltage_context,
            digital_voltage_scan=peer_evidence.digital_peer_voltage_scan,
            usb_reference_scan=peer_evidence.usb_peer_reference_scan,
            serial_reference_scan=peer_evidence.serial_peer_reference_scan,
            serial_roster=request.peer_scan_inputs.serial_peer_roster,
            usb_c_port_roster=request.usb_c_port_roster,
        ),
        mapped=MappedCandidateInputs(
            external_protection=coverage.external_protection,
            crystal_network=coverage.crystal_network,
            regulator_feedback=coverage.regulator_feedback,
            signal_divider=coverage.signal_divider,
            rc_filter=coverage.rc_filter,
        ),
        pcb=pcb_candidate_inputs,
        usb_data_path=UsbDataPathCandidateInputs(authored_map=policy.usb_data_path_map),
    )
    prepared = DesignLintEvaluationPreparation(
        request=request,
        catalog=catalog,
        source_hashes=source_hashes,
        input_pcb_coverage=input_pcb_coverage,
        mapped_pcb_coverage=mapped_pcb_coverage,
        coverage=coverage,
        candidate_inputs=candidate_inputs,
        peer_evidence=peer_evidence,
        component_role_resolution=component_role_resolution,
        complementary_alias_resolution=complementary_alias_resolution,
        overrides=overrides,
        ignores={str(item.fingerprint): item for item in policy.ignores},
        default_modes=default_modes,
    )
    return DesignLintEvaluationPreparationResult(prepared=prepared)
