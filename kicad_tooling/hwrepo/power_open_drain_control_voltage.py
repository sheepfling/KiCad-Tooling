"""Review open-collector control lines with voltage-mismatched pull-up rails."""

from __future__ import annotations

from .control_input_inventory import control_input_family
from .design_lint_types import Candidate
from .digital_peer_voltage_analysis import (
    IC_REFERENCE,
    nominal_voltage_from_net_name,
    pin_assignment_index,
    unambiguous_voltage_named_supply,
)
from .digital_peer_voltage_types import VoltageNamedRail
from .netlist_contract_models import NetlistContract
from .resistor_paths import positive_power_nets, visible_resistor_paths
from .return_nets import is_return_like_net_name

RULE_ID = "power.open_drain_control_input_pullup_voltage_review"
_OPEN_COLLECTOR_TYPES = frozenset({"open_collector"})


def open_drain_control_pullup_voltage_candidates(
    observed: NetlistContract,
) -> tuple[Candidate, ...]:
    """Prompt when a visible pull-up label differs from either endpoint supply label.

    This bounded clue check needs a directly shared open-collector signal, a
    recognized reset/enable/boot input, fitted resistor paths resolving to one
    positive voltage-named rail, and complete native pin-type inventories for
    both IC endpoints. It does not infer logic compatibility.
    """
    assignments = pin_assignment_index(observed)
    dnp = {reference.casefold() for reference in observed.dnp_components}
    functions = {pin.casefold(): function for pin, function in observed.pin_functions.items()}
    pin_types = {
        pin.casefold(): value.strip().casefold()
        for pin, value in observed.pin_electrical_types.items()
    }
    targets = {
        net
        for net in positive_power_nets(observed)
        if nominal_voltage_from_net_name(net) is not None
    }
    paths_by_net = {
        net.casefold(): paths for net, paths in visible_resistor_paths(observed, targets).items()
    }
    supplies: dict[str, VoltageNamedRail | None] = {}
    by_net = {
        net: tuple(sorted(set(pins), key=lambda pin: (pin.casefold(), pin)))
        for net, pins in observed.nets.items()
        if nominal_voltage_from_net_name(net) is None and not is_return_like_net_name(net)
    }
    candidates: list[Candidate] = []

    for net, pins in sorted(by_net.items(), key=lambda item: (item[0].casefold(), item[0])):
        paths = paths_by_net.get(net.casefold(), ())
        if not paths:
            continue
        pullup_rails = {path.rail_net for path in paths}
        if len(pullup_rails) != 1:
            continue
        pullup_rail = next(iter(pullup_rails))
        pullup_voltage = nominal_voltage_from_net_name(pullup_rail)
        if pullup_voltage is None:
            continue
        pullup_paths = tuple(path for path in paths if path.rail_net == pullup_rail)

        for driver_pin in pins:
            driver_reference, separator, _number = driver_pin.rpartition(".")
            driver_key = driver_reference.casefold()
            if (
                not separator
                or driver_key in dnp
                or not IC_REFERENCE.fullmatch(driver_reference)
                or driver_key not in assignments.symbols_by_reference_key
                or pin_types.get(driver_pin.casefold()) not in _OPEN_COLLECTOR_TYPES
                or assignments.net_names_by_pin_key.get(driver_pin.casefold()) != frozenset({net})
            ):
                continue
            for input_pin in pins:
                input_reference, input_separator, _input_number = input_pin.rpartition(".")
                input_key = input_reference.casefold()
                input_function = functions.get(input_pin.casefold(), "")
                if (
                    not input_separator
                    or input_key == driver_key
                    or input_key in dnp
                    or not IC_REFERENCE.fullmatch(input_reference)
                    or input_key not in assignments.symbols_by_reference_key
                    or pin_types.get(input_pin.casefold()) != "input"
                    or control_input_family(input_function) is None
                    or assignments.net_names_by_pin_key.get(input_pin.casefold())
                    != frozenset({net})
                ):
                    continue

                if driver_reference not in supplies:
                    supplies[driver_reference] = unambiguous_voltage_named_supply(
                        driver_reference, observed, assignments
                    )
                if input_reference not in supplies:
                    supplies[input_reference] = unambiguous_voltage_named_supply(
                        input_reference, observed, assignments
                    )
                driver_supply = supplies[driver_reference]
                input_supply = supplies[input_reference]
                if driver_supply is None or input_supply is None:
                    continue
                relations = tuple(
                    relation
                    for relation, supply in (
                        ("pullup_higher_than_driver", driver_supply),
                        ("pullup_lower_than_driver", driver_supply),
                        ("pullup_higher_than_receiver", input_supply),
                        ("pullup_lower_than_receiver", input_supply),
                    )
                    if (pullup_voltage > supply.voltage_v and "higher" in relation)
                    or (pullup_voltage < supply.voltage_v and "lower" in relation)
                )
                if not relations:
                    continue

                candidates.append(
                    Candidate(
                        rule_id=RULE_ID,
                        subject=(
                            f"{driver_pin} -> {input_pin} on {net}: open-collector pull-up "
                            "voltage-domain review"
                        ),
                        message=(
                            "A visible fitted resistor path pulls this open-collector control "
                            "signal to a positive voltage-labeled rail that differs from at least "
                            "one endpoint supply label. Review the output pin's absolute maximum, "
                            "the receiver's VIH and absolute maximum, and power sequencing. Net "
                            "labels do not establish actual voltage, device limits, or "
                            "incompatibility; this prompt does not require level translation."
                        ),
                        evidence={
                            "signal_net": (net,),
                            "open_collector_output": (
                                (
                                    f"{driver_pin}: {functions.get(driver_pin.casefold(), '')} "
                                    f"({assignments.symbols_by_reference_key[driver_key]})"
                                ),
                            ),
                            "control_input": (
                                (
                                    f"{input_pin}: {input_function} "
                                    f"({assignments.symbols_by_reference_key[input_key]})"
                                ),
                            ),
                            "pullup_paths": tuple(
                                f"{'+'.join(path.references)} ({path.resistance_ohms:g} Ω): "
                                f"{net} ↔ {path.rail_net}"
                                for path in pullup_paths
                            ),
                            "pullup_rail_label": (f"{pullup_rail}: {pullup_voltage} V",),
                            "driver_supply_label": (
                                f"{driver_supply.net}: {driver_supply.voltage_v} V",
                            ),
                            "receiver_supply_label": (
                                f"{input_supply.net}: {input_supply.voltage_v} V",
                            ),
                            "pullup_label_relations": relations,
                        },
                    )
                )

    return tuple(sorted(candidates, key=lambda item: (item.subject.casefold(), item.subject)))
