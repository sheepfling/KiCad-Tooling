"""Review fitted SPI data-output pins that share one schematic net."""

from __future__ import annotations

from .design_lint_types import Candidate
from .models import NetlistContract
from .return_nets import is_return_like_net_name
from .spi_participants import is_spi_data_output_function, is_spi_ic_reference

RULE_ID = "bus.spi_data_outputs_share_net"
_SUPPORTED_OUTPUT_TYPES = frozenset({"output", "tri_state", "bidirectional", "passive"})


def spi_data_outputs_share_net_candidates(observed: NetlistContract) -> tuple[Candidate, ...]:
    """Find unambiguous fitted SPI data-output groups not resolved by ERC.

    Only exact MISO/SDO/CIPO aliases on fitted IC references are considered.
    Native ``input`` pins are receivers and do not count. If two counted pins
    have native ``output`` type, ERC already has a direct conflict to report.
    """
    fitted = {reference.casefold(): reference for reference in observed.components}
    dnp = {reference.casefold() for reference in observed.dnp_components}
    pin_numbers = {
        reference.casefold(): {number.casefold() for number in numbers}
        for reference, numbers in observed.component_pin_numbers.items()
    }
    nets_by_pin: dict[str, set[str]] = {}
    for net, pins in observed.nets.items():
        for pin in pins:
            nets_by_pin.setdefault(pin.casefold(), set()).add(net)
    pin_types = {
        pin.casefold(): value.strip().casefold()
        for pin, value in observed.pin_electrical_types.items()
    }

    endpoints_by_net: dict[str, list[tuple[str, str, str, str]]] = {}
    unsupported_by_net: set[str] = set()
    output_counts_by_net: dict[str, set[str]] = {}
    display_names: dict[str, set[str]] = {}
    for pin, function in observed.pin_functions.items():
        reference, separator, number = pin.rpartition(".")
        reference_key = reference.casefold()
        canonical_reference = fitted.get(reference_key)
        if (
            not separator
            or canonical_reference is None
            or reference_key in dnp
            or not is_spi_ic_reference(canonical_reference)
            or not is_spi_data_output_function(function)
        ):
            continue
        assigned_nets = nets_by_pin.get(pin.casefold(), set())
        if len(assigned_nets) != 1:
            continue
        net = next(iter(assigned_nets))
        if not net.strip() or is_return_like_net_name(net):
            continue
        key = net.casefold()
        display_names.setdefault(key, set()).add(net)
        if number.casefold() not in pin_numbers.get(reference_key, set()):
            unsupported_by_net.add(key)
            continue
        electrical_type = pin_types.get(pin.casefold())
        if electrical_type == "input":
            continue
        if electrical_type not in _SUPPORTED_OUTPUT_TYPES:
            unsupported_by_net.add(key)
            continue
        endpoints_by_net.setdefault(key, []).append(
            (canonical_reference, pin, function, electrical_type)
        )
        if electrical_type == "output":
            output_counts_by_net.setdefault(key, set()).add(pin.casefold())

    findings: list[Candidate] = []
    for key, endpoints in sorted(endpoints_by_net.items()):
        if (
            key in unsupported_by_net
            or len(display_names.get(key, ())) != 1
            or len(output_counts_by_net.get(key, ())) >= 2
        ):
            continue
        ordered = sorted(set(endpoints), key=lambda item: tuple(part.casefold() for part in item))
        by_reference: dict[str, list[tuple[str, str, str, str]]] = {}
        for endpoint in ordered:
            by_reference.setdefault(endpoint[0].casefold(), []).append(endpoint)
        if len(by_reference) < 2 or any(len(items) != 1 for items in by_reference.values()):
            continue

        net = next(iter(display_names[key]))
        references = tuple(
            sorted((items[0][0] for items in by_reference.values()), key=str.casefold)
        )
        pins = tuple(sorted((item[1] for item in ordered), key=str.casefold))
        functions = tuple(sorted((item[2] for item in ordered), key=str.casefold))
        electrical_types = tuple(sorted((item[3] for item in ordered), key=str.casefold))
        findings.append(
            Candidate(
                rule_id=RULE_ID,
                subject=f"{', '.join(references)}: SPI data-output pins share {net}",
                message=(
                    f"Fitted IC SPI MISO/SDO/CIPO pins {', '.join(pins)} share one schematic net "
                    f"({net}) with native pin types {', '.join(electrical_types)}. Review whether "
                    "the shared data path is intentional. Tri-state and other shared-bus designs "
                    "can be valid; pin-function names do not prove bus membership or driver behavior."
                ),
                evidence={
                    "components": references,
                    "functions": functions,
                    "pins": pins,
                    "pin_types": electrical_types,
                    "net": (net,),
                },
            )
        )
    return tuple(findings)
