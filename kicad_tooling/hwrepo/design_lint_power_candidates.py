"""Translate schematic power-source and component-supply observations."""

from __future__ import annotations

from .capacitor_hold_up_models import CapacitorHoldUpMap
from .component_pin_patterns import (
    component_supply_pins_on_different_nets,
    unconnected_generic_power_input_component_pins,
)
from .component_power_input_domains import same_voltage_power_inputs_on_different_nets
from .component_power_output_candidates import unconnected_power_output_candidates
from .component_role_models import ComponentRoleMap
from .component_roles import resolve_component_role_map
from .component_supply_range_models import ComponentSupplyVoltageRangeMap
from .design_lint_component_unconnected_pin_candidate_evidence import (
    UnconnectedComponentPinCandidate,
)
from .design_lint_power_candidate_evidence import PowerCandidate
from .design_lint_power_capacitor_hold_up import capacitor_hold_up_candidates
from .design_lint_power_decoupling import ic_decoupling_candidates
from .design_lint_power_inputs import PowerCandidateInputs
from .design_lint_power_regulator_passives import regulator_required_passive_candidates
from .design_lint_power_regulator_pin_roles import regulator_pin_role_candidates
from .design_lint_power_regulator_support_net_coverage import (
    regulator_support_pin_net_coverage_candidates,
)
from .design_lint_power_regulator_support_nets import regulator_support_pin_net_candidates
from .design_lint_power_regulator_support_roles import regulator_support_pin_role_candidates
from .design_lint_power_supply_range import component_supply_voltage_range_candidates
from .design_lint_power_supply_range_coverage import (
    component_supply_range_pin_coverage_candidates,
)
from .design_lint_power_supply_range_map_coverage import (
    component_supply_range_map_coverage_candidates,
)
from .design_lint_types import Candidate
from .ic_decoupling_models import IcDecouplingMap
from .net_dc_reference import connector_capacitor_only_nets
from .netlist_contract_models import NetlistContract
from .power_decoupling import ic_power_rails_without_fitted_capacitors
from .power_enable_controls import enable_control_tied_to_return_candidates
from .power_negative_rail import positive_supply_pins_on_negative_rails
from .power_open_drain_control_voltage import open_drain_control_pullup_voltage_candidates
from .power_path_models import PowerPathMap
from .power_pin_net_roles import named_power_pin_net_role_conflicts
from .power_pin_paths import power_inputs_without_supported_source_paths
from .power_rails import numbered_power_rail_groups
from .regulator_support_models import RegulatorSupportPinNetMap, RegulatorSupportPinRoleMap


def power_candidates(
    observed: NetlistContract,
    *,
    component_role_map: ComponentRoleMap | None = None,
    power_path_map: PowerPathMap | None = None,
    reviewed_connector_references: tuple[str, ...] = (),
    peer_unconnected_power_output_pins: frozenset[str] = frozenset(),
    ic_decoupling_map: IcDecouplingMap | None = None,
    capacitor_hold_up_map: CapacitorHoldUpMap | None = None,
    component_supply_voltage_range_map: ComponentSupplyVoltageRangeMap | None = None,
    regulator_support_pin_role_map: RegulatorSupportPinRoleMap | None = None,
    regulator_support_pin_net_map: RegulatorSupportPinNetMap | None = None,
) -> tuple[Candidate, ...]:
    """Compatibility adapter for the named power candidate input group."""
    return scan_power_candidates(
        observed,
        PowerCandidateInputs(
            component_role_map=component_role_map,
            power_path_map=power_path_map,
            power_sequence_map=None,
            oscillator_output_path_map=None,
            ic_decoupling_map=ic_decoupling_map,
            capacitor_hold_up_map=capacitor_hold_up_map,
            component_supply_voltage_range_map=component_supply_voltage_range_map,
            regulator_support_pin_role_map=regulator_support_pin_role_map,
            regulator_support_pin_net_map=regulator_support_pin_net_map,
        ),
        reviewed_connector_references=reviewed_connector_references,
        peer_unconnected_power_output_pins=peer_unconnected_power_output_pins,
    )


