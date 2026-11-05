"""Review direct GPIO drives into control pins across voltage-named rails."""

from __future__ import annotations

import re

from .control_input_inventory import control_input_family
from .design_lint_types import Candidate
from .digital_peer_voltage_analysis import (
    IC_REFERENCE,
    endpoint_matches_native,
    nominal_voltage_from_net_name,
    pin_assignment_index,
    unambiguous_voltage_named_supply,
)
from .digital_peer_voltage_models import DigitalPeerVoltageAnalysis
from .digital_peer_voltage_types import DigitalPeerPinAssignmentIndex, VoltageNamedRail
from .netlist_contract_models import NetlistContract
from .return_nets import is_return_like_net_name

RULE_ID = "power.gpio_to_control_input_voltage_review"
_GPIO_OUTPUT_FUNCTION = re.compile(r"^(?:(?:GPIO|IO)\d*|P[A-Z]\d+)$", re.IGNORECASE)


def _is_gpio_output_function(function: str) -> bool:
    return _GPIO_OUTPUT_FUNCTION.fullmatch(function.strip()) is not None


def _is_exactly_mapped(
    output_reference: str,
    output_pin: str,
    input_reference: str,
    input_pin: str,
    net: str,
    observed: NetlistContract,
    analysis: DigitalPeerVoltageAnalysis | None,
    assignments: DigitalPeerPinAssignmentIndex,
) -> bool:
    if analysis is None:
        return False
    return any(
        link.output_limits is not None
        and link.input_limits is not None
        and link.driver.reference.casefold() == output_reference.casefold()
        and link.driver.pin.casefold() == output_pin.casefold()
        and link.driver.net == net
        and link.receiver.reference.casefold() == input_reference.casefold()
        and link.receiver.pin.casefold() == input_pin.casefold()
        and link.receiver.net == net
        and endpoint_matches_native(link.driver, observed, assignments)
        and endpoint_matches_native(link.receiver, observed, assignments)
        for link in analysis.links
    )


def gpio_to_control_input_voltage_candidates(
    observed: NetlistContract,
    analysis: DigitalPeerVoltageAnalysis | None = None,
) -> tuple[Candidate, ...]:
    """Flag direct GPIO-to-control links with a higher explicitly named source rail."""
    assignments = pin_assignment_index(observed)
    dnp = {reference.casefold() for reference in observed.dnp_components}
    functions = {pin.casefold(): function for pin, function in observed.pin_functions.items()}
    electrical_types = {
        pin.casefold(): value.strip().casefold()
        for pin, value in observed.pin_electrical_types.items()
    }
    rails: dict[str, VoltageNamedRail | None] = {}
    by_net: dict[str, tuple[str, ...]] = {
        net: tuple(sorted(pins, key=lambda pin: (pin.casefold(), pin)))
        for net, pins in observed.nets.items()
        if not is_return_like_net_name(net) and nominal_voltage_from_net_name(net) is None
    }
    candidates: list[Candidate] = []

    for net, pins in sorted(by_net.items(), key=lambda item: (item[0].casefold(), item[0])):
        for output_pin in pins:
            output_reference, separator, _number = output_pin.rpartition(".")
            output_key = output_reference.casefold()
            output_function = functions.get(output_pin.casefold(), "")
            if (
                not separator
                or output_key in dnp
                or not IC_REFERENCE.fullmatch(output_reference)
                or output_key not in assignments.symbols_by_reference_key
                or electrical_types.get(output_pin.casefold()) != "output"
                or not _is_gpio_output_function(output_function)
                or assignments.net_names_by_pin_key.get(output_pin.casefold()) != frozenset({net})
            ):
                continue
            for input_pin in pins:
                input_reference, input_separator, _input_number = input_pin.rpartition(".")
                input_key = input_reference.casefold()
                input_function = functions.get(input_pin.casefold(), "")
                if (
                    not input_separator
                    or input_key == output_key
                    or input_key in dnp
                    or not IC_REFERENCE.fullmatch(input_reference)
                    or input_key not in assignments.symbols_by_reference_key
                    or electrical_types.get(input_pin.casefold()) != "input"
                    or control_input_family(input_function) is None
                    or assignments.net_names_by_pin_key.get(input_pin.casefold())
                    != frozenset({net})
                ):
                    continue

                if output_reference not in rails:
                    rails[output_reference] = unambiguous_voltage_named_supply(
                        output_reference, observed, assignments
                    )
                if input_reference not in rails:
                    rails[input_reference] = unambiguous_voltage_named_supply(
                        input_reference, observed, assignments
                    )
                output_rail = rails[output_reference]
                input_rail = rails[input_reference]
                if (
                    output_rail is None
                    or input_rail is None
                    or output_rail.voltage_v <= input_rail.voltage_v
                    or _is_exactly_mapped(
                        output_reference,
                        output_pin,
                        input_reference,
                        input_pin,
                        net,
                        observed,
                        analysis,
                        assignments,
                    )
                ):
                    continue

                candidates.append(
                    Candidate(
                        rule_id=RULE_ID,
                        subject=(
                            f"{output_pin} -> {input_pin}: GPIO-to-control voltage-domain review"
                        ),
                        message=(
                            "A direct GPIO output is assigned to a named reset, enable, or boot "
                            "control input, and the output component's explicit supply label has "
                            "a higher parsed nominal value than the input component's supply "
                            "label. Review the exact device limits and circuit conditions. Rail "
                            "names do not establish actual voltage, output range, input tolerance, "
                            "or incompatibility; this prompt does not require level translation. "
                            "A complete exact digital-peer voltage map is evaluated separately."
                        ),
                        evidence={
                            "signal_net": (net,),
                            "GPIO_output": (
                                (
                                    f"{output_pin}: {output_function} ("
                                    f"{assignments.symbols_by_reference_key[output_key]})"
                                ),
                            ),
                            "control_input": (
                                (
                                    f"{input_pin}: {input_function} ("
                                    f"{assignments.symbols_by_reference_key[input_key]})"
                                ),
                            ),
                            "output_supply_label": (
                                f"{output_rail.net}: {output_rail.voltage_v} V",
                            ),
                            "input_supply_label": (f"{input_rail.net}: {input_rail.voltage_v} V",),
                        },
                    )
                )

    return tuple(
        sorted(
            candidates,
            key=lambda item: (
                item.subject.casefold(),
                item.subject,
            ),
        )
    )
