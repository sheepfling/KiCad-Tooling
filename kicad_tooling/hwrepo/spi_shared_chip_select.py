"""Review fitted SPI device inputs that share one chip-select net."""

from __future__ import annotations

from .design_lint_types import Candidate
from .models import NetlistContract
from .spi_participants import is_spi_chip_select_function, is_spi_ic_reference

RULE_ID = "bus.spi_chip_select_inputs_share_net"


def spi_chip_select_inputs_share_net_candidates(
    observed: NetlistContract,
) -> tuple[Candidate, ...]:
    """Find multiple fitted IC chip-select inputs assigned to one exact net.

    Only native input-typed pins with bounded SPI chip-select functions count.
    Driver pins are retained only to suppress groups that already contain two
    native output pins, which ERC can classify independently.
    """
    fitted = {reference.casefold(): reference for reference in observed.components}
    dnp = {reference.casefold() for reference in observed.dnp_components}
    assignments_by_pin: dict[str, set[str]] = {}
    for net, pins in observed.nets.items():
        for pin in pins:
            assignments_by_pin.setdefault(pin.casefold(), set()).add(net)
    pin_types = {
        pin.casefold(): value.strip().casefold()
        for pin, value in observed.pin_electrical_types.items()
    }

    inputs_by_net: dict[str, list[tuple[str, str, str]]] = {}
    outputs_by_net: dict[str, set[str]] = {}
    display_names: dict[str, set[str]] = {}
    for pin, function in observed.pin_functions.items():
        reference, separator, _number = pin.rpartition(".")
        reference_key = reference.casefold()
        canonical_reference = fitted.get(reference_key)
        if (
            not separator
            or canonical_reference is None
            or reference_key in dnp
            or not is_spi_ic_reference(canonical_reference)
            or not is_spi_chip_select_function(function)
            or _number not in observed.component_pin_numbers.get(canonical_reference, ())
        ):
            continue
        assigned_nets = assignments_by_pin.get(pin.casefold(), set())
        if len(assigned_nets) != 1:
            continue
        net = next(iter(assigned_nets))
        if not net.strip():
            continue
        key = net.casefold()
        display_names.setdefault(key, set()).add(net)
        electrical_type = pin_types.get(pin.casefold())
        if electrical_type == "input":
            inputs_by_net.setdefault(key, []).append((canonical_reference, pin, function))
        elif electrical_type == "output":
            outputs_by_net.setdefault(key, set()).add(pin.casefold())

    findings: list[Candidate] = []
    for key, endpoints in sorted(inputs_by_net.items()):
        if len(display_names.get(key, ())) != 1 or len(outputs_by_net.get(key, ())) >= 2:
            continue
        ordered = sorted(set(endpoints), key=lambda item: tuple(part.casefold() for part in item))
        by_reference: dict[str, list[tuple[str, str, str]]] = {}
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
        findings.append(
            Candidate(
                rule_id=RULE_ID,
                subject=f"{', '.join(references)}: SPI chip-select inputs share {net}",
                message=(
                    f"Fitted IC chip-select input pins {', '.join(pins)} share one schematic net "
                    f"({net}). Review whether selecting these devices together is intentional. "
                    "Shared chip-select wiring can be deliberate; native function names do not "
                    "prove polarity, device role, or required bus topology."
                ),
                evidence={
                    "components": references,
                    "functions": functions,
                    "pins": pins,
                    "pin_types": tuple("input" for _ in pins),
                    "net": (net,),
                },
            )
        )
    return tuple(findings)
