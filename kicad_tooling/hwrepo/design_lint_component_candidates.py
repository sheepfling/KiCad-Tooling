"""Translate discrete-component and two-pin topology observations."""

from __future__ import annotations

from .component_diode_rail_orientation import diodes_with_anode_below_cathode_on_named_rails
from .component_mosfet_terminal_order import mosfets_with_unusual_drain_source_rail_order
from .component_pin_patterns import UnconnectedNamedComponentPin, unconnected_named_component_pins
from .component_polarized_capacitor_orientation import polarized_capacitors_on_reversed_named_rails
from .component_return_pins import unconnected_component_return_pins
from .component_role_models import ComponentRoleMap
from .component_roles import component_role_binding_evidence
from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate
from .led_heuristics import (
    leds_directly_between_positive_and_return_nets,
    leds_directly_driven_without_visible_series_resistor,
)
from .models import NetlistContract
from .mosfet_gate_connectivity import (
    mosfet_gates_without_peer,
    mosfet_gates_without_visible_source_bias,
)
from .oscillator_output_path_candidates import oscillator_output_path_candidates
from .oscillator_output_path_models import OscillatorOutputPathMap
from .power_path_models import PowerPathMap
from .two_pin_components import two_pin_components_on_same_net


def _unconnected_named_pin_candidate(
    pin: UnconnectedNamedComponentPin,
    *,
    rule_id: DesignLintRuleId,
    description: str,
) -> Candidate:
    return Candidate(
        rule_id=rule_id,
        subject=f"{pin.pin}: {pin.function}",
        message=(
            f"This component's named {description} pin has no net assignment. "
            "Review whether the pin is intentionally unused or a connection is missing."
        ),
        evidence={pin.pin: ()},
    )


def component_candidates(
    observed: NetlistContract,
    *,
    component_role_map: ComponentRoleMap | None = None,
    power_path_map: PowerPathMap | None = None,
    oscillator_output_path_map: OscillatorOutputPathMap | None = None,
    reviewed_connector_references: tuple[str, ...] = (),
) -> tuple[Candidate, ...]:
    """Build review prompts for component polarity, role, and same-net patterns."""
    found: list[Candidate] = []
    found.extend(mosfet_gates_without_peer(observed))
    found.extend(mosfet_gates_without_visible_source_bias(observed))
    found.extend(mosfets_with_unusual_drain_source_rail_order(observed))
    found.extend(polarized_capacitors_on_reversed_named_rails(observed))
    found.extend(diodes_with_anode_below_cathode_on_named_rails(observed))
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

    for led in leds_directly_driven_without_visible_series_resistor(
        observed, component_role_map, power_path_map
    ):
        role_evidence = (
            {} if led.role_binding is None else component_role_binding_evidence(led.role_binding)
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

    for component in two_pin_components_on_same_net(observed, component_role_map):
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
        elif component.kind == "switch":
            rule_id = "component.two_pin_switch_same_net"
            message = (
                "Both pins of this supported fitted two-pin SPST switch are assigned to the same "
                "schematic net, so the switch cannot separate those nets in this netlist. Review "
                "whether the bypass is intentional. This finding does not establish that the "
                "topology is wrong."
            )
            kind_evidence = {"component_kind": (component.kind,)}
        else:
            rule_id = "component.two_pin_passive_same_net"
            message = (
                "Both pins of this supported fitted two-pin passive are assigned to the "
                "same schematic net, so the part is bypassed by that net assignment. "
                "Review the intended topology and whether the same-net assignment is "
                "deliberate. This finding does not establish that the topology is wrong."
            )
            kind_evidence = {"passive_kind": (component.kind,)}
        role_evidence = (
            {}
            if component.role_binding is None
            else component_role_binding_evidence(component.role_binding)
        )
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
                    **role_evidence,
                },
            )
        )

    named_component_pins = unconnected_named_component_pins(observed, reviewed_connector_references)
    for pin in named_component_pins:
        if pin.category == "supply":
            found.append(
                _unconnected_named_pin_candidate(
                    pin,
                    rule_id="component.unconnected_supply_pin",
                    description="supply",
                )
            )
    for pin in unconnected_component_return_pins(observed, reviewed_connector_references):
        found.append(
            _unconnected_named_pin_candidate(
                pin,
                rule_id="component.unconnected_return_pin",
                description="return",
            )
        )
    found.extend(oscillator_output_path_candidates(observed, oscillator_output_path_map))
    return tuple(found)
