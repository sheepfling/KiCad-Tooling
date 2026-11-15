"""Bounded I2C signal endpoints on explicitly identified connectors."""

from __future__ import annotations

from .casefold_mapping_lookup import casefolded_unique_index
from .connector_identity import connector_candidate_references
from .connector_pin_metadata import connector_pin_metadata_matches_inventory
from .i2c_addressing import i2c_signal_role
from .i2c_signal_endpoints import I2cSignalEndpoint
from .netlist_contract_models import NetlistContract
from .netlist_pin_assignments import netlist_pin_net_index


def i2c_connector_signal_endpoints(
    observed: NetlistContract,
) -> tuple[I2cSignalEndpoint, ...]:
    """Return complete connector SDA/SCL pairs with unique native assignments.

    Connector identity and the exact SDA/SCL functions are bounded clues, not
    an approved pinout. Incomplete inventory/metadata, duplicate roles, open or
    ambiguous assignments, and DNP connectors are omitted.
    """
    fitted = casefolded_unique_index(observed.components)
    connectors = casefolded_unique_index(
        {
            reference: reference
            for reference in connector_candidate_references(observed)
            if reference.casefold() in fitted
        }
    )
    if not connectors:
        return ()

    dnp = {reference.casefold() for reference in observed.dnp_components}
    inventories = casefolded_unique_index(observed.component_pin_numbers)
    functions = casefolded_unique_index(observed.pin_functions)
    electrical_types = casefolded_unique_index(observed.pin_electrical_types)
    nets_by_pin = netlist_pin_net_index(observed)
    roles_by_reference: dict[str, dict[str, list[tuple[str, tuple[str, ...]]]]] = {}

    for pin, function in observed.pin_functions.items():
        reference, separator, number = pin.rpartition(".")
        reference_key = reference.casefold()
        role = i2c_signal_role(function)
        if (
            not separator
            or reference_key not in connectors
            or pin.casefold() not in functions
            or role is None
        ):
            continue
        assignments = tuple(
            sorted(nets_by_pin.get(pin.casefold(), ()), key=lambda item: (item.casefold(), item))
        )
        roles_by_reference.setdefault(reference_key, {}).setdefault(role, []).append(
            (f"{connectors[reference_key]}.{number}", assignments)
        )

    endpoints: list[I2cSignalEndpoint] = []
    for reference_key, reference in sorted(connectors.items()):
        if reference_key in dnp:
            continue
        inventory = inventories.get(reference_key, ())
        folded_inventory = tuple(number.casefold() for number in inventory)
        if (
            not inventory
            or len(set(folded_inventory)) != len(folded_inventory)
            or not connector_pin_metadata_matches_inventory(
                reference,
                inventory,
                functions,
                electrical_types,
            )
        ):
            continue

        roles = roles_by_reference.get(reference_key, {})
        sda_pins = roles.get("SDA", ())
        scl_pins = roles.get("SCL", ())
        if len(sda_pins) != 1 or len(scl_pins) != 1:
            continue
        sda_pin, sda_assignments = sda_pins[0]
        scl_pin, scl_assignments = scl_pins[0]
        if len(sda_assignments) != 1 or len(scl_assignments) != 1:
            continue
        endpoints.append(
            I2cSignalEndpoint(
                reference=reference,
                sda_pin=sda_pin,
                scl_pin=scl_pin,
                sda_net=sda_assignments[0],
                scl_net=scl_assignments[0],
                sda_type=electrical_types.get(sda_pin.casefold(), "unknown").strip().casefold(),
                scl_type=electrical_types.get(scl_pin.casefold(), "unknown").strip().casefold(),
            )
        )

    return tuple(sorted(endpoints, key=lambda item: (item.reference.casefold(), item.reference)))
