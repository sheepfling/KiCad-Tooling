"""Final REVIEW, block, and finding report assembly for design lint."""

from __future__ import annotations

from typing import Literal

from .design_lint_evaluation_types import (
    DesignLintEvaluationReportInput,
)
from .i2c_pullup_models import I2cPullupHeuristicCoverage
from .models import (
    ControlInputBiasHeuristicCoverage,
    DesignLintReport,
    PcbKeepoutCoverageReport,
)
from .pcb_rf_antenna_models import PcbRfModuleAntennaCoverageReport


def assemble_design_lint_report(
    context: DesignLintEvaluationReportInput,
) -> DesignLintReport:
    """Apply source-bound coverage disposition and assemble the typed report."""
    project_id = context.project_id
    coach = context.coach
    policy = context.policy
    catalog = context.catalog
    source_hashes = context.source_hashes
    seen = context.seen
    findings = context.findings
    geometry_coverage = context.geometry_coverage
    component_role_resolution = context.component_role_resolution
    complementary_alias_resolution = context.complementary_alias_resolution
    i2c_address_coverage = context.i2c_address_coverage
    external_protection_coverage = context.external_protection_coverage
    crystal_network_coverage = context.crystal_network_coverage
    regulator_feedback_coverage = context.regulator_feedback_coverage
    rc_filter_coverage = context.rc_filter_coverage
    connector_return_distribution_coverage = context.connector_return_distribution_coverage
    pcb_decoupling_coverage = context.pcb_decoupling_coverage
    pcb_protection_path_coverage = context.pcb_protection_path_coverage
    pcb_track_width_coverage = context.pcb_track_width_coverage
    pcb_reference_plane_coverage = context.pcb_reference_plane_coverage
    pcb_switching_loop_coverage = context.pcb_switching_loop_coverage
    pcb_differential_pair_coverage = context.pcb_differential_pair_coverage
    pcb_signal_path_coverage = context.pcb_signal_path_coverage
    pcb_keepout_coverage = context.pcb_keepout_coverage
    pcb_rf_module_antenna_coverage = context.pcb_rf_module_antenna_coverage
    stm32_pin_map_coverage = context.stm32_pin_map_coverage
    mapped_check_runs = context.mapped_check_runs
    connector_coverage = context.connector_coverage
    connector_peer_pin_coverage = context.connector_peer_pin_coverage
    component_peer_pin_coverage = context.component_peer_pin_coverage
    digital_peer_voltage_coverage = context.digital_peer_voltage_coverage
    usb_peer_reference_coverage = context.usb_peer_reference_coverage
    serial_peer_reference_coverage = context.serial_peer_reference_coverage
    control_input_bias_coverage = context.control_input_bias_coverage
    i2c_pullup_heuristic_coverage = context.i2c_pullup_heuristic_coverage

    stale = tuple(item for item in policy.ignores if item.fingerprint not in seen)
    open_findings = tuple(item for item in findings if item.disposition == "OPEN")
    status: Literal["PASS", "REVIEW", "FAIL", "BLOCKED"] = (
        "BLOCKED"
        if geometry_coverage.status == "BLOCKED"
        or bool(component_role_resolution.issues)
        or bool(complementary_alias_resolution.issues)
        or i2c_address_coverage.status == "BLOCKED"
        or external_protection_coverage.status == "BLOCKED"
        or crystal_network_coverage.status == "BLOCKED"
        or regulator_feedback_coverage.status == "BLOCKED"
        or rc_filter_coverage.status == "BLOCKED"
        or connector_return_distribution_coverage.status == "BLOCKED"
        or pcb_decoupling_coverage.status == "BLOCKED"
        or pcb_protection_path_coverage.status == "BLOCKED"
        or pcb_track_width_coverage.status == "BLOCKED"
        or pcb_reference_plane_coverage.status == "BLOCKED"
        or pcb_switching_loop_coverage.status == "BLOCKED"
        or pcb_differential_pair_coverage.status == "BLOCKED"
        or pcb_signal_path_coverage.status == "BLOCKED"
        or pcb_keepout_coverage.status == "BLOCKED"
        or pcb_rf_module_antenna_coverage.status == "BLOCKED"
        or stm32_pin_map_coverage.status == "BLOCKED"
        or any(item.status == "BLOCKED" for item in mapped_check_runs)
        else "FAIL"
        if any(item.mode == "block" for item in open_findings)
        else "REVIEW"
        if open_findings
        or stale
        or geometry_coverage.status in {"PARTIAL", "UNSUPPORTED"}
        or i2c_address_coverage.status == "INCOMPLETE"
        or crystal_network_coverage.status == "INCOMPLETE"
        or regulator_feedback_coverage.status == "INCOMPLETE"
        or rc_filter_coverage.status == "INCOMPLETE"
        or connector_return_distribution_coverage.status == "INCOMPLETE"
        or (connector_coverage is not None and connector_coverage.status != "COMPLETE")
        or pcb_decoupling_coverage.status == "INCOMPLETE"
        or pcb_protection_path_coverage.status == "INCOMPLETE"
        or pcb_track_width_coverage.status == "INCOMPLETE"
        or pcb_reference_plane_coverage.status == "INCOMPLETE"
        or pcb_switching_loop_coverage.status == "INCOMPLETE"
        or pcb_differential_pair_coverage.status == "INCOMPLETE"
        or pcb_signal_path_coverage.status == "INCOMPLETE"
        or pcb_keepout_coverage.status == "INCOMPLETE"
        or pcb_rf_module_antenna_coverage.status == "INCOMPLETE"
        or stm32_pin_map_coverage.status == "INCOMPLETE"
        or (
            connector_peer_pin_coverage is not None
            and connector_peer_pin_coverage.status == "INCOMPLETE_PIN_INVENTORY"
        )
        else "PASS"
    )
    actions: tuple[str, ...] = ()
    issues: tuple[str, ...] = (
        component_role_resolution.issues
        + complementary_alias_resolution.issues
        + (() if geometry_coverage.issue is None else (geometry_coverage.issue,))
        + i2c_address_coverage.issues
        + (() if i2c_address_coverage.issue is None else (i2c_address_coverage.issue,))
        + (
            ()
            if external_protection_coverage.issue is None
            else (external_protection_coverage.issue,)
        )
        + (() if crystal_network_coverage.issue is None else (crystal_network_coverage.issue,))
        + (
            ()
            if regulator_feedback_coverage.issue is None
            else (regulator_feedback_coverage.issue,)
        )
        + (() if rc_filter_coverage.issue is None else (rc_filter_coverage.issue,))
        + (
            ()
            if connector_return_distribution_coverage.issue is None
            else (connector_return_distribution_coverage.issue,)
        )
        + (() if pcb_decoupling_coverage.issue is None else (pcb_decoupling_coverage.issue,))
        + (
            ()
            if pcb_protection_path_coverage.issue is None
            else (pcb_protection_path_coverage.issue,)
        )
        + (() if pcb_track_width_coverage.issue is None else (pcb_track_width_coverage.issue,))
        + (
            ()
            if pcb_reference_plane_coverage.issue is None
            else (pcb_reference_plane_coverage.issue,)
        )
        + (
            ()
            if pcb_switching_loop_coverage.issue is None
            else (pcb_switching_loop_coverage.issue,)
        )
        + (
            ()
            if pcb_differential_pair_coverage.issue is None
            else (pcb_differential_pair_coverage.issue,)
        )
        + (() if pcb_signal_path_coverage.issue is None else (pcb_signal_path_coverage.issue,))
        + (() if stm32_pin_map_coverage.issue is None else (stm32_pin_map_coverage.issue,))
        + tuple(
            item.reason
            for item in mapped_check_runs
            if item.status == "BLOCKED" and item.reason is not None
        )
    )
    if any(item.status == "BLOCKED" for item in mapped_check_runs):
        actions += (
            "Restore a source-bound native netlist digest for each configured mapped topology check, then rerun design lint.",
        )
    if geometry_coverage.status in {"PARTIAL", "UNSUPPORTED"}:
        actions += (
            (
                "Review schematic geometry coverage; unsupported symbols or formats can hide "
                "additional near-miss candidates."
            ),
        )
    if geometry_coverage.status == "BLOCKED":
        actions += ("Repair source-bound schematic geometry evidence, then rerun design lint.",)
    if component_role_resolution.issues:
        actions += (
            "Refresh the project component role map against the exact native part, symbol, footprint, and pin inventory, then rerun design lint.",
        )
    if complementary_alias_resolution.issues:
        actions += (
            "Refresh the project complementary pin-function alias map against exact native symbol identities and pin functions, then rerun design lint.",
        )
    if i2c_address_coverage.status == "INCOMPLETE":
        address_coverage_action = (
            "Review the I2C address-map coverage entries; resolve dynamic or incomplete address "
            "evidence before relying on collision results."
        )
        actions += (address_coverage_action,)
    if i2c_address_coverage.status == "BLOCKED":
        actions += ("Repair source-bound I2C address evidence, then rerun design lint.",)
    if external_protection_coverage.status == "BLOCKED":
        actions += ("Repair source-bound external-protection evidence, then rerun design lint.",)
    if crystal_network_coverage.status == "INCOMPLETE":
        actions += (
            (
                "Review the mapped crystal network identities, pin assignments, DNP state, and "
                "capacitance values against the project requirement."
            ),
        )
    if crystal_network_coverage.status == "BLOCKED":
        actions += ("Repair source-bound crystal network evidence, then rerun design lint.",)
    if regulator_feedback_coverage.status == "INCOMPLETE":
        feedback_coverage_action = (
            "Review mapped regulator identities, feedback pin assignments, fitted divider parts, "
            "and nominal setpoint against the project requirement."
        )
        actions += (feedback_coverage_action,)
    if regulator_feedback_coverage.status == "BLOCKED":
        actions += ("Repair source-bound regulator feedback evidence, then rerun design lint.",)
    if rc_filter_coverage.status == "INCOMPLETE":
        actions += (
            (
                "Review mapped RC filter identities, pin assignments, fitted state, passive values, "
                "and any unlisted parallel components against the project requirement."
            ),
        )
    if rc_filter_coverage.status == "BLOCKED":
        actions += ("Repair source-bound RC filter evidence, then rerun design lint.",)
    if connector_return_distribution_coverage.status == "INCOMPLETE":
        actions += (
            (
                "Complete connector interface coverage and assign each mapped interface pin an "
                "explicit signal, return, supply, shield, or other role before relying on the "
                "return-distribution threshold."
            ),
        )
    if connector_return_distribution_coverage.status == "BLOCKED":
        actions += (
            (
                "Repair source-bound connector coverage or interface-catalog evidence, then rerun "
                "design lint."
            ),
        )
    if (
        connector_peer_pin_coverage is not None
        and connector_peer_pin_coverage.status == "INCOMPLETE_PIN_INVENTORY"
    ):
        actions += (
            "Review exact-symbol connector peer coverage and restore complete native pin-number inventories for the listed references before relying on open-pin comparisons.",
        )
    if pcb_decoupling_coverage.status == "BLOCKED":
        actions += ("Repair source-bound PCB geometry evidence, then rerun design lint.",)
    if pcb_decoupling_coverage.status == "INCOMPLETE":
        actions += (
            "Review mapped IC and capacitor pad identities, fitted state, copper paths, and the project-authored distance limit.",
        )
    if pcb_protection_path_coverage.status == "BLOCKED":
        actions += ("Repair source-bound PCB protection-path evidence, then rerun design lint.",)
    if pcb_protection_path_coverage.status == "INCOMPLETE":
        actions += (
            "Review mapped connector and protector pad identities, native copper connectivity, and the project-authored distance or via-count limits.",
        )
    if pcb_track_width_coverage.status == "BLOCKED":
        actions += ("Repair source-bound PCB geometry evidence, then rerun design lint.",)
    if pcb_track_width_coverage.status == "INCOMPLETE":
        actions += (
            "Review mapped track-width coverage; a zone-only or unrouted net needs an explicit project decision.",
        )
    if pcb_reference_plane_coverage.status == "BLOCKED":
        actions += ("Repair source-bound PCB geometry evidence, then rerun design lint.",)
    if pcb_reference_plane_coverage.status == "INCOMPLETE":
        actions += (
            "Review mapped reference-plane route coverage; supported straight segments and native filled-zone contours are required.",
        )
    if pcb_switching_loop_coverage.status == "BLOCKED":
        actions += ("Repair source-bound PCB stack and copper evidence, then rerun design lint.",)
    if pcb_switching_loop_coverage.status == "INCOMPLETE":
        actions += (
            "Review the exact switching-loop pad order, authored area proxy limit, fitted state, and shared filled return-plane island.",
        )
    if pcb_differential_pair_coverage.status == "BLOCKED":
        actions += ("Repair source-bound native DRC rule evidence, then rerun design lint.",)
    if pcb_differential_pair_coverage.status == "INCOMPLETE":
        actions += (
            "Review each authored differential-pair requirement against the exact active native DRC rule and supported KiCad pair names.",
        )
    if pcb_signal_path_coverage.status == "BLOCKED":
        actions += (
            "Restore source-bound native PCB and DRC evidence, then rerun signal-path lint.",
        )
    if pcb_signal_path_coverage.status == "INCOMPLETE":
        actions += (
            "Review each mapped signal path against its source-netlist endpoints, native copper component, and exact active KiCad DRC length or skew rule.",
        )
    if pcb_keepout_coverage.status == "BLOCKED":
        actions += ("Repair source-bound PCB keepout evidence, then rerun design lint.",)
    if pcb_keepout_coverage.status == "INCOMPLETE":
        actions += (
            "Review each named PCB keepout against its approved geometry, copper layers, and restriction settings.",
        )
    if pcb_rf_module_antenna_coverage.status == "BLOCKED":
        actions += (
            "Repair source-bound RF module and PCB placement evidence, then rerun design lint.",
        )
    if pcb_rf_module_antenna_coverage.status == "INCOMPLETE":
        actions += (
            "Review each mapped RF module identity, fitted disposition, RF feed net, and placement-relative antenna keepout against its independent requirement.",
        )
    if stm32_pin_map_coverage.status == "BLOCKED":
        actions += ("Repair the CubeMX source or pin-map evidence, then rerun design lint.",)
    if stm32_pin_map_coverage.status == "INCOMPLETE":
        actions += (
            "Review each detected STM32 component and add a complete project-owned CubeMX pin map, or record a reasoned rule decision.",
        )
    if connector_coverage is not None and connector_coverage.status in {
        "UNASSESSED",
        "SCOPE_UNREVIEWED",
    }:
        if status == "PASS":
            status = "REVIEW"
        actions += (
            (
                "Review the complete schematic connector inventory and record a project-owned "
                "connector_inventory_review basis, including an explicit no-interface decision "
                "when applicable."
            ),
        )
    elif connector_coverage is not None and connector_coverage.status in {
        "INCOMPLETE",
        "UNDECLARED",
    }:
        if status == "PASS":
            status = "REVIEW"
        actions += (
            (
                "Complete connector interface coverage or record a reasoned not-applicable "
                "decision for each candidate reference."
            ),
        )
    if open_findings:
        actions += (
            (
                "Review each open finding against an independent pinout or design requirement; "
                "fix the source or record an exact, reasoned project-owned ignore."
            ),
        )
    if stale:
        actions += ("Remove or update stale ignores after reviewing the changed netlist evidence.",)
    return DesignLintReport(
        status=status,
        project_id=project_id,
        rule_catalog=catalog,
        source_hashes=source_hashes,
        netlist_sha256=coach.netlist_sha256,
        native_summary=coach.native_summary,
        native_status=coach.native_status,
        findings=tuple(findings),
        mapped_check_runs=mapped_check_runs,
        control_input_bias_coverage=(
            control_input_bias_coverage or ControlInputBiasHeuristicCoverage()
        ),
        i2c_pullup_heuristic_coverage=(
            i2c_pullup_heuristic_coverage or I2cPullupHeuristicCoverage()
        ),
        digital_peer_voltage_coverage=digital_peer_voltage_coverage,
        usb_peer_reference_coverage=usb_peer_reference_coverage,
        serial_peer_reference_coverage=serial_peer_reference_coverage,
        connector_peer_pin_coverage=connector_peer_pin_coverage,
        component_peer_pin_coverage=component_peer_pin_coverage,
        connector_coverage=connector_coverage,
        stm32_pin_map_coverage=stm32_pin_map_coverage,
        schematic_geometry=geometry_coverage,
        i2c_address_coverage=i2c_address_coverage,
        external_protection_coverage=external_protection_coverage,
        crystal_network_coverage=crystal_network_coverage,
        regulator_feedback_coverage=regulator_feedback_coverage,
        rc_filter_coverage=rc_filter_coverage,
        connector_return_distribution=connector_return_distribution_coverage,
        pcb_decoupling=pcb_decoupling_coverage,
        pcb_protection_path=pcb_protection_path_coverage,
        pcb_track_width=pcb_track_width_coverage,
        pcb_reference_plane=pcb_reference_plane_coverage,
        pcb_switching_loop=pcb_switching_loop_coverage,
        pcb_differential_pair_rules=pcb_differential_pair_coverage,
        pcb_signal_path_rules=pcb_signal_path_coverage,
        pcb_keepout_coverage=pcb_keepout_coverage or PcbKeepoutCoverageReport(),
        pcb_rf_module_antenna_coverage=(
            pcb_rf_module_antenna_coverage or PcbRfModuleAntennaCoverageReport()
        ),
        stale_ignores=stale,
        rule_overrides=policy.rules,
        issues=issues,
        next_actions=actions,
    )
