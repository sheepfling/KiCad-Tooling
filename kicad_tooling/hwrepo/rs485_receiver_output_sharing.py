"""Review fitted RS-485 receiver outputs that share one schematic net."""

from __future__ import annotations

from .casefold_mapping_lookup import lookup_unique_casefold
from .component_references import is_integrated_circuit_reference
from .design_lint_types import Candidate
from .netlist_contract_models import NetlistContract
from .netlist_pin_assignments import netlist_pin_net_index
from .return_nets import is_return_like_net_name
from .rs485_data_functions import explicit_rs485_transceiver_identity, rs485_data_pin_role

RULE_ID = "bus.rs485_receiver_outputs_share_net"
_SUPPORTED_OUTPUT_TYPES = frozenset({"output", "tri_state", "bidirectional", "passive"})


def rs485_receiver_output_sharing_candidates(
    observed: NetlistContract,
) -> tuple[Candidate, ...]:
    """Find unambiguous fitted RS-485 RO pins from multiple ICs on one net.

    The prompt is review-only by default. A switched, multiplexed, or otherwise
    intentionally shared receiver path can be valid; native functions and pin
    assignments do not establish bus intent or actual output enable behavior.
    Nets already classified as return-like and direct output-to-output cases
    are left to their more specific review or ERC diagnostics.
    """
    fitted = {reference.casefold(): reference for reference in observed.components}
    dnp = {reference.casefold() for reference in observed.dnp_components}
    nets_by_pin = netlist_pin_net_index(observed)
    pin_types = {
        pin.casefold(): value.strip().casefold()
        for pin, value in observed.pin_electrical_types.items()
    }

    receiver_pins: dict[str, list[tuple[str, str, str]]] = {}
    for pin, function in observed.pin_functions.items():
        reference, separator, number = pin.rpartition(".")
        if not separator or not reference or not number:
            continue
        if rs485_data_pin_role(function) != "rx":
            continue
        receiver_pins.setdefault(reference.casefold(), []).append((pin, number, function))

    by_net: dict[str, list[tuple[str, str, str, str]]] = {}
    display_names: dict[str, set[str]] = {}
    unsupported_nets: set[str] = set()
    for folded_reference, role_pins in sorted(receiver_pins.items()):
        reference = fitted.get(folded_reference)
        if (
            reference is None
            or folded_reference in dnp
            or not is_integrated_circuit_reference(reference)
        ):
            continue
        identity = explicit_rs485_transceiver_identity(observed, reference)
        if identity is None:
            continue

        assignments_for_role = {
            net
            for pin, _number, _function in role_pins
            for net in nets_by_pin.get(pin.casefold(), ())
        }
        if len(role_pins) != 1:
            unsupported_nets.update(net.casefold() for net in assignments_for_role)
            continue

        pin, number, function = role_pins[0]
        inventory = lookup_unique_casefold(observed.component_pin_numbers, reference)
        if (
            inventory is None
            or len({item.casefold() for item in inventory}) != len(inventory)
            or number.casefold() not in {item.casefold() for item in inventory}
        ):
            unsupported_nets.update(net.casefold() for net in nets_by_pin.get(pin.casefold(), ()))
            continue

        assigned_nets = nets_by_pin.get(pin.casefold(), set())
        pin_type = pin_types.get(pin.casefold())
        if len(assigned_nets) != 1 or pin_type not in _SUPPORTED_OUTPUT_TYPES:
            unsupported_nets.update(net.casefold() for net in assigned_nets)
            continue
        net = next(iter(assigned_nets))
        if not net.strip() or is_return_like_net_name(net):
            continue
        key = net.casefold()
        by_net.setdefault(key, []).append((reference, pin, function, pin_type))
        display_names.setdefault(key, set()).add(net)

    findings: list[Candidate] = []
    for key, endpoints in sorted(by_net.items()):
        ordered = sorted(set(endpoints), key=lambda item: tuple(part.casefold() for part in item))
        by_reference: dict[str, list[tuple[str, str, str, str]]] = {}
        for endpoint in ordered:
            by_reference.setdefault(endpoint[0].casefold(), []).append(endpoint)
        if (
            key in unsupported_nets
            or len(display_names.get(key, ())) != 1
            or len(by_reference) < 2
            or any(len(items) != 1 for items in by_reference.values())
            or sum(item[3] == "output" for item in ordered) >= 2
        ):
            continue

        net = next(iter(display_names[key]))
        references = tuple(
            sorted((items[0][0] for items in by_reference.values()), key=str.casefold)
        )
        pins = tuple(sorted((item[1] for item in ordered), key=str.casefold))
        functions = tuple(sorted((item[2] for item in ordered), key=str.casefold))
        pin_types_for_net = tuple(sorted((item[3] for item in ordered), key=str.casefold))
        identity_basis = tuple(
            sorted(
                {
                    explicit_rs485_transceiver_identity(observed, reference) or ""
                    for reference in references
                },
                key=str.casefold,
            )
        )
        findings.append(
            Candidate(
                rule_id=RULE_ID,
                subject=f"{', '.join(references)}: RS-485 receiver-output pins share {net}",
                message=(
                    f"Fitted RS-485 receiver-output pins {', '.join(pins)} share one schematic "
                    f"net ({net}) with native pin types {', '.join(pin_types_for_net)}. Review "
                    "whether this shared path is intentional. A switched or multiplexed path "
                    "may be valid; pin-function names do not establish output-enable behavior, "
                    "required bus topology, PCB copper, or physical continuity."
                ),
                evidence={
                    "components": references,
                    "functions": functions,
                    "pins": pins,
                    "pin_types": pin_types_for_net,
                    "net": (net,),
                    "identity_basis": identity_basis,
                },
            )
        )
    return tuple(findings)
