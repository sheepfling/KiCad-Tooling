"""Reviewable heuristic findings from source-bound native netlist evidence."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from functools import lru_cache
from importlib.resources import files
from pathlib import Path
from typing import Literal
from uuid import uuid4

from ..validate import hashes
from .bus_heuristics import (
    ComplementaryPinFunctionAliasResolution,
    can_buses_without_local_termination,
    can_peer_assignment_divergences,
    complementary_signal_gaps,
    i2c_buses_with_low_equivalent_pullup_resistance,
    i2c_buses_with_multiple_pullup_rail_families,
    i2c_buses_without_local_pullups,
    resolve_complementary_pin_function_aliases,
    spi_active_low_chip_selects_without_pullups,
    unconnected_interface_pins,
)
from .bus_heuristics import (
    i2c_pullup_heuristic_coverage as resolve_i2c_pullup_heuristic_coverage,
)
from .connector_coverage import (
    evaluate as evaluate_connector_coverage,
)
from .connector_coverage import (
    source_matched_connector_peer_assignment_groups,
    source_matched_connector_pin_evidence,
)
from .connector_pins import (
    component_peer_power_pin_assignment_divergences,
    component_supply_pins_on_different_nets,
    connector_peer_pin_assignment_divergences,
    connector_peer_pin_assignment_outliers,
    connector_peer_pin_heuristic_coverage,
    connectors_without_connected_return,
    power_function_key,
    similar_connector_pin_groups,
    unconnected_generic_power_input_component_pins,
    unconnected_generic_power_input_connector_pins,
    unconnected_named_component_pins,
    unconnected_named_connector_pins,
)
from .connector_return_distribution import scan_connector_return_distribution_map
from .contract_coach import inspect_summary as inspect_contract_summary
from .contract_coach import pinned_image
from .contracts import parse_model_text, read_model, repo_path, write_model
from .control_inputs import (
    connected_control_inputs_without_visible_rail_resistor,
    control_input_bias_heuristic_coverage,
    unconnected_control_inputs,
)
from .crystal_networks import scan_crystal_network_map
from .differential_pair_names import named_differential_pairs
from .digital_peer_voltage_review import (
    DigitalPeerVoltageScan,
    format_nominal_voltage,
    scan_digital_peer_voltage_reviews,
)
from .discovery import load_config, load_registry
from .electrical import load_analysis
from .evidence import digest
from .external_protection import evaluate as evaluate_external_protection
from .i2c_addressing import scan_i2c_address_map, unmapped_i2c_responders
from .led_heuristics import (
    leds_directly_between_positive_and_return_nets,
    leds_directly_driven_without_visible_series_resistor,
    resolve_component_role_map,
)
from .models import (
    AnalysisNotApplicable,
    AnalysisPending,
    ComponentRoleMap,
    ConnectorCoverageReport,
    ConnectorMappedPinEvidence,
    ConnectorReturnDistributionCoverageReport,
    ConnectorReturnDistributionMap,
    ContractCoachReport,
    ControlInputBiasHeuristicCoverage,
    ControlInputsAnalysis,
    CrystalNetworkCoverageReport,
    CrystalNetworkMap,
    DesignLintFinding,
    DesignLintMappedCheckRun,
    DesignLintPolicy,
    DesignLintReport,
    DesignLintRuleCatalog,
    DesignLintRuleCatalogDocument,
    DesignLintRuleId,
    DesignLintRuleOverride,
    DigitalPeerVoltageAnalysis,
    DigitalPeerVoltageRuleCoverage,
    ExternalProtectionCoverageReport,
    I2cAddressCoverageReport,
    I2cAddressMap,
    I2cPullupAnalysis,
    I2cPullupHeuristicCoverage,
    I2cResponderAddressCoverageEntry,
    InterfaceRecord,
    InterfacesCatalog,
    NetlistContract,
    PcbDecouplingCoverageReport,
    PcbDecouplingMap,
    PcbDifferentialPairRuleCoverageReport,
    PcbDifferentialPairRuleMap,
    PcbProtectionPathCoverageReport,
    PcbProtectionPathMap,
    PcbReferencePlaneCoverageReport,
    PcbReferencePlaneMap,
    PcbSwitchingLoopCoverageReport,
    PcbSwitchingLoopMap,
    PcbTrackWidthCoverageReport,
    PcbTrackWidthMap,
    PowerPathMap,
    PowerSequenceMap,
    ProjectConfig,
    ProjectKind,
    ProjectManifest,
    RcFilterCoverageReport,
    RcFilterMap,
    RegulatorFeedbackCoverageReport,
    RegulatorFeedbackMap,
    SchematicGeometryCoverage,
    SchematicGeometryRuleCoverageStatus,
    SchematicGeometryRuleId,
    SchematicGeometrySourceBinding,
    SerialPeerAnalysis,
    SerialPeerReferenceCoverageReport,
    SerialPeerReferenceLinkCoverageEntry,
    SimilarConnectorPinGroup,
    SpiAnalysis,
    Stm32CubeMxPinMap,
    Stm32PinMapCoverageReport,
    Stm32PinMapMismatch,
    UsbCAnalysis,
    UsbCProtectionAnalysis,
    UsbDataPathMap,
    UsbPeerEndpointGroupCoverage,
    UsbPeerReferenceCoverageReport,
)
from .net_dc_reference import connector_capacitor_only_nets
from .open_drain_heuristics import open_output_bias_gaps
from .pcb_decoupling import pcb_decoupling_entries
from .pcb_drc_coverage import scan_source_bound_rule_map
from .pcb_protection_path import pcb_protection_path_entries
from .pcb_reference_planes import pcb_reference_plane_entries
from .pcb_return_paths import (
    capture_native_pcb_connectivity,
    expected_probe_sha256,
    native_pcb_command_matches,
)
from .pcb_switching_loops import pcb_switching_loop_entries
from .pcb_track_width import pcb_track_width_entries
from .power_decoupling import ic_power_rails_without_fitted_capacitors
from .power_paths import power_path_mismatches
from .power_pin_paths import power_inputs_without_supported_source_paths
from .power_rails import numbered_power_rail_groups
from .power_sequences import (
    power_sequence_graph_has_cycle,
    power_sequence_mismatches,
    power_sequence_observed_enable_cycles,
)
from .rc_filters import scan_rc_filter_map
from .regulator_feedback import scan_regulator_feedback_map
from .return_nets import (
    is_return_like_net_name,
    return_label_groups_without_pin_roles,
    return_net_groups,
)
from .schematic_geometry import (
    MAX_SHEET_OCCURRENCES,
    SchematicGeometryScan,
    resolve_schematic_sheet_path,
    scan_schematic_geometry_tree,
    schematic_sheet_references,
)
from .serial_participants import SerialPeerRosterContext, unmapped_serial_peers
from .serial_peer_reference_review import (
    SerialPeerReferenceScan,
    scan_serial_peer_reference_reviews,
)
from .spi_participants import SpiRosterContext, unmapped_spi_participants
from .stm32_pin_map import (
    CubeMxDocument,
    parse_cubemx_ioc,
    stm32_pin_map_mismatches,
    unmapped_stm32_devices,
)
from .two_pin_components import two_pin_components_on_same_net
from .usb_c_ports import UsbCPortRosterContext, unmapped_usb_c_ports
from .usb_data_paths import usb_data_path_mismatches
from .usb_peer_reference_review import UsbPeerReferenceScan, scan_usb_peer_reference_reviews


@dataclass(frozen=True)
class Candidate:
    rule_id: DesignLintRuleId
    subject: str
    message: str
    evidence: dict[str, tuple[str, ...]]


@dataclass(frozen=True)
class DigitalPeerVoltageLintContext:
    """Project contract state and provenance for covered SPI and UART prompts."""

    state: Literal["not_configured", "pending", "not_applicable", "required"]
    analysis: DigitalPeerVoltageAnalysis | None = None
    source_path: str | None = None
    source_sha256: str | None = None


def _schematic_geometry_evidence(
    scan: SchematicGeometryScan,
    sheet_instance_path: str,
) -> dict[str, tuple[str, ...]]:
    """Bind a geometry finding to its exact sheet occurrence and source bytes."""
    binding = next(
        (item for item in scan.source_bindings if item.sheet_instance_path == sheet_instance_path),
        None,
    )
    source_path = scan.source_path if binding is None else binding.source_path
    source_sha256 = scan.source_sha256 if binding is None else binding.source_sha256
    evidence = {
        "schematic": (source_path,),
        "schematic_sha256": (source_sha256,),
        "sheet_instance_path": (sheet_instance_path,),
        "sheet_path": (" / ".join(binding.sheet_path) if binding is not None else "",),
        "schematic_root": (scan.source_path,),
        "schematic_root_sha256": (scan.source_sha256,),
        "schematic_tree_sha256": (scan.source_tree_sha256 or scan.source_sha256,),
    }
    return evidence


_SCHEMATIC_GEOMETRY_RULE_IDS: tuple[SchematicGeometryRuleId, ...] = (
    "schematic.wire_end_on_pin_line",
    "schematic.pin_tip_on_wire_interior",
    "schematic.wire_endpoint_near_pin_tip",
    "schematic.label_near_wire_endpoint",
    "schematic.unmarked_wire_crossing",
    "schematic.unmarked_t_junction",
    "schematic.coincident_text_anchors",
    "schematic.free_text_overlap",
    "schematic.free_text_over_wire",
    "schematic.free_text_over_symbol_body",
    "schematic.wire_through_symbol_body",
)


def _schematic_geometry_coverage(
    scan: SchematicGeometryScan,
    netlist_sha256: str | None,
    rule_modes: Mapping[SchematicGeometryRuleId, Literal["review", "block", "off"]],
) -> SchematicGeometryCoverage:
    """Report completeness only for the schematic geometry rules the project enabled."""
    counts = {
        "schematic.wire_end_on_pin_line": len(scan.findings),
        "schematic.pin_tip_on_wire_interior": len(scan.pin_tip_on_wire_interiors),
        "schematic.wire_endpoint_near_pin_tip": len(scan.wire_endpoints_near_pin_tips),
        "schematic.label_near_wire_endpoint": len(scan.labels_near_wire_endpoints),
        "schematic.unmarked_wire_crossing": len(scan.unmarked_wire_crossings),
        "schematic.unmarked_t_junction": len(scan.unmarked_t_junctions),
        "schematic.coincident_text_anchors": len(scan.coincident_text_anchors),
        "schematic.free_text_overlap": len(scan.free_text_overlaps),
        "schematic.free_text_over_wire": len(scan.free_text_wire_overlaps),
        "schematic.free_text_over_symbol_body": len(scan.free_text_symbol_body_overlaps),
        "schematic.wire_through_symbol_body": len(scan.wires_through_symbol_bodies),
    }
    rule_coverage: dict[SchematicGeometryRuleId, SchematicGeometryRuleCoverageStatus] = {}
    active_issues: dict[SchematicGeometryRuleId, tuple[str, ...]] = {}
    for rule_id in _SCHEMATIC_GEOMETRY_RULE_IDS:
        mode = rule_modes[rule_id]
        if mode == "off":
            rule_coverage[rule_id] = "DISABLED"
            continue
        issues = scan.unsupported_by_rule.get(rule_id, ())
        if not scan.unsupported_by_rule and scan.status in {"PARTIAL", "UNSUPPORTED"}:
            issues = scan.unsupported
        if scan.status == "UNSUPPORTED":
            rule_coverage[rule_id] = "UNSUPPORTED"
            active_issues[rule_id] = issues or scan.unsupported
        elif issues:
            rule_coverage[rule_id] = "PARTIAL"
            active_issues[rule_id] = issues
        else:
            rule_coverage[rule_id] = "COMPLETE"

    active_rules: tuple[SchematicGeometryRuleId, ...] = tuple(
        rule_id for rule_id in _SCHEMATIC_GEOMETRY_RULE_IDS if rule_modes[rule_id] != "off"
    )
    active_statuses = tuple(rule_coverage[rule_id] for rule_id in active_rules)
    status: Literal["COMPLETE", "PARTIAL", "UNSUPPORTED", "DISABLED"] = (
        "DISABLED"
        if not active_rules
        else "UNSUPPORTED"
        if "UNSUPPORTED" in active_statuses
        else "PARTIAL"
        if "PARTIAL" in active_statuses
        else "COMPLETE"
    )
    mode: Literal["review", "block", "off"] = (
        "off"
        if not active_rules
        else "block"
        if any(rule_modes[rule_id] == "block" for rule_id in active_rules)
        else "review"
    )
    return SchematicGeometryCoverage(
        status=status,
        mode=mode,
        rule_modes=rule_modes,
        rule_coverage=rule_coverage,
        unsupported_by_rule=active_issues,
        source_path=scan.source_path,
        source_sha256=scan.source_sha256,
        source_tree_sha256=scan.source_tree_sha256,
        source_bindings=tuple(
            SchematicGeometrySourceBinding(
                source_path=item.source_path,
                source_sha256=item.source_sha256,
                sheet_instance_path=item.sheet_instance_path,
                sheet_path=item.sheet_path,
            )
            for item in scan.source_bindings
        ),
        netlist_sha256=netlist_sha256,
        kicad_version=scan.kicad_version,
        schematic_version=scan.schematic_version,
        finding_count=sum(counts.values()),
        unsupported=tuple(sorted({issue for issues in active_issues.values() for issue in issues})),
    )


@lru_cache(maxsize=1)
def rule_catalog() -> DesignLintRuleCatalog:
    """Load and hash the installed rule definition shipped with this package."""
    content = files("kicad_tooling.hwrepo").joinpath("design-lint-rules.json").read_bytes()
    document = parse_model_text(content.decode("utf-8"), DesignLintRuleCatalogDocument)
    return DesignLintRuleCatalog(
        schema_version=document.schema_version,
        sha256=hashlib.sha256(content).hexdigest(),
        rules=document.rules,
    )


def _connector_group_message(group: SimilarConnectorPinGroup) -> str:
    scope = (
        f" This comparison is scoped to source-reviewed peer-assignment group "
        f"{group.peer_assignment_group}."
        if group.peer_assignment_group is not None
        else ""
    )
    if group.reviewed_role == "supply" and group.reviewed_voltage_domain is not None:
        return (
            "Connector supply contacts with the same source-reviewed voltage domain "
            f"({group.reviewed_voltage_domain}) use different or missing nets. Review whether "
            "they share a rail, are intentionally switched or isolated, or have independent "
            "sources; this role and domain classification does not require commonality." + scope
        )
    function = group.function
    if function == "ground/return":
        return (
            "Connector return pins identified by symbol functions or the source-matched project "
            "interface map use different or missing nets. Review whether the domains should be "
            "common, bonded, or intentionally isolated; role classification alone does not "
            "require commonality." + scope
        )
    if power_function_key(function) is not None:
        return (
            "Matching connector supply pins use different or missing nets. Review whether they "
            "share a rail, are intentionally separate, or have independent supplies." + scope
        )
    return (
        "Matching connector pin functions use different or missing nets. Review the intended "
        "pinout and signal relationship." + scope
    )


def _connector_group_role_source_evidence(
    group: SimilarConnectorPinGroup,
    observed: NetlistContract,
    reviewed_connector_pins: Mapping[str, ConnectorMappedPinEvidence],
) -> dict[str, tuple[str, ...]]:
    if group.reviewed_role == "supply" and group.reviewed_voltage_domain is not None:
        domain = str(group.reviewed_voltage_domain)
        sources = [
            f"{pin}: project interface catalog role=supply; "
            f"voltage_domain={domain}; "
            f"native symbol function={observed.pin_functions.get(pin) or '<unnamed>'}"
            for pin in sorted(group.pins)
        ]
        return {
            "role_classification_sources": tuple(sources),
            "reviewed_voltage_domain": (domain,),
        }
    if group.function != "ground/return":
        return {}

    sources: list[str] = []
    has_catalog_role = False
    for pin in sorted(group.pins):
        native_function = observed.pin_functions.get(pin) or "<unnamed>"
        mapped = reviewed_connector_pins.get(pin)
        if mapped is not None and mapped.role == "return":
            has_catalog_role = True
            sources.append(
                f"{pin}: project interface catalog role=return; "
                f"native symbol function={native_function}"
            )
        else:
            sources.append(f"{pin}: native symbol function={native_function}")
    if not has_catalog_role:
        return {}
    return {"role_classification_sources": tuple(sources)}


def _format_i2c_address(address: int | None) -> str:
    return "dynamic or unresolved" if address is None else f"0x{address:02X}"


def _format_polygon_area_mm2(area_twice_nm2: int | None) -> str:
    if area_twice_nm2 is None:
        return "unavailable"
    millionths = (area_twice_nm2 + 1_000_000) // 2_000_000
    return f"{millionths // 1_000_000}.{millionths % 1_000_000:06d} mm^2"


def _i2c_address_evidence(
    entries: Sequence[I2cResponderAddressCoverageEntry],
) -> dict[str, tuple[str, ...]]:
    evidence: dict[str, tuple[str, ...]] = {}
    for entry in entries:
        evidence[f"{entry.reference}.symbol"] = (
            f"expected {entry.expected_symbol}; observed {entry.observed_symbol or 'unknown'}",
        )
        evidence[f"{entry.reference}.SDA"] = (
            f"{entry.sda_pin} -> {', '.join(entry.sda_nets) or 'unconnected'}",
        )
        evidence[f"{entry.reference}.SCL"] = (
            f"{entry.scl_pin} -> {', '.join(entry.scl_nets) or 'unconnected'}",
        )
        address_evidence = (
            f"expected {_format_i2c_address(entry.expected_address)}; "
            f"observed {_format_i2c_address(entry.observed_address)}"
        )
        evidence[f"{entry.reference}.address"] = (address_evidence,)
        for bit in entry.address_bits:
            bit_evidence = (
                f"{bit.pin} function {bit.observed_function or 'unknown'}; "
                f"nets {', '.join(bit.nets) or 'unconnected'}; "
                f"resolved {bit.resolved_value if bit.resolved_value is not None else 'unknown'}"
            )
            evidence[f"{entry.reference}.bit{bit.bit}"] = (bit_evidence,)
        evidence[f"{entry.reference}.basis"] = (entry.basis,)
    return evidence


def candidates(
    observed: NetlistContract,
    catalog: DesignLintRuleCatalog | None = None,
    schematic_geometry: SchematicGeometryScan | None = None,
    i2c_address_coverage: I2cAddressCoverageReport | None = None,
    external_protection_coverage: ExternalProtectionCoverageReport | None = None,
    crystal_network_coverage: CrystalNetworkCoverageReport | None = None,
    regulator_feedback_coverage: RegulatorFeedbackCoverageReport | None = None,
    rc_filter_coverage: RcFilterCoverageReport | None = None,
    connector_return_distribution: ConnectorReturnDistributionCoverageReport | None = None,
    pcb_decoupling_coverage: PcbDecouplingCoverageReport | None = None,
    pcb_protection_path_coverage: PcbProtectionPathCoverageReport | None = None,
    pcb_track_width_coverage: PcbTrackWidthCoverageReport | None = None,
    pcb_switching_loop_coverage: PcbSwitchingLoopCoverageReport | None = None,
    pcb_differential_pair_coverage: PcbDifferentialPairRuleCoverageReport | None = None,
    pcb_differential_pair_rule_map: PcbDifferentialPairRuleMap | None = None,
    i2c_address_map: I2cAddressMap | None = None,
    usb_data_path_map: UsbDataPathMap | None = None,
    stm32_pin_map_coverage: Stm32PinMapCoverageReport | None = None,
    spi_roster: SpiRosterContext | None = None,
    usb_c_port_roster: UsbCPortRosterContext | None = None,
    power_path_map: PowerPathMap | None = None,
    power_sequence_map: PowerSequenceMap | None = None,
    pcb_reference_plane_coverage: PcbReferencePlaneCoverageReport | None = None,
    control_input_bias_coverage: ControlInputBiasHeuristicCoverage | None = None,
    i2c_pullup_heuristic_coverage: I2cPullupHeuristicCoverage | None = None,
    digital_peer_voltage_context: DigitalPeerVoltageLintContext | None = None,
    component_role_map: ComponentRoleMap | None = None,
    serial_peer_roster: SerialPeerRosterContext | None = None,
    reviewed_connector_references: tuple[str, ...] = (),
    complementary_alias_resolution: ComplementaryPinFunctionAliasResolution | None = None,
    connector_coverage: ConnectorCoverageReport | None = None,
    digital_peer_voltage_scan: DigitalPeerVoltageScan | None = None,
    usb_peer_reference_scan: UsbPeerReferenceScan | None = None,
    serial_peer_reference_scan: SerialPeerReferenceScan | None = None,
) -> tuple[Candidate, ...]:
    """Named rules share one fingerprint and review-decision lifecycle."""
    reviewed_connector_pins = source_matched_connector_pin_evidence(
        observed,
        connector_coverage,
    )
    reviewed_connector_peer_assignment_groups = source_matched_connector_peer_assignment_groups(
        observed,
        connector_coverage,
    )
    found: list[Candidate] = []
    unconnected_named_pins = unconnected_named_connector_pins(
        observed,
        reviewed_connector_references,
        reviewed_connector_pins,
    )
    named_open_connector_pins = frozenset(item.pin for item in unconnected_named_pins)
    unconnected_power_input_pins = unconnected_generic_power_input_connector_pins(
        observed,
        reviewed_connector_references,
        excluded_pins=named_open_connector_pins,
    )
    unconnected_power_input_pin_keys = frozenset(
        item.pin.casefold() for item in unconnected_power_input_pins
    )
    for pin in unconnected_power_input_pins:
        evidence = {
            "symbol": (pin.symbol,),
            "pin_electrical_type": (pin.electrical_type,),
            pin.pin: (),
        }
        if pin.function is not None:
            evidence["native_pin_function"] = (pin.function,)
        found.append(
            Candidate(
                rule_id="connector.unconnected_power_input",
                subject=f"{pin.pin}: generic native power-input pin is unassigned",
                message=(
                    "KiCad's native symbol metadata classifies this generic connector pin as "
                    "power_in, but the exported netlist assigns it to no net. Review the approved "
                    "pinout to determine whether the contact is intentionally open or whether a "
                    "power or reference connection is missing. The electrical type does not "
                    "identify the contact's specific role or require it to be connected."
                ),
                evidence=evidence,
            )
        )
    for bridge in leds_directly_between_positive_and_return_nets(observed):
        found.append(
            Candidate(
                rule_id="component.led_directly_across_supply_and_return",
                subject=f"{bridge.reference}: LED directly spans supply and return",
                message=(
                    "Both pins of this supported two-pin LED symbol are assigned directly to a "
                    "recognized positive rail and return net. Review whether a visible series "
                    "limiting element or a current-controlled driver is missing, and verify the "
                    "device polarity and source behavior. Netlist topology alone does not "
                    "establish operating current, off-board limiting, or physical board paths."
                ),
                evidence={
                    "symbol": (bridge.symbol,),
                    "led_pins": bridge.pins,
                    "positive_net": (bridge.positive_net,),
                    "return_net": (bridge.return_net,),
                },
            )
        )
    for led in leds_directly_driven_without_visible_series_resistor(observed, component_role_map):
        role_evidence = (
            {}
            if led.role_binding is None
            else {
                "classified_role": (led.role_binding.role,),
                "role_part_id": (led.role_binding.part_id,),
                "role_symbol": (led.role_binding.symbol,),
                "role_footprint": (led.role_binding.footprint,),
                "role_pin_inventory": tuple(
                    f"{pin.number}={pin.function}/{pin.electrical_type}"
                    for pin in sorted(
                        led.role_binding.pins,
                        key=lambda item: (item.number.casefold(), item.number),
                    )
                ),
                "role_basis": (led.role_binding.basis,),
                "role_binding_sha256": (led.role_binding_sha256 or "",),
            }
        )
        found.append(
            Candidate(
                rule_id="component.led_directly_driven_from_output",
                subject=f"{led.reference}: LED directly shares an output net and a rail",
                message=(
                    "A native output-capable pin shares one LED terminal net, and the other LED "
                    "terminal is directly assigned to a recognized supply or return. Review "
                    "whether the output or assembly provides intentional current limiting or a "
                    "series element is missing. This prompt does not infer LED polarity, allowed "
                    "current, output limits, or off-board behavior."
                ),
                evidence={
                    "symbol": (led.symbol,),
                    "led_pins": led.led_pins,
                    "output_pins": led.output_pins,
                    "output_pin_types": led.output_pin_types,
                    "driven_net": (led.driven_net,),
                    "opposite_net": (led.opposite_net,),
                    "opposite_net_role": (led.opposite_net_role,),
                    **role_evidence,
                },
            )
        )
    mapped_capacitor_references = tuple(
        reference
        for reference, binding in resolve_component_role_map(
            observed, component_role_map
        ).by_reference.items()
        if binding.role == "capacitor"
    )
    for gap in ic_power_rails_without_fitted_capacitors(
        observed, reviewed_connector_references, mapped_capacitor_references
    ):
        found.append(
            Candidate(
                rule_id="power.ic_rail_without_fitted_capacitor",
                subject=f"{gap.net}: IC supply decoupling review",
                message=(
                    "This recognized positive rail has IC power-input pins but no fitted "
                    "capacitor connected to a distinct return-like schematic net. Review the "
                    "device datasheets and intended placement; net presence alone does not "
                    "establish local placement, value, or a physical return path."
                ),
                evidence={
                    "net": (gap.net,),
                    "power_input_pins": gap.input_pins,
                    "component_references": gap.component_references,
                },
            )
        )
    mapped_power_input_pins: frozenset[str] = (
        frozenset(path.end.pin for path in power_path_map.paths)
        if power_path_map is not None
        else frozenset[str]()
    )
    for gap in power_inputs_without_supported_source_paths(
        observed,
        covered_input_pins=mapped_power_input_pins,
        declared_connector_references=reviewed_connector_references,
    ):
        if gap.source_nets:
            source_path_message = (
                "A fitted power-input pin shares a net with a fitted capacitor to a return, "
                "but no supported path was found to any recognized positive rail or fitted "
                "power_out pin. Review the intended source and any switching, isolation, or "
                "external supply path."
            )
            source_anchor_state = "recognized"
        else:
            source_path_message = (
                "A fitted power-input pin shares a net with a fitted capacitor to a return, "
                "but no recognized positive-rail net or fitted power_out pin was found to "
                "establish a source anchor. Review custom rail names, external connector "
                "supplies, or an intentionally isolated domain; a project-authored power-path "
                "map can record the required relationship."
            )
            source_anchor_state = "not_recognized"
        found.append(
            Candidate(
                rule_id="power.input_without_supported_source_path",
                subject=f"{gap.net}: power-input source-path review",
                message=(
                    source_path_message
                    + " This heuristic recognizes only native-inventoried two-pin "
                    "low-resistance resistors, inductors, ferrite beads, fuses, and polyfuses; "
                    "it does not prove that a connection is required or that a path conducts."
                ),
                evidence={
                    "net": (gap.net,),
                    "power_input_pins": gap.input_pins,
                    "fitted_capacitors_to_return": gap.capacitor_references,
                    "recognized_source_nets": gap.source_nets,
                    "source_anchor_state": (source_anchor_state,),
                },
            )
        )
    for net in connector_capacitor_only_nets(observed, reviewed_connector_references):
        found.append(
            Candidate(
                rule_id="net.connector_capacitor_only_no_dc_anchor",
                subject=f"{net.net}: connector/capacitor-only net",
                message=(
                    "Every fitted pin assigned to this net belongs to a supported connector or "
                    "capacitor symbol, so the schematic shows no local DC-driving or biasing "
                    "component on this net. Review whether a local DC reference is required "
                    "or supplied by an off-board source, internal bias, or circuitry outside "
                    "this bounded pattern. This heuristic does not trace a complete DC path, "
                    "identify an analog function, or prove that the circuit is missing a required "
                    "bias."
                ),
                evidence={
                    "net": (net.net,),
                    "connector_pins": net.connector_pins,
                    "capacitor_pins": net.capacitor_pins,
                    "component_symbols": net.component_symbols,
                },
            )
        )
    repeated_connector_pin_groups = similar_connector_pin_groups(
        observed,
        reviewed_connector_references,
        reviewed_connector_pins,
        reviewed_connector_peer_assignment_groups,
    )
    for group in repeated_connector_pin_groups:
        group_pin_keys = {pin.casefold() for pin in group.pins}
        if group_pin_keys and group_pin_keys <= unconnected_power_input_pin_keys:
            # The native power-input type provides the more specific open-pin finding.
            continue
        found.append(
            Candidate(
                rule_id="connector.repeated_pin_function",
                subject=f"{group.symbol}: {group.function}",
                message=_connector_group_message(group),
                evidence={
                    **dict(group.pins),
                    **_connector_group_role_source_evidence(
                        group,
                        observed,
                        reviewed_connector_pins,
                    ),
                    **(
                        {}
                        if group.peer_assignment_group is None
                        else {
                            "peer_assignment_group": (group.peer_assignment_group,),
                            "peer_assignment_basis": group.peer_assignment_basis,
                        }
                    ),
                },
            )
        )
    for group in connector_peer_pin_assignment_outliers(
        observed,
        reviewed_connector_references,
        reviewed_connector_peer_assignment_groups,
    ):
        if {pin.casefold() for pin in group.outlier_pins} <= unconnected_power_input_pin_keys:
            # The typed power-input finding already identifies every open outlier pin.
            continue
        if any(
            set(group.assignments) <= set(specific_group.pins)
            for specific_group in repeated_connector_pin_groups
        ):
            # A source-matched role finding already gives the same peers' exact
            # per-pin net assignments and a more useful classification.
            continue
        evidence = dict(group.assignments)
        evidence["symbol"] = (group.symbol,)
        evidence["pin_number"] = (group.pin_number,)
        evidence["outlier_pins"] = group.outlier_pins
        if group.peer_assignment_group is not None:
            evidence["peer_assignment_group"] = (group.peer_assignment_group,)
            evidence["peer_assignment_basis"] = group.peer_assignment_basis
        found.append(
            Candidate(
                rule_id="connector.peer_pin_assignment_outlier",
                subject=f"{group.symbol} pin {group.pin_number}",
                message=(
                    "The same pin number on fitted instances of this exact connector symbol has "
                    "an unconnected or minority assignment, and at least one peer has no "
                    "meaningful native pin-function role. Review the approved pinout and any "
                    "intentional per-port isolation; matching symbol contacts do not prove that "
                    "their nets must be common."
                    + (
                        " The comparison is scoped by a source-reviewed peer-assignment group."
                        if group.peer_assignment_group is not None
                        else ""
                    )
                ),
                evidence=evidence,
            )
        )
    for group in connector_peer_pin_assignment_divergences(
        observed,
        reviewed_connector_references,
        reviewed_connector_peer_assignment_groups,
    ):
        if any(
            set(group.assignments) <= set(specific_group.pins)
            for specific_group in repeated_connector_pin_groups
        ):
            # Keep one finding when the higher-confidence role comparison
            # already covers every contact in this generic peer group.
            continue
        found.append(
            Candidate(
                rule_id="connector.peer_pin_assignment_divergence",
                subject=f"{group.symbol} pin {group.pin_number}",
                message=(
                    "Fitted instances of this exact connector symbol assign the same pin number "
                    "to different nets, and at least one instance has no meaningful native "
                    "pin-function role. KiCad's generic Pin_N placeholder is treated as unknown. "
                    "Review the approved pinout to decide whether these assignments should match "
                    "or are intentionally independent; symbol identity alone does not establish "
                    "a required connection."
                    + (
                        " The comparison is scoped by a source-reviewed peer-assignment group."
                        if group.peer_assignment_group is not None
                        else ""
                    )
                ),
                evidence={
                    **group.assignments,
                    "symbol": (group.symbol,),
                    "pin_number": (group.pin_number,),
                    "missing_pin_function_pins": group.missing_function_pins,
                    **(
                        {}
                        if group.peer_assignment_group is None
                        else {
                            "peer_assignment_group": (group.peer_assignment_group,),
                            "peer_assignment_basis": group.peer_assignment_basis,
                        }
                    ),
                },
            )
        )
    for group in component_supply_pins_on_different_nets(observed, reviewed_connector_references):
        found.append(
            Candidate(
                rule_id="component.repeated_supply_pin_function",
                subject=f"{group.reference} ({group.symbol}): {group.function} supply pins",
                message=(
                    "Pins on this component with a matching supply function use different or "
                    "ambiguous nets. Review the component pinout for an intended split, filter, "
                    "or missing connection."
                ),
                evidence=dict(group.pins),
            )
        )
    for group in component_peer_power_pin_assignment_divergences(
        observed, reviewed_connector_references
    ):
        if group.role == "ground/return":
            message = (
                "The same recognized return pin on fitted non-connector components with this exact "
                "symbol is assigned to different nets. Review whether the domains are intentionally "
                "separate or a return connection is missing; matching symbol pins do not prove the "
                "nets should be common."
            )
        else:
            message = (
                "The same recognized supply pin on fitted non-connector components with this exact "
                "symbol is assigned to different nets. Review whether the separate rails are "
                "intentional or a supply connection is missing; matching symbol pins do not prove "
                "the nets should be common."
            )
        found.append(
            Candidate(
                rule_id="component.peer_power_pin_assignment_divergence",
                subject=(
                    f"{group.symbol} pin {group.pin_number} ({group.function}): "
                    "peer power assignments differ"
                ),
                message=message,
                evidence={
                    **group.assignments,
                    "symbol": (group.symbol,),
                    "pin_number": (group.pin_number,),
                    "pin_function": (group.function,),
                    "peer_role": (group.role,),
                },
            )
        )
    for component in two_pin_components_on_same_net(observed):
        pin_assignments = tuple(
            f"{component.reference}.{number} -> {component.net}" for number in component.pin_numbers
        )
        if component.kind == "diode":
            rule_id: DesignLintRuleId = "component.two_pin_diode_same_net"
            message = (
                "Both pins of this supported fitted two-pin diode are assigned to the same "
                "schematic net, bypassing the device in that netlist. Review the intended "
                "topology, population state, and footprint pin mapping. This finding does not "
                "establish that the topology is wrong."
            )
            kind_evidence = {"component_kind": (component.kind,)}
        elif component.kind == "crystal":
            rule_id = "component.two_pin_crystal_same_net"
            message = (
                "Both pins of this supported fitted two-pin crystal are assigned to the same "
                "schematic net, shorting its two terminals in that netlist. Review whether the "
                "crystal is intentionally bypassed or a resonator path is missing. This finding "
                "does not establish that the topology is wrong."
            )
            kind_evidence = {"component_kind": (component.kind,)}
        elif component.kind in {"fuse", "polyfuse"}:
            rule_id = "component.two_pin_fuse_same_net"
            message = (
                "Both pins of this supported fitted two-pin fuse are assigned to the same "
                "schematic net, bypassing the protection element in that netlist. Review "
                "whether the fuse is intentionally bypassed or a series protection path is "
                "missing. This finding does not establish that the topology is wrong."
            )
            kind_evidence = {"component_kind": (component.kind,)}
        elif component.kind == "ferrite_bead":
            rule_id = "component.two_pin_ferrite_same_net"
            message = (
                "Both pins of this supported fitted two-pin ferrite bead are assigned to the same "
                "schematic net, bypassing the filter element in that netlist. Review whether the "
                "bead is intentionally bypassed or a series filter path is missing. This finding "
                "does not establish that the topology is wrong."
            )
            kind_evidence = {"component_kind": (component.kind,)}
        else:
            rule_id = "component.two_pin_passive_same_net"
            message = (
                "Both pins of this supported fitted two-pin passive are assigned to the "
                "same schematic net, so the part is bypassed by that net assignment. "
                "Review the intended topology, population state, and any deliberate jumper "
                "or measurement use. This finding does not establish that the topology is "
                "wrong."
            )
            kind_evidence = {"passive_kind": (component.kind,)}
        found.append(
            Candidate(
                rule_id=rule_id,
                subject=(
                    f"{component.reference} ({component.value} {component.kind}) "
                    "has both pins on one net"
                ),
                message=message,
                evidence={
                    "symbol": (component.symbol,),
                    "value": (component.value,),
                    **kind_evidence,
                    "net": (component.net,),
                    "pin_assignments": pin_assignments,
                },
            )
        )
    repeated_pin_evidence = {
        pin
        for item in found
        if item.rule_id == "connector.repeated_pin_function"
        for pin in item.evidence
    }
    for pin in unconnected_named_pins:
        # A repeated-function finding already reports missing members in its group.
        if pin.pin in repeated_pin_evidence:
            continue
        if pin.category == "supply":
            rule_id: DesignLintRuleId = "connector.unconnected_supply_pin"
            description = "supply"
            review = "whether it is intentionally unused or a power connection is missing"
        else:
            rule_id = "connector.unconnected_return_pin"
            description = "return"
            review = (
                "whether it is intentionally unused or isolated, or a return connection is missing"
            )
        found.append(
            Candidate(
                rule_id=rule_id,
                subject=f"{pin.pin}: {pin.function}",
                message=(
                    f"This source-matched project interface maps the connector contact as {description}, "
                    f"but it has no net assignment. Review {review}."
                    if pin.role_source == "project_interface"
                    else f"This named connector {description} pin has no net assignment. "
                    f"Review {review}."
                ),
                evidence={
                    pin.pin: (),
                    **(
                        {"role_source": ("project interface catalog",)}
                        if pin.role_source == "project_interface"
                        else {}
                    ),
                },
            )
        )
    for pin in unconnected_generic_power_input_component_pins(
        observed, reviewed_connector_references
    ):
        evidence = {
            "symbol": (pin.symbol,),
            "pin_electrical_type": (pin.electrical_type,),
            pin.pin: (),
        }
        if pin.function is not None:
            evidence["native_pin_function"] = (pin.function,)
        found.append(
            Candidate(
                rule_id="component.unconnected_power_input",
                subject=f"{pin.pin}: generic native power-input pin is unassigned",
                message=(
                    "KiCad's native symbol metadata classifies this generic component pin as "
                    "power_in, but the exported netlist assigns it to no net. Review whether the "
                    "pin is intentionally open or a power/reference connection is missing. The "
                    "electrical type does not identify the pin's specific role or require it to "
                    "be connected."
                ),
                evidence=evidence,
            )
        )
    for pin in unconnected_named_component_pins(observed, reviewed_connector_references):
        if pin.category == "supply":
            rule_id: DesignLintRuleId = "component.unconnected_supply_pin"
            description = "supply"
        else:
            rule_id = "component.unconnected_return_pin"
            description = "return"
        found.append(
            Candidate(
                rule_id=rule_id,
                subject=f"{pin.pin}: {pin.function}",
                message=(
                    f"This component's named {description} pin has no net assignment. "
                    "Review whether the pin is intentionally unused or a connection is missing."
                ),
                evidence={pin.pin: ()},
            )
        )
    for pin in unconnected_control_inputs(observed):
        found.append(
            Candidate(
                rule_id="control.unconnected_control_input",
                subject=f"{pin.pin}: {pin.function}",
                message=(
                    f"This recognized {pin.family} input pin has no net assignment. Review "
                    "whether it is intentionally unused, handled by internal/off-board "
                    "circuitry, or missing a connection."
                ),
                evidence={
                    pin.pin: (),
                    "function": (pin.function,),
                    "family": (pin.family,),
                    "electrical_type": (pin.electrical_type,),
                },
            )
        )
    covered_control_nets = {
        entry.net.casefold()
        for entry in (
            () if control_input_bias_coverage is None else control_input_bias_coverage.entries
        )
        if entry.status == "COVERED"
    }
    for gap in connected_control_inputs_without_visible_rail_resistor(observed):
        if gap.net.casefold() in covered_control_nets:
            continue
        controls = tuple(
            f"{control.pin}: {control.function} ({control.family}, {control.electrical_type})"
            for control in gap.controls
        )
        found.append(
            Candidate(
                rule_id="control.connected_control_input_without_visible_bias",
                subject=f"{gap.net}: connected control input has no visible rail resistor",
                message=(
                    "This assigned net contains a recognized reset, enable, or boot/strap input, "
                    "but no fitted conventional resistor is directly visible between the net "
                    "and a recognized positive or return net. Review whether an internal or "
                    "off-board bias, a connected driver, or another topology establishes the "
                    "intended state, and whether a local path is required. This finding does "
                    "not establish that a resistor is required."
                ),
                evidence={
                    "net": (gap.net,),
                    "control_inputs": controls,
                    "output_capable_peers": gap.output_capable_peers,
                },
            )
        )
    for gap in open_output_bias_gaps(observed):
        bias_description = (
            "pull-up to a recognized positive rail"
            if gap.bias == "pull_up"
            else "pull-down to a recognized return"
        )
        output_kind = "open-collector" if gap.bias == "pull_up" else "open-emitter"
        found.append(
            Candidate(
                rule_id=(
                    "signal.open_collector_input_without_visible_bias"
                    if gap.bias == "pull_up"
                    else "signal.open_emitter_input_without_visible_bias"
                ),
                subject=f"{gap.net}: {output_kind} signal has no visible local bias resistor",
                message=(
                    f"This assigned net joins a native {output_kind} output pin and a native input, "
                    f"but no fitted conventional resistor is visible for the expected {bias_description}. "
                    "Review whether an internal or off-board bias, or another topology, establishes "
                    "the intended state and whether a local resistor is required. This prompt does "
                    "not establish that a resistor is required or that any visible resistor has a "
                    "suitable value."
                ),
                evidence={
                    "net": (gap.net,),
                    "expected_bias": (bias_description,),
                    "open_output_pins": gap.output_pins,
                    "input_pins": gap.input_pins,
                    "visible_resistors_on_signal_net": gap.visible_resistors,
                },
            )
        )
    connectors_with_unconnected_return = {
        item.pin.rsplit(".", 1)[0] for item in unconnected_named_pins if item.category == "return"
    }
    for group in connectors_without_connected_return(
        observed,
        reviewed_connector_references,
        reviewed_connector_pins,
    ):
        # A specifically named unconnected return is a more precise finding.
        if group.reference in connectors_with_unconnected_return:
            continue
        return_named_candidates = tuple(
            f"{pin}: {net}"
            for pin, nets in sorted(group.pins.items())
            for net in nets
            if is_return_like_net_name(net)
        )
        message = (
            f"This connector has {group.connected_pin_count} connected non-shield pins, but no "
            "native symbol function or a source-matched project interface role identifies a connected "
            "ground/return. Review the approved "
            "pinout to determine whether one contact is a signal return or the interface is "
            "intentionally isolated."
        )
        evidence = dict(group.pins)
        if return_named_candidates:
            message += (
                " Some assigned net labels look return-related; their spelling does not "
                "identify the connector pin role."
            )
            evidence["return_named_net_candidates"] = return_named_candidates
        found.append(
            Candidate(
                rule_id="connector.no_connected_return",
                subject=(
                    f"{group.reference}: return pin role not identified"
                    if return_named_candidates
                    else f"{group.reference}: no connected return"
                ),
                message=message,
                evidence=evidence,
            )
        )
    for group in return_net_groups(observed):
        found.append(
            Candidate(
                rule_id="net.numbered_returns",
                subject=group.stem,
                message=(
                    "Separately numbered return nets may be intended as one return domain. "
                    "Review whether they are common, bonded, or intentionally isolated."
                ),
                evidence=dict(group.nets),
            )
        )
    for group in numbered_power_rail_groups(observed):
        found.append(
            Candidate(
                rule_id="net.numbered_power_rails",
                subject=group.stem,
                message=(
                    "Separately numbered positive supply nets may be intended as one rail. "
                    "Review whether they are common, intentionally isolated, or represent "
                    "independent supplies; similar names do not establish a required connection."
                ),
                evidence=dict(group.nets),
            )
        )
    for group in return_label_groups_without_pin_roles(observed):
        found.append(
            Candidate(
                rule_id="net.return_labels_without_pin_roles",
                subject=group.stem,
                message=(
                    "Multiple return-like net labels are assigned to pins whose exported symbol "
                    "functions do not identify a return. Review the connector pinout and decide "
                    "whether these domains are common, bonded, or intentionally isolated; labels "
                    "alone do not establish that they should be joined."
                ),
                evidence=dict(group.nets),
            )
        )
    pullup_coverage_entries = (
        ()
        if i2c_pullup_heuristic_coverage is None
        or i2c_pullup_heuristic_coverage.status == "BLOCKED"
        else i2c_pullup_heuristic_coverage.entries
    )
    covered_i2c_pullup_gaps = {
        (
            entry.sda_net.casefold(),
            entry.scl_net.casefold(),
            entry.missing_lines,
        )
        for entry in pullup_coverage_entries
        if entry.status == "COVERED"
    }
    for bus in i2c_buses_without_local_pullups(observed):
        if (
            bus.sda_net.casefold(),
            bus.scl_net.casefold(),
            bus.missing_lines,
        ) in covered_i2c_pullup_gaps:
            continue
        found.append(
            Candidate(
                rule_id="bus.i2c_missing_pullup",
                subject=f"SDA {bus.sda_net} / SCL {bus.scl_net}",
                message=(
                    "This named SDA/SCL pair has no visible 1 kΩ–100 kΩ resistor path to a "
                    "named positive rail on "
                    f"{', '.join(bus.missing_lines)}. Review internal or off-board pull-ups."
                ),
                evidence={
                    "SDA": (bus.sda_net,),
                    "SCL": (bus.scl_net,),
                    "pins": (*bus.sda_pins, *bus.scl_pins),
                    "missing_pullups": bus.missing_lines,
                },
            )
        )
    for bus in i2c_buses_with_low_equivalent_pullup_resistance(observed):
        found.append(
            Candidate(
                rule_id="bus.i2c_low_equivalent_resistance",
                subject=f"SDA {bus.sda_net} / SCL {bus.scl_net}",
                message=(
                    "Recognized fitted pull-ups in parallel have nominal effective resistance "
                    f"below 1 kΩ on {', '.join(bus.lines)}. Review the approved bus range, rail, "
                    "and sink-current limits; capacitance and timing are not modeled."
                ),
                evidence={
                    "SDA": (bus.sda_net,),
                    "SCL": (bus.scl_net,),
                    "lines": bus.lines,
                    "pins": (*bus.pins["SDA"], *bus.pins["SCL"]),
                    "equivalent_ohms": tuple(
                        f"{line}={bus.equivalent_ohms[line]}Ω" for line in bus.lines
                    ),
                    "pullup_resistors": tuple(
                        item for line in bus.lines for item in bus.resistors[line]
                    ),
                },
            )
        )
    for bus in i2c_buses_with_multiple_pullup_rail_families(observed):
        found.append(
            Candidate(
                rule_id="bus.i2c_multiple_pullup_rail_families",
                subject=f"SDA {bus.sda_net} / SCL {bus.scl_net}",
                message=(
                    "Visible fitted I2C pull-up paths use different recognized positive-rail "
                    f"families ({', '.join(bus.rail_families)}). Review the bus voltage limits, "
                    "pull-up rail, and any level-shifting topology; rail names alone do not "
                    "establish voltage compatibility."
                ),
                evidence={
                    "SDA": (bus.sda_net,),
                    "SCL": (bus.scl_net,),
                    "pins": bus.pins,
                    "rail_families": bus.rail_families,
                    "pullup_paths": bus.pullup_paths,
                },
            )
        )
    for gap in spi_active_low_chip_selects_without_pullups(observed):
        found.append(
            Candidate(
                rule_id="bus.spi_active_low_chip_select_without_pullup",
                subject=f"{gap.net}: active-low SPI chip-select bias",
                message=(
                    "This assigned active-low chip-select input has no visible 1 kΩ–100 kΩ "
                    "resistor path to a recognized positive rail. Review the device's reset-time "
                    "state and any internal or off-board bias; the pin name alone does not "
                    "establish that an external pull-up is required."
                ),
                evidence={
                    "net": (gap.net,),
                    "active_low_chip_select_pins": gap.pins,
                    "recognized_positive_rails": gap.positive_rails,
                    "visible_pullup_paths": (),
                },
            )
        )
    for pin in unconnected_interface_pins(observed):
        if pin.protocol == "i2c":
            rule_id: DesignLintRuleId = "bus.i2c_unconnected_pin"
            description = "I²C signal"
        elif pin.protocol == "spi":
            rule_id = "bus.spi_unconnected_chip_select"
            description = "SPI chip-select"
        elif pin.protocol == "usb_c":
            rule_id = "bus.usb_c_unconnected_cc_pin"
            description = "USB-C configuration-channel"
        else:
            rule_id = "bus.can_unconnected_line"
            description = "CANH/CANL line"
        found.append(
            Candidate(
                rule_id=rule_id,
                subject=f"{pin.pin}: {pin.function}",
                message=(
                    f"This named {description} pin has no net assignment. Review whether it is "
                    "intentionally unused or a connection is missing."
                ),
                evidence={pin.pin: (), "function": (pin.function,)},
            )
        )
    for bus in can_buses_without_local_termination(observed):
        found.append(
            Candidate(
                rule_id="bus.can_missing_termination",
                subject=f"CANH {bus.high_net} / CANL {bus.low_net}",
                message=(
                    "No visible 108 Ω–132 Ω resistor is connected directly across these named "
                    "CAN lines. Review external or split termination and the intended bus topology."
                ),
                evidence={
                    "CANH": (bus.high_net,),
                    "CANL": (bus.low_net,),
                    "pins": (*bus.high_pins, *bus.low_pins),
                    "termination": (),
                },
            )
        )
    for divergence in can_peer_assignment_divergences(observed):
        found.append(
            Candidate(
                rule_id="bus.can_peer_assignment_divergence",
                subject=(
                    f"{divergence.shared_role} {divergence.shared_net}: "
                    "peer pair assignments diverge"
                ),
                message=(
                    f"Complete CAN pin pairs share {divergence.shared_role} net "
                    f"{divergence.shared_net}, but their {divergence.complementary_role} "
                    f"pins use multiple nets ({', '.join(divergence.complementary_nets)}). "
                    "Review whether the separate pair assignments are intentional; pin names "
                    "do not establish common-bus intent or physical connectivity."
                ),
                evidence={
                    "shared_role": (divergence.shared_role,),
                    "shared_net": (divergence.shared_net,),
                    "complementary_role": (divergence.complementary_role,),
                    "complementary_nets": divergence.complementary_nets,
                    "participants": divergence.participants,
                },
            )
        )
    for gap in complementary_signal_gaps(observed, complementary_alias_resolution):
        if (
            gap.family == "CAN"
            and gap.alias_symbol is None
            and gap.pins["positive"]
            and gap.pins["negative"]
            and (not gap.nets["positive"] or not gap.nets["negative"])
        ):
            # The per-pin CAN rule already reports open CANH/CANL assignments.
            continue
        evidence = {
            "positive_pins": gap.pins["positive"],
            "negative_pins": gap.pins["negative"],
            "positive_nets": gap.nets["positive"],
            "negative_nets": gap.nets["negative"],
        }
        if gap.alias_symbol is not None:
            if gap.alias_basis is None or gap.alias_sha256 is None:
                raise AssertionError(
                    "Resolved complementary aliases must retain their basis digest"
                )
            evidence.update(
                {
                    "alias_symbol": (gap.alias_symbol,),
                    "alias_basis": (gap.alias_basis,),
                    "alias_sha256": (gap.alias_sha256,),
                }
            )
        found.append(
            Candidate(
                rule_id="bus.complementary_pair_assignment",
                subject=f"{gap.reference}: {gap.family} pair",
                message=(
                    f"A recognized {gap.family} complementary pair has an incomplete or ambiguous "
                    f"schematic assignment: {gap.reason}. Review the interface pin map."
                ),
                evidence=evidence,
            )
        )
    for pair in named_differential_pairs(observed.nets, pcb_differential_pair_rule_map):
        found.append(
            Candidate(
                rule_id="signal.named_pair_without_reviewed_requirement",
                subject=f"{pair.positive_net} / {pair.negative_net}",
                message=(
                    "These source net names match a recognized complementary-signal pattern. "
                    "Review whether they form a physical differential pair and, if so, add "
                    "project-owned PCB constraints. The name pattern does not establish pair "
                    "intent, routing quality, or an acceptable skew limit."
                ),
                evidence={
                    "positive_net": (pair.positive_net,),
                    "positive_references": pair.positive_references,
                    "negative_net": (pair.negative_net,),
                    "negative_references": pair.negative_references,
                    "naming_pattern": (pair.naming_pattern,),
                },
            )
        )
    if schematic_geometry is not None:
        for item in schematic_geometry.findings:
            endpoint_x, endpoint_y = item.wire_endpoint_mm
            found.append(
                Candidate(
                    rule_id="schematic.wire_end_on_pin_line",
                    subject=f"{item.reference}.{item.pin_number}: wire endpoint on pin segment",
                    message=(
                        "The native netlist marks this pin unconnected, while a wire endpoint lies "
                        "along its transformed pin segment. Review the schematic and intended "
                        "connection before changing the drawing."
                    ),
                    evidence={
                        **_schematic_geometry_evidence(
                            schematic_geometry, item.sheet_instance_path
                        ),
                        "symbol": (item.symbol_library_id,),
                        "symbol_uuid": (item.symbol_uuid,),
                        "pin": (f"{item.reference}.{item.pin_number}",),
                        "pin_uuid": (item.pin_uuid or "<unavailable>",),
                        "pin_tip_mm": (f"{item.pin_tip_mm[0]:.6f},{item.pin_tip_mm[1]:.6f}",),
                        "wire_uuid": (item.wire_uuid,),
                        "wire_endpoint_mm": (f"{endpoint_x:.6f},{endpoint_y:.6f}",),
                        "distance_to_pin_tip_mm": (f"{item.distance_to_pin_tip_mm:.6f}",),
                        "distance_along_pin_mm": (f"{item.distance_along_pin_mm:.6f}",),
                        "kicad_version": (schematic_geometry.kicad_version,),
                    },
                )
            )
        for item in schematic_geometry.pin_tip_on_wire_interiors:
            pin_x, pin_y = item.pin_tip_mm
            start_x, start_y = item.wire_segment_start_mm
            end_x, end_y = item.wire_segment_end_mm
            found.append(
                Candidate(
                    rule_id="schematic.pin_tip_on_wire_interior",
                    subject=f"{item.reference}.{item.pin_number}: pin tip on wire interior",
                    message=(
                        "The native netlist marks this pin unconnected, although its tip lies on "
                        "the interior of a wire segment. Review whether a junction or explicit "
                        "connection is intended; the lint does not edit schematic geometry."
                    ),
                    evidence={
                        **_schematic_geometry_evidence(
                            schematic_geometry, item.sheet_instance_path
                        ),
                        "symbol": (item.symbol_library_id,),
                        "symbol_uuid": (item.symbol_uuid,),
                        "pin": (f"{item.reference}.{item.pin_number}",),
                        "pin_uuid": (item.pin_uuid or "<unavailable>",),
                        "pin_tip_mm": (f"{pin_x:.6f},{pin_y:.6f}",),
                        "wire_uuid": (item.wire_uuid,),
                        "wire_segment_start_mm": (f"{start_x:.6f},{start_y:.6f}",),
                        "wire_segment_end_mm": (f"{end_x:.6f},{end_y:.6f}",),
                        "distance_to_wire_mm": (f"{item.distance_to_wire_mm:.6f}",),
                        "kicad_version": (schematic_geometry.kicad_version,),
                    },
                )
            )
        for item in schematic_geometry.wire_endpoints_near_pin_tips:
            endpoint_x, endpoint_y = item.wire_endpoint_mm
            pin_x, pin_y = item.pin_tip_mm
            found.append(
                Candidate(
                    rule_id="schematic.wire_endpoint_near_pin_tip",
                    subject=f"{item.reference}.{item.pin_number}: wire endpoint near pin tip",
                    message=(
                        "The native netlist marks this pin unconnected, and a wire endpoint is "
                        f"{item.distance_to_pin_tip_mm:.3f} mm from its tip. Review this near miss "
                        "and the native ERC finding; the lint does not connect or repair the "
                        "schematic."
                    ),
                    evidence={
                        **_schematic_geometry_evidence(
                            schematic_geometry, item.sheet_instance_path
                        ),
                        "symbol": (item.symbol_library_id,),
                        "symbol_uuid": (item.symbol_uuid,),
                        "pin": (f"{item.reference}.{item.pin_number}",),
                        "pin_uuid": (item.pin_uuid or "<unavailable>",),
                        "pin_tip_mm": (f"{pin_x:.6f},{pin_y:.6f}",),
                        "wire_uuid": (item.wire_uuid,),
                        "wire_endpoint_mm": (f"{endpoint_x:.6f},{endpoint_y:.6f}",),
                        "distance_to_pin_tip_mm": (f"{item.distance_to_pin_tip_mm:.6f}",),
                        "kicad_version": (schematic_geometry.kicad_version,),
                    },
                )
            )
        for item in schematic_geometry.labels_near_wire_endpoints:
            endpoint_evidence = tuple(
                f"{candidate.wire_uuid}@{candidate.wire_endpoint_mm[0]:.6f},"
                f"{candidate.wire_endpoint_mm[1]:.6f} "
                f"({candidate.distance_mm:.6f} mm)"
                for candidate in item.candidates
            )
            found.append(
                Candidate(
                    rule_id="schematic.label_near_wire_endpoint",
                    subject=f"{item.label_kind} {item.text!r}: near wire endpoint",
                    message=(
                        "This label anchor misses nearby wire geometry but lies within the "
                        "heuristic's 1.27 mm review radius of a wire endpoint. Review whether the "
                        "label or wire should meet; the lint does not change the drawing."
                    ),
                    evidence={
                        **_schematic_geometry_evidence(
                            schematic_geometry, item.sheet_instance_path
                        ),
                        "label_kind": (item.label_kind,),
                        "label_text": (item.text,),
                        "label_uuid": (item.label_uuid,),
                        "label_anchor_mm": (f"{item.anchor_mm[0]:.6f},{item.anchor_mm[1]:.6f}",),
                        "near_wire_endpoints": endpoint_evidence,
                        "kicad_version": (schematic_geometry.kicad_version,),
                    },
                )
            )
        for item in schematic_geometry.unmarked_wire_crossings:
            x, y = item.crossing_mm
            found.append(
                Candidate(
                    rule_id="schematic.unmarked_wire_crossing",
                    subject=f"unmarked orthogonal wire crossing at {x:.3f},{y:.3f} mm",
                    message=(
                        "Two wire interiors cross without a junction marker. Review whether the "
                        "signals should connect; intentional unconnected crossings are valid and "
                        "will also be reported."
                    ),
                    evidence={
                        **_schematic_geometry_evidence(
                            schematic_geometry, item.sheet_instance_path
                        ),
                        "crossing_mm": (f"{x:.6f},{y:.6f}",),
                        "wire_uuids": item.wire_uuids,
                        "kicad_version": (schematic_geometry.kicad_version,),
                    },
                )
            )
        for item in schematic_geometry.unmarked_t_junctions:
            x, y = item.junction_mm
            found.append(
                Candidate(
                    rule_id="schematic.unmarked_t_junction",
                    subject=f"unmarked T-junction at {x:.3f},{y:.3f} mm",
                    message=(
                        "A wire endpoint touches the interior of another wire without a junction "
                        "marker. Review whether the branch should connect; this geometry hint "
                        "does not join or repair nets."
                    ),
                    evidence={
                        **_schematic_geometry_evidence(
                            schematic_geometry, item.sheet_instance_path
                        ),
                        "junction_mm": (f"{x:.6f},{y:.6f}",),
                        "endpoint_wire_uuid": (item.endpoint_wire_uuid,),
                        "interior_wire_uuid": (item.interior_wire_uuid,),
                        "kicad_version": (schematic_geometry.kicad_version,),
                    },
                )
            )
        for item in schematic_geometry.coincident_text_anchors:
            x, y = item.anchor_mm
            found.append(
                Candidate(
                    rule_id="schematic.coincident_text_anchors",
                    subject=f"free-text anchors coincide at {x:.3f},{y:.3f} mm",
                    message=(
                        "Two free-text objects use coincident insertion anchors. Review their "
                        "rendered placement; anchor coincidence alone does not prove glyph "
                        "overlap or a design error."
                    ),
                    evidence={
                        **_schematic_geometry_evidence(
                            schematic_geometry, item.sheet_instance_path
                        ),
                        "anchor_mm": (f"{x:.6f},{y:.6f}",),
                        "first_text": (item.first_text,),
                        "first_text_uuid": (item.first_uuid,),
                        "second_text": (item.second_text,),
                        "second_text_uuid": (item.second_uuid,),
                        "kicad_version": (schematic_geometry.kicad_version,),
                    },
                )
            )
        for item in schematic_geometry.free_text_overlaps:
            x0, y0, x1, y1 = item.overlap_box_mm
            found.append(
                Candidate(
                    rule_id="schematic.free_text_overlap",
                    subject=(f"free-text envelopes overlap: {item.first_uuid}, {item.second_uuid}"),
                    message=(
                        "Two top-level free-text glyph envelopes overlap. Review the rendered "
                        "sheet; this approximate standard-font geometry is a drawing-quality "
                        "hint, not an electrical finding or an edit instruction."
                    ),
                    evidence={
                        **_schematic_geometry_evidence(
                            schematic_geometry, item.sheet_instance_path
                        ),
                        "first_text": (item.first_text,),
                        "first_text_uuid": (item.first_uuid,),
                        "first_text_box_mm": (
                            ",".join(f"{value:.6f}" for value in item.first_box_mm),
                        ),
                        "second_text": (item.second_text,),
                        "second_text_uuid": (item.second_uuid,),
                        "second_text_box_mm": (
                            ",".join(f"{value:.6f}" for value in item.second_box_mm),
                        ),
                        "overlap_box_mm": (f"{x0:.6f},{y0:.6f},{x1:.6f},{y1:.6f}",),
                        "kicad_version": (schematic_geometry.kicad_version,),
                    },
                )
            )
        for item in schematic_geometry.free_text_wire_overlaps:
            start_x, start_y = item.wire_segment_start_mm
            end_x, end_y = item.wire_segment_end_mm
            box = ",".join(f"{value:.6f}" for value in item.text_box_mm)
            found.append(
                Candidate(
                    rule_id="schematic.free_text_over_wire",
                    subject=f"wire {item.wire_uuid} crosses free-text envelope {item.text_uuid}",
                    message=(
                        "A schematic wire centerline intersects a guarded free-text glyph envelope. "
                        "Review the rendered sheet; this approximate graphical finding does not "
                        "change connectivity or imply electrical intent."
                    ),
                    evidence={
                        **_schematic_geometry_evidence(
                            schematic_geometry, item.sheet_instance_path
                        ),
                        "text": (item.text,),
                        "text_uuid": (item.text_uuid,),
                        "text_box_mm": (box,),
                        "wire_uuid": (item.wire_uuid,),
                        "overlap_segment_mm": (
                            f"{start_x:.6f},{start_y:.6f},{end_x:.6f},{end_y:.6f}",
                        ),
                        "overlap_length_mm": (f"{item.overlap_length_mm:.6f}",),
                        "kicad_version": (schematic_geometry.kicad_version,),
                    },
                )
            )
        for item in schematic_geometry.free_text_symbol_body_overlaps:
            overlap_box = ",".join(f"{value:.6f}" for value in item.overlap_box_mm)
            body_box = ",".join(f"{value:.6f}" for value in item.body_box_mm)
            text_box = ",".join(f"{value:.6f}" for value in item.text_box_mm)
            found.append(
                Candidate(
                    rule_id="schematic.free_text_over_symbol_body",
                    subject=f"free text {item.text_uuid} overlaps {item.reference} body envelope",
                    message=(
                        "A supported free-text glyph envelope overlaps a guarded symbol-body "
                        "envelope. Review the rendered sheet; axis-aligned bounds can include "
                        "empty space and do not establish electrical meaning."
                    ),
                    evidence={
                        **_schematic_geometry_evidence(
                            schematic_geometry, item.sheet_instance_path
                        ),
                        "text": (item.text,),
                        "text_uuid": (item.text_uuid,),
                        "text_box_mm": (text_box,),
                        "reference": (item.reference,),
                        "symbol_library_id": (item.symbol_library_id,),
                        "symbol_uuid": (item.symbol_uuid,),
                        "body_box_mm": (body_box,),
                        "overlap_box_mm": (overlap_box,),
                        "overlap_area_mm2": (f"{item.overlap_area_mm2:.6f}",),
                        "kicad_version": (schematic_geometry.kicad_version,),
                    },
                )
            )
        for item in schematic_geometry.wires_through_symbol_bodies:
            start_x, start_y = item.overlap_start_mm
            end_x, end_y = item.overlap_end_mm
            body_box = ",".join(f"{value:.6f}" for value in item.body_box_mm)
            found.append(
                Candidate(
                    rule_id="schematic.wire_through_symbol_body",
                    subject=f"wire {item.wire_uuid} crosses {item.reference} body envelope",
                    message=(
                        "A schematic wire centerline runs through a guarded symbol-body envelope. "
                        "Review the rendered sheet; the bounding box is graphical evidence and "
                        "does not establish pin connectivity or design intent."
                    ),
                    evidence={
                        **_schematic_geometry_evidence(
                            schematic_geometry, item.sheet_instance_path
                        ),
                        "reference": (item.reference,),
                        "symbol_library_id": (item.symbol_library_id,),
                        "symbol_uuid": (item.symbol_uuid,),
                        "body_box_mm": (body_box,),
                        "wire_uuid": (item.wire_uuid,),
                        "overlap_segment_mm": (
                            f"{start_x:.6f},{start_y:.6f},{end_x:.6f},{end_y:.6f}",
                        ),
                        "overlap_length_mm": (f"{item.overlap_length_mm:.6f}",),
                        "kicad_version": (schematic_geometry.kicad_version,),
                    },
                )
            )
    if i2c_address_coverage is not None:
        for entry in i2c_address_coverage.entries:
            if (
                entry.status == "COMPLETE"
                and entry.mode == "strapped"
                and entry.expected_address != entry.observed_address
            ):
                found.append(
                    Candidate(
                        rule_id="bus.i2c_address_mismatch",
                        subject=(
                            f"{entry.reference} on {entry.segment_id}: "
                            f"{_format_i2c_address(entry.observed_address)}"
                        ),
                        message=(
                            "Source-bound address-pin nets resolve to a different static I2C "
                            "address than the project map declares. Review the strap wiring, "
                            "device profile, or approved address."
                        ),
                        evidence={
                            "segment": (entry.segment_id,),
                            **_i2c_address_evidence((entry,)),
                        },
                    )
                )
        address_groups: dict[tuple[str, int], list[I2cResponderAddressCoverageEntry]] = {}
        for entry in i2c_address_coverage.entries:
            if entry.status == "COMPLETE" and entry.observed_address is not None:
                address_groups.setdefault((entry.segment_id, entry.observed_address), []).append(
                    entry
                )
        for (segment_id, address), entries in sorted(address_groups.items()):
            if len(entries) < 2:
                continue
            references = tuple(sorted(entry.reference for entry in entries))
            found.append(
                Candidate(
                    rule_id="bus.i2c_address_collision",
                    subject=f"{segment_id}: {', '.join(references)} at {_format_i2c_address(address)}",
                    message=(
                        "Multiple fitted responders on this declared I2C segment resolve to the "
                        "same static address. Review the address map or any mux isolation not "
                        "represented by the declared segment."
                    ),
                    evidence={
                        "segment": (segment_id,),
                        "address": (_format_i2c_address(address),),
                        **_i2c_address_evidence(entries),
                    },
                )
            )

    for responder in unmapped_i2c_responders(observed, i2c_address_map):
        net_pairs = tuple(f"{sda} / {scl}" for sda, scl in responder.signal_pairs)
        has_map = i2c_address_map is not None
        found.append(
            Candidate(
                rule_id="bus.i2c_unmapped_responder",
                subject=f"{responder.reference}: I2C address-map coverage",
                message=(
                    f"{responder.reference} has assigned native SDA/SCL pin functions but "
                    + (
                        "is not listed as a responder in the project address map. "
                        if has_map
                        else "no project I2C address map is configured. "
                    )
                    + "Review whether it is a static or dynamic responder, or intentionally "
                    "outside address checking."
                ),
                evidence={
                    "SDA_pins": responder.sda_pins,
                    "SCL_pins": responder.scl_pins,
                    "assigned_net_pairs": net_pairs,
                    "address_map": (("configured",) if has_map else ("not_configured",)),
                },
            )
        )

    serial_scope = serial_peer_roster or SerialPeerRosterContext(state="not_configured")
    serial_analysis = serial_scope.analysis
    for peer in unmapped_serial_peers(observed, serial_scope):
        if serial_scope.state == "required":
            scope_text = "is not listed in the project serial-peer map"
        elif serial_scope.state == "pending":
            scope_text = "is a candidate while the project serial-peer review remains pending"
        elif serial_scope.state == "not_applicable":
            scope_text = (
                "is a candidate despite the project serial-peer review being marked not applicable"
            )
        else:
            scope_text = "has no configured project serial-peer map"
        evidence = {
            "interface_channel": (peer.channel,),
            "TX_pins": peer.tx_pins,
            "RX_pins": peer.rx_pins,
            "assigned_signal_pins": peer.signal_assignments,
            "discovery_basis": (peer.discovery_basis,),
            "serial_peer_map_state": (serial_scope.state,),
        }
        if serial_scope.source_path is not None:
            evidence["electrical_contract_path"] = (serial_scope.source_path,)
        if serial_scope.source_sha256 is not None:
            evidence["electrical_contract_sha256"] = (serial_scope.source_sha256,)
        found.append(
            Candidate(
                rule_id="bus.serial_unmapped_peer",
                subject=(f"{peer.reference}: serial-peer map coverage ({peer.channel})"),
                message=(
                    f"{peer.reference} has "
                    + (
                        "assigned TX/RX-like pin functions"
                        if peer.discovery_basis == "pin_function"
                        else "assigned pins on explicitly UART/USART-labeled TX/RX nets"
                    )
                    + f" and {scope_text}. Review whether it is a missing logic-level UART "
                    "endpoint, an unused alternate function, or another interface. Net labels "
                    "are discovery clues only; this prompt does not assert that a peer or "
                    "connection is required."
                ),
                evidence=evidence,
            )
        )

    serial_reference_scan = serial_peer_reference_scan or scan_serial_peer_reference_reviews(
        observed, serial_analysis, reviewed_connector_references
    )
    for peer in serial_reference_scan.reviews:
        shared_links = tuple(
            f"{link.net}: {link.output_pin} ({link.output_function}, {link.output_type}) -> "
            f"{link.input_pin} ({link.input_function}, {link.input_type})"
            for link in peer.links
        )
        evidence = {
            "first_component": (peer.first_reference,),
            "second_component": (peer.second_reference,),
            "first_reference_net": (peer.first_reference_domain.net,),
            "first_reference_pin_assignments": tuple(
                f"{item.pin} ({item.function}, {item.electrical_type})={item.net}"
                for item in peer.first_reference_domain.pins
            ),
            "second_reference_net": (peer.second_reference_domain.net,),
            "second_reference_pin_assignments": tuple(
                f"{item.pin} ({item.function}, {item.electrical_type})={item.net}"
                for item in peer.second_reference_domain.pins
            ),
            "serial_peer_map_state": (serial_scope.state,),
        }
        if peer.links:
            evidence["shared_serial_pin_assignments"] = shared_links
        if peer.label_links:
            evidence["serial_label_link_assignments"] = tuple(
                f"{link.channel}: TX {link.tx_net} ({link.first_tx_pin}, {link.second_tx_pin}); "
                f"RX {link.rx_net} ({link.first_rx_pin}, {link.second_rx_pin})"
                for link in peer.label_links
            )
            evidence["discovery_basis"] = (
                ("native_pin_function", "net_label") if peer.links else ("net_label",)
            )
        if serial_scope.source_path is not None:
            evidence["electrical_contract_path"] = (serial_scope.source_path,)
        if serial_scope.source_sha256 is not None:
            evidence["electrical_contract_sha256"] = (serial_scope.source_sha256,)
        message = (
            "Source-bound UART TX and RX pins share a native signal net while their "
            "explicitly named reference pins use separate schematic nets. Review the "
            "approved interface requirement for a common reference, an explicit bond, "
            "or intentional isolation. This prompt does not establish board copper or "
            "off-board reference continuity."
        )
        if peer.label_links and not peer.links:
            message = (
                "Exact UART/USART TX and RX channel labels connect the same two fitted ICs, "
                "while their explicitly named reference pins use separate schematic nets. "
                "Review whether this is a direct peer or one segment of a translated path, "
                "and whether its references should be common, bonded, or intentionally "
                "separate. This prompt does not trace other components or establish board "
                "copper or off-board reference continuity."
            )
        found.append(
            Candidate(
                rule_id="bus.serial_peer_reference_review",
                subject=(
                    f"{peer.first_reference} / {peer.second_reference}: serial reference-domain review"
                ),
                message=message,
                evidence=evidence,
            )
        )

    usb_data_map_sha256 = (
        hashlib.sha256(usb_data_path_map.model_dump_json().encode("utf-8")).hexdigest()
        if usb_data_path_map is not None
        else None
    )
    usb_scan = usb_peer_reference_scan or scan_usb_peer_reference_reviews(
        observed, usb_data_path_map, reviewed_connector_references
    )
    for peer in usb_scan.reviews:
        connector_identity = (
            f"{peer.connector_reference}: {peer.connector_symbol}; {peer.connector_footprint}"
        )
        positive_link = (
            f"{', '.join(peer.data_link.connector_positive_pins)} / "
            f"{', '.join(peer.data_link.phy_positive_pins)}"
        )
        negative_link = (
            f"{', '.join(peer.data_link.connector_negative_pins)} / "
            f"{', '.join(peer.data_link.phy_negative_pins)}"
        )
        if peer.data_link.positive_series_resistor is None:
            positive_link += f"={peer.data_link.connector_positive_net}"
        else:
            positive_link += (
                f"={peer.data_link.connector_positive_net} to "
                f"{peer.data_link.phy_positive_net} through "
                f"{peer.data_link.positive_series_resistor.reference}"
            )
        if peer.data_link.negative_series_resistor is None:
            negative_link += f"={peer.data_link.connector_negative_net}"
        else:
            negative_link += (
                f"={peer.data_link.connector_negative_net} to "
                f"{peer.data_link.phy_negative_net} through "
                f"{peer.data_link.negative_series_resistor.reference}"
            )
        evidence = {
            "connector": (connector_identity,),
            "phy": (f"{peer.phy_reference}: {peer.phy_symbol}; {peer.phy_footprint}",),
            "connector_reference_net": (peer.connector_reference_net,),
            "connector_reference_pin_assignments": tuple(
                f"{item.pin} ({item.function}, {item.electrical_type})={item.net}"
                for item in peer.connector_reference_pins
            ),
            "phy_reference_net": (peer.phy_reference_net,),
            "phy_reference_pin_assignments": tuple(
                f"{item.pin} ({item.function}, {item.electrical_type})={item.net}"
                for item in peer.phy_reference_pins
            ),
            "USB_D+_link": (positive_link,),
            "USB_D-_link": (negative_link,),
            "USB_data_map_state": (
                "configured" if usb_data_path_map is not None else "not_configured",
            ),
        }
        if peer.data_link.port_group is not None:
            evidence["USB_port_group"] = (peer.data_link.port_group,)
        if peer.data_link.positive_shunt_branches:
            evidence["USB_D+_shunt_branches"] = tuple(
                f"{branch.data_pin} ({branch.symbol}) to "
                f"{branch.reference_pin}={branch.reference_net}"
                for branch in peer.data_link.positive_shunt_branches
            )
        if peer.data_link.negative_shunt_branches:
            evidence["USB_D-_shunt_branches"] = tuple(
                f"{branch.data_pin} ({branch.symbol}) to "
                f"{branch.reference_pin}={branch.reference_net}"
                for branch in peer.data_link.negative_shunt_branches
            )
        if peer.data_link.positive_series_resistor is not None:
            resistor = peer.data_link.positive_series_resistor
            evidence["USB_D+_series_resistor"] = (
                (
                    f"{resistor.reference} ({resistor.symbol}, {resistor.value or 'unspecified'}; "
                    f"{resistor.connector_pin}={resistor.connector_net}, "
                    f"{resistor.phy_pin}={resistor.phy_net})"
                ),
            )
        if peer.data_link.negative_series_resistor is not None:
            resistor = peer.data_link.negative_series_resistor
            evidence["USB_D-_series_resistor"] = (
                (
                    f"{resistor.reference} ({resistor.symbol}, {resistor.value or 'unspecified'}; "
                    f"{resistor.connector_pin}={resistor.connector_net}, "
                    f"{resistor.phy_pin}={resistor.phy_net})"
                ),
            )
        if usb_data_map_sha256 is not None:
            evidence["USB_data_map_sha256"] = (usb_data_map_sha256,)
        found.append(
            Candidate(
                rule_id="bus.usb_peer_reference_review",
                subject=(
                    f"{peer.connector_reference} / {peer.phy_reference}: "
                    "USB reference-domain review"
                    + (
                        f" (port {peer.data_link.port_group})"
                        if peer.data_link.port_group is not None
                        else ""
                    )
                ),
                message=(
                    "Supported USB 2.0 D+ and D- connector-to-PHY paths (direct or through one "
                    "fitted two-pin series resistor per line) have separate explicit endpoint "
                    "reference nets. Review whether this interface needs a common reference, an "
                    "explicit bond, or intentional isolation. Pin functions and the bounded "
                    "topology only identify a candidate; this prompt does not prove the required "
                    "relationship, component behavior, PCB copper, or off-board continuity."
                ),
                evidence=evidence,
            )
        )

    spi_scope = spi_roster or SpiRosterContext(state="not_configured")
    for participant in unmapped_spi_participants(observed, spi_scope):
        if spi_scope.state == "required":
            scope_text = "is not listed in the project SPI device map"
        elif spi_scope.state == "pending":
            scope_text = "is a candidate while the project SPI review remains pending"
        elif spi_scope.state == "not_applicable":
            scope_text = "is a candidate despite the project SPI review being marked not applicable"
        else:
            scope_text = "has no configured project SPI device map"
        evidence = {
            "SCK_pins": participant.clock_pins,
            "input_data_pins": participant.input_data_pins,
            "output_data_pins": participant.output_data_pins,
            "chip_select_pins": participant.chip_select_pins,
            "assigned_signal_pins": participant.signal_assignments,
            "SPI_roster_state": (spi_scope.state,),
        }
        if spi_scope.source_path is not None:
            evidence["electrical_contract_path"] = (spi_scope.source_path,)
        if spi_scope.source_sha256 is not None:
            evidence["electrical_contract_sha256"] = (spi_scope.source_sha256,)
        found.append(
            Candidate(
                rule_id="bus.spi_unmapped_participant",
                subject=f"{participant.reference}: SPI roster coverage",
                message=(
                    f"{participant.reference} has assigned SPI-like clock/data pin functions and "
                    f"a named chip-select function, and {scope_text}. Review whether it is an "
                    "omitted device, an SPI controller, or a pin-function match for another "
                    "interface. This is a coverage prompt, not a finding that the design must "
                    "connect or include the device."
                ),
                evidence=evidence,
            )
        )

    peer_voltage_scope = digital_peer_voltage_context or DigitalPeerVoltageLintContext(
        state="not_configured"
    )
    peer_voltage_scan = digital_peer_voltage_scan or scan_digital_peer_voltage_reviews(
        observed, peer_voltage_scope.analysis
    )
    for peer in (item for item in peer_voltage_scan.reviews if item.interface == "SPI"):
        shared_links = tuple(
            f"{link.net}: {link.output_pin} ({link.output_function}, {link.output_type}) -> "
            f"{link.input_pin} ({link.input_function}, {link.input_type})"
            for link in peer.links
        )
        evidence = {
            "output_component": (peer.output_reference,),
            "input_component": (peer.input_reference,),
            "output_supply_net": (peer.output_rail.net,),
            "output_supply_label_value": (format_nominal_voltage(peer.output_rail.voltage_v),),
            "input_supply_net": (peer.input_rail.net,),
            "input_supply_label_value": (format_nominal_voltage(peer.input_rail.voltage_v),),
            "shared_SPI_pin_assignments": shared_links,
            "authored_voltage_map_state": (peer_voltage_scope.state,),
        }
        if peer_voltage_scope.source_path is not None:
            evidence["electrical_contract_path"] = (peer_voltage_scope.source_path,)
        if peer_voltage_scope.source_sha256 is not None:
            evidence["electrical_contract_sha256"] = (peer_voltage_scope.source_sha256,)
        found.append(
            Candidate(
                rule_id="bus.spi_peer_voltage_review",
                subject=(
                    f"{peer.output_reference} -> {peer.input_reference}: SPI voltage-domain review"
                ),
                message=(
                    "Source-bound native pins show an SPI output-capable endpoint and input-capable "
                    "peer on one net, while their uniquely identified power-input nets contain "
                    "different voltage-explicit labels. Treat those parsed label values as review "
                    "clues only. Confirm sourced supply, output, and receiver limits; this prompt "
                    "does not establish incompatibility or recommend level translation. A complete "
                    "exact digital-peer voltage map is checked separately."
                ),
                evidence=evidence,
            )
        )

    for peer in (item for item in peer_voltage_scan.reviews if item.interface == "serial"):
        shared_links = tuple(
            f"{link.net}: {link.output_pin} ({link.output_function}, {link.output_type}) -> "
            f"{link.input_pin} ({link.input_function}, {link.input_type})"
            for link in peer.links
        )
        evidence = {
            "output_component": (peer.output_reference,),
            "input_component": (peer.input_reference,),
            "output_supply_net": (peer.output_rail.net,),
            "output_supply_label_value": (format_nominal_voltage(peer.output_rail.voltage_v),),
            "input_supply_net": (peer.input_rail.net,),
            "input_supply_label_value": (format_nominal_voltage(peer.input_rail.voltage_v),),
            "shared_serial_pin_assignments": shared_links,
            "authored_voltage_map_state": (peer_voltage_scope.state,),
        }
        if peer_voltage_scope.source_path is not None:
            evidence["electrical_contract_path"] = (peer_voltage_scope.source_path,)
        if peer_voltage_scope.source_sha256 is not None:
            evidence["electrical_contract_sha256"] = (peer_voltage_scope.source_sha256,)
        found.append(
            Candidate(
                rule_id="bus.serial_peer_voltage_review",
                subject=(
                    f"{peer.output_reference} -> {peer.input_reference}: serial voltage-domain review"
                ),
                message=(
                    "Source-bound native pins show a UART-like TX output-capable endpoint and "
                    "RX input-capable peer on one net, while their uniquely identified power-input "
                    "nets contain different voltage-explicit labels. Treat those parsed label values "
                    "as review clues only. Confirm sourced supply, output, and receiver limits; this "
                    "prompt does not establish incompatibility or recommend level translation. A "
                    "complete exact digital-peer voltage map is checked separately."
                ),
                evidence=evidence,
            )
        )

    usb_c_scope = usb_c_port_roster or UsbCPortRosterContext(state="not_configured")
    if usb_c_scope.state == "required":
        usb_c_scope_text = "is not listed in the project USB-C port role map"
    elif usb_c_scope.state == "pending":
        usb_c_scope_text = "is a candidate while the project USB-C port review remains pending"
    elif usb_c_scope.state == "not_applicable":
        usb_c_scope_text = (
            "is a candidate despite the project USB-C review being marked not applicable"
        )
    else:
        usb_c_scope_text = "has no configured project USB-C port role map"
    for port in unmapped_usb_c_ports(observed, usb_c_scope, reviewed_connector_references):
        evidence = {
            "CC1_pins": port.cc1_pins,
            "CC2_pins": port.cc2_pins,
            "CC_assignments": port.signal_assignments,
            "USB_C_roster_state": (usb_c_scope.state,),
        }
        if usb_c_scope.source_path is not None:
            evidence["electrical_contract_path"] = (usb_c_scope.source_path,)
        if usb_c_scope.source_sha256 is not None:
            evidence["electrical_contract_sha256"] = (usb_c_scope.source_sha256,)
        found.append(
            Candidate(
                rule_id="bus.usb_c_unreviewed_port",
                subject=f"{port.reference}: USB-C role-map coverage",
                message=(
                    f"{port.reference} exports connector pin functions CC1 and CC2 and "
                    f"{usb_c_scope_text}. Review whether this is a USB-C port and, if so, "
                    "record its approved source, sink, or dual-role requirements. The pin names "
                    "do not establish port role, Rp/Rd, controller behavior, VBUS path, or "
                    "protection requirements."
                ),
                evidence=evidence,
            )
        )

    if external_protection_coverage is not None:
        for entry in external_protection_coverage.entries:
            if entry.status == "UNDECLARED":
                found.append(
                    Candidate(
                        rule_id="protection.unreviewed_interface_pin",
                        subject=(
                            f"{entry.connector_pin}: "
                            f"{entry.interface_signal or 'external interface signal'}"
                        ),
                        message=(
                            "This project-reviewed connector pin has no protection applicability "
                            "decision. Map the required protector channel or record a reasoned "
                            "not-required decision; the rule does not assume protection is needed."
                        ),
                        evidence={
                            "connector": (entry.connector_reference,),
                            "signal": (entry.interface_signal or "unknown",),
                            "net": entry.observed_nets,
                        },
                    )
                )
            elif entry.status in {"INCOMPLETE", "STALE"}:
                found.append(
                    Candidate(
                        rule_id="protection.mapped_device_mismatch",
                        subject=f"{entry.connector_pin}: mapped protection requirement",
                        message=(
                            "The project-mapped protection identity or pin/net assignment differs "
                            "from source-bound native evidence. Review the connector map and device "
                            "pinout."
                        ),
                        evidence={
                            "connector": (entry.connector_reference,),
                            "signal": (entry.interface_signal or "unknown",),
                            "expected_net": (entry.signal_net or "<not declared>",),
                            "observed_nets": entry.observed_nets,
                            "protection_devices": entry.device_references,
                            "issues": entry.issues,
                        },
                    )
                )
    if crystal_network_coverage is not None:
        for entry in crystal_network_coverage.entries:
            if entry.status == "COMPLETE":
                continue
            calculated = (
                "unavailable"
                if entry.calculated_minimum_load_pf is None
                or entry.calculated_maximum_load_pf is None
                else (
                    f"{entry.calculated_minimum_load_pf:g}–{entry.calculated_maximum_load_pf:g} pF"
                )
            )
            found.append(
                Candidate(
                    rule_id="oscillator.crystal_load_network_mismatch",
                    subject=f"{entry.oscillator_reference}: mapped crystal load network",
                    message=(
                        "The source-bound oscillator, resonator, load-capacitor topology, or "
                        "nominal load estimate differs from the project-authored requirement. "
                        "Review the exact pin map and device requirements."
                    ),
                    evidence={
                        "oscillator": (entry.oscillator_reference,),
                        "resonator": (entry.resonator_reference,),
                        "load_capacitors": entry.load_capacitor_references,
                        "potential_extra_load_capacitors": entry.extra_capacitor_references,
                        "potential_extra_load_capacitor_pin_nets": tuple(
                            f"{reference}: {', '.join(pin_nets)}"
                            for reference, pin_nets in sorted(
                                entry.extra_capacitor_pin_nets.items()
                            )
                        ),
                        "pin_nets": tuple(
                            f"{pin} -> {', '.join(nets) or 'unconnected'}"
                            for pin, nets in sorted(entry.node_nets.items())
                        ),
                        "capacitance_pf": tuple(
                            f"{reference}={value:g} pF"
                            for reference, value in sorted(entry.capacitance_pf.items())
                        ),
                        "formula": (entry.formula,),
                        "calculated_nominal_load_pf": (calculated,),
                        "target_nominal_load_pf": (
                            (
                                f"{entry.target_minimum_load_pf:g}–"
                                f"{entry.target_maximum_load_pf:g} pF"
                            ),
                        ),
                        "stray_capacitance_assumption_pf": (
                            (
                                f"{entry.minimum_stray_capacitance_pf:g}–"
                                f"{entry.maximum_stray_capacitance_pf:g} pF"
                            ),
                        ),
                        "basis": (entry.basis,),
                        "issues": entry.issues,
                    },
                )
            )
    if regulator_feedback_coverage is not None:
        for entry in regulator_feedback_coverage.entries:
            if entry.status == "COMPLETE":
                continue
            calculated = (
                "unavailable"
                if entry.calculated_output_minimum_v is None
                or entry.calculated_output_maximum_v is None
                else (
                    f"{entry.calculated_output_minimum_v:g}–{entry.calculated_output_maximum_v:g} V"
                )
            )
            feedback_reference_range = (
                f"{entry.feedback_reference_minimum_v:g}–{entry.feedback_reference_maximum_v:g} V"
            )
            target_output_range = (
                f"{entry.target_output_minimum_v:g}–{entry.target_output_maximum_v:g} V"
            )
            found.append(
                Candidate(
                    rule_id="power.regulator_feedback_mismatch",
                    subject=f"{entry.regulator_reference}: mapped feedback divider",
                    message=(
                        "The source-bound regulator identity, two-resistor feedback topology, "
                        "nominal values, or calculated output range differs from the "
                        "project-authored requirement. Review the device data sheet and pin map."
                    ),
                    evidence={
                        "profile": (entry.id,),
                        "regulator": (entry.regulator_reference,),
                        "output_net": (entry.output_net,),
                        "reference_net": (entry.reference_net,),
                        "feedback_net": (entry.feedback_net or "<unresolved>",),
                        "pin_nets": tuple(
                            f"{pin} -> {', '.join(nets) or 'unconnected'}"
                            for pin, nets in sorted(entry.pin_nets.items())
                        ),
                        "nominal_resistance_ohms": tuple(
                            f"{reference}={value:g} Ω"
                            for reference, value in sorted(entry.nominal_resistance_ohms.items())
                        ),
                        "formula": (entry.formula,),
                        "feedback_reference_range_v": (feedback_reference_range,),
                        "calculated_nominal_output_range_v": (calculated,),
                        "target_output_range_v": (target_output_range,),
                        "basis": (entry.basis,),
                        "issues": entry.issues,
                    },
                )
            )
    if rc_filter_coverage is not None:
        for entry in rc_filter_coverage.entries:
            if entry.status == "COMPLETE":
                continue
            calculated = (
                "unavailable"
                if entry.calculated_corner_hz is None
                else f"{entry.calculated_corner_hz:g} Hz"
            )
            found.append(
                Candidate(
                    rule_id="filter.rc_corner_mismatch",
                    subject=f"{entry.id}: mapped first-order RC low-pass filter",
                    message=(
                        "The source-bound resistor/capacitor identity, series/shunt topology, "
                        "nominal values, or calculated corner differs from the project-authored "
                        "requirement. Review the schematic and intended source/load conditions."
                    ),
                    evidence={
                        "profile": (entry.id,),
                        "resistor": (entry.resistor_reference,),
                        "capacitor": (entry.capacitor_reference,),
                        "input_net": (entry.input_net,),
                        "filtered_net": (entry.filtered_net,),
                        "reference_net": (entry.reference_net,),
                        "pin_nets": tuple(
                            f"{pin} -> {', '.join(nets) or 'unconnected'}"
                            for pin, nets in sorted(entry.pin_nets.items())
                        ),
                        "nominal_resistance_ohms": (
                            "unavailable"
                            if entry.resistance_ohms is None
                            else f"{entry.resistance_ohms:g} Ω",
                        ),
                        "nominal_capacitance_pf": (
                            "unavailable"
                            if entry.capacitance_pf is None
                            else f"{entry.capacitance_pf:g} pF",
                        ),
                        "formula": (entry.formula,),
                        "calculated_nominal_corner_hz": (calculated,),
                        "target_corner_hz": (
                            (
                                f"{entry.target_minimum_corner_hz:g}–"
                                f"{entry.target_maximum_corner_hz:g} Hz"
                            ),
                        ),
                        "nominal_resistance_range_ohms": (
                            (
                                f"{entry.nominal_resistance_range_ohms[0]:g}–"
                                f"{entry.nominal_resistance_range_ohms[1]:g} Ω"
                            ),
                        ),
                        "nominal_capacitance_range_pf": (
                            (
                                f"{entry.nominal_capacitance_range_pf[0]:g}–"
                                f"{entry.nominal_capacitance_range_pf[1]:g} pF"
                            ),
                        ),
                        "unlisted_parallel_components": entry.unlisted_parallel_components,
                        "basis": (entry.basis,),
                        "issues": entry.issues,
                    },
                )
            )
    if usb_data_path_map is not None:
        map_sha256 = usb_data_map_sha256 or ""
        for mismatch in usb_data_path_mismatches(usb_data_path_map, observed):
            found.append(
                Candidate(
                    rule_id="bus.usb_data_path_mismatch",
                    subject=f"{mismatch.interface_id}: USB {mismatch.line} path",
                    message=(
                        "The connector-to-PHY USB reference pins or exact mapped bond differ "
                        "from the project-authored reference policy. Review the pins, nets, and "
                        "bond component; the map records schematic intent but does not prove "
                        "component conduction or PCB continuity."
                        if mismatch.line == "reference"
                        else "The connector-to-PHY USB data path differs from the project-authored, "
                        "PHY-specific topology. Review the exact pin assignments, fitted series "
                        "component, and manufacturer basis. This check does not infer a universal "
                        "USB resistor requirement or establish PCB continuity."
                    ),
                    evidence={
                        "interface": (mismatch.interface_id,),
                        "basis": (mismatch.basis,),
                        "line": (mismatch.line,),
                        "connector": (
                            (
                                f"{mismatch.connector_reference}: "
                                f"{mismatch.connector_symbol}; {mismatch.connector_footprint}"
                            ),
                        ),
                        "connector_pin": (mismatch.connector_pin,),
                        "expected_connector_net": (mismatch.connector_net,),
                        "phy": (
                            (
                                f"{mismatch.phy_reference}: "
                                f"{mismatch.phy_symbol}; {mismatch.phy_footprint}"
                            ),
                        ),
                        "phy_pin": (mismatch.phy_pin,),
                        "expected_phy_net": (mismatch.phy_net,),
                        "expected_topology": (mismatch.expected_topology,),
                        "reference_policy": (
                            "none"
                            if mismatch.reference_policy is None
                            else mismatch.reference_policy,
                        ),
                        "reference_bond": (
                            "none"
                            if mismatch.reference_bond_reference is None
                            else mismatch.reference_bond_reference,
                        ),
                        "reference_bond_identity": (
                            "none"
                            if mismatch.reference_bond_identity is None
                            else mismatch.reference_bond_identity,
                        ),
                        "reference_bond_side_a": (
                            "none"
                            if mismatch.reference_bond_side_a is None
                            else mismatch.reference_bond_side_a,
                        ),
                        "reference_bond_side_b": (
                            "none"
                            if mismatch.reference_bond_side_b is None
                            else mismatch.reference_bond_side_b,
                        ),
                        "series_resistor": (
                            "none"
                            if mismatch.series_resistor_reference is None
                            else mismatch.series_resistor_reference,
                        ),
                        "series_resistor_identity": (
                            "none"
                            if mismatch.series_resistor_reference is None
                            else (
                                f"{mismatch.series_resistor_symbol}; "
                                f"{mismatch.series_resistor_footprint}"
                            ),
                        ),
                        "series_resistance_range_ohms": (
                            "none"
                            if mismatch.series_resistance_range_ohms is None
                            else (
                                f"{mismatch.series_resistance_range_ohms[0]:g}–"
                                f"{mismatch.series_resistance_range_ohms[1]:g} Ω"
                            ),
                        ),
                        "map_sha256": (map_sha256,),
                        "issues": mismatch.issues,
                    },
                )
            )
    if power_path_map is not None:
        map_sha256 = hashlib.sha256(power_path_map.model_dump_json().encode("utf-8")).hexdigest()
        for mismatch in power_path_mismatches(power_path_map, observed):
            found.append(
                Candidate(
                    rule_id="power.mapped_series_path_mismatch",
                    subject=f"{mismatch.path_id}: required power path differs",
                    message=(
                        "The mapped power path differs from the project-authored component and "
                        "pin/net assignments. Review the named endpoints and fitted series "
                        "components. This check does not establish component conduction, "
                        "electrical suitability, or PCB copper continuity."
                    ),
                    evidence={
                        "path": (mismatch.path_id,),
                        "basis": (mismatch.basis,),
                        "start_endpoint": (f"{mismatch.start_pin} on {mismatch.start_net}",),
                        "end_endpoint": (f"{mismatch.end_pin} on {mismatch.end_net}",),
                        "mapped_elements": mismatch.elements,
                        "map_sha256": (map_sha256,),
                        "issues": mismatch.issues,
                    },
                )
            )
    if power_sequence_map is not None:
        map_sha256 = hashlib.sha256(
            power_sequence_map.model_dump_json().encode("utf-8")
        ).hexdigest()
        for mismatch in power_sequence_mismatches(power_sequence_map, observed):
            found.append(
                Candidate(
                    rule_id="power.mapped_sequence_dependency_mismatch",
                    subject=f"{mismatch.stage_id}: required power-sequence stage differs",
                    message=(
                        "The project's mapped rail, power-good, or enable endpoints differ from "
                        "the native netlist. Review the explicit dependency map and component "
                        "identity. A matching topology does not establish startup timing, control "
                        "state, electrical suitability, or physical rail behavior."
                    ),
                    evidence={
                        "sequence_map_basis": (power_sequence_map.basis,),
                        "stage": (mismatch.stage_id,),
                        "stage_basis": (mismatch.stage_basis,),
                        "enable_control": (mismatch.enable_control,),
                        "expected_endpoints": mismatch.expected_endpoints,
                        "dependencies": tuple(
                            f"{item.id}: {item.predecessor_stage} → "
                            f"{item.successor_stage} on {item.signal_net}"
                            for item in power_sequence_map.dependencies
                            if mismatch.stage_id.casefold()
                            in {
                                item.predecessor_stage.casefold(),
                                item.successor_stage.casefold(),
                            }
                        ),
                        "output_endpoint": (f"{mismatch.output_pin} on {mismatch.output_net}",),
                        "map_sha256": (map_sha256,),
                        "issues": mismatch.issues,
                    },
                )
            )
        declared_cycle = power_sequence_graph_has_cycle(power_sequence_map)
        observed_cycles = power_sequence_observed_enable_cycles(power_sequence_map, observed)
        if declared_cycle or observed_cycles:
            cycle_issues = (
                *(("The project-authored dependency graph is cyclic",) if declared_cycle else ()),
                *(
                    "The mapped native output-to-enable topology is cyclic across stages "
                    + ", ".join(cycle.stage_ids)
                    for cycle in observed_cycles
                ),
            )
            if declared_cycle and observed_cycles:
                subject = "authored and mapped power-sequence topology contains a cycle"
            elif declared_cycle:
                subject = "project-authored power-sequence dependency graph contains a cycle"
            else:
                subject = "mapped native output-to-enable topology contains a cycle"
            found.append(
                Candidate(
                    rule_id="power.mapped_sequence_dependency_mismatch",
                    subject=subject,
                    message=(
                        "A mapped power-sequence graph contains a cycle. Review the stage "
                        "directions, enable polarity, and source requirement. Native output-to-"
                        "enable edges are considered only when both exact mapped stages match "
                        "the netlist; this does not establish startup behavior or infer stage "
                        "roles from pin names or device families."
                    ),
                    evidence={
                        "sequence_map_basis": (power_sequence_map.basis,),
                        "dependencies": tuple(
                            f"{item.predecessor_stage} → {item.successor_stage} on {item.signal_net}"
                            for item in power_sequence_map.dependencies
                        ),
                        "declared_dependency_cycle": (str(declared_cycle).lower(),),
                        "observed_output_to_enable_cycle_stages": tuple(
                            ", ".join(cycle.stage_ids) for cycle in observed_cycles
                        ),
                        "observed_output_to_enable_cycle_edges": tuple(
                            edge for cycle in observed_cycles for edge in cycle.edges
                        ),
                        "map_sha256": (map_sha256,),
                        "issues": cycle_issues,
                    },
                )
            )
    if connector_return_distribution is not None:
        for entry in connector_return_distribution.entries:
            if entry.status not in {"OUT_OF_RANGE", "INCOMPLETE"}:
                continue
            ratio = (
                "undefined (no return contacts)"
                if entry.signal_to_return_ratio is None
                else f"{entry.signal_to_return_ratio:g} signals per return"
            )
            found.append(
                Candidate(
                    rule_id="connector.return_distribution",
                    subject=(
                        f"{entry.connector_reference or entry.interface_id}: "
                        "reviewed return-contact distribution"
                    ),
                    message=(
                        "The explicitly role-classified interface is outside its project-authored "
                        "signal-to-return contact threshold or lacks complete role evidence. "
                        "Review the pin allocation; this ratio does not require returns to share "
                        "a net."
                    ),
                    evidence={
                        "profile": (entry.id,),
                        "connector": (entry.connector_reference or "<no bound connector>",),
                        "interface": (entry.interface_id,),
                        "signal_contact_count": (str(entry.signal_pin_count),),
                        "signal_pins": tuple(
                            f"interface {number} -> {pin}"
                            for number, pin in sorted(entry.signal_pin_map.items())
                        ),
                        "return_contact_count": (str(entry.return_pin_count),),
                        "return_pins": tuple(
                            f"interface {number} -> {pin}"
                            for number, pin in sorted(entry.return_pin_map.items())
                        ),
                        "supply_pins_excluded": tuple(
                            f"interface {number} -> {pin}"
                            for number, pin in sorted(entry.supply_pin_map.items())
                        ),
                        "shield_pins_excluded": tuple(
                            f"interface {number} -> {pin}"
                            for number, pin in sorted(entry.shield_pin_map.items())
                        ),
                        "other_pins_excluded": tuple(
                            f"interface {number} -> {pin}"
                            for number, pin in sorted(entry.other_pin_map.items())
                        ),
                        "unclassified_pins": tuple(
                            f"interface {number} -> {pin}"
                            for number, pin in sorted(entry.unclassified_pin_map.items())
                        ),
                        "required_return_contact_count": (str(entry.required_return_pin_count),),
                        "signal_to_return_ratio": (ratio,),
                        "minimum_signal_pin_count": (str(entry.minimum_signal_pin_count),),
                        "maximum_signal_to_return_ratio": (
                            f"{entry.maximum_signal_to_return_ratio:g}",
                        ),
                        "basis": (entry.basis,),
                        "issues": entry.issues,
                    },
                )
            )
    if pcb_decoupling_coverage is not None:
        for entry in pcb_decoupling_coverage.entries:
            if entry.status == "COMPLETE" and entry.max_distance_um is not None:
                continue
            measured: list[str] = []
            for candidate in entry.candidates:
                distance = (
                    "unavailable"
                    if candidate.distance_nm is None
                    else f"{candidate.distance_nm // 1000}.{candidate.distance_nm % 1000:03d} um"
                )
                via_distance = (
                    "unavailable"
                    if candidate.return_via_distance_nm is None
                    else f"{candidate.return_via_distance_nm // 1000}.{candidate.return_via_distance_nm % 1000:03d} um"
                )
                via_id = candidate.nearest_return_via_id or "unavailable"
                state = "eligible" if candidate.eligible else "not eligible"
                measured.append(
                    f"{candidate.reference}: supply-pad distance {distance}; "
                    f"connected return vias {candidate.connected_return_via_count}; "
                    f"nearest return via {via_id} at {via_distance}; {state}"
                )
            found.append(
                Candidate(
                    rule_id="pcb.decoupling_proximity",
                    subject=f"{entry.id}: IC supply {entry.ic_supply_pad}",
                    message=(
                        "Review the mapped decoupling capacitor placement and copper paths. "
                        "The supply-pad and optional connected return-via distances are geometric "
                        "screens; they do not estimate loop inductance or prove adequate decoupling."
                    ),
                    evidence={
                        "ic_supply_pad": (entry.ic_supply_pad,),
                        "ic_return_pad": (entry.ic_return_pad,),
                        "supply_net": (entry.ic_supply_net,),
                        "return_net": (entry.ic_return_net,),
                        "selection": (entry.selection,),
                        "maximum_center_distance_um": (
                            "not configured"
                            if entry.max_distance_um is None
                            else str(entry.max_distance_um),
                        ),
                        "maximum_return_via_distance_um": (
                            "not configured"
                            if entry.max_return_via_distance_um is None
                            else str(entry.max_return_via_distance_um),
                        ),
                        "selected_capacitors": entry.selected_capacitors,
                        "candidate_distances": tuple(measured),
                        "issues": entry.issues
                        + tuple(
                            issue for candidate in entry.candidates for issue in candidate.issues
                        ),
                        "distance_basis": (
                            "Euclidean distance between native IC supply-pad center and native capacitor supply-pad center",
                        ),
                        "return_via_distance_basis": (
                            "Euclidean distance from the native capacitor return-pad center to a via listed in that pad's native copper-connectivity component",
                        ),
                    },
                )
            )
    if pcb_protection_path_coverage is not None:
        for entry in pcb_protection_path_coverage.entries:
            if entry.status == "COMPLETE":
                continue
            entry_distance = (
                "unavailable"
                if entry.connector_to_protection_distance_nm is None
                else f"{entry.connector_to_protection_distance_nm} nm"
            )
            nearest_via_distance = (
                "unavailable"
                if entry.nearest_reference_via_distance_nm is None
                else f"{entry.nearest_reference_via_distance_nm} nm"
            )
            via_count = (
                "not configured"
                if entry.reference_vias_within_radius is None
                else f"{entry.reference_vias_within_radius} within {entry.reference_via_radius_um} um"
            )
            found.append(
                Candidate(
                    rule_id="pcb.protection_entry_path",
                    subject=(
                        f"{entry.id}: {entry.connector_signal_pad} to {entry.protection_signal_pad}"
                    ),
                    message=(
                        "Review the mapped connector-to-protection pad path and reference-via "
                        "coverage against the project limits. Pad-center distance is a straight-line "
                        "screen, not routed copper length; native connectivity does not prove that "
                        "the protector intercepts every transient or that the device is effective."
                    ),
                    evidence={
                        "connector_signal_pad": (entry.connector_signal_pad,),
                        "protection_signal_pad": (entry.protection_signal_pad,),
                        "protection_reference_pad": (entry.protection_reference_pad,),
                        "signal_net": (entry.signal_net,),
                        "reference_net": (entry.reference_net,),
                        "connector_footprint": (
                            entry.expected_connector_footprint,
                            entry.observed_connector_footprint or "missing",
                        ),
                        "protection_footprint": (
                            entry.expected_protection_footprint,
                            entry.observed_protection_signal_footprint or "missing",
                            entry.observed_protection_reference_footprint or "missing",
                        ),
                        "observed_pad_nets": (
                            f"{entry.connector_signal_pad}={entry.observed_connector_signal_net or 'unconnected'}",
                            f"{entry.protection_signal_pad}={entry.observed_protection_signal_net or 'unconnected'}",
                            f"{entry.protection_reference_pad}={entry.observed_protection_reference_net or 'unconnected'}",
                        ),
                        "native_signal_path_connected": (
                            "yes" if entry.native_signal_path_connected else "no",
                        ),
                        "connector_to_protection_pad_center_distance": (entry_distance,),
                        "maximum_project_distance_um": (
                            "not configured"
                            if entry.max_entry_distance_um is None
                            else str(entry.max_entry_distance_um),
                        ),
                        "native_connected_reference_vias": (
                            str(entry.connected_reference_via_count),
                        ),
                        "reference_vias_within_project_radius": (via_count,),
                        "nearest_connected_reference_via_distance": (nearest_via_distance,),
                        "minimum_vias_in_project_radius": (
                            "not configured"
                            if entry.minimum_reference_vias is None
                            else str(entry.minimum_reference_vias),
                        ),
                        "issues": entry.issues,
                    },
                )
            )
    if pcb_track_width_coverage is not None:
        for entry in pcb_track_width_coverage.entries:
            below = tuple(item for item in entry.tracks if item.below_minimum)
            if entry.status == "COMPLETE" and not below:
                continue
            measured_tracks = tuple(
                f"{item.track_uuid} {item.layer}: "
                f"{item.width_nm // 1000}.{item.width_nm % 1000:03d} um; "
                f"minimum {item.minimum_width_um} um; "
                f"start {item.start_nm[0]},{item.start_nm[1]} nm; "
                f"end {item.end_nm[0]},{item.end_nm[1]} nm"
                for item in entry.tracks
            )
            found.append(
                Candidate(
                    rule_id="pcb.minimum_track_width",
                    subject=f"{entry.id}: net {entry.net}",
                    message=(
                        "Review the mapped PCB track widths against the project's explicit net "
                        "screen. This measurement does not calculate current capacity or "
                        "temperature rise."
                    ),
                    evidence={
                        "net": (entry.net,),
                        "minimum_track_width_um": (str(entry.minimum_width_um),),
                        "measured_tracks": measured_tracks,
                        "below_minimum_track_uuids": tuple(item.track_uuid for item in below),
                        "coverage_status": (entry.status,),
                        "basis": (entry.basis,),
                        "issues": entry.issues,
                        "metric": (
                            "KiCad native track item GetWidth in integer nanometers compared "
                            + "with the project-authored minimum",
                        ),
                    },
                )
            )
    if pcb_reference_plane_coverage is not None:
        for entry in pcb_reference_plane_coverage.entries:
            by_track: dict[str, list[bool]] = {}
            for item in entry.tracks:
                by_track.setdefault(item.track_uuid, []).append(item.below_minimum)
            below_track_uuids = tuple(
                sorted(
                    (track_uuid for track_uuid, layers in by_track.items() if all(layers)),
                    key=str.casefold,
                )
            )
            if entry.status == "COMPLETE" and not below_track_uuids:
                continue
            measurements = tuple(
                f"{item.track_uuid}: {item.signal_layer} over {item.reference_layer}; "
                f"covered {item.covered_fraction_numerator}/"
                f"{item.covered_fraction_denominator}; "
                f"minimum {entry.minimum_referenced_fraction}; "
                f"zones {', '.join(item.reference_zone_uuids) or 'none'}; "
                f"endpoint vias {', '.join(item.endpoint_via_ids) or 'none'}; "
                "endpoint via centers in reference holes "
                f"{', '.join(item.endpoint_via_ids_with_center_in_reference_holes) or 'none'}"
                for item in entry.tracks
            )
            endpoint_via_hole_candidates = tuple(
                sorted(
                    {
                        via_id
                        for item in entry.tracks
                        if item.track_uuid in below_track_uuids
                        for via_id in item.endpoint_via_ids_with_center_in_reference_holes
                    },
                    key=str.casefold,
                )
            )
            message = (
                "Review the mapped signal-track centerline coverage over immediately "
                "adjacent filled reference copper. This geometric screen can highlight "
                "possible plane interruptions, but it does not establish a continuous "
                "return-current path or assess the electrical effect."
            )
            if endpoint_via_hole_candidates:
                message += (
                    " The native contours place mapped endpoint signal-via centers inside "
                    "reference-zone holes, but do not identify which clearance created a hole "
                    "when clearances merge. Those intervals remain uncovered; inspect the "
                    "geometry before interpreting them as a return-path interruption."
                )
            if entry.review_excluded_short_tracks and entry.excluded_short_track_uuids:
                message += (
                    " Short segments below the configured minimum were excluded and are included "
                    "in this review because the project requested coverage review."
                )
            found.append(
                Candidate(
                    rule_id="pcb.reference_plane_coverage",
                    subject=(
                        f"{entry.id}: {entry.signal_net} over "
                        f"{', '.join(entry.signal_layers)} / {entry.reference_net}"
                    ),
                    message=message,
                    evidence={
                        "signal_net": (entry.signal_net,),
                        "signal_layers": entry.signal_layers,
                        "reference_net": (entry.reference_net,),
                        "minimum_track_length_um": (str(entry.minimum_track_length_um),),
                        "minimum_referenced_fraction": (str(entry.minimum_referenced_fraction),),
                        "review_excluded_short_tracks": (
                            str(entry.review_excluded_short_tracks).lower(),
                        ),
                        "measured_tracks": measurements,
                        "below_threshold_track_uuids": below_track_uuids,
                        "endpoint_via_hole_candidates": endpoint_via_hole_candidates,
                        "excluded_short_track_uuids": entry.excluded_short_track_uuids,
                        "coverage_status": (entry.status,),
                        "basis": (entry.basis,),
                        "issues": entry.issues,
                        "metric": (
                            "Exact rational share of each native straight-track centerline "
                            + "inside the union of filled same-net zones on each immediately "
                            "adjacent copper layer, measured independently per layer",
                        ),
                    },
                )
            )
    if pcb_switching_loop_coverage is not None:
        for entry in pcb_switching_loop_coverage.entries:
            if entry.status == "COMPLETE" and entry.maximum_area_um2 is not None:
                continue
            area = (
                "unavailable"
                if entry.loop_area_twice_nm2 is None
                else f"{entry.loop_area_twice_nm2 / 2_000_000_000_000:.6f} mm^2"
            )
            found.append(
                Candidate(
                    rule_id="pcb.switching_loop_geometry",
                    subject=f"{entry.id}: return net {entry.return_net}",
                    message=(
                        "Review the mapped switching-current loop, measured trace chains, and "
                        "return-plane evidence. The area is a polygon through authored pad "
                        "centers; trace lengths use native endpoint geometry. Neither establishes "
                        "the full current path or estimates parasitics, emissions, stability, or "
                        "electrical performance."
                    ),
                    evidence={
                        "loop_pad_order": entry.loop_pads,
                        "pad_center_polygon_area": (area,),
                        "trace_route_status": (entry.route_status,),
                        "trace_route_edges": tuple(
                            f"{item.edge_index}: {item.from_pad} to {item.to_pad}; "
                            f"{item.status}; length "
                            f"{item.length_nm if item.length_nm is not None else 'unavailable'} nm; "
                            f"tracks {', '.join(item.track_uuids) or 'none'}"
                            + (
                                f"; filled zone {item.plane_zone_uuid}, island "
                                f"{item.plane_island_index}; contour doubled area "
                                f"{item.plane_island_area_twice_nm2} nm^2"
                                if item.plane_zone_uuid is not None
                                else ""
                            )
                            + ("; " + item.issue if item.issue is not None else "")
                            for item in entry.route_edges
                        ),
                        "maximum_area_um2": (
                            "not configured"
                            if entry.maximum_area_um2 is None
                            else str(entry.maximum_area_um2),
                        ),
                        "area_exceeds_limit": (
                            "not evaluated"
                            if entry.area_exceeds_limit is None
                            else str(entry.area_exceeds_limit).lower(),
                        ),
                        "return_net": (entry.return_net,),
                        "return_plane_layer": (entry.return_plane_layer,),
                        "return_plane_pads": entry.return_plane_pads,
                        "return_plane_status": (entry.return_plane_status,),
                        "return_zone_uuid": (
                            () if entry.return_zone_uuid is None else (entry.return_zone_uuid,)
                        ),
                        "return_island_index": (
                            ()
                            if entry.return_island_index is None
                            else (str(entry.return_island_index),)
                        ),
                        "coverage_status": (entry.status,),
                        "basis": (entry.basis,),
                        "issues": entry.issues,
                        "metric": (
                            "Absolute shoelace area of project-ordered native pad centers; "
                            + "trace lengths follow uniquely resolved native track chains; "
                            + "plane edges identify one shared filled island and can report its "
                            + "native contour area",
                        ),
                        "validation_boundary": (
                            "component internals, current distribution, parasitics, hardware, "
                            + "and simulation remain outside this measurement",
                        ),
                    },
                )
            )
    if pcb_differential_pair_coverage is not None:
        for entry in pcb_differential_pair_coverage.entries:
            if entry.status != "INCOMPLETE":
                continue
            constraint_evidence = tuple(
                f"{item.constraint}: {item.status}"
                + ("" if item.issue is None else f" ({item.issue})")
                for item in entry.constraints
                if item.status != "COVERED"
            )
            found.append(
                Candidate(
                    rule_id="pcb.differential_pair_rule_coverage",
                    subject=f"{entry.id}: {entry.positive_net} / {entry.negative_net}",
                    message=(
                        "This project-authored differential-pair requirement is missing an exact, "
                        "active native DRC rule or supported pair identity. Review the pair map, "
                        "KiCad rule file, and ignored-check settings."
                    ),
                    evidence={
                        "positive_net": (entry.positive_net,),
                        "negative_net": (entry.negative_net,),
                        "pair_selector": (entry.pair_selector,),
                        "basis": (entry.basis,),
                        "constraints": constraint_evidence,
                        "issues": entry.issues,
                    },
                )
            )
    if stm32_pin_map_coverage is not None:
        for device in stm32_pin_map_coverage.unmapped_devices:
            found.append(
                Candidate(
                    rule_id="mcu.stm32_cubemx_pin_map",
                    subject=f"{device.reference}: STM32 CubeMX pin-map coverage is missing",
                    message=(
                        "This fitted component is identified as an STM32 device, but the project "
                        "has no explicit CubeMX pin-map contract for it. Confirm that CubeMX is "
                        "the firmware source; if so, map every package pin to a KiCad symbol pin "
                        "or record a reasoned exclusion. This name-based discovery prompt does "
                        "not establish that the device is configured by CubeMX."
                    ),
                    evidence={
                        "reference": (device.reference,),
                        "part": (device.observed_part,),
                        "symbol": (device.observed_symbol or "<unknown>",),
                        "native_netlist_sha256": (device.netlist_sha256,),
                    },
                )
            )
        for mismatch in stm32_pin_map_coverage.mismatches:
            expected_labels = (
                ("<not checked>",)
                if mismatch.accepted_ioc_gpio_labels is None
                else tuple(
                    "<absent>" if item is None else item
                    for item in mismatch.accepted_ioc_gpio_labels
                )
            )
            found.append(
                Candidate(
                    rule_id="mcu.stm32_cubemx_pin_map",
                    subject=(
                        f"{mismatch.reference}.{mismatch.port_pin}: "
                        "CubeMX and KiCad pin map differs from the project contract"
                    ),
                    message=(
                        "A project-mapped STM32 package pin disagrees with the authored "
                        "CubeMX/KiCad pin-map contract. Review the MCU pinout, schematic net, "
                        "and firmware configuration. " + "; ".join(mismatch.issues)
                    ),
                    evidence={
                        "mcu_reference": (mismatch.reference,),
                        "package_pin": (mismatch.port_pin,),
                        "symbol_pin": (f"{mismatch.reference}.{mismatch.symbol_pin}",),
                        "expected_net": (mismatch.expected_net,),
                        "observed_net": mismatch.observed_nets or ("<unconnected>",),
                        "accepted_ioc_signal": mismatch.accepted_ioc_signals,
                        "observed_ioc_signal": (mismatch.observed_ioc_signal or "<missing>",),
                        "accepted_ioc_gpio_label": expected_labels,
                        "observed_ioc_gpio_label": (
                            mismatch.observed_ioc_gpio_label or "<absent>",
                        ),
                        "ioc_path": (mismatch.ioc_path,),
                        "ioc_sha256": (mismatch.ioc_sha256,),
                        "map_sha256": (mismatch.map_sha256,),
                        "native_netlist_sha256": (mismatch.netlist_sha256,),
                    },
                )
            )
    active_ids = {
        item.rule_id for item in (catalog or rule_catalog()).rules if item.status == "active"
    }
    unknown_ids = sorted({item.rule_id for item in found} - active_ids)
    if unknown_ids:
        raise ValueError(
            f"Design-lint candidates emit rules absent from the active catalog: {unknown_ids}"
        )
    return tuple(sorted(found, key=lambda item: (item.rule_id, item.subject)))


def fingerprint(item: Candidate) -> str:
    """Bind an ignore to exact observed pins/nets, independent of unrelated files."""
    payload = {
        "rule_id": item.rule_id,
        "subject": item.subject,
        "evidence": {key: sorted(value) for key, value in sorted(item.evidence.items())},
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _stm32_pin_map_sha256(pin_maps: Sequence[Stm32CubeMxPinMap]) -> str:
    payload = [item.model_dump(mode="json") for item in sorted(pin_maps, key=lambda item: item.id)]
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _mapped_check_run(
    rule_id: Literal[
        "bus.usb_data_path_mismatch",
        "power.mapped_series_path_mismatch",
        "power.mapped_sequence_dependency_mismatch",
    ],
    map_sha256: str | None,
    requirement_count: int,
    netlist_sha256: str | None,
    candidates_for_rule: Sequence[Candidate],
    mode: Literal["review", "block", "off"],
) -> DesignLintMappedCheckRun:
    finding_count = sum(item.rule_id == rule_id for item in candidates_for_rule)
    if map_sha256 is None:
        return DesignLintMappedCheckRun(
            rule_id=rule_id,
            status="NOT_CONFIGURED",
            mode=mode,
            netlist_sha256=netlist_sha256,
            reason="No project-authored map was supplied for this check.",
        )
    if netlist_sha256 is None:
        return DesignLintMappedCheckRun(
            rule_id=rule_id,
            status="BLOCKED",
            mode=mode,
            map_sha256=map_sha256,
            requirement_count=requirement_count,
            finding_count=finding_count,
            reason="The evaluated netlist had no source-bound SHA-256.",
        )
    return DesignLintMappedCheckRun(
        rule_id=rule_id,
        status="EVALUATED",
        mode=mode,
        map_sha256=map_sha256,
        netlist_sha256=netlist_sha256,
        requirement_count=requirement_count,
        finding_count=finding_count,
    )


def _digital_peer_voltage_coverage(
    scan: DigitalPeerVoltageScan,
    context: DigitalPeerVoltageLintContext,
    default_modes: Mapping[DesignLintRuleId, Literal["review", "block", "off"]],
    overrides: Mapping[str, DesignLintRuleOverride],
    netlist_sha256: str,
) -> tuple[DigitalPeerVoltageRuleCoverage, ...]:
    """Bind bounded peer-voltage applicability counts to their sources and policy."""
    result: list[DigitalPeerVoltageRuleCoverage] = []
    for item in scan.coverage:
        rule_id: Literal["bus.spi_peer_voltage_review", "bus.serial_peer_voltage_review"] = (
            "bus.spi_peer_voltage_review"
            if item.interface == "SPI"
            else "bus.serial_peer_voltage_review"
        )
        override = overrides.get(rule_id)
        mode = default_modes[rule_id] if override is None else override.mode
        status: Literal["NO_SUPPORTED_ENDPOINTS", "NO_DIRECT_PEERS", "INCOMPLETE", "EVALUATED"] = (
            "NO_SUPPORTED_ENDPOINTS"
            if item.recognized_endpoint_count == 0
            else "INCOMPLETE"
            if item.assigned_endpoint_count < item.recognized_endpoint_count
            or item.voltage_comparison_count < item.direct_peer_link_count
            else "NO_DIRECT_PEERS"
            if item.direct_peer_link_count == 0
            else "EVALUATED"
        )
        result.append(
            DigitalPeerVoltageRuleCoverage(
                rule_id=rule_id,
                status=status,
                mode=mode,
                netlist_sha256=netlist_sha256,
                authored_map_state=context.state,
                authored_map_path=context.source_path,
                authored_map_sha256=context.source_sha256,
                recognized_endpoint_count=item.recognized_endpoint_count,
                assigned_endpoint_count=item.assigned_endpoint_count,
                direct_peer_link_count=item.direct_peer_link_count,
                voltage_comparison_count=item.voltage_comparison_count,
                same_voltage_link_count=item.same_voltage_link_count,
                different_voltage_link_count=item.different_voltage_link_count,
                mapped_mismatch_link_count=item.mapped_mismatch_link_count,
                candidate_group_count=item.review_candidate_group_count,
            )
        )
    return tuple(result)


def _usb_peer_reference_coverage(
    scan: UsbPeerReferenceScan,
    default_modes: Mapping[DesignLintRuleId, Literal["review", "block", "off"]],
    overrides: Mapping[str, DesignLintRuleOverride],
    netlist_sha256: str,
    usb_data_path_map: UsbDataPathMap | None,
) -> UsbPeerReferenceCoverageReport:
    """Bind USB heuristic applicability counts to the native source and policy."""
    rule_id: Literal["bus.usb_peer_reference_review"] = "bus.usb_peer_reference_review"
    mode = default_modes[rule_id]
    if override := overrides.get(rule_id):
        mode = override.mode
    item = scan.coverage
    recognized_group_count = item.recognized_connector_group_count + item.recognized_phy_group_count
    status: Literal["NO_USB_ENDPOINTS", "INCOMPLETE", "NO_SUPPORTED_PEER_PATHS", "EVALUATED"] = (
        "NO_USB_ENDPOINTS"
        if recognized_group_count == 0
        else "INCOMPLETE"
        if item.incomplete_group_count > 0
        else "NO_SUPPORTED_PEER_PATHS"
        if item.supported_data_path_count == 0
        else "EVALUATED"
    )
    map_sha256 = (
        hashlib.sha256(usb_data_path_map.model_dump_json().encode("utf-8")).hexdigest()
        if usb_data_path_map is not None
        else None
    )
    return UsbPeerReferenceCoverageReport(
        rule_id=rule_id,
        status=status,
        mode=mode,
        netlist_sha256=netlist_sha256,
        usb_data_path_map_sha256=map_sha256,
        endpoint_groups=tuple(
            UsbPeerEndpointGroupCoverage(
                endpoint_role=entry.endpoint_role,
                reference=entry.reference,
                port_group=entry.port_group,
                disposition=entry.disposition,
            )
            for entry in item.endpoint_groups
        ),
        recognized_connector_group_count=item.recognized_connector_group_count,
        supported_connector_group_count=item.supported_connector_group_count,
        recognized_phy_group_count=item.recognized_phy_group_count,
        supported_phy_group_count=item.supported_phy_group_count,
        dnp_group_count=item.dnp_group_count,
        incomplete_group_count=item.incomplete_group_count,
        supported_data_path_count=item.supported_data_path_count,
        common_reference_path_count=item.common_reference_path_count,
        separate_reference_path_count=item.separate_reference_path_count,
        mapped_separate_reference_path_count=item.mapped_separate_reference_path_count,
        candidate_group_count=item.review_candidate_group_count,
    )


def _serial_peer_reference_coverage(
    scan: SerialPeerReferenceScan,
    context: SerialPeerRosterContext,
    default_modes: Mapping[DesignLintRuleId, Literal["review", "block", "off"]],
    overrides: Mapping[str, DesignLintRuleOverride],
    netlist_sha256: str,
) -> SerialPeerReferenceCoverageReport:
    """Bind serial reference applicability counts to the native source and policy."""
    rule_id: Literal["bus.serial_peer_reference_review"] = "bus.serial_peer_reference_review"
    mode = default_modes[rule_id]
    if override := overrides.get(rule_id):
        mode = override.mode
    discovered = scan.native_peer_link_count + scan.label_peer_link_count
    status: Literal["NO_DIRECT_PEERS", "INCOMPLETE", "EVALUATED"] = (
        "NO_DIRECT_PEERS"
        if discovered == 0
        else "INCOMPLETE"
        if scan.incomplete_reference_link_count > 0
        else "EVALUATED"
    )
    map_sha256 = (
        hashlib.sha256(context.analysis.model_dump_json().encode("utf-8")).hexdigest()
        if context.analysis is not None
        else None
    )
    return SerialPeerReferenceCoverageReport(
        rule_id=rule_id,
        status=status,
        mode=mode,
        netlist_sha256=netlist_sha256,
        authored_map_state=context.state,
        authored_map_path=context.source_path,
        authored_map_source_sha256=context.source_sha256,
        authored_serial_peer_map_sha256=map_sha256,
        link_entries=tuple(
            SerialPeerReferenceLinkCoverageEntry(
                discovery_basis=entry.discovery_basis,
                first_reference=entry.first_reference,
                second_reference=entry.second_reference,
                signal_group=entry.signal_group,
                signal_nets=entry.signal_nets,
                signal_pins=entry.signal_pins,
                disposition=entry.disposition,
            )
            for entry in scan.link_entries
        ),
        native_peer_link_count=scan.native_peer_link_count,
        label_peer_link_count=scan.label_peer_link_count,
        supported_reference_link_count=scan.supported_reference_link_count,
        incomplete_reference_link_count=scan.incomplete_reference_link_count,
        common_reference_link_count=scan.common_reference_link_count,
        separate_reference_link_count=scan.separate_reference_link_count,
        mapped_separate_reference_link_count=scan.mapped_separate_reference_link_count,
        candidate_group_count=scan.candidate_group_count,
    )


def evaluate(
    project_id: str,
    coach: ContractCoachReport,
    policy: DesignLintPolicy,
    connector_coverage: ConnectorCoverageReport | None = None,
    schematic_geometry: SchematicGeometryScan | None = None,
    geometry_coverage: SchematicGeometryCoverage | None = None,
    i2c_address_coverage: I2cAddressCoverageReport | None = None,
    external_protection_coverage: ExternalProtectionCoverageReport | None = None,
    crystal_network_coverage: CrystalNetworkCoverageReport | None = None,
    regulator_feedback_coverage: RegulatorFeedbackCoverageReport | None = None,
    rc_filter_coverage: RcFilterCoverageReport | None = None,
    connector_return_distribution_coverage: ConnectorReturnDistributionCoverageReport | None = None,
    pcb_decoupling_coverage: PcbDecouplingCoverageReport | None = None,
    pcb_protection_path_coverage: PcbProtectionPathCoverageReport | None = None,
    pcb_track_width_coverage: PcbTrackWidthCoverageReport | None = None,
    pcb_switching_loop_coverage: PcbSwitchingLoopCoverageReport | None = None,
    pcb_differential_pair_coverage: PcbDifferentialPairRuleCoverageReport | None = None,
    stm32_pin_map_coverage: Stm32PinMapCoverageReport | None = None,
    spi_roster: SpiRosterContext | None = None,
    usb_c_port_roster: UsbCPortRosterContext | None = None,
    pcb_reference_plane_coverage: PcbReferencePlaneCoverageReport | None = None,
    control_input_bias_coverage: ControlInputBiasHeuristicCoverage | None = None,
    i2c_pullup_heuristic_coverage: I2cPullupHeuristicCoverage | None = None,
    digital_peer_voltage_context: DigitalPeerVoltageLintContext | None = None,
    serial_peer_roster: SerialPeerRosterContext | None = None,
) -> DesignLintReport:
    """Apply independently authored decisions without treating findings as requirements."""
    catalog = rule_catalog()
    if i2c_pullup_heuristic_coverage is not None:
        coverage_issue = (
            i2c_pullup_heuristic_coverage.issue
            if i2c_pullup_heuristic_coverage.status == "BLOCKED"
            else "I2C pull-up coverage uses a different or unavailable native netlist hash."
            if i2c_pullup_heuristic_coverage.entries
            and i2c_pullup_heuristic_coverage.netlist_sha256 != coach.netlist_sha256
            else None
        )
        if coverage_issue is not None:
            blocked_coverage = I2cPullupHeuristicCoverage(
                status="BLOCKED",
                source_path=i2c_pullup_heuristic_coverage.source_path,
                source_sha256=i2c_pullup_heuristic_coverage.source_sha256,
                issue=coverage_issue,
            )
            return DesignLintReport(
                status="BLOCKED",
                project_id=project_id,
                source_hashes=coach.source_hashes,
                netlist_sha256=coach.netlist_sha256,
                native_summary=coach.native_summary,
                native_status=coach.native_status,
                rule_catalog=catalog,
                i2c_pullup_heuristic_coverage=blocked_coverage,
                issues=(coverage_issue,),
                next_actions=(
                    "Recreate I2C pull-up coverage from the current native netlist and contract.",
                ),
            )
    stm32_override = next(
        (item for item in policy.rules if item.rule_id == "mcu.stm32_cubemx_pin_map"),
        None,
    )
    stm32_mode: Literal["review", "block", "off"] = (
        "review" if stm32_override is None else stm32_override.mode
    )
    if stm32_pin_map_coverage is None:
        if stm32_mode == "off":
            stm32_pin_map_coverage = Stm32PinMapCoverageReport(
                status="DISABLED",
                mode="off",
                map_sha256=(
                    _stm32_pin_map_sha256(policy.stm32_pin_maps) if policy.stm32_pin_maps else None
                ),
            )
        elif policy.stm32_pin_maps:
            stm32_pin_map_coverage = Stm32PinMapCoverageReport(
                status="BLOCKED",
                mode=stm32_mode,
                map_sha256=_stm32_pin_map_sha256(policy.stm32_pin_maps),
                issue="Source-bound CubeMX IOC contents were not supplied for the configured pin map",
            )
        elif coach.observed is not None and coach.netlist_sha256 is not None:
            unmapped = unmapped_stm32_devices(
                coach.observed, (), netlist_sha256=coach.netlist_sha256
            )
            stm32_pin_map_coverage = Stm32PinMapCoverageReport(
                status="INCOMPLETE" if unmapped else "NOT_REQUESTED",
                mode=stm32_mode if unmapped else None,
                netlist_sha256=coach.netlist_sha256 if unmapped else None,
                unmapped_devices=unmapped,
            )
        else:
            stm32_pin_map_coverage = Stm32PinMapCoverageReport()
    source_hashes = dict(coach.source_hashes)
    for source_path, source_sha256 in stm32_pin_map_coverage.ioc_source_hashes.items():
        previous_sha256 = source_hashes.get(source_path)
        if previous_sha256 is not None and previous_sha256 != source_sha256:
            raise ValueError(f"Conflicting source hashes for CubeMX input {source_path}")
        source_hashes[source_path] = source_sha256
    pair_override = next(
        (item for item in policy.rules if item.rule_id == "pcb.differential_pair_rule_coverage"),
        None,
    )
    pair_mode: Literal["review", "block", "off"] = (
        "review" if pair_override is None else pair_override.mode
    )
    pair_map = policy.pcb_differential_pair_rule_map
    pair_map_sha256 = (
        hashlib.sha256(pair_map.model_dump_json().encode("utf-8")).hexdigest()
        if pair_map is not None
        else None
    )
    if pair_map is not None and pair_mode == "off":
        pcb_differential_pair_coverage = PcbDifferentialPairRuleCoverageReport(
            status="DISABLED",
            mode="off",
            map_sha256=pair_map_sha256,
        )
    loop_override = next(
        (item for item in policy.rules if item.rule_id == "pcb.switching_loop_geometry"),
        None,
    )
    loop_mode: Literal["review", "block", "off"] = (
        "review" if loop_override is None else loop_override.mode
    )
    loop_map = policy.pcb_switching_loop_map
    if loop_map is not None and loop_mode == "off":
        pcb_switching_loop_coverage = PcbSwitchingLoopCoverageReport(
            status="DISABLED",
            mode="off",
            map_sha256=hashlib.sha256(loop_map.model_dump_json().encode("utf-8")).hexdigest(),
        )
    reference_plane_map: PcbReferencePlaneMap | None = policy.pcb_reference_plane_map
    reference_plane_override = next(
        (item for item in policy.rules if item.rule_id == "pcb.reference_plane_coverage"),
        None,
    )
    reference_plane_mode: Literal["review", "block", "off"] = (
        "review" if reference_plane_override is None else reference_plane_override.mode
    )
    reference_plane_map_sha256 = (
        hashlib.sha256(reference_plane_map.model_dump_json().encode("utf-8")).hexdigest()
        if reference_plane_map is not None
        else None
    )
    if pcb_reference_plane_coverage is None:
        if reference_plane_map is None:
            pcb_reference_plane_coverage = PcbReferencePlaneCoverageReport()
        elif reference_plane_mode == "off":
            pcb_reference_plane_coverage = PcbReferencePlaneCoverageReport(
                status="DISABLED",
                mode="off",
                map_sha256=reference_plane_map_sha256,
            )
        else:
            pcb_reference_plane_coverage = PcbReferencePlaneCoverageReport(
                status="BLOCKED",
                mode=reference_plane_mode,
                map_sha256=reference_plane_map_sha256,
                issue="Source-bound native PCB geometry was not supplied for the reference-plane map",
            )
    protection_path_map: PcbProtectionPathMap | None = policy.pcb_protection_path_map
    protection_path_override = next(
        (item for item in policy.rules if item.rule_id == "pcb.protection_entry_path"),
        None,
    )
    protection_path_mode: Literal["review", "block", "off"] = (
        "review" if protection_path_override is None else protection_path_override.mode
    )
    protection_path_map_sha256 = (
        hashlib.sha256(protection_path_map.model_dump_json().encode("utf-8")).hexdigest()
        if protection_path_map is not None
        else None
    )
    if pcb_protection_path_coverage is None:
        if protection_path_map is None:
            pcb_protection_path_coverage = PcbProtectionPathCoverageReport()
        elif protection_path_mode == "off":
            pcb_protection_path_coverage = PcbProtectionPathCoverageReport(
                status="DISABLED",
                mode=protection_path_mode,
                map_sha256=protection_path_map_sha256,
            )
        else:
            pcb_protection_path_coverage = PcbProtectionPathCoverageReport(
                status="BLOCKED",
                mode=protection_path_mode,
                map_sha256=protection_path_map_sha256,
                issue="Source-bound native PCB geometry was not supplied for the protection path map",
            )
    if coach.status != "READY_FOR_REVIEW" or coach.observed is None:
        rc_filter_coverage = (
            RcFilterCoverageReport(
                status="BLOCKED",
                issue="Source-bound native netlist evidence is unavailable for RC filter review",
            )
            if policy.rc_filter_map is not None
            else RcFilterCoverageReport()
        )
        connector_return_distribution_coverage = (
            ConnectorReturnDistributionCoverageReport(
                status="BLOCKED",
                issue=(
                    "Source-bound native netlist evidence is unavailable for connector "
                    "return-distribution review"
                ),
            )
            if policy.connector_return_distribution_map is not None
            else ConnectorReturnDistributionCoverageReport()
        )
        pcb_decoupling_coverage = (
            PcbDecouplingCoverageReport(
                status="BLOCKED",
                issue="Source-bound native netlist evidence is unavailable for PCB decoupling review",
            )
            if policy.pcb_decoupling_map is not None
            else PcbDecouplingCoverageReport()
        )
        pcb_track_width_coverage = (
            PcbTrackWidthCoverageReport(
                status="BLOCKED",
                issue="Source-bound native PCB geometry is unavailable for track-width review",
            )
            if policy.pcb_track_width_map is not None
            else PcbTrackWidthCoverageReport()
        )
        if loop_map is None:
            pcb_switching_loop_coverage = PcbSwitchingLoopCoverageReport()
        elif loop_mode == "off":
            pcb_switching_loop_coverage = PcbSwitchingLoopCoverageReport(
                status="DISABLED", mode=loop_mode
            )
        else:
            pcb_switching_loop_coverage = PcbSwitchingLoopCoverageReport(
                status="BLOCKED",
                mode=loop_mode,
                map_sha256=hashlib.sha256(loop_map.model_dump_json().encode("utf-8")).hexdigest(),
                issue="Source-bound native PCB stack and copper evidence is unavailable for switching-loop review",
            )
        if policy.pcb_differential_pair_rule_map is None:
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
                issue="Source-bound native DRC evidence is unavailable for differential-pair rule coverage",
            )
        missing_evidence_issues = coach.issues or ("Source-bound netlist evidence is unavailable",)
        if policy.component_role_map is not None:
            missing_evidence_issues += (
                "The project component role map cannot be checked without source-bound native netlist evidence.",
            )
        if policy.complementary_pin_function_alias_map is not None:
            missing_evidence_issues += (
                "The project complementary pin-function alias map cannot be checked without source-bound native netlist evidence.",
            )
        return DesignLintReport(
            status="BLOCKED",
            project_id=project_id,
            rule_catalog=catalog,
            native_summary=coach.native_summary,
            native_status=coach.native_status,
            rc_filter_coverage=rc_filter_coverage,
            connector_return_distribution=connector_return_distribution_coverage,
            pcb_decoupling=pcb_decoupling_coverage,
            pcb_protection_path=pcb_protection_path_coverage,
            pcb_track_width=pcb_track_width_coverage,
            pcb_reference_plane=pcb_reference_plane_coverage,
            pcb_switching_loop=pcb_switching_loop_coverage,
            pcb_differential_pair_rules=pcb_differential_pair_coverage,
            stm32_pin_map_coverage=stm32_pin_map_coverage,
            issues=missing_evidence_issues,
            next_actions=("Repair the native evidence, then rerun design lint.",),
        )
    component_role_resolution = resolve_component_role_map(
        coach.observed, policy.component_role_map
    )
    complementary_alias_resolution = resolve_complementary_pin_function_aliases(
        coach.observed, policy.complementary_pin_function_alias_map
    )
    if geometry_coverage is None and schematic_geometry is not None:
        geometry_rule_ids = _SCHEMATIC_GEOMETRY_RULE_IDS
        overrides = {
            item.rule_id: item for item in policy.rules if item.rule_id in geometry_rule_ids
        }
        rule_modes: dict[SchematicGeometryRuleId, Literal["review", "block", "off"]] = {
            rule_id: overrides[rule_id].mode if rule_id in overrides else "off"
            for rule_id in geometry_rule_ids
        }
        geometry_coverage = _schematic_geometry_coverage(
            schematic_geometry, coach.netlist_sha256, rule_modes
        )
    if geometry_coverage is None:
        geometry_coverage = SchematicGeometryCoverage()
    if external_protection_coverage is None:
        external_protection_coverage = ExternalProtectionCoverageReport()
    if i2c_address_coverage is None:
        address_map: I2cAddressMap | None = policy.i2c_address_map
        if address_map is None:
            i2c_address_coverage = I2cAddressCoverageReport()
        elif coach.netlist_sha256 is None:
            i2c_address_coverage = I2cAddressCoverageReport(
                status="BLOCKED",
                issue="Source-bound native netlist hash is unavailable for I2C address review",
            )
        else:
            try:
                i2c_address_coverage = scan_i2c_address_map(
                    address_map, coach.observed, coach.netlist_sha256
                )
            except (OSError, ValueError, TypeError) as exc:
                i2c_address_coverage = I2cAddressCoverageReport(
                    status="BLOCKED",
                    netlist_sha256=coach.netlist_sha256,
                    issue=f"Could not compare the I2C address map with native evidence: {exc}",
                )
    if crystal_network_coverage is None:
        network_map: CrystalNetworkMap | None = policy.crystal_network_map
        if network_map is None:
            crystal_network_coverage = CrystalNetworkCoverageReport()
        elif coach.netlist_sha256 is None:
            crystal_network_coverage = CrystalNetworkCoverageReport(
                status="BLOCKED",
                issue="Source-bound native netlist hash is unavailable for crystal network review",
            )
        else:
            try:
                crystal_network_coverage = scan_crystal_network_map(
                    network_map, coach.observed, coach.netlist_sha256
                )
            except (OSError, ValueError, TypeError) as exc:
                crystal_network_coverage = CrystalNetworkCoverageReport(
                    status="BLOCKED",
                    netlist_sha256=coach.netlist_sha256,
                    issue=f"Could not compare the crystal network map with native evidence: {exc}",
                )
    if regulator_feedback_coverage is None:
        feedback_map: RegulatorFeedbackMap | None = policy.regulator_feedback_map
        if feedback_map is None:
            regulator_feedback_coverage = RegulatorFeedbackCoverageReport()
        elif coach.netlist_sha256 is None:
            regulator_feedback_coverage = RegulatorFeedbackCoverageReport(
                status="BLOCKED",
                issue="Source-bound native netlist hash is unavailable for regulator feedback review",
            )
        else:
            try:
                regulator_feedback_coverage = scan_regulator_feedback_map(
                    feedback_map, coach.observed, coach.netlist_sha256
                )
            except (OSError, ValueError, TypeError) as exc:
                regulator_feedback_coverage = RegulatorFeedbackCoverageReport(
                    status="BLOCKED",
                    netlist_sha256=coach.netlist_sha256,
                    issue=f"Could not compare the regulator feedback map with native evidence: {exc}",
                )
    if rc_filter_coverage is None:
        filter_map: RcFilterMap | None = policy.rc_filter_map
        if filter_map is None:
            rc_filter_coverage = RcFilterCoverageReport()
        elif coach.netlist_sha256 is None:
            rc_filter_coverage = RcFilterCoverageReport(
                status="BLOCKED",
                issue="Source-bound native netlist hash is unavailable for RC filter review",
            )
        else:
            try:
                rc_filter_coverage = scan_rc_filter_map(
                    filter_map, coach.observed, coach.netlist_sha256
                )
            except (OSError, ValueError, TypeError) as exc:
                rc_filter_coverage = RcFilterCoverageReport(
                    status="BLOCKED",
                    netlist_sha256=coach.netlist_sha256,
                    issue=f"Could not compare the RC filter map with native evidence: {exc}",
                )
    if connector_return_distribution_coverage is None:
        distribution_map: ConnectorReturnDistributionMap | None = (
            policy.connector_return_distribution_map
        )
        if distribution_map is None:
            connector_return_distribution_coverage = ConnectorReturnDistributionCoverageReport()
        else:
            try:
                connector_return_distribution_coverage = scan_connector_return_distribution_map(
                    distribution_map,
                    connector_coverage,
                    coach.netlist_sha256,
                )
            except (OSError, ValueError, TypeError) as exc:
                connector_return_distribution_coverage = ConnectorReturnDistributionCoverageReport(
                    status="BLOCKED",
                    netlist_sha256=coach.netlist_sha256,
                    interface_catalog_sha256=(
                        None
                        if connector_coverage is None
                        else connector_coverage.interface_catalog_sha256
                    ),
                    issue=(
                        "Could not compare the connector return-distribution map with "
                        f"source-bound evidence: {exc}"
                    ),
                )
    if pcb_decoupling_coverage is None:
        pcb_decoupling_coverage = (
            PcbDecouplingCoverageReport(
                status="BLOCKED",
                issue="Native PCB geometry evidence was not supplied for the configured decoupling map",
            )
            if policy.pcb_decoupling_map is not None
            else PcbDecouplingCoverageReport()
        )
    if pcb_track_width_coverage is None:
        pcb_track_width_coverage = (
            PcbTrackWidthCoverageReport(
                status="BLOCKED",
                issue="Native PCB geometry evidence was not supplied for the configured track-width map",
            )
            if policy.pcb_track_width_map is not None
            else PcbTrackWidthCoverageReport()
        )
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
    overrides = {item.rule_id: item for item in policy.rules}
    ignores = {item.fingerprint: item for item in policy.ignores}
    default_modes: dict[DesignLintRuleId, Literal["review", "block", "off"]] = {
        item.rule_id: item.default_mode for item in catalog.rules
    }
    peer_voltage_scope = digital_peer_voltage_context or DigitalPeerVoltageLintContext(
        state="not_configured"
    )
    digital_peer_voltage_scan = scan_digital_peer_voltage_reviews(
        coach.observed, peer_voltage_scope.analysis
    )
    digital_peer_voltage_coverage = (
        ()
        if coach.netlist_sha256 is None
        else _digital_peer_voltage_coverage(
            digital_peer_voltage_scan,
            peer_voltage_scope,
            default_modes,
            overrides,
            coach.netlist_sha256,
        )
    )
    reviewed_connector_references = (
        tuple(
            entry.reference
            for entry in connector_coverage.entries
            if entry.interface_id is not None
        )
        if connector_coverage is not None
        else ()
    )
    usb_peer_reference_scan = scan_usb_peer_reference_reviews(
        coach.observed,
        policy.usb_data_path_map,
        reviewed_connector_references,
    )
    usb_peer_reference_coverage = (
        None
        if coach.netlist_sha256 is None
        else _usb_peer_reference_coverage(
            usb_peer_reference_scan,
            default_modes,
            overrides,
            coach.netlist_sha256,
            policy.usb_data_path_map,
        )
    )
    serial_scope = serial_peer_roster or SerialPeerRosterContext(state="not_configured")
    serial_peer_reference_scan = scan_serial_peer_reference_reviews(
        coach.observed,
        serial_scope.analysis,
        reviewed_connector_references,
    )
    serial_peer_reference_coverage = (
        None
        if coach.netlist_sha256 is None
        else _serial_peer_reference_coverage(
            serial_peer_reference_scan,
            serial_scope,
            default_modes,
            overrides,
            coach.netlist_sha256,
        )
    )
    candidate_items = candidates(
        coach.observed,
        catalog,
        schematic_geometry,
        i2c_address_coverage,
        external_protection_coverage,
        crystal_network_coverage,
        regulator_feedback_coverage,
        rc_filter_coverage,
        connector_return_distribution_coverage,
        pcb_decoupling_coverage,
        pcb_protection_path_coverage,
        pcb_track_width_coverage,
        pcb_switching_loop_coverage,
        pcb_differential_pair_coverage,
        policy.pcb_differential_pair_rule_map,
        policy.i2c_address_map,
        policy.usb_data_path_map,
        stm32_pin_map_coverage,
        spi_roster,
        usb_c_port_roster,
        policy.power_path_map,
        policy.power_sequence_map,
        pcb_reference_plane_coverage,
        control_input_bias_coverage,
        i2c_pullup_heuristic_coverage,
        digital_peer_voltage_context,
        policy.component_role_map,
        serial_peer_roster,
        reviewed_connector_references,
        complementary_alias_resolution,
        connector_coverage=connector_coverage,
        digital_peer_voltage_scan=digital_peer_voltage_scan,
        usb_peer_reference_scan=usb_peer_reference_scan,
        serial_peer_reference_scan=serial_peer_reference_scan,
    )
    connector_peer_pin_coverage = (
        None
        if coach.netlist_sha256 is None
        else connector_peer_pin_heuristic_coverage(
            coach.observed,
            coach.netlist_sha256,
            reviewed_connector_references,
            source_matched_connector_pin_evidence(coach.observed, connector_coverage),
            source_matched_connector_peer_assignment_groups(coach.observed, connector_coverage),
            repeated_function_finding_count=sum(
                item.rule_id == "connector.repeated_pin_function" for item in candidate_items
            ),
            peer_pin_outlier_finding_count=sum(
                item.rule_id == "connector.peer_pin_assignment_outlier" for item in candidate_items
            ),
            peer_pin_divergence_finding_count=sum(
                item.rule_id == "connector.peer_pin_assignment_divergence"
                for item in candidate_items
            ),
        )
    )
    usb_rule_id: Literal["bus.usb_data_path_mismatch"] = "bus.usb_data_path_mismatch"
    power_path_rule_id: Literal["power.mapped_series_path_mismatch"] = (
        "power.mapped_series_path_mismatch"
    )
    power_sequence_rule_id: Literal["power.mapped_sequence_dependency_mismatch"] = (
        "power.mapped_sequence_dependency_mismatch"
    )
    usb_override = overrides.get(usb_rule_id)
    power_path_override = overrides.get(power_path_rule_id)
    power_sequence_override = overrides.get(power_sequence_rule_id)
    usb_map = policy.usb_data_path_map
    power_path_map = policy.power_path_map
    power_sequence_map = policy.power_sequence_map
    mapped_check_runs = (
        _mapped_check_run(
            usb_rule_id,
            None
            if usb_map is None
            else hashlib.sha256(usb_map.model_dump_json().encode("utf-8")).hexdigest(),
            0 if usb_map is None else len(usb_map.interfaces),
            coach.netlist_sha256,
            candidate_items,
            default_modes[usb_rule_id] if usb_override is None else usb_override.mode,
        ),
        _mapped_check_run(
            power_path_rule_id,
            None
            if power_path_map is None
            else hashlib.sha256(power_path_map.model_dump_json().encode("utf-8")).hexdigest(),
            0 if power_path_map is None else len(power_path_map.paths),
            coach.netlist_sha256,
            candidate_items,
            default_modes[power_path_rule_id]
            if power_path_override is None
            else power_path_override.mode,
        ),
        _mapped_check_run(
            power_sequence_rule_id,
            None
            if power_sequence_map is None
            else hashlib.sha256(power_sequence_map.model_dump_json().encode("utf-8")).hexdigest(),
            0
            if power_sequence_map is None
            else len(power_sequence_map.stages) + len(power_sequence_map.dependencies),
            coach.netlist_sha256,
            candidate_items,
            default_modes[power_sequence_rule_id]
            if power_sequence_override is None
            else power_sequence_override.mode,
        ),
    )
    seen: set[str] = set()
    findings: list[DesignLintFinding] = []
    for item in candidate_items:
        key = fingerprint(item)
        seen.add(key)
        override = overrides.get(item.rule_id)
        mode: Literal["review", "block", "off"] = (
            default_modes[item.rule_id] if override is None else override.mode
        )
        ignored = ignores.get(key)
        if ignored is not None and ignored.rule_id != item.rule_id:
            return DesignLintReport(
                status="BLOCKED",
                project_id=project_id,
                source_hashes=source_hashes,
                netlist_sha256=coach.netlist_sha256,
                native_summary=coach.native_summary,
                native_status=coach.native_status,
                rule_catalog=catalog,
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
                stm32_pin_map_coverage=stm32_pin_map_coverage,
                control_input_bias_coverage=(
                    control_input_bias_coverage or ControlInputBiasHeuristicCoverage()
                ),
                i2c_pullup_heuristic_coverage=(
                    i2c_pullup_heuristic_coverage or I2cPullupHeuristicCoverage()
                ),
                connector_peer_pin_coverage=connector_peer_pin_coverage,
                issues=(f"Ignore {key} names the wrong rule",),
            )
        disposition: Literal["OPEN", "IGNORED", "RULE_OFF"] = (
            "RULE_OFF" if mode == "off" else "IGNORED" if ignored is not None else "OPEN"
        )
        findings.append(
            DesignLintFinding(
                rule_id=item.rule_id,
                fingerprint=key,
                subject=item.subject,
                message=item.message,
                evidence=item.evidence,
                mode=mode,
                disposition=disposition,
                reason=(
                    override.reason
                    if disposition == "RULE_OFF" and override is not None
                    else ignored.reason
                    if ignored is not None
                    else None
                ),
            )
        )
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
        stale_ignores=stale,
        rule_overrides=policy.rules,
        issues=issues,
        next_actions=actions,
    )


def _connector_coverage(
    root: Path, config: ProjectConfig, observed: NetlistContract
) -> ConnectorCoverageReport:
    """Bind project connector reviews to the configured interface catalog when used."""
    needs_catalog = bool(config.interfaces) or any(
        review.disposition == "interface" for review in config.connector_reviews
    )
    if not needs_catalog:
        return evaluate_connector_coverage(
            observed,
            config.interfaces,
            config.connector_reviews,
            inventory_review=config.connector_inventory_review,
        )

    registry = load_registry(root)
    catalog_relative = registry.catalogs.interfaces
    catalog_path = repo_path(root, catalog_relative)
    catalog_hash: str | None = None
    catalog: InterfacesCatalog | None = None
    issues: list[str] = []
    try:
        catalog_hash = digest(catalog_path)
        catalog = read_model(catalog_path, InterfacesCatalog)
        if digest(catalog_path) != catalog_hash:
            issues.append("Interface catalog changed during connector coverage inspection")
    except (OSError, ValueError, TypeError) as exc:
        issues.append(f"Could not read the configured interface catalog: {exc}")

    interfaces: dict[str, InterfaceRecord] = {}
    if catalog is not None:
        for record in catalog.interfaces:
            if record.id in interfaces:
                issues.append(f"Interface catalog repeats ID {record.id}")
            else:
                interfaces[record.id] = record
        missing = sorted(set(config.interfaces) - interfaces.keys())
        issues.extend(
            f"Project interface ID is absent from the catalog: {identifier}"
            for identifier in missing
        )

    return evaluate_connector_coverage(
        observed,
        config.interfaces,
        config.connector_reviews,
        interfaces=interfaces,
        interface_catalog_path=catalog_relative,
        interface_catalog_sha256=catalog_hash,
        catalog_issues=tuple(issues),
        inventory_review=config.connector_inventory_review,
    )


def _usb_c_protection_scope(
    root: Path,
    config: ProjectConfig,
    connector_coverage: ConnectorCoverageReport,
) -> tuple[dict[str, str], str | None, str | None]:
    """Return connector pins whose protection disposition is owned by USB-C review."""
    if config.electrical is None:
        return {}, None, None
    path = repo_path(root, config.electrical)
    relative_path = path.relative_to(root).as_posix()
    expected_digest = digest(path)
    contract = load_analysis(root, config)
    if digest(path) != expected_digest:
        raise ValueError("Electrical contract changed during external-protection inspection")
    handled: dict[str, str] = {}
    if contract is None or not isinstance(contract.usb_c, UsbCAnalysis):
        return handled, relative_path, expected_digest
    for port in contract.usb_c.ports:
        prefix = f"{port.connector}.".casefold()
        handled[port.cc1.connector_pin] = port.cc1.net
        handled[port.cc2.connector_pin] = port.cc2.net
        handled.update(
            {
                assignment.pin: assignment.net
                for assignment in port.vbus_pins
                if assignment.pin.casefold().startswith(prefix)
            }
        )
        handled.update(
            {pin: port.ground_net for pin in port.ground_pins if pin.casefold().startswith(prefix)}
        )
    handled.update(_mapped_usb_c_protection_pins(contract.usb_c, connector_coverage))
    return handled, relative_path, expected_digest


def _spi_roster_context(root: Path, config: ProjectConfig) -> SpiRosterContext:
    """Load the SPI roster and bind it to the exact project electrical contract."""
    if config.electrical is None:
        return SpiRosterContext(state="not_configured")
    path = repo_path(root, config.electrical)
    relative_path = path.relative_to(root).as_posix()
    expected_digest = digest(path)
    contract = load_analysis(root, config)
    if digest(path) != expected_digest:
        raise ValueError("Electrical contract changed during SPI roster inspection")
    spi = None if contract is None else contract.spi
    if isinstance(spi, SpiAnalysis):
        state = "required"
        analysis = spi
    else:
        mode = getattr(spi, "mode", None)
        state = mode if mode in {"pending", "not_applicable"} else "not_configured"
        analysis = None
    return SpiRosterContext(
        state=state,
        analysis=analysis,
        source_path=relative_path,
        source_sha256=expected_digest,
    )


def _serial_peer_roster_context(root: Path, config: ProjectConfig) -> SerialPeerRosterContext:
    """Load the serial peer map and bind it to the exact electrical contract."""
    if config.electrical is None:
        return SerialPeerRosterContext(state="not_configured")
    path = repo_path(root, config.electrical)
    relative_path = path.relative_to(root).as_posix()
    expected_digest = digest(path)
    contract = load_analysis(root, config)
    if digest(path) != expected_digest:
        raise ValueError("Electrical contract changed during serial-peer map inspection")
    section = None if contract is None else contract.serial_peers
    if isinstance(section, SerialPeerAnalysis):
        state = "required"
        analysis = section
    else:
        mode = getattr(section, "mode", None)
        state = mode if mode in {"pending", "not_applicable"} else "not_configured"
        analysis = None
    return SerialPeerRosterContext(
        state=state,
        analysis=analysis,
        source_path=relative_path,
        source_sha256=expected_digest,
    )


def _digital_peer_voltage_lint_context(
    root: Path, config: ProjectConfig
) -> DigitalPeerVoltageLintContext:
    """Read and hash-bind the optional exact digital-peer voltage map."""
    if config.electrical is None:
        return DigitalPeerVoltageLintContext(state="not_configured")
    path = repo_path(root, config.electrical)
    relative_path = path.relative_to(root).as_posix()
    expected_digest = digest(path)
    contract = load_analysis(root, config)
    if digest(path) != expected_digest:
        raise ValueError("Electrical contract changed during digital-peer voltage inspection")
    section = None if contract is None else contract.digital_peer_voltages
    if isinstance(section, DigitalPeerVoltageAnalysis):
        state = "required"
        analysis = section
    elif isinstance(section, AnalysisPending):
        state = "pending"
        analysis = None
    elif isinstance(section, AnalysisNotApplicable):
        state = "not_applicable"
        analysis = None
    else:
        state = "not_configured"
        analysis = None
    return DigitalPeerVoltageLintContext(
        state=state,
        analysis=analysis,
        source_path=relative_path,
        source_sha256=expected_digest,
    )


def _control_input_bias_coverage(
    root: Path,
    config: ProjectConfig,
    observed: NetlistContract,
    netlist_sha256: str,
) -> ControlInputBiasHeuristicCoverage:
    """Bind control-bias heuristic resolution to the current electrical contract bytes."""
    if config.electrical is None:
        return control_input_bias_heuristic_coverage(
            observed,
            netlist_sha256=netlist_sha256,
            source_path=None,
            source_sha256=None,
            state="not_configured",
        )
    path = repo_path(root, config.electrical)
    relative_path = path.relative_to(root).as_posix()
    expected_digest = digest(path)
    contract = load_analysis(root, config)
    if digest(path) != expected_digest:
        raise ValueError("Electrical contract changed during control-input heuristic inspection")
    control_inputs = None if contract is None else contract.control_inputs
    if isinstance(control_inputs, ControlInputsAnalysis):
        state = "required"
        spec = control_inputs
    elif isinstance(control_inputs, AnalysisPending):
        state = "pending"
        spec = None
    elif isinstance(control_inputs, AnalysisNotApplicable):
        state = "not_applicable"
        spec = None
    else:
        state = "not_configured"
        spec = None
    return control_input_bias_heuristic_coverage(
        observed,
        netlist_sha256=netlist_sha256,
        source_path=relative_path,
        source_sha256=expected_digest,
        state=state,
        spec=spec,
    )


def _i2c_pullup_heuristic_coverage(
    root: Path,
    config: ProjectConfig,
    observed: NetlistContract,
    netlist_sha256: str,
) -> I2cPullupHeuristicCoverage:
    """Bind I2C hint resolution to the exact electrical contract and native netlist."""
    if config.electrical is None:
        return resolve_i2c_pullup_heuristic_coverage(
            observed,
            netlist_sha256=netlist_sha256,
            source_path=None,
            source_sha256=None,
            state="not_configured",
        )
    path = repo_path(root, config.electrical)
    relative_path = path.relative_to(root).as_posix()
    expected_digest = digest(path)
    contract = load_analysis(root, config)
    if digest(path) != expected_digest:
        raise ValueError("Electrical contract changed during I2C pull-up heuristic inspection")
    pullups = None if contract is None else contract.i2c_pullups
    if isinstance(pullups, I2cPullupAnalysis):
        state = "required"
        spec = pullups
    elif isinstance(pullups, AnalysisPending):
        state = "pending"
        spec = None
    elif isinstance(pullups, AnalysisNotApplicable):
        state = "not_applicable"
        spec = None
    else:
        state = "not_configured"
        spec = None
    return resolve_i2c_pullup_heuristic_coverage(
        observed,
        netlist_sha256=netlist_sha256,
        source_path=relative_path,
        source_sha256=expected_digest,
        state=state,
        spec=spec,
    )


def _usb_c_port_roster_context(root: Path, config: ProjectConfig) -> UsbCPortRosterContext:
    """Load USB-C role coverage and bind it to the exact project electrical contract."""
    if config.electrical is None:
        return UsbCPortRosterContext(state="not_configured")
    path = repo_path(root, config.electrical)
    relative_path = path.relative_to(root).as_posix()
    expected_digest = digest(path)
    contract = load_analysis(root, config)
    if digest(path) != expected_digest:
        raise ValueError("Electrical contract changed during USB-C port roster inspection")
    usb_c = None if contract is None else contract.usb_c
    if isinstance(usb_c, UsbCAnalysis):
        state = "required"
        analysis = usb_c
    else:
        mode = getattr(usb_c, "mode", None)
        state = mode if mode in {"pending", "not_applicable"} else "not_configured"
        analysis = None
    return UsbCPortRosterContext(
        state=state,
        analysis=analysis,
        source_path=relative_path,
        source_sha256=expected_digest,
    )


def _mapped_usb_c_protection_pins(
    analysis: UsbCAnalysis,
    connector_coverage: ConnectorCoverageReport,
) -> dict[str, str]:
    """Map covered connector pins to exact non-reference nets in USB-C protector maps."""
    handled: dict[str, str] = {}
    for port in analysis.ports:
        if not isinstance(port.protection, UsbCProtectionAnalysis):
            continue
        reference_nets = {port.ground_net, port.vbus_net, port.cc1.net, port.cc2.net}
        protected_signal_nets = {
            assignment.net
            for component in port.protection.components
            for assignment in component.pins
            if assignment.net not in reference_nets
        }
        for connector in connector_coverage.entries:
            if connector.reference.casefold() != port.connector.casefold():
                continue
            if connector.status != "COVERED":
                continue
            for pin in connector.mapped_pins:
                if len(pin.nets) == 1 and pin.nets[0] in protected_signal_nets:
                    handled[pin.component_pin] = pin.nets[0]
    return handled


def _external_protection_coverage(
    root: Path,
    config: ProjectConfig,
    policy: DesignLintPolicy,
    observed: NetlistContract,
    connector_coverage: ConnectorCoverageReport,
    netlist_sha256: str | None,
) -> ExternalProtectionCoverageReport:
    """Bind authored protection maps and reused USB-C dispositions to native evidence."""
    has_reviewed_interface_pins = any(
        entry.status == "COVERED" and entry.mapped_pins for entry in connector_coverage.entries
    )
    if policy.external_protection_map is None and not has_reviewed_interface_pins:
        return evaluate_external_protection(None, observed, None, netlist_sha256)
    try:
        handled, contract_path, contract_hash = _usb_c_protection_scope(
            root, config, connector_coverage
        )
    except (OSError, ValueError, TypeError) as exc:
        return ExternalProtectionCoverageReport(
            status="BLOCKED",
            netlist_sha256=netlist_sha256,
            issue=(
                "Could not inspect the electrical contract for duplicate USB-C protection "
                f"coverage: {exc}"
            ),
        )
    return evaluate_external_protection(
        policy.external_protection_map,
        observed,
        connector_coverage,
        netlist_sha256,
        handled_by_existing_contract=handled,
        electrical_contract_path=contract_path,
        electrical_contract_sha256=contract_hash,
    )


def _scan_schematic_geometry(
    root: Path,
    config: ProjectConfig,
    coach: ContractCoachReport,
    policy: DesignLintPolicy,
) -> tuple[SchematicGeometryScan | None, SchematicGeometryCoverage]:
    """Run geometry only for explicit project opt-in and bind it to native evidence."""
    geometry_rule_ids = _SCHEMATIC_GEOMETRY_RULE_IDS
    overrides = {item.rule_id: item for item in policy.rules if item.rule_id in geometry_rule_ids}
    if not overrides:
        return None, SchematicGeometryCoverage()
    rule_modes: dict[SchematicGeometryRuleId, Literal["review", "block", "off"]] = {
        rule_id: overrides[rule_id].mode if rule_id in overrides else "off"
        for rule_id in geometry_rule_ids
    }
    active_modes = tuple(mode for mode in rule_modes.values() if mode != "off")
    if not active_modes:
        return None, SchematicGeometryCoverage(
            status="DISABLED",
            mode="off",
            rule_modes=rule_modes,
            rule_coverage={rule_id: "DISABLED" for rule_id in geometry_rule_ids},
        )
    mode: Literal["review", "block"] = "block" if "block" in active_modes else "review"

    relative_path: str | None = None
    expected_source_hash: str | None = None
    try:
        schematic_relative = Path(config.project).with_suffix(".kicad_sch").as_posix()
        if coach.netlist_sha256 is None or coach.observed is None:
            raise ValueError("Source-bound native netlist evidence is unavailable")
        source_path = repo_path(root, schematic_relative)
        relative_path = source_path.relative_to(root).as_posix()
        project_directory = source_path.parent.relative_to(root).as_posix()
        expected_source_hash = coach.source_hashes.get(relative_path)
        if expected_source_hash is None:
            raise ValueError(
                "Primary schematic is absent from the source-bound native summary hashes"
            )

        source_files: dict[str, bytes] = {}
        pending = [relative_path]
        while pending:
            current_path = pending.pop()
            if current_path in source_files:
                continue
            if len(source_files) >= MAX_SHEET_OCCURRENCES:
                raise ValueError(
                    f"Schematic source tree exceeds {MAX_SHEET_OCCURRENCES} unique files"
                )
            current_file = repo_path(root, current_path)
            expected_hash = coach.source_hashes.get(current_path)
            if expected_hash is None:
                raise ValueError(
                    "Referenced hierarchical schematic is absent from the "
                    f"source-bound native summary hashes: {current_path}"
                )
            source = current_file.read_bytes()
            actual_hash = hashlib.sha256(source).hexdigest()
            if actual_hash != expected_hash:
                raise ValueError(
                    f"Schematic differs from the source-bound native summary: {current_path}"
                )
            source_files[current_path] = source
            for sheet in schematic_sheet_references(source):
                child_path = resolve_schematic_sheet_path(
                    current_path,
                    project_directory,
                    sheet.file,
                )
                repo_path(root, child_path)
                if child_path not in source_files:
                    pending.append(child_path)

        unconnected_pins = frozenset(
            pin for pins in coach.observed.unconnected_nets.values() for pin in pins
        )
        scan = scan_schematic_geometry_tree(
            source_files,
            root_path=relative_path,
            project_directory=project_directory,
            project_name=source_path.stem,
            kicad_version=config.kicad_version,
            unconnected_pins=unconnected_pins,
        )
        if any(
            binding.source_path not in source_files
            or hashlib.sha256(source_files[binding.source_path]).hexdigest()
            != binding.source_sha256
            for binding in scan.source_bindings
        ):
            raise ValueError("Geometry scan returned an unbound hierarchical source instance")
        if scan.source_sha256 != expected_source_hash:
            raise ValueError("Geometry scan source hash differs from native source evidence")
        coverage = _schematic_geometry_coverage(scan, coach.netlist_sha256, rule_modes)
        return scan, coverage
    except (OSError, ValueError, TypeError) as exc:
        return None, SchematicGeometryCoverage(
            status="BLOCKED",
            mode=mode,
            rule_modes=rule_modes,
            source_path=relative_path,
            source_sha256=expected_source_hash,
            netlist_sha256=coach.netlist_sha256,
            kicad_version=config.kicad_version,
            issue=f"Could not bind schematic geometry to native evidence: {exc}",
        )


def _scan_pcb_geometry(
    root: Path,
    config: ProjectConfig,
    coach: ContractCoachReport,
    policy: DesignLintPolicy,
) -> tuple[
    PcbDecouplingCoverageReport,
    PcbProtectionPathCoverageReport,
    PcbTrackWidthCoverageReport,
    PcbReferencePlaneCoverageReport,
    PcbSwitchingLoopCoverageReport,
]:
    """Capture one native PCB snapshot for all configured geometry review maps."""
    decoupling_map: PcbDecouplingMap | None = policy.pcb_decoupling_map
    protection_path_map: PcbProtectionPathMap | None = policy.pcb_protection_path_map
    track_width_map: PcbTrackWidthMap | None = policy.pcb_track_width_map
    reference_plane_map: PcbReferencePlaneMap | None = policy.pcb_reference_plane_map
    switching_loop_map: PcbSwitchingLoopMap | None = policy.pcb_switching_loop_map
    if (
        decoupling_map is None
        and protection_path_map is None
        and track_width_map is None
        and reference_plane_map is None
        and switching_loop_map is None
    ):
        return (
            PcbDecouplingCoverageReport(),
            PcbProtectionPathCoverageReport(),
            PcbTrackWidthCoverageReport(),
            PcbReferencePlaneCoverageReport(),
            PcbSwitchingLoopCoverageReport(),
        )
    overrides = {item.rule_id: item for item in policy.rules}
    decoupling_override = overrides.get("pcb.decoupling_proximity")
    decoupling_mode = "review" if decoupling_override is None else decoupling_override.mode
    protection_path_override = overrides.get("pcb.protection_entry_path")
    protection_path_mode = (
        "review" if protection_path_override is None else protection_path_override.mode
    )
    track_width_override = overrides.get("pcb.minimum_track_width")
    track_width_mode = "review" if track_width_override is None else track_width_override.mode
    switching_loop_override = overrides.get("pcb.switching_loop_geometry")
    switching_loop_mode = (
        "review" if switching_loop_override is None else switching_loop_override.mode
    )
    reference_plane_override = overrides.get("pcb.reference_plane_coverage")
    reference_plane_mode = (
        "review" if reference_plane_override is None else reference_plane_override.mode
    )
    decoupling_disabled = decoupling_map is None or decoupling_mode == "off"
    protection_path_disabled = protection_path_map is None or protection_path_mode == "off"
    track_width_disabled = track_width_map is None or track_width_mode == "off"
    reference_plane_disabled = reference_plane_map is None or reference_plane_mode == "off"
    switching_loop_disabled = switching_loop_map is None or switching_loop_mode == "off"
    if (
        decoupling_disabled
        and protection_path_disabled
        and track_width_disabled
        and reference_plane_disabled
        and switching_loop_disabled
    ):
        return (
            PcbDecouplingCoverageReport(status="DISABLED", mode=decoupling_mode)
            if decoupling_map is not None
            else PcbDecouplingCoverageReport(),
            PcbProtectionPathCoverageReport(status="DISABLED", mode=protection_path_mode)
            if protection_path_map is not None
            else PcbProtectionPathCoverageReport(),
            PcbTrackWidthCoverageReport(status="DISABLED", mode=track_width_mode)
            if track_width_map is not None
            else PcbTrackWidthCoverageReport(),
            PcbReferencePlaneCoverageReport(status="DISABLED", mode=reference_plane_mode)
            if reference_plane_map is not None
            else PcbReferencePlaneCoverageReport(),
            PcbSwitchingLoopCoverageReport(status="DISABLED", mode=switching_loop_mode)
            if switching_loop_map is not None
            else PcbSwitchingLoopCoverageReport(),
        )
    board_relative = Path(config.project).with_suffix(".kicad_pcb").as_posix()
    board_path = repo_path(root, board_relative)
    output = root / "build" / "design-lint" / f"pcb-geometry-{uuid4().hex[:12]}"
    board_hash: str | None = None
    try:
        if config.kind is not ProjectKind.PCB:
            raise ValueError("PCB geometry requirements need an authoritative PCB project")
        if coach.netlist_sha256 is None:
            raise ValueError("Source-bound native netlist hash is unavailable")
        board_hash = digest(board_path)
        if coach.source_hashes.get(board_relative) != board_hash:
            raise ValueError(
                "Authoritative PCB is absent from, or differs from, native source hashes"
            )
        command, snapshot = capture_native_pcb_connectivity(root, config, output)
        if snapshot is None:
            raise ValueError(
                "Native PCB geometry probe failed; inspect "
                f"{output.relative_to(root).as_posix()}/native.command.json"
            )
        if (
            snapshot.schema_version != "10"
            or snapshot.board_sha256 != board_hash
            or snapshot.kicad_version != config.kicad_version
            or snapshot.image != pinned_image(config.image)
            or snapshot.probe_sha256 != expected_probe_sha256()
            or not snapshot.zones_refilled
            or not native_pcb_command_matches(command, config)
        ):
            raise ValueError(
                "Native PCB geometry evidence does not match the reviewed source/toolchain"
            )
        snapshot_path = output / "snapshot.json"
        write_model(snapshot_path, snapshot)
        if (
            digest(board_path) != board_hash
            or hashes(root, config.source_roots) != coach.source_hashes
        ):
            raise ValueError("Project sources changed during native PCB geometry capture")
        snapshot_relative = snapshot_path.relative_to(root).as_posix()
        snapshot_hash = digest(snapshot_path)
        probe_hash = expected_probe_sha256()
        decoupling_report = PcbDecouplingCoverageReport()
        if decoupling_map is not None:
            if decoupling_mode == "off":
                decoupling_report = PcbDecouplingCoverageReport(
                    status="DISABLED", mode=decoupling_mode
                )
            else:
                entries = pcb_decoupling_entries(decoupling_map, snapshot)
                decoupling_report = PcbDecouplingCoverageReport(
                    status="COMPLETE"
                    if all(item.status == "COMPLETE" for item in entries)
                    else "INCOMPLETE",
                    mode=decoupling_mode,
                    map_sha256=hashlib.sha256(
                        decoupling_map.model_dump_json().encode("utf-8")
                    ).hexdigest(),
                    board_path=board_relative,
                    board_sha256=board_hash,
                    snapshot_path=snapshot_relative,
                    snapshot_sha256=snapshot_hash,
                    probe_sha256=probe_hash,
                    kicad_version=snapshot.kicad_version,
                    image=snapshot.image,
                    netlist_sha256=coach.netlist_sha256,
                    entries=entries,
                )
        track_width_report = PcbTrackWidthCoverageReport()
        if track_width_map is not None:
            if track_width_mode == "off":
                track_width_report = PcbTrackWidthCoverageReport(
                    status="DISABLED", mode=track_width_mode
                )
            else:
                entries = pcb_track_width_entries(track_width_map, snapshot)
                track_width_report = PcbTrackWidthCoverageReport(
                    status="COMPLETE"
                    if all(item.status == "COMPLETE" for item in entries)
                    else "INCOMPLETE",
                    mode=track_width_mode,
                    map_sha256=hashlib.sha256(
                        track_width_map.model_dump_json().encode("utf-8")
                    ).hexdigest(),
                    board_path=board_relative,
                    board_sha256=board_hash,
                    snapshot_path=snapshot_relative,
                    snapshot_sha256=snapshot_hash,
                    probe_sha256=probe_hash,
                    kicad_version=snapshot.kicad_version,
                    image=snapshot.image,
                    netlist_sha256=coach.netlist_sha256,
                    entries=entries,
                )
        reference_plane_report = PcbReferencePlaneCoverageReport()
        if reference_plane_map is not None:
            if reference_plane_mode == "off":
                reference_plane_report = PcbReferencePlaneCoverageReport(
                    status="DISABLED", mode=reference_plane_mode
                )
            else:
                entries = pcb_reference_plane_entries(reference_plane_map, snapshot)
                reference_plane_report = PcbReferencePlaneCoverageReport(
                    status="COMPLETE"
                    if all(item.status == "COMPLETE" for item in entries)
                    else "INCOMPLETE",
                    mode=reference_plane_mode,
                    map_sha256=hashlib.sha256(
                        reference_plane_map.model_dump_json().encode("utf-8")
                    ).hexdigest(),
                    board_path=board_relative,
                    board_sha256=board_hash,
                    snapshot_path=snapshot_relative,
                    snapshot_sha256=snapshot_hash,
                    probe_sha256=probe_hash,
                    kicad_version=snapshot.kicad_version,
                    image=snapshot.image,
                    netlist_sha256=coach.netlist_sha256,
                    entries=entries,
                )
        switching_loop_report = PcbSwitchingLoopCoverageReport()
        if switching_loop_map is not None:
            if switching_loop_mode == "off":
                switching_loop_report = PcbSwitchingLoopCoverageReport(
                    status="DISABLED", mode=switching_loop_mode
                )
            else:
                entries = pcb_switching_loop_entries(switching_loop_map, snapshot)
                switching_loop_report = PcbSwitchingLoopCoverageReport(
                    status="COMPLETE"
                    if all(item.status == "COMPLETE" for item in entries)
                    else "INCOMPLETE",
                    mode=switching_loop_mode,
                    map_sha256=hashlib.sha256(
                        switching_loop_map.model_dump_json().encode("utf-8")
                    ).hexdigest(),
                    board_path=board_relative,
                    board_sha256=board_hash,
                    snapshot_path=snapshot_relative,
                    snapshot_sha256=snapshot_hash,
                    probe_sha256=probe_hash,
                    kicad_version=snapshot.kicad_version,
                    image=snapshot.image,
                    netlist_sha256=coach.netlist_sha256,
                    entries=entries,
                )
        protection_path_report = PcbProtectionPathCoverageReport()
        if protection_path_map is not None:
            if protection_path_mode == "off":
                protection_path_report = PcbProtectionPathCoverageReport(
                    status="DISABLED", mode=protection_path_mode
                )
            else:
                entries = pcb_protection_path_entries(protection_path_map, snapshot)
                protection_path_report = PcbProtectionPathCoverageReport(
                    status="COMPLETE"
                    if all(item.status == "COMPLETE" for item in entries)
                    else "INCOMPLETE",
                    mode=protection_path_mode,
                    map_sha256=hashlib.sha256(
                        protection_path_map.model_dump_json().encode("utf-8")
                    ).hexdigest(),
                    board_path=board_relative,
                    board_sha256=board_hash,
                    snapshot_path=snapshot_relative,
                    snapshot_sha256=snapshot_hash,
                    probe_sha256=probe_hash,
                    kicad_version=snapshot.kicad_version,
                    image=snapshot.image,
                    netlist_sha256=coach.netlist_sha256,
                    entries=entries,
                )
        return (
            decoupling_report,
            protection_path_report,
            track_width_report,
            reference_plane_report,
            switching_loop_report,
        )
    except (OSError, ValueError, TypeError) as exc:
        issue = f"Could not bind native PCB geometry evidence: {exc}"
        decoupling_report = (
            PcbDecouplingCoverageReport(
                status="BLOCKED",
                mode=decoupling_mode,
                map_sha256=hashlib.sha256(
                    decoupling_map.model_dump_json().encode("utf-8")
                ).hexdigest(),
                board_path=board_relative,
                issue=issue,
            )
            if decoupling_map is not None and not decoupling_disabled
            else PcbDecouplingCoverageReport(status="DISABLED", mode=decoupling_mode)
            if decoupling_map is not None
            else PcbDecouplingCoverageReport()
        )
        protection_path_report = (
            PcbProtectionPathCoverageReport(
                status="BLOCKED",
                mode=protection_path_mode,
                map_sha256=hashlib.sha256(
                    protection_path_map.model_dump_json().encode("utf-8")
                ).hexdigest(),
                board_path=board_relative,
                issue=issue,
            )
            if protection_path_map is not None and not protection_path_disabled
            else PcbProtectionPathCoverageReport(status="DISABLED", mode=protection_path_mode)
            if protection_path_map is not None
            else PcbProtectionPathCoverageReport()
        )
        track_width_report = (
            PcbTrackWidthCoverageReport(
                status="BLOCKED",
                mode=track_width_mode,
                map_sha256=hashlib.sha256(
                    track_width_map.model_dump_json().encode("utf-8")
                ).hexdigest(),
                board_path=board_relative,
                issue=issue,
            )
            if track_width_map is not None and not track_width_disabled
            else PcbTrackWidthCoverageReport(status="DISABLED", mode=track_width_mode)
            if track_width_map is not None
            else PcbTrackWidthCoverageReport()
        )
        reference_plane_report = (
            PcbReferencePlaneCoverageReport(
                status="BLOCKED",
                mode=reference_plane_mode,
                map_sha256=hashlib.sha256(
                    reference_plane_map.model_dump_json().encode("utf-8")
                ).hexdigest(),
                board_path=board_relative,
                issue=issue,
            )
            if reference_plane_map is not None and not reference_plane_disabled
            else PcbReferencePlaneCoverageReport(status="DISABLED", mode=reference_plane_mode)
            if reference_plane_map is not None
            else PcbReferencePlaneCoverageReport()
        )
        switching_loop_report = (
            PcbSwitchingLoopCoverageReport(
                status="BLOCKED",
                mode=switching_loop_mode,
                map_sha256=hashlib.sha256(
                    switching_loop_map.model_dump_json().encode("utf-8")
                ).hexdigest(),
                board_path=board_relative,
                issue=issue,
            )
            if switching_loop_map is not None and not switching_loop_disabled
            else PcbSwitchingLoopCoverageReport(status="DISABLED", mode=switching_loop_mode)
            if switching_loop_map is not None
            else PcbSwitchingLoopCoverageReport()
        )
    return (
        decoupling_report,
        protection_path_report,
        track_width_report,
        reference_plane_report,
        switching_loop_report,
    )


def scan_stm32_pin_maps(
    root: Path,
    policy: DesignLintPolicy,
    observed: NetlistContract,
    netlist_sha256: str | None,
) -> Stm32PinMapCoverageReport:
    """Read and hash project-local CubeMX files before comparing authored pin maps."""
    root = root.resolve()
    override = next(
        (item for item in policy.rules if item.rule_id == "mcu.stm32_cubemx_pin_map"),
        None,
    )
    mode: Literal["review", "block", "off"] = "review" if override is None else override.mode
    map_sha256 = _stm32_pin_map_sha256(policy.stm32_pin_maps) if policy.stm32_pin_maps else None
    if mode == "off":
        return Stm32PinMapCoverageReport(
            status="DISABLED",
            mode=mode,
            map_sha256=map_sha256,
        )
    if netlist_sha256 is None:
        if policy.stm32_pin_maps:
            return Stm32PinMapCoverageReport(
                status="BLOCKED",
                mode=mode,
                map_sha256=map_sha256,
                issue="Source-bound native netlist hash is unavailable for STM32 pin-map review",
            )
        return Stm32PinMapCoverageReport()
    if not policy.stm32_pin_maps:
        unmapped = unmapped_stm32_devices(observed, (), netlist_sha256=netlist_sha256)
        return Stm32PinMapCoverageReport(
            status="INCOMPLETE" if unmapped else "NOT_REQUESTED",
            mode=mode if unmapped else None,
            netlist_sha256=netlist_sha256 if unmapped else None,
            unmapped_devices=unmapped,
        )

    source_hashes: dict[str, str] = {}
    documents: dict[str, CubeMxDocument] = {}
    mismatches: list[Stm32PinMapMismatch] = []
    try:
        for pin_map in policy.stm32_pin_maps:
            source_path = repo_path(root, pin_map.ioc_path)
            relative_path = source_path.relative_to(root).as_posix()
            before = digest(source_path)
            content = source_path.read_bytes()
            source_sha256 = hashlib.sha256(content).hexdigest()
            if before != source_sha256 or digest(source_path) != source_sha256:
                raise ValueError(f"CubeMX IOC changed while being read: {relative_path}")
            source_hashes[relative_path] = source_sha256
            document = documents.get(relative_path)
            if document is None:
                document = parse_cubemx_ioc(content)
                documents[relative_path] = document
            if document.issues:
                raise ValueError(
                    f"CubeMX IOC has unsupported or ambiguous pin assignments in "
                    f"{relative_path}: {document.issues[0]}"
                )
            mismatches.extend(
                stm32_pin_map_mismatches(
                    pin_map,
                    observed,
                    document,
                    ioc_sha256=source_sha256,
                    map_sha256=map_sha256 or "",
                    netlist_sha256=netlist_sha256,
                )
            )
        mapped = tuple(item.reference for item in policy.stm32_pin_maps)
        unmapped = unmapped_stm32_devices(observed, mapped, netlist_sha256=netlist_sha256)
        return Stm32PinMapCoverageReport(
            status="INCOMPLETE" if unmapped else "COMPLETE",
            mode=mode,
            map_sha256=map_sha256,
            netlist_sha256=netlist_sha256,
            ioc_source_hashes=source_hashes,
            mapped_pin_count=sum(len(item.pins) for item in policy.stm32_pin_maps),
            excluded_pin_count=sum(len(item.exclusions) for item in policy.stm32_pin_maps),
            mismatches=tuple(mismatches),
            unmapped_devices=unmapped,
        )
    except (OSError, UnicodeError, ValueError) as exc:
        return Stm32PinMapCoverageReport(
            status="BLOCKED",
            mode=mode,
            map_sha256=map_sha256,
            netlist_sha256=netlist_sha256,
            ioc_source_hashes=source_hashes,
            issue=f"Could not compare the project STM32 pin map with source evidence: {exc}",
        )


def inspect_summary(root: Path, project_id: str, native_summary: Path) -> DesignLintReport:
    """Read the exact native source and the current project-owned lint decisions."""
    root = root.resolve()
    coach = inspect_contract_summary(root, project_id, native_summary)
    try:
        project = next(item for item in load_registry(root).projects if item.id == project_id)
        manifest_path = repo_path(root, project.config)
        manifest_hash = digest(manifest_path)
        manifest = read_model(manifest_path, ProjectManifest)
        policy_path = repo_path(manifest_path.parent, manifest.checks)
        policy_hash = digest(policy_path)
        config = load_config(root, project.config)
        policy = config.design_lint or DesignLintPolicy()
        if coach.status != "READY_FOR_REVIEW" or coach.observed is None:
            report = evaluate(project_id, coach, policy)
            if digest(manifest_path) != manifest_hash or digest(policy_path) != policy_hash:
                raise ValueError("Project manifest or lint policy changed during inspection")
            return report.model_copy(
                update={
                    "project_manifest_sha256": manifest_hash,
                    "policy_path": policy_path.relative_to(root).as_posix(),
                    "policy_sha256": policy_hash,
                }
            )
        if hashes(root, config.source_roots) != coach.source_hashes:
            raise ValueError("Declared source changed while reading design-lint policy")
        spi_roster = _spi_roster_context(root, config)
        serial_peer_roster = _serial_peer_roster_context(root, config)
        digital_peer_voltage_context = _digital_peer_voltage_lint_context(root, config)
        usb_c_port_roster = _usb_c_port_roster_context(root, config)
        geometry_scan, geometry_coverage = _scan_schematic_geometry(root, config, coach, policy)
        (
            pcb_decoupling_coverage,
            pcb_protection_path_coverage,
            pcb_track_width_coverage,
            pcb_reference_plane_coverage,
            pcb_switching_loop_coverage,
        ) = _scan_pcb_geometry(root, config, coach, policy)
        pair_map: PcbDifferentialPairRuleMap | None = policy.pcb_differential_pair_rule_map
        pair_override = next(
            (
                item
                for item in policy.rules
                if item.rule_id == "pcb.differential_pair_rule_coverage"
            ),
            None,
        )
        pair_mode: Literal["review", "block", "off"] = (
            "review" if pair_override is None else pair_override.mode
        )
        if pair_map is None:
            pair_rule_coverage = PcbDifferentialPairRuleCoverageReport()
        elif pair_mode == "off":
            pair_rule_coverage = PcbDifferentialPairRuleCoverageReport(
                status="DISABLED",
                mode=pair_mode,
                map_sha256=hashlib.sha256(pair_map.model_dump_json().encode("utf-8")).hexdigest(),
            )
        else:
            try:
                pair_rule_coverage = scan_source_bound_rule_map(
                    root,
                    config,
                    pair_map,
                    coach.observed,
                    dict(coach.source_hashes),
                    native_summary,
                    pair_mode,
                )
            except (OSError, ValueError, TypeError) as exc:
                pair_rule_coverage = PcbDifferentialPairRuleCoverageReport(
                    status="BLOCKED",
                    mode=pair_mode,
                    map_sha256=hashlib.sha256(
                        pair_map.model_dump_json().encode("utf-8")
                    ).hexdigest(),
                    issue=f"Could not verify source-bound differential-pair DRC rule coverage: {exc}",
                )
        coverage = _connector_coverage(root, config, coach.observed)
        stm32_pin_map_coverage = scan_stm32_pin_maps(
            root,
            policy,
            coach.observed,
            coach.netlist_sha256,
        )
        control_bias_coverage = (
            _control_input_bias_coverage(
                root,
                config,
                coach.observed,
                coach.netlist_sha256,
            )
            if coach.netlist_sha256 is not None
            else ControlInputBiasHeuristicCoverage(
                status="BLOCKED",
                issue="Native netlist hash is unavailable for control-input bias review.",
            )
        )
        i2c_pullup_coverage = (
            _i2c_pullup_heuristic_coverage(
                root,
                config,
                coach.observed,
                coach.netlist_sha256,
            )
            if coach.netlist_sha256 is not None
            else I2cPullupHeuristicCoverage(
                status="BLOCKED",
                issue="Native netlist hash is unavailable for I2C pull-up review.",
            )
        )
        protection_coverage = _external_protection_coverage(
            root,
            config,
            policy,
            coach.observed,
            coverage,
            coach.netlist_sha256,
        )
        report = evaluate(
            project_id,
            coach,
            policy,
            connector_coverage=coverage,
            schematic_geometry=geometry_scan,
            geometry_coverage=geometry_coverage,
            external_protection_coverage=protection_coverage,
            pcb_decoupling_coverage=pcb_decoupling_coverage,
            pcb_protection_path_coverage=pcb_protection_path_coverage,
            pcb_track_width_coverage=pcb_track_width_coverage,
            pcb_reference_plane_coverage=pcb_reference_plane_coverage,
            pcb_switching_loop_coverage=pcb_switching_loop_coverage,
            pcb_differential_pair_coverage=pair_rule_coverage,
            stm32_pin_map_coverage=stm32_pin_map_coverage,
            spi_roster=spi_roster,
            serial_peer_roster=serial_peer_roster,
            usb_c_port_roster=usb_c_port_roster,
            control_input_bias_coverage=control_bias_coverage,
            i2c_pullup_heuristic_coverage=i2c_pullup_coverage,
            digital_peer_voltage_context=digital_peer_voltage_context,
        )
        connector_catalog = report.connector_coverage
        if (
            digest(manifest_path) != manifest_hash
            or digest(policy_path) != policy_hash
            or (
                connector_catalog is not None
                and connector_catalog.interface_catalog_path is not None
                and connector_catalog.interface_catalog_sha256 is not None
                and digest(repo_path(root, connector_catalog.interface_catalog_path))
                != connector_catalog.interface_catalog_sha256
            )
            or (
                protection_coverage.electrical_contract_path is not None
                and digest(repo_path(root, protection_coverage.electrical_contract_path))
                != protection_coverage.electrical_contract_sha256
            )
            or any(
                digest(repo_path(root, source_path)) != source_sha256
                for source_path, source_sha256 in stm32_pin_map_coverage.ioc_source_hashes.items()
            )
            or (
                spi_roster.source_path is not None
                and digest(repo_path(root, spi_roster.source_path)) != spi_roster.source_sha256
            )
            or (
                serial_peer_roster.source_path is not None
                and digest(repo_path(root, serial_peer_roster.source_path))
                != serial_peer_roster.source_sha256
            )
            or (
                digital_peer_voltage_context.source_path is not None
                and digest(repo_path(root, digital_peer_voltage_context.source_path))
                != digital_peer_voltage_context.source_sha256
            )
            or (
                usb_c_port_roster.source_path is not None
                and digest(repo_path(root, usb_c_port_roster.source_path))
                != usb_c_port_roster.source_sha256
            )
            or (
                control_bias_coverage.source_path is not None
                and digest(repo_path(root, control_bias_coverage.source_path))
                != control_bias_coverage.source_sha256
            )
            or (
                i2c_pullup_coverage.source_path is not None
                and digest(repo_path(root, i2c_pullup_coverage.source_path))
                != i2c_pullup_coverage.source_sha256
            )
        ):
            raise ValueError("Project manifest or lint policy changed during inspection")
        return report.model_copy(
            update={
                "project_manifest_sha256": manifest_hash,
                "policy_path": policy_path.relative_to(root).as_posix(),
                "policy_sha256": policy_hash,
            }
        )
    except (OSError, ValueError, StopIteration) as exc:
        return DesignLintReport(
            status="BLOCKED",
            project_id=project_id,
            native_summary=coach.native_summary,
            native_status=coach.native_status,
            issues=(str(exc),),
            next_actions=("Repair the project-owned policy or source inventory, then rerun lint.",),
        )


def text_report(report: DesignLintReport) -> str:
    lines = [
        f"Design lint: {report.status}",
        f"Project: {report.project_id}",
        f"Native summary: {report.native_summary or 'unavailable'}",
        f"Validation summary status: {report.native_status or 'unavailable'}",
    ]
    if report.project_manifest_sha256:
        lines.append(f"Project manifest SHA-256: {report.project_manifest_sha256}")
    if report.policy_path is not None:
        lines.append(f"Lint policy: {report.policy_path} ({report.policy_sha256 or 'unavailable'})")
    if report.rule_catalog is not None:
        active_count = sum(item.status == "active" for item in report.rule_catalog.rules)
        lines.append(
            f"Rule catalog: schema {report.rule_catalog.schema_version}, "
            f"{active_count} active rules, SHA-256 {report.rule_catalog.sha256 or 'unavailable'}"
        )
    geometry = report.schematic_geometry
    mode = geometry.mode or "not configured"
    lines.append(f"Schematic geometry coverage: {geometry.status} (mode: {mode})")
    lines.append("Mapped topology check runs:")
    for item in report.mapped_check_runs:
        lines.append(
            f"  {item.rule_id}: {item.status} (mode: {item.mode}; "
            f"{item.requirement_count} authored item(s), {item.finding_count} finding(s))"
        )
        if item.map_sha256 is not None:
            lines.append(f"    Map SHA-256: {item.map_sha256}")
        if item.netlist_sha256 is not None:
            lines.append(f"    Native netlist SHA-256: {item.netlist_sha256}")
        if item.reason is not None:
            lines.append(f"    Reason: {item.reason}")
    if report.digital_peer_voltage_coverage:
        lines.append("Direct SPI/UART peer-voltage heuristic coverage:")
        for item in report.digital_peer_voltage_coverage:
            lines.append(
                f"  {item.rule_id}: {item.status} (mode: {item.mode}; "
                f"{item.recognized_endpoint_count} recognized pin function(s), "
                f"{item.assigned_endpoint_count} assigned, "
                f"{item.direct_peer_link_count} direct link(s), "
                f"{item.voltage_comparison_count} voltage comparison(s), "
                f"{item.same_voltage_link_count} same-label, "
                f"{item.different_voltage_link_count} different-label "
                f"({item.mapped_mismatch_link_count} map-covered), "
                f"{item.candidate_group_count} review group(s))"
            )
            if item.authored_map_path is not None:
                lines.append(
                    f"    Authored voltage map: {item.authored_map_path} "
                    f"(SHA-256 {item.authored_map_sha256})"
                )
            lines.append(f"    Native netlist SHA-256: {item.netlist_sha256}")
    usb_peer_coverage = report.usb_peer_reference_coverage
    if usb_peer_coverage is not None:
        lines.append("USB peer-reference heuristic coverage:")
        lines.append(
            f"  {usb_peer_coverage.rule_id}: {usb_peer_coverage.status} "
            f"(mode: {usb_peer_coverage.mode}; "
            f"connector groups {usb_peer_coverage.supported_connector_group_count}/"
            f"{usb_peer_coverage.recognized_connector_group_count}; "
            f"PHY groups {usb_peer_coverage.supported_phy_group_count}/"
            f"{usb_peer_coverage.recognized_phy_group_count}; "
            f"{usb_peer_coverage.incomplete_group_count} incomplete, "
            f"{usb_peer_coverage.dnp_group_count} DNP)"
        )
        status_explanation = {
            "NO_USB_ENDPOINTS": "No supported USB data-pin function groups were recognized in the native netlist.",
            "INCOMPLETE": (
                f"{usb_peer_coverage.incomplete_group_count} recognized endpoint group(s) "
                "lacked complete evidence; any supported paths remain listed below."
            ),
            "NO_SUPPORTED_PEER_PATHS": (
                "No direct or single-resistor USB D+/D− connector-to-PHY path matched "
                "the supported topology."
            ),
            "EVALUATED": "At least one supported connector-to-PHY path was checked.",
        }[usb_peer_coverage.status]
        lines.append(f"    Applicability: {status_explanation}")
        if usb_peer_coverage.endpoint_groups:
            lines.append("    Recognized endpoint groups:")
            for endpoint in usb_peer_coverage.endpoint_groups:
                endpoint_role = "PHY" if endpoint.endpoint_role == "phy" else "connector"
                port_group = (
                    f"port {endpoint.port_group}"
                    if endpoint.port_group is not None
                    else "unnumbered port"
                )
                lines.append(
                    f"      {endpoint_role} {endpoint.reference} ({port_group}): "
                    f"{endpoint.disposition}"
                )
        lines.append(
            f"    {usb_peer_coverage.supported_data_path_count} supported peer path(s): "
            f"{usb_peer_coverage.common_reference_path_count} common-reference, "
            f"{usb_peer_coverage.separate_reference_path_count} separate-reference "
            f"({usb_peer_coverage.mapped_separate_reference_path_count} map-covered; "
            f"{usb_peer_coverage.candidate_group_count} review candidate(s))"
        )
        if usb_peer_coverage.usb_data_path_map_sha256 is not None:
            lines.append(
                f"    USB data-path map SHA-256: {usb_peer_coverage.usb_data_path_map_sha256}"
            )
        lines.append(f"    Native netlist SHA-256: {usb_peer_coverage.netlist_sha256}")
    serial_peer_coverage = report.serial_peer_reference_coverage
    if serial_peer_coverage is not None:
        lines.append("UART peer-reference heuristic coverage:")
        lines.append(
            f"  {serial_peer_coverage.rule_id}: {serial_peer_coverage.status} "
            f"(mode: {serial_peer_coverage.mode}; "
            f"{serial_peer_coverage.native_peer_link_count} native-function link(s), "
            f"{serial_peer_coverage.label_peer_link_count} label link(s); "
            f"{serial_peer_coverage.supported_reference_link_count} supported, "
            f"{serial_peer_coverage.incomplete_reference_link_count} incomplete; "
            f"{serial_peer_coverage.common_reference_link_count} common-reference, "
            f"{serial_peer_coverage.separate_reference_link_count} separate-reference "
            f"({serial_peer_coverage.mapped_separate_reference_link_count} map-covered; "
            f"{serial_peer_coverage.candidate_group_count} review candidate(s))"
        )
        status_explanation = {
            "NO_DIRECT_PEERS": (
                "No direct TX-to-RX links matched the bounded native-function or "
                "numbered-label checks."
            ),
            "INCOMPLETE": (
                f"{serial_peer_coverage.incomplete_reference_link_count} discovered link(s) "
                "lacked complete explicit reference-pin evidence; supported links remain counted."
            ),
            "EVALUATED": (
                "Every discovered direct serial link had complete explicit reference-pin evidence."
            ),
        }[serial_peer_coverage.status]
        lines.append(f"    Applicability: {status_explanation}")
        if serial_peer_coverage.link_entries:
            lines.append("    Discovered serial links:")
            for entry in serial_peer_coverage.link_entries:
                if entry.discovery_basis == "native_function":
                    basis = "native-function"
                    peers = f"{entry.first_reference} -> {entry.second_reference}"
                else:
                    basis = "channel-label"
                    peers = f"{entry.first_reference} / {entry.second_reference}"
                lines.append(
                    f"      {basis}: {peers} ({entry.signal_group}; "
                    f"nets {', '.join(entry.signal_nets)}; "
                    f"pins {', '.join(entry.signal_pins)}): {entry.disposition}"
                )
        lines.append(f"    Authored serial-peer map: {serial_peer_coverage.authored_map_state}")
        if serial_peer_coverage.authored_map_path is not None:
            lines.append(
                f"    Map source: {serial_peer_coverage.authored_map_path} "
                f"(SHA-256 {serial_peer_coverage.authored_map_source_sha256})"
            )
        if serial_peer_coverage.authored_serial_peer_map_sha256 is not None:
            lines.append(
                "    Typed serial-peer map SHA-256: "
                f"{serial_peer_coverage.authored_serial_peer_map_sha256}"
            )
        lines.append(f"    Native netlist SHA-256: {serial_peer_coverage.netlist_sha256}")
    if geometry.source_path is not None:
        lines.append(
            f"  Source: {geometry.source_path} (SHA-256 {geometry.source_sha256 or 'unavailable'})"
        )
        lines.append(
            "  Source tree SHA-256: "
            f"{geometry.source_tree_sha256 or 'unavailable'}; "
            f"{len(geometry.source_bindings)} sheet instance(s) bound"
        )
        for binding in geometry.source_bindings:
            sheet_display = " / ".join(binding.sheet_path) or "root"
            lines.append(
                f"    {sheet_display} [{binding.sheet_instance_path}]: "
                f"{binding.source_path} (SHA-256 {binding.source_sha256})"
            )
    stm32 = report.stm32_pin_map_coverage
    lines.append(
        f"STM32 CubeMX pin-map coverage: {stm32.status} "
        f"(mode: {stm32.mode or 'not configured'}; "
        f"{stm32.mapped_pin_count} mapped, {stm32.excluded_pin_count} excluded, "
        f"{len(stm32.mismatches)} mismatch(es))"
    )
    for source_path, source_sha256 in sorted(stm32.ioc_source_hashes.items()):
        lines.append(f"  CubeMX IOC: {source_path} (SHA-256 {source_sha256})")
    for device in stm32.unmapped_devices:
        lines.append(f"  Unmapped STM32 candidate: {device.reference} ({device.observed_part})")
    if stm32.issue is not None:
        lines.append(f"  Issue: {stm32.issue}")
    decoupling = report.pcb_decoupling
    lines.append(
        f"PCB decoupling coverage: {decoupling.status} (mode: {decoupling.mode or 'not configured'})"
    )
    if decoupling.board_path is not None:
        lines.append(
            f"  Board: {decoupling.board_path} (SHA-256 {decoupling.board_sha256 or 'unavailable'})"
        )
    if decoupling.snapshot_path is not None:
        lines.append(
            f"  Native geometry: {decoupling.snapshot_path} (SHA-256 {decoupling.snapshot_sha256 or 'unavailable'})"
        )
    for entry in decoupling.entries:
        lines.append(
            f"  {entry.id}: {entry.status}; IC supply {entry.ic_supply_pad}; "
            f"selected capacitors {', '.join(entry.selected_capacitors) or 'none'}"
        )
        for candidate in entry.candidates:
            distance = (
                "unavailable"
                if candidate.distance_nm is None
                else f"{candidate.distance_nm // 1000}.{candidate.distance_nm % 1000:03d} um"
            )
            lines.append(
                f"    {candidate.reference}: {distance}; "
                f"eligible={'yes' if candidate.eligible else 'no'}"
            )
    if decoupling.issue is not None:
        lines.append(f"  Issue: {decoupling.issue}")
    protection_path = report.pcb_protection_path
    lines.append(
        f"PCB protection-path coverage: {protection_path.status} "
        f"(mode: {protection_path.mode or 'not configured'})"
    )
    if protection_path.board_path is not None:
        lines.append(
            f"  Board: {protection_path.board_path} "
            f"(SHA-256 {protection_path.board_sha256 or 'unavailable'})"
        )
    if protection_path.snapshot_path is not None:
        lines.append(
            f"  Native geometry: {protection_path.snapshot_path} "
            f"(SHA-256 {protection_path.snapshot_sha256 or 'unavailable'})"
        )
    for entry in protection_path.entries:
        distance = (
            "unavailable"
            if entry.connector_to_protection_distance_nm is None
            else f"{entry.connector_to_protection_distance_nm} nm"
        )
        via_measurement = (
            "not configured"
            if entry.reference_vias_within_radius is None
            else f"{entry.reference_vias_within_radius} within {entry.reference_via_radius_um} um"
        )
        lines.append(
            f"  {entry.id}: {entry.status}; {entry.connector_signal_pad} to "
            f"{entry.protection_signal_pad} {distance}; reference pad "
            f"{entry.protection_reference_pad}, connected vias "
            f"{entry.connected_reference_via_count}, radius count {via_measurement}"
        )
        for issue in entry.issues:
            lines.append(f"    Coverage issue: {issue}")
    if protection_path.issue is not None:
        lines.append(f"  Issue: {protection_path.issue}")
    track_width = report.pcb_track_width
    lines.append(
        f"PCB track-width coverage: {track_width.status} "
        f"(mode: {track_width.mode or 'not configured'})"
    )
    if track_width.board_path is not None:
        lines.append(
            f"  Board: {track_width.board_path} "
            f"(SHA-256 {track_width.board_sha256 or 'unavailable'})"
        )
    if track_width.snapshot_path is not None:
        lines.append(
            f"  Native geometry: {track_width.snapshot_path} "
            f"(SHA-256 {track_width.snapshot_sha256 or 'unavailable'})"
        )
    for entry in track_width.entries:
        lines.append(
            f"  {entry.id}: {entry.status}; net {entry.net}; minimum {entry.minimum_width_um} um"
        )
        for item in entry.tracks:
            width = f"{item.width_nm // 1000}.{item.width_nm % 1000:03d} um"
            state = "below minimum" if item.below_minimum else "meets minimum"
            lines.append(
                f"    {item.track_uuid} {item.layer}: {width}; {state}; "
                f"start {item.start_nm[0]},{item.start_nm[1]} nm; "
                f"end {item.end_nm[0]},{item.end_nm[1]} nm"
            )
        for issue in entry.issues:
            lines.append(f"    Coverage issue: {issue}")
    if track_width.issue is not None:
        lines.append(f"  Issue: {track_width.issue}")
    reference_plane = report.pcb_reference_plane
    lines.append(
        f"PCB reference-plane coverage: {reference_plane.status} "
        f"(mode: {reference_plane.mode or 'not configured'})"
    )
    if reference_plane.board_path is not None:
        lines.append(
            f"  Board: {reference_plane.board_path} "
            f"(SHA-256 {reference_plane.board_sha256 or 'unavailable'})"
        )
    if reference_plane.snapshot_path is not None:
        lines.append(
            f"  Native geometry: {reference_plane.snapshot_path} "
            f"(SHA-256 {reference_plane.snapshot_sha256 or 'unavailable'})"
        )
    for entry in reference_plane.entries:
        lines.append(
            f"  {entry.id}: {entry.status}; {entry.signal_net} on "
            f"{', '.join(entry.signal_layers)}; reference {entry.reference_net}; "
            f"minimum centerline coverage {entry.minimum_referenced_fraction}; "
            f"minimum track length {entry.minimum_track_length_um} um; "
            "short-track review "
            f"{'enabled' if entry.review_excluded_short_tracks else 'disabled'}"
        )
        for item in entry.tracks:
            fraction = f"{item.covered_fraction_numerator}/{item.covered_fraction_denominator}"
            state = "below minimum" if item.below_minimum else "meets minimum"
            lines.append(
                f"    {item.track_uuid}: {item.signal_layer} over {item.reference_layer}; "
                f"centerline coverage {fraction}; {state}; zones "
                f"{', '.join(item.reference_zone_uuids) or 'none'}"
            )
        if entry.excluded_short_track_uuids:
            lines.append(
                "    Excluded tracks below minimum length: "
                + ", ".join(entry.excluded_short_track_uuids)
            )
        for issue in entry.issues:
            lines.append(f"    Coverage issue: {issue}")
    if reference_plane.issue is not None:
        lines.append(f"  Issue: {reference_plane.issue}")
    switching_loop = report.pcb_switching_loop
    lines.append(
        f"PCB switching-loop coverage: {switching_loop.status} "
        f"(mode: {switching_loop.mode or 'not configured'})"
    )
    if switching_loop.board_path is not None:
        lines.append(
            f"  Board: {switching_loop.board_path} "
            f"(SHA-256 {switching_loop.board_sha256 or 'unavailable'})"
        )
    if switching_loop.snapshot_path is not None:
        lines.append(
            f"  Native geometry: {switching_loop.snapshot_path} "
            f"(SHA-256 {switching_loop.snapshot_sha256 or 'unavailable'})"
        )
    for entry in switching_loop.entries:
        area = _format_polygon_area_mm2(entry.loop_area_twice_nm2)
        limit = (
            "not configured" if entry.maximum_area_um2 is None else f"{entry.maximum_area_um2} um^2"
        )
        lines.append(
            f"  {entry.id}: {entry.status}; pad-center polygon {area}; limit {limit}; "
            f"return plane {entry.return_net} on {entry.return_plane_layer}: "
            f"{entry.return_plane_status}; trace-route coverage {entry.route_status}"
        )
        if entry.return_zone_uuid is not None:
            lines.append(
                f"    Filled zone {entry.return_zone_uuid}, island {entry.return_island_index}"
            )
        for route_edge in entry.route_edges:
            length = "unavailable" if route_edge.length_nm is None else f"{route_edge.length_nm} nm"
            tracks = ", ".join(route_edge.track_uuids) or "none"
            detail = (
                f"    Route edge {route_edge.edge_index} {route_edge.from_pad} to "
                f"{route_edge.to_pad}: {route_edge.kind} {route_edge.status}; "
                f"length {length}; tracks {tracks}"
            )
            if route_edge.plane_zone_uuid is not None:
                contour_area = (
                    "unavailable"
                    if route_edge.plane_island_area_twice_nm2 is None
                    else f"{route_edge.plane_island_area_twice_nm2} nm^2"
                )
                detail += (
                    f"; filled zone {route_edge.plane_zone_uuid}, "
                    f"island {route_edge.plane_island_index}; contour doubled area {contour_area}"
                )
            if route_edge.issue is not None:
                detail += f"; {route_edge.issue}"
            lines.append(detail)
        for issue in entry.issues:
            lines.append(f"    Review: {issue}")
    if switching_loop.issue is not None:
        lines.append(f"  Coverage issue: {switching_loop.issue}")
    pair_rules = report.pcb_differential_pair_rules
    lines.append(
        "PCB differential-pair DRC rule coverage: "
        f"{pair_rules.status} (mode: {pair_rules.mode or 'not configured'})"
    )
    if pair_rules.project_path is not None:
        lines.append(
            f"  Project settings: {pair_rules.project_path} "
            f"(SHA-256 {pair_rules.project_sha256 or 'unavailable'})"
        )
    if pair_rules.rules_path is not None:
        lines.append(
            f"  Native rules: {pair_rules.rules_path} "
            f"(SHA-256 {pair_rules.rules_sha256 or 'absent'})"
        )
    if pair_rules.board_path is not None:
        lines.append(
            f"  Board: {pair_rules.board_path} (SHA-256 {pair_rules.board_sha256 or 'unavailable'})"
        )
    if pair_rules.native_drc_path is not None:
        lines.append(
            f"  Native DRC: {pair_rules.native_drc_path} "
            f"(SHA-256 {pair_rules.native_drc_sha256 or 'unavailable'})"
        )
    if pair_rules.kicad_version is not None:
        lines.append(f"  KiCad version: {pair_rules.kicad_version}")
    for entry in pair_rules.entries:
        lines.append(
            f"  {entry.id}: {entry.status}; {entry.positive_net} / {entry.negative_net}; "
            f"selector {entry.pair_selector}"
        )
        for item in entry.constraints:
            expected = f"min={item.expected_min_nm}, max={item.expected_max_nm} nm"
            observed = f"min={item.observed_min_nm}, max={item.observed_max_nm} nm"
            rules = ", ".join(item.rule_names) or "none"
            lines.append(
                f"    {item.constraint}: {item.status}; expected {expected}; "
                f"observed {observed}; rules {rules}"
            )
            if item.issue is not None:
                lines.append(f"      Issue: {item.issue}")
        for issue in entry.issues:
            lines.append(f"    Coverage issue: {issue}")
    if pair_rules.issue is not None:
        lines.append(f"  Coverage issue: {pair_rules.issue}")
    if geometry.netlist_sha256 is not None:
        lines.append(f"  Native netlist SHA-256: {geometry.netlist_sha256}")
    if geometry.kicad_version is not None:
        lines.append(f"  KiCad version: {geometry.kicad_version}")
    if geometry.schematic_version is not None:
        lines.append(f"  Schematic file version: {geometry.schematic_version}")
    if geometry.finding_count:
        lines.append(f"  Localized candidates: {geometry.finding_count}")
    for unsupported in geometry.unsupported:
        lines.append(f"  Unsupported coverage: {unsupported}")
    if geometry.issue is not None:
        lines.append(f"  Coverage issue: {geometry.issue}")
    address_coverage = report.i2c_address_coverage
    lines.append(f"I2C address-map coverage: {address_coverage.status}")
    if address_coverage.netlist_sha256 is not None:
        lines.append(f"  Native netlist SHA-256: {address_coverage.netlist_sha256}")
    lines.append(f"  Scope: {address_coverage.scope}")
    for entry in address_coverage.entries:
        lines.append(
            f"  {entry.status} responder {entry.reference} on {entry.segment_id}: "
            f"expected {_format_i2c_address(entry.expected_address)}, "
            f"observed {_format_i2c_address(entry.observed_address)}"
        )
        lines.append(
            f"    Symbol: {entry.observed_symbol or 'unknown'} (expected {entry.expected_symbol})"
        )
        lines.append(f"    SDA: {entry.sda_pin} -> {', '.join(entry.sda_nets) or '<unconnected>'}")
        lines.append(f"    SCL: {entry.scl_pin} -> {', '.join(entry.scl_nets) or '<unconnected>'}")
        lines.append(f"    Basis: {entry.basis}")
        for bit in entry.address_bits:
            value = "unknown" if bit.resolved_value is None else str(bit.resolved_value)
            lines.append(
                f"    Address bit {bit.bit}: {bit.pin} ({bit.observed_function or 'unknown'}), "
                f"nets={', '.join(bit.nets) or '<unconnected>'}, value={value}"
            )
        for issue in entry.issues:
            lines.append(f"    Issue: {issue}")
    for issue in address_coverage.issues:
        lines.append(f"  Coverage issue: {issue}")
    if address_coverage.issue is not None:
        lines.append(f"  Coverage issue: {address_coverage.issue}")
    control_bias = report.control_input_bias_coverage
    covered_control_bias = sum(entry.status == "COVERED" for entry in control_bias.entries)
    lines.append(
        "Control-input bias heuristic coverage: "
        f"{control_bias.status} ({covered_control_bias}/"
        f"{len(control_bias.entries)} candidate nets covered)"
    )
    if control_bias.source_path is not None:
        lines.append(
            f"  Electrical contract: {control_bias.source_path} "
            f"(SHA-256 {control_bias.source_sha256})"
        )
    if control_bias.netlist_sha256 is not None:
        lines.append(f"  Native netlist SHA-256: {control_bias.netlist_sha256}")
    for entry in control_bias.entries:
        pins = ", ".join(entry.control_pins)
        lines.append(f"  {entry.status} {entry.net}: {pins}")
        if entry.signal_id is not None:
            lines.append(
                f"    Requirement: {entry.signal_id}; bias={entry.bias_mode}; "
                f"basis={entry.bias_basis}"
            )
            if entry.bias_reason is not None:
                lines.append(f"    Decision: {entry.bias_reason}")
        for issue in entry.issues:
            lines.append(f"    Coverage issue: {issue}")
    if control_bias.issue is not None:
        lines.append(f"  Coverage issue: {control_bias.issue}")
    i2c_pullup_coverage = report.i2c_pullup_heuristic_coverage
    covered_i2c_pullups = sum(entry.status == "COVERED" for entry in i2c_pullup_coverage.entries)
    lines.append(
        "I2C pull-up heuristic coverage: "
        f"{i2c_pullup_coverage.status} ({covered_i2c_pullups}/"
        f"{len(i2c_pullup_coverage.entries)} candidate pairs covered)"
    )
    if i2c_pullup_coverage.source_path is not None:
        lines.append(
            f"  Electrical contract: {i2c_pullup_coverage.source_path} "
            f"(SHA-256 {i2c_pullup_coverage.source_sha256})"
        )
    if i2c_pullup_coverage.netlist_sha256 is not None:
        lines.append(f"  Native netlist SHA-256: {i2c_pullup_coverage.netlist_sha256}")
    for entry in i2c_pullup_coverage.entries:
        lines.append(
            f"  {entry.status} SDA {entry.sda_net} / SCL {entry.scl_net}; "
            f"missing heuristic paths: {', '.join(entry.missing_lines)}"
        )
        if entry.bus_id is not None:
            lines.append(f"    Requirement: {entry.bus_id}; checks: {', '.join(entry.check_ids)}")
        for issue in entry.issues:
            lines.append(f"    Coverage issue: {issue}")
    if i2c_pullup_coverage.issue is not None:
        lines.append(f"  Coverage issue: {i2c_pullup_coverage.issue}")
    protection_coverage = report.external_protection_coverage
    lines.append(f"External-protection coverage: {protection_coverage.status}")
    if protection_coverage.netlist_sha256 is not None:
        lines.append(f"  Native netlist SHA-256: {protection_coverage.netlist_sha256}")
    if protection_coverage.electrical_contract_path is not None:
        lines.append(
            "  Existing electrical contract: "
            f"{protection_coverage.electrical_contract_path} "
            f"({protection_coverage.electrical_contract_sha256 or 'unavailable'})"
        )
    lines.append(f"  Scope: {protection_coverage.scope}")
    for entry in protection_coverage.entries:
        signal = f" ({entry.interface_signal})" if entry.interface_signal is not None else ""
        net = f" -> {entry.signal_net}" if entry.signal_net is not None else ""
        lines.append(f"  {entry.status} {entry.connector_pin}{signal}{net}")
        if entry.basis is not None:
            lines.append(f"    Basis: {entry.basis}")
        if entry.device_references:
            lines.append(f"    Devices: {', '.join(entry.device_references)}")
        for issue in entry.issues:
            lines.append(f"    Issue: {issue}")
    if protection_coverage.issue is not None:
        lines.append(f"  Coverage issue: {protection_coverage.issue}")
    crystal_coverage = report.crystal_network_coverage
    lines.append(f"Crystal load-network coverage: {crystal_coverage.status}")
    if crystal_coverage.netlist_sha256 is not None:
        lines.append(f"  Native netlist SHA-256: {crystal_coverage.netlist_sha256}")
    lines.append(f"  Scope: {crystal_coverage.scope}")
    for entry in crystal_coverage.entries:
        lines.append(
            f"  {entry.status} oscillator {entry.oscillator_reference}, "
            f"resonator {entry.resonator_reference}, "
            f"load caps {', '.join(entry.load_capacitor_references)}"
        )
        for pin, nets in sorted(entry.node_nets.items()):
            lines.append(f"    {pin}: {', '.join(nets) or '<unconnected>'}")
        for reference, pin_nets in sorted(entry.extra_capacitor_pin_nets.items()):
            lines.append(f"    Potential extra capacitor {reference}: {', '.join(pin_nets)}")
        for reference, value in sorted(entry.capacitance_pf.items()):
            lines.append(f"    {reference}: {value:g} pF nominal")
        lines.append(f"    Formula: {entry.formula}")
        if (
            entry.calculated_minimum_load_pf is not None
            and entry.calculated_maximum_load_pf is not None
        ):
            lines.append(
                "    Calculated nominal load: "
                f"{entry.calculated_minimum_load_pf:g}–"
                f"{entry.calculated_maximum_load_pf:g} pF; target "
                f"{entry.target_minimum_load_pf:g}–{entry.target_maximum_load_pf:g} pF"
            )
        stray_range = (
            f"{entry.minimum_stray_capacitance_pf:g}–{entry.maximum_stray_capacitance_pf:g} pF"
        )
        lines.append(f"    Stray capacitance assumption: {stray_range}")
        lines.append(f"    Basis: {entry.basis}")
        for issue in entry.issues:
            lines.append(f"    Issue: {issue}")
    if crystal_coverage.issue is not None:
        lines.append(f"  Coverage issue: {crystal_coverage.issue}")
    feedback_coverage = report.regulator_feedback_coverage
    lines.append(f"Regulator feedback coverage: {feedback_coverage.status}")
    if feedback_coverage.netlist_sha256 is not None:
        lines.append(f"  Native netlist SHA-256: {feedback_coverage.netlist_sha256}")
    lines.append(f"  Scope: {feedback_coverage.scope}")
    for entry in feedback_coverage.entries:
        lines.append(
            f"  {entry.status} regulator {entry.regulator_reference} "
            f"(profile {entry.id}), output {entry.output_net}, reference {entry.reference_net}"
        )
        lines.append(f"    Feedback net: {entry.feedback_net or '<unresolved>'}")
        for pin, nets in sorted(entry.pin_nets.items()):
            lines.append(f"    {pin}: {', '.join(nets) or '<unconnected>'}")
        for reference, value in sorted(entry.nominal_resistance_ohms.items()):
            lines.append(f"    {reference}: {value:g} Ω nominal")
        lines.append(f"    Formula: {entry.formula}")
        if (
            entry.calculated_output_minimum_v is not None
            and entry.calculated_output_maximum_v is not None
        ):
            lines.append(
                "    Calculated nominal output: "
                f"{entry.calculated_output_minimum_v:g}–"
                f"{entry.calculated_output_maximum_v:g} V; target "
                f"{entry.target_output_minimum_v:g}–{entry.target_output_maximum_v:g} V"
            )
        lines.append(
            "    Feedback-reference range: "
            f"{entry.feedback_reference_minimum_v:g}–"
            f"{entry.feedback_reference_maximum_v:g} V"
        )
        lines.append(f"    Basis: {entry.basis}")
        for issue in entry.issues:
            lines.append(f"    Issue: {issue}")
    if feedback_coverage.issue is not None:
        lines.append(f"  Coverage issue: {feedback_coverage.issue}")
    filter_coverage = report.rc_filter_coverage
    lines.append(f"RC filter coverage: {filter_coverage.status}")
    if filter_coverage.netlist_sha256 is not None:
        lines.append(f"  Native netlist SHA-256: {filter_coverage.netlist_sha256}")
    lines.append(f"  Scope: {filter_coverage.scope}")
    for entry in filter_coverage.entries:
        lines.append(
            f"  {entry.status} filter {entry.id}: {entry.resistor_reference} + "
            f"{entry.capacitor_reference}, {entry.input_net} -> {entry.filtered_net} "
            f"referenced to {entry.reference_net}"
        )
        for pin, nets in sorted(entry.pin_nets.items()):
            lines.append(f"    {pin}: {', '.join(nets) or '<unconnected>'}")
        if entry.resistance_ohms is not None:
            lines.append(f"    {entry.resistor_reference}: {entry.resistance_ohms:g} Ω nominal")
        if entry.capacitance_pf is not None:
            lines.append(f"    {entry.capacitor_reference}: {entry.capacitance_pf:g} pF nominal")
        lines.append(f"    Formula: {entry.formula}")
        if entry.calculated_corner_hz is not None:
            lines.append(
                f"    Calculated nominal corner: {entry.calculated_corner_hz:g} Hz; "
                f"target {entry.target_minimum_corner_hz:g}–"
                f"{entry.target_maximum_corner_hz:g} Hz"
            )
        if entry.unlisted_parallel_components:
            lines.append(
                "    Unlisted parallel components: " + ", ".join(entry.unlisted_parallel_components)
            )
        lines.append(f"    Basis: {entry.basis}")
        for issue in entry.issues:
            lines.append(f"    Issue: {issue}")
    if filter_coverage.issue is not None:
        lines.append(f"  Coverage issue: {filter_coverage.issue}")
    distribution = report.connector_return_distribution
    lines.append(f"Connector return-distribution coverage: {distribution.status}")
    if distribution.netlist_sha256 is not None:
        lines.append(f"  Native netlist SHA-256: {distribution.netlist_sha256}")
    if distribution.interface_catalog_sha256 is not None:
        lines.append(f"  Interface catalog SHA-256: {distribution.interface_catalog_sha256}")
    lines.append(f"  Scope: {distribution.scope}")
    for entry in distribution.entries:
        lines.append(
            f"  {entry.status} profile {entry.id}: connector "
            f"{entry.connector_reference or '<unbound>'}, interface {entry.interface_id}"
        )
        lines.append(
            f"    Signal contacts: {entry.signal_pin_count}; return contacts: "
            f"{entry.return_pin_count}; required returns at threshold: "
            f"{entry.required_return_pin_count}"
        )
        ratio = (
            "undefined (no return contacts)"
            if entry.signal_to_return_ratio is None
            else f"{entry.signal_to_return_ratio:g} signals per return"
        )
        lines.append(
            f"    Ratio: {ratio}; scope minimum: {entry.minimum_signal_pin_count} signals; "
            f"maximum: {entry.maximum_signal_to_return_ratio:g}"
        )
        for role, pin_map in (
            ("signal", entry.signal_pin_map),
            ("return", entry.return_pin_map),
            ("supply", entry.supply_pin_map),
            ("shield", entry.shield_pin_map),
            ("other", entry.other_pin_map),
            ("unclassified", entry.unclassified_pin_map),
        ):
            if pin_map:
                pins = ", ".join(f"{number}->{pin}" for number, pin in sorted(pin_map.items()))
                lines.append(f"    {role.title()} pins: {pins}")
        lines.append(f"    Basis: {entry.basis}")
        for issue in entry.issues:
            lines.append(f"    Issue: {issue}")
    if distribution.issue is not None:
        lines.append(f"  Coverage issue: {distribution.issue}")
    for override in report.rule_overrides:
        lines.append(f"Rule {override.rule_id}: {override.mode} ({override.reason})")
    if report.connector_coverage is not None:
        coverage = report.connector_coverage
        lines.append(f"Connector coverage: {coverage.status}")
        lines.append(f"  Scope: {coverage.scope}")
        if coverage.inventory_review_basis is not None:
            lines.append(f"  Inventory review basis: {coverage.inventory_review_basis}")
        if coverage.interface_catalog_path is not None:
            lines.append(
                "  Interface catalog: "
                f"{coverage.interface_catalog_path} "
                f"({coverage.interface_catalog_sha256 or 'unavailable'})"
            )
        for identifier in coverage.unbound_interface_ids:
            lines.append(f"  Unbound interface: {identifier}")
        for issue in coverage.catalog_issues:
            lines.append(f"  Catalog issue: {issue}")
        for entry in coverage.entries:
            lines.append(f"  {entry.status} connector {entry.reference}")
            if entry.interface_id is not None:
                lines.append(f"    Interface: {entry.interface_id}")
            if entry.basis:
                lines.append(f"    Basis: {entry.basis}")
            if entry.peer_assignment_group is not None:
                lines.append(f"    Peer-assignment group: {entry.peer_assignment_group}")
                lines.append(f"    Peer-assignment basis: {entry.peer_assignment_basis}")
            for pin in entry.mapped_pins:
                function = pin.symbol_function or "<unnamed>"
                nets = ", ".join(pin.nets) or "<unconnected>"
                lines.append(
                    f"    Interface pin {pin.interface_pin_number} ({pin.interface_signal}) "
                    f"maps to {pin.component_pin}: role={pin.role or '<unclassified>'}; "
                    f"symbol={function}; nets={nets}"
                )
            for pin, reason in entry.unlisted_pin_reasons.items():
                lines.append(f"    Reviewed unlisted pin {pin}: {reason}")
            for pin in entry.interface_pins_unmapped:
                lines.append(f"    Unmapped interface pin: {pin}")
            for pin in entry.interface_pins_unknown:
                lines.append(f"    Unknown interface pin: {pin}")
            for pin in entry.component_pins_unaccounted:
                lines.append(f"    Unreviewed component pin: {pin}")
            for pin in entry.component_pins_unknown:
                lines.append(f"    Unknown component pin: {pin}")
            for issue in entry.issues:
                lines.append(f"    Issue: {issue}")
    peer_coverage = report.connector_peer_pin_coverage
    if peer_coverage is not None:
        lines.append(f"Connector peer-pin heuristic coverage: {peer_coverage.status}")
        lines.append(f"  Native netlist SHA-256: {peer_coverage.netlist_sha256}")
        lines.append(
            f"  Connector candidates: {peer_coverage.connector_candidate_count}; fitted: "
            f"{peer_coverage.fitted_connector_count}; exact-symbol peer groups: "
            f"{peer_coverage.exact_symbol_peer_group_count}"
        )
        lines.append(
            f"  Exact-symbol pin groups: {peer_coverage.exact_symbol_pin_group_count}; "
            f"unknown functions: "
            f"{peer_coverage.exact_symbol_pin_groups_with_unknown_function_count}; "
            f"common assignments: {peer_coverage.exact_symbol_pin_groups_with_common_assignment_count}; "
            f"different assignments: "
            f"{peer_coverage.exact_symbol_pin_groups_with_different_assignments_count}; "
            f"all unassigned: {peer_coverage.exact_symbol_pin_groups_all_unassigned_count}; "
            f"with an open assignment: "
            f"{peer_coverage.exact_symbol_pin_groups_with_open_assignment_count}"
        )
        lines.append(
            f"  Repeated function groups: {peer_coverage.repeated_function_group_count}; "
            f"common assignments: "
            f"{peer_coverage.repeated_function_groups_with_common_assignment_count}; "
            f"different assignments: "
            f"{peer_coverage.repeated_function_groups_with_different_assignments_count}; "
            f"all unassigned: {peer_coverage.repeated_function_groups_all_unassigned_count}; "
            f"with an open assignment: "
            f"{peer_coverage.repeated_function_groups_with_open_assignment_count}"
        )
        lines.append(
            "  Review findings: repeated-function "
            f"{peer_coverage.repeated_function_finding_count}; peer outliers "
            f"{peer_coverage.peer_pin_outlier_finding_count}; peer divergences "
            f"{peer_coverage.peer_pin_divergence_finding_count}"
        )
        lines.append(f"  Scope: {peer_coverage.scope}")
        for reference in peer_coverage.incomplete_pin_inventory_references:
            lines.append(f"  Incomplete exact-symbol pin inventory: {reference}")
    for finding in report.findings:
        lines.append(
            f"{finding.disposition} [{finding.rule_id}] {finding.subject} ({finding.fingerprint})"
        )
        lines.append(f"  {finding.message}")
        for name, related in finding.evidence.items():
            lines.append(f"  {name}: {', '.join(related) or '<unconnected>'}")
        if finding.reason:
            lines.append(f"  Reason: {finding.reason}")
    for stale in report.stale_ignores:
        lines.append(f"STALE_IGNORE [{stale.rule_id}] {stale.fingerprint}: {stale.reason}")
    for issue in report.issues:
        lines.append(f"Issue: {issue}")
    for action in report.next_actions:
        lines.append(f"Next: {action}")
    return "\n".join(lines)
