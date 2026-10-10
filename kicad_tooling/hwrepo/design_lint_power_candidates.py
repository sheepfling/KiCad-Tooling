"""Translate schematic power-source and component-supply observations."""

from __future__ import annotations

from .component_pin_patterns import (
    component_supply_pins_on_different_nets,
    unconnected_generic_power_input_component_pins,
)
from .component_roles import resolve_component_role_map
from .design_lint_types import Candidate
from .models import ComponentRoleMap, NetlistContract, PowerPathMap
from .net_dc_reference import connector_capacitor_only_nets
from .power_decoupling import ic_power_rails_without_fitted_capacitors
from .power_pin_paths import power_inputs_without_supported_source_paths


def power_candidates(
    observed: NetlistContract,
    *,
    component_role_map: ComponentRoleMap | None = None,
    power_path_map: PowerPathMap | None = None,
    reviewed_connector_references: tuple[str, ...] = (),
) -> tuple[Candidate, ...]:
    """Build review prompts for rails, fitted supplies, and visible source paths."""
    found: list[Candidate] = []
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
    return tuple(found)