def scan_power_candidates(
    observed: NetlistContract,
    inputs: PowerCandidateInputs,
    *,
    reviewed_connector_references: tuple[str, ...] = (),
    peer_unconnected_power_output_pins: frozenset[str] = frozenset(),
) -> tuple[Candidate, ...]:
    """Build power findings from the prepared power requirements as one group."""
    found: list[Candidate] = []
    component_role_map = inputs.component_role_map
    power_path_map = inputs.power_path_map
    ic_decoupling_map = inputs.ic_decoupling_map
    found.extend(
        regulator_required_passive_candidates(observed, inputs.regulator_passive_topology_map)
    )
    found.extend(regulator_pin_role_candidates(observed, inputs.regulator_passive_topology_map))
    found.extend(
        regulator_support_pin_role_candidates(observed, inputs.regulator_support_pin_role_map)
    )
    found.extend(
        regulator_support_pin_net_candidates(observed, inputs.regulator_support_pin_net_map)
    )
    found.extend(
        regulator_support_pin_net_coverage_candidates(
            observed,
            inputs.regulator_support_pin_role_map,
            inputs.regulator_support_pin_net_map,
        )
    )
    found.extend(capacitor_hold_up_candidates(observed, inputs.capacitor_hold_up_map))
    found.extend(
        component_supply_voltage_range_candidates(
            observed,
            inputs.component_supply_voltage_range_map,
        )
    )
    found.extend(
        component_supply_range_pin_coverage_candidates(
            observed,
            inputs.component_supply_voltage_range_map,
        )
    )
    found.extend(
        component_supply_range_map_coverage_candidates(
            observed,
            inputs.component_supply_voltage_range_map,
        )
    )
    found.extend(
        named_power_pin_net_role_conflicts(
            observed,
            reviewed_connector_references=reviewed_connector_references,
        )
    )
    for split in same_voltage_power_inputs_on_different_nets(observed):
        found.append(
            PowerCandidate.from_source_evidence(
                split,
                subject=(
                    f"{split.reference} ({split.symbol}): distinct supply inputs on "
                    f"separate {split.nominal_voltage} V-labeled nets"
                ),
                message=(
                    "Distinct native power-input functions on this fitted IC are assigned "
                    "to separate net labels with the same explicit nominal-voltage clue. "
                    "Review whether the split is intentional, such as filtering or a separate "
                    "supply domain. The labels do not establish actual voltage or require the "
                    "nets to be joined."
                ),
            )
        )
    found.extend(ic_decoupling_candidates(observed, ic_decoupling_map))
    found.extend(positive_supply_pins_on_negative_rails(observed))
    found.extend(enable_control_tied_to_return_candidates(observed))
    found.extend(open_drain_control_pullup_voltage_candidates(observed))
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
            PowerCandidate.from_source_evidence(
                gap,
                subject=f"{gap.net}: IC supply decoupling review",
                message=(
                    "This recognized positive rail has IC power-input pins but no fitted "
                    "capacitor connected to a distinct return-like schematic net. Review the "
                    "device datasheets and intended placement; net presence alone does not "
                    "establish local placement, value, or a physical return path."
                ),
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
        else:
            source_path_message = (
                "A fitted power-input pin shares a net with a fitted capacitor to a return, "
                "but no recognized positive-rail net or fitted power_out pin was found to "
                "establish a source anchor. Review custom rail names, external connector "
                "supplies, or an intentionally isolated domain; a project-authored power-path "
                "map can record the required relationship."
            )
        found.append(
            PowerCandidate.from_source_evidence(
                gap,
                subject=f"{gap.net}: power-input source-path review",
                message=(
                    source_path_message
                    + " This heuristic recognizes only native-inventoried two-pin "
                    "low-resistance resistors, inductors, ferrite beads, fuses, and polyfuses; "
                    "it does not prove that a connection is required or that a path conducts."
                ),
            )
        )

    for net in connector_capacitor_only_nets(observed, reviewed_connector_references):
        found.append(
            PowerCandidate.from_source_evidence(
                net,
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
            )
        )

    for group in component_supply_pins_on_different_nets(observed, reviewed_connector_references):
        found.append(
            PowerCandidate.from_source_evidence(
                group,
                subject=f"{group.reference} ({group.symbol}): {group.function} supply pins",
                message=(
                    "Pins on this component with a matching supply function use different or "
                    "ambiguous nets. Review the component pinout for an intended split, filter, "
                    "or missing connection."
                ),
            )
        )

    for pin in unconnected_generic_power_input_component_pins(
        observed, reviewed_connector_references
    ):
        found.append(
            UnconnectedComponentPinCandidate.from_source_evidence(
                pin,
                subject=f"{pin.pin}: generic native power-input pin is unassigned",
                message=(
                    "KiCad's native symbol metadata classifies this generic component pin as "
                    "power_in, but the exported netlist assigns it to no net. Review whether the "
                    "pin is intentionally open or a power/reference connection is missing. The "
                    "electrical type does not identify the pin's specific role or require it to "
                    "be connected."
                ),
            )
        )

    found.extend(
        unconnected_power_output_candidates(
            observed,
            declared_connector_references=reviewed_connector_references,
            peer_unconnected_pins=peer_unconnected_power_output_pins,
        )
    )

    for group in numbered_power_rail_groups(observed):
        found.append(
            PowerCandidate.from_source_evidence(
                group,
                subject=group.stem,
                message=(
                    "Separately numbered positive supply nets may be intended as one rail. "
                    "Review whether they are common, intentionally isolated, or represent "
                    "independent supplies; similar names do not establish a required connection."
                ),
            )
        )

    return tuple(found)
