"""Reviewable heuristic findings from source-bound native netlist evidence."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from dataclasses import replace

from typing_extensions import Unpack

from .component_peer_pin_candidate_types import ComponentPeerCandidateInputs
from .component_peer_pin_evaluation import component_peer_pin_assignment_scans
from .design_lint_bus_candidates import scan_bus_candidates
from .design_lint_bus_inputs import BusCandidateInputs
from .design_lint_candidate_inputs import (
    ComponentCandidateInputs,
    ConnectorCandidateInputs,
    DesignLintCandidateInputs,
    MappedCandidateInputs,
)
from .design_lint_candidate_legacy_arguments import LegacyCandidateArguments
from .design_lint_candidate_results import DesignLintCandidateScanResult
from .design_lint_catalog import rule_catalog
from .design_lint_component_candidates import (
    ComponentTopologyCandidateInputs,
    scan_component_candidates,
)
from .design_lint_component_peer_candidates import scan_component_peer_candidates
from .design_lint_connector_candidates import scan_connector_candidates
from .design_lint_control_candidates import scan_control_candidates
from .design_lint_control_inputs import ControlCandidateInputs
from .design_lint_mapped_coverage_candidates import (
    MappedCoverageCandidateInputs,
    scan_mapped_coverage_candidates,
)
from .design_lint_mapped_topology_results import MappedTopologyFindingCounts
from .design_lint_pcb_board_only_candidates import pcb_board_only_footprint_candidates
from .design_lint_pcb_component_inventory_candidates import (
    pcb_component_inventory_candidates,
)
from .design_lint_pcb_inputs import PcbCandidateInputs
from .design_lint_pcb_measurement_candidates import scan_pcb_measurement_candidates
from .design_lint_pcb_pad_net_candidates import pcb_pad_net_candidates
from .design_lint_pcb_required_fitted_reference_candidates import (
    pcb_required_fitted_reference_candidates,
)
from .design_lint_pcb_requirement_candidates import scan_pcb_requirement_candidates
from .design_lint_pcb_thermal_pad_scope import explicit_thermal_pad_scope_candidates
from .design_lint_peer_candidates import scan_peer_candidates
from .design_lint_peer_inputs import PeerCandidateInputs, PeerCandidateScanInputs
from .design_lint_power_candidates import scan_power_candidates
from .design_lint_power_inputs import PowerCandidateInputs
from .design_lint_return_distribution_candidates import return_distribution_candidates
from .design_lint_rule_models import DesignLintRuleCatalog
from .design_lint_schematic_geometry import schematic_geometry_candidates
from .design_lint_stm32_candidates import stm32_candidates
from .design_lint_types import Candidate
from .design_lint_usb_data_path_inputs import UsbDataPathCandidateInputs
from .i2c_address_inputs import I2cAddressCandidateInput
from .i2c_pullup_inputs import I2cPullupSnifferInput
from .netlist_contract_models import NetlistContract
from .peer_reference_candidate_keys import PeerReferenceCandidateKeys


def fingerprint(item: Candidate) -> str:
    """Bind an ignore to exact observed pins/nets, independent of unrelated files."""
    payload = {
        "rule_id": item.rule_id,
        "subject": item.subject,
        "evidence": {key: sorted(value) for key, value in sorted(item.evidence.items())},
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def validate_catalogued_candidates(
    items: Sequence[Candidate],
    catalog: DesignLintRuleCatalog,
) -> None:
    """Reject candidates from any theme that are absent from the active catalog."""
    active_ids = {item.rule_id for item in catalog.rules if item.status == "active"}
    unknown_ids = sorted({item.rule_id for item in items} - active_ids)
    if unknown_ids:
        raise ValueError(
            f"Design-lint candidates emit rules absent from the active catalog: {unknown_ids}"
        )


def candidates(
    observed: NetlistContract,
    catalog: DesignLintRuleCatalog | None = None,
    **legacy: Unpack[LegacyCandidateArguments],
) -> tuple[Candidate, ...]:
    """Adapt legacy inputs to the shared typed candidate scanner."""
    resolved_catalog = catalog if catalog is not None else rule_catalog()
    return scan_candidates(
        DesignLintCandidateInputs(
            observed=observed,
            catalog=resolved_catalog,
            schematic_geometry=legacy.get("schematic_geometry"),
            reviewed_connector_references=legacy.get("reviewed_connector_references", ()),
            connector=ConnectorCandidateInputs(
                coverage=legacy.get("connector_coverage"),
                return_distribution=legacy.get("connector_return_distribution"),
                stateful_contact_map=legacy.get("connector_stateful_contact_map"),
                power_output_review_enabled=legacy.get(
                    "connector_power_output_review_enabled", True
                ),
            ),
            component=ComponentCandidateInputs(
                peer_pin_assignment_scans=legacy.get("peer_pin_assignment_scans"),
                peer_power_output_review_enabled=legacy.get(
                    "peer_power_output_review_enabled", True
                ),
            ),
            control=ControlCandidateInputs.from_legacy_arguments(
                observed,
                legacy.get("control_input_bias_coverage"),
            ),
            power=PowerCandidateInputs(
                component_role_map=legacy.get("component_role_map"),
                power_path_map=legacy.get("power_path_map"),
                power_sequence_map=legacy.get("power_sequence_map"),
                oscillator_output_path_map=legacy.get("oscillator_output_path_map"),
                ic_decoupling_map=legacy.get("ic_decoupling_map"),
                led_current_map=legacy.get("led_current_map"),
                regulator_support_pin_role_map=legacy.get("regulator_support_pin_role_map"),
                regulator_support_pin_net_map=legacy.get("regulator_support_pin_net_map"),
            ),
            bus=BusCandidateInputs(
                observed=observed,
                i2c_address=I2cAddressCandidateInput.from_candidate_arguments(
                    observed,
                    legacy.get("i2c_address_map"),
                    legacy.get("i2c_address_coverage"),
                ),
                i2c_pullup=I2cPullupSnifferInput.from_legacy_arguments(
                    observed, legacy.get("i2c_pullup_heuristic_coverage")
                ),
                complementary_alias_resolution=legacy.get("complementary_alias_resolution"),
                i2c_peer_reference_scan=legacy.get("i2c_peer_reference_scan"),
                spi_roster=legacy.get("spi_roster"),
                spi_peer_reference_scan=legacy.get("spi_peer_reference_scan"),
                can_peer_reference_scan=legacy.get("can_peer_reference_scan"),
                rs485_peer_reference_scan=legacy.get("rs485_peer_reference_scan"),
                pcb_differential_pair_rule_map=legacy.get("pcb_differential_pair_rule_map"),
                reviewed_connector_references=legacy.get("reviewed_connector_references", ()),
            ),
            peer=PeerCandidateInputs(
                digital_voltage_context=legacy.get("digital_peer_voltage_context"),
                digital_voltage_scan=legacy.get("digital_peer_voltage_scan"),
                usb_reference_scan=legacy.get("usb_peer_reference_scan"),
                serial_reference_scan=legacy.get("serial_peer_reference_scan"),
                serial_roster=legacy.get("serial_peer_roster"),
                usb_c_port_roster=legacy.get("usb_c_port_roster"),
            ),
            mapped=MappedCandidateInputs(
                external_protection=legacy.get("external_protection_coverage"),
                crystal_network=legacy.get("crystal_network_coverage"),
                regulator_feedback=legacy.get("regulator_feedback_coverage"),
                signal_divider=legacy.get("signal_divider_coverage"),
                rc_filter=legacy.get("rc_filter_coverage"),
            ),
            pcb=PcbCandidateInputs(
                component_inventory=legacy.get("pcb_component_inventory_coverage"),
                decoupling=legacy.get("pcb_decoupling_coverage"),
                protection_path=legacy.get("pcb_protection_path_coverage"),
                track_width=legacy.get("pcb_track_width_coverage"),
                reference_plane=legacy.get("pcb_reference_plane_coverage"),
                switching_loop=legacy.get("pcb_switching_loop_coverage"),
                differential_pair=legacy.get("pcb_differential_pair_coverage"),
                signal_path=legacy.get("pcb_signal_path_coverage"),
                keepout=legacy.get("pcb_keepout_coverage"),
                rf_antenna=legacy.get("pcb_rf_module_antenna_coverage"),
                touch_pad_clearance=legacy.get("pcb_touch_pad_clearance_coverage"),
                thermal_via=legacy.get("pcb_thermal_via_coverage"),
                stm32_pin_map=legacy.get("stm32_pin_map_coverage"),
                is_pcb_project=legacy.get("is_pcb_project", False),
                thermal_via_map=legacy.get("pcb_thermal_via_map"),
            ),
            usb_data_path=UsbDataPathCandidateInputs(authored_map=legacy.get("usb_data_path_map")),
            netlist_sha256=legacy.get("netlist_sha256"),
        )
    )


def scan_candidate_result(
    inputs: DesignLintCandidateInputs,
) -> DesignLintCandidateScanResult:
    """Aggregate typed theme outputs and preserve one active-catalog lifecycle."""
    observed = inputs.observed
    catalog = inputs.catalog
    schematic_geometry = inputs.schematic_geometry
    reviewed_connector_references = inputs.reviewed_connector_references
    connector_coverage = inputs.connector.coverage
    connector_return_distribution = inputs.connector.return_distribution
    connector_stateful_contact_map = inputs.connector.stateful_contact_map
    connector_power_output_review_enabled = inputs.connector.power_output_review_enabled
    component_role_map = inputs.power.component_role_map
    power_path_map = inputs.power.power_path_map
    oscillator_output_path_map = inputs.power.oscillator_output_path_map
    led_current_map = inputs.power.led_current_map
    peer_pin_assignment_scans = inputs.component.peer_pin_assignment_scans
    peer_power_output_review_enabled = inputs.component.peer_power_output_review_enabled
    power_sequence_map = inputs.power.power_sequence_map
    pcb_component_inventory_coverage = inputs.pcb.component_inventory
    stm32_pin_map_coverage = inputs.pcb.stm32_pin_map
    usb_data_path = inputs.usb_data_path
    spi_roster = inputs.bus.spi_roster
    found: list[Candidate] = []
    peer_pin_scans = peer_pin_assignment_scans or component_peer_pin_assignment_scans(
        observed,
        reviewed_connector_references,
    )
    peer_unconnected_power_output_pins: frozenset[str] = (
        frozenset(
            pin.casefold()
            for group in peer_pin_scans.power_output.outliers
            for pin, nets in group.assignments.items()
            if not nets
        )
        if peer_power_output_review_enabled
        else frozenset[str]()
    )
    connector_result = scan_connector_candidates(
        observed,
        connector_coverage=connector_coverage,
        reviewed_connector_references=reviewed_connector_references,
        power_output_review_enabled=connector_power_output_review_enabled,
        stateful_contact_map=connector_stateful_contact_map,
    )
    found.extend(connector_result.candidates)
    found.extend(return_distribution_candidates(connector_return_distribution))
    found.extend(pcb_component_inventory_candidates(pcb_component_inventory_coverage))
    found.extend(pcb_board_only_footprint_candidates(pcb_component_inventory_coverage))
    found.extend(pcb_required_fitted_reference_candidates(pcb_component_inventory_coverage))
    found.extend(pcb_pad_net_candidates(pcb_component_inventory_coverage))
    control_result = scan_control_candidates(inputs.control)
    found.extend(control_result.candidates)
    component_result = scan_component_candidates(
        ComponentTopologyCandidateInputs(
            observed=observed,
            component_role_map=component_role_map,
            power_path_map=power_path_map,
            oscillator_output_path_map=oscillator_output_path_map,
            led_current_map=led_current_map,
            netlist_sha256=inputs.netlist_sha256,
            reviewed_connector_references=reviewed_connector_references,
        )
    )
    found.extend(component_result.candidates)
    found.extend(
        scan_power_candidates(
            observed,
            inputs.power,
            reviewed_connector_references=reviewed_connector_references,
            peer_unconnected_power_output_pins=peer_unconnected_power_output_pins,
        )
    )
    component_peer_result = scan_component_peer_candidates(
        ComponentPeerCandidateInputs(
            observed=observed,
            peer_pin_scans=peer_pin_scans,
            reviewed_connector_references=reviewed_connector_references,
            control_pin_keys=control_result.unconnected_pin_keys,
        )
    )
    component_peer_findings = component_peer_result.candidates
    found.extend(component_peer_findings)
    bus_result = scan_bus_candidates(
        replace(
            inputs.bus,
            component_peer_findings=component_peer_findings,
            connector_coverage=inputs.connector.coverage,
            reviewed_connector_references=reviewed_connector_references,
        )
    )
    found.extend(bus_result.candidates)
    if schematic_geometry is not None:
        found.extend(schematic_geometry_candidates(schematic_geometry))
    found.extend(
        scan_peer_candidates(
            PeerCandidateScanInputs(
                observed=observed,
                peer=inputs.peer,
                reviewed_connector_references=reviewed_connector_references,
                spi_roster=spi_roster,
                usb_data_path=usb_data_path,
            )
        )
    )
    mapped_coverage_result = scan_mapped_coverage_candidates(
        MappedCoverageCandidateInputs(
            observed=observed,
            coverage=inputs.mapped,
            usb_data_path=usb_data_path,
            power_path_map=power_path_map,
            power_sequence_map=power_sequence_map,
        )
    )
    found.extend(mapped_coverage_result.candidates)
    found.extend(scan_pcb_measurement_candidates(inputs.pcb))
    found.extend(scan_pcb_requirement_candidates(inputs.pcb))
    if inputs.pcb.is_pcb_project:
        found.extend(
            explicit_thermal_pad_scope_candidates(
                observed,
                inputs.pcb.thermal_via_map,
            )
        )
    found.extend(stm32_candidates(stm32_pin_map_coverage))
    found.extend(inputs.pcb.dru_rule_candidates)
    found.extend(inputs.pcb.native_drc_candidates)
    items = tuple(sorted(found, key=lambda item: (item.rule_id, item.subject)))
    validate_catalogued_candidates(items, catalog)
    pcb_peer_keys = PeerReferenceCandidateKeys.from_candidates(
        (*inputs.pcb.dru_rule_candidates, *inputs.pcb.native_drc_candidates)
    )
    return DesignLintCandidateScanResult(
        candidates=items,
        peer_reference_keys=bus_result.peer_reference_keys.merge(pcb_peer_keys),
        connector_peer_pin_finding_counts=connector_result.peer_pin_finding_counts,
        component_peer_pin_finding_counts=component_peer_result.finding_counts,
        mapped_topology_finding_counts=MappedTopologyFindingCounts(
            usb_data_path_mismatch=mapped_coverage_result.usb_data_path_finding_count,
            power_series_path_mismatch=mapped_coverage_result.power_path_finding_count,
            power_sequence_dependency_mismatch=mapped_coverage_result.power_sequence_finding_count,
            oscillator_output_path_mismatch=component_result.oscillator_output_path_finding_count,
            led_current_range_mismatch=sum(
                item.rule_id == "component.mapped_led_current_range_mismatch" for item in items
            ),
        ),
    )


def scan_candidates(inputs: DesignLintCandidateInputs) -> tuple[Candidate, ...]:
    """Compatibility adapter for callers that need only the flattened findings."""
    return scan_candidate_result(inputs).candidates
