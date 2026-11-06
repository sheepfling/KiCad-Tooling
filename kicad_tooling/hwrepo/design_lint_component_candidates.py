"""Translate discrete-component and two-pin topology observations."""

from __future__ import annotations

from dataclasses import dataclass

from .component_bjt_base_bias import bjts_without_visible_emitter_bias
from .component_bjt_base_drive import bjts_with_direct_output_base_drive
from .component_bjt_terminal_order import bjts_with_unusual_collector_emitter_rail_order
from .component_diode_rail_orientation import diodes_with_anode_below_cathode_on_named_rails
from .component_mosfet_gate_drive import mosfets_with_direct_output_gate_drive
from .component_mosfet_terminal_order import mosfets_with_unusual_drain_source_rail_order
from .component_pin_patterns import (
    UnconnectedNamedComponentPin,
    UnconnectedNamedComponentPinCategory,
    unconnected_named_component_pins,
)
from .component_polarized_capacitor_orientation import polarized_capacitors_on_reversed_named_rails
from .component_repeated_signal_pins import (
    component_repeated_signal_pin_unassigned,
    component_signal_pin_net_divergences,
)
from .component_return_pins import unconnected_component_return_pins
from .component_role_models import ComponentRoleMap
from .design_lint_component_bjt_terminals import (
    bjts_with_base_collector_on_same_net,
    bjts_with_base_emitter_on_same_net,
    bjts_with_collector_emitter_on_same_net,
)
from .design_lint_component_mosfet_terminals import (
    mosfets_with_drain_source_on_same_net,
    mosfets_with_gate_drain_on_same_net,
    mosfets_with_gate_source_on_same_net,
)
from .design_lint_component_transformers import (
    transformer_winding_groups_share_net_candidates,
    transformer_winding_same_net_candidates,
)
from .design_lint_component_unconnected_pin_candidate_evidence import (
    UnconnectedComponentPinCandidate,
)
from .design_lint_led_candidate_evidence import LedTopologyCandidate
from .design_lint_led_current_candidates import led_current_range_candidates
from .design_lint_two_pin_candidate_evidence import (
    TwoPinComponentFindingEvidence,
    TwoPinSameNetCandidate,
)
from .design_lint_types import Candidate
from .led_current_models import LedCurrentMap
from .led_heuristics import (
    leds_directly_between_positive_and_return_nets,
    leds_directly_driven_without_visible_series_resistor,
)
from .mosfet_gate_connectivity import (
    mosfet_gates_without_peer,
    mosfet_gates_without_visible_source_bias,
)
from .netlist_contract_models import NetlistContract
from .oscillator_output_path_candidates import oscillator_output_path_candidates
from .oscillator_output_path_models import OscillatorOutputPathMap
from .power_path_models import PowerPathMap
from .two_pin_batteries import two_pin_battery_same_net_candidates
from .two_pin_buzzers import two_pin_buzzer_same_net_candidates
from .two_pin_components import two_pin_components_on_same_net
from .two_pin_leds import two_pin_led_same_net_candidates
from .two_pin_motors import two_pin_motor_same_net_candidates
from .two_pin_solar_cells import two_pin_solar_cell_same_net_candidates
from .two_pin_speakers import two_pin_speaker_same_net_candidates
from .two_pin_thermocouples import two_pin_thermocouple_same_net_candidates


@dataclass(frozen=True, slots=True)
class ComponentTopologyCandidateInputs:
    """Native observation and authored component maps for component checks."""

    observed: NetlistContract
    component_role_map: ComponentRoleMap | None
    power_path_map: PowerPathMap | None
    oscillator_output_path_map: OscillatorOutputPathMap | None
    led_current_map: LedCurrentMap | None
    netlist_sha256: str | None
    reviewed_connector_references: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ComponentCandidateScanResult:
    """Component findings with their oscillator-map finding count."""

    candidates: tuple[Candidate, ...]

    @property
    def oscillator_output_path_finding_count(self) -> int:
        return sum(
            item.rule_id == "oscillator.output_load_path_mismatch" for item in self.candidates
        )


def _unconnected_named_pin_candidate(
    pin: UnconnectedNamedComponentPin,
    *,
    description: UnconnectedNamedComponentPinCategory,
) -> Candidate:
    if pin.category != description:
        raise ValueError("Named component pin description must match its scanner category")
    return UnconnectedComponentPinCandidate.from_source_evidence(
        pin,
        subject=f"{pin.pin}: {pin.function}",
        message=(
            f"This component's named {description} pin has no net assignment. "
            "Review whether the pin is intentionally unused or a connection is missing."
        ),
    )


def component_candidates(
    observed: NetlistContract,
    *,
    component_role_map: ComponentRoleMap | None = None,
    power_path_map: PowerPathMap | None = None,
    oscillator_output_path_map: OscillatorOutputPathMap | None = None,
    led_current_map: LedCurrentMap | None = None,
    netlist_sha256: str | None = None,
    reviewed_connector_references: tuple[str, ...] = (),
) -> tuple[Candidate, ...]:
    """Preserve the keyword-based component candidate interface."""
    return scan_component_candidates(
        ComponentTopologyCandidateInputs(
            observed=observed,
            component_role_map=component_role_map,
            power_path_map=power_path_map,
            oscillator_output_path_map=oscillator_output_path_map,
            led_current_map=led_current_map,
            netlist_sha256=netlist_sha256,
            reviewed_connector_references=reviewed_connector_references,
        )
    ).candidates


def scan_component_candidates(
    inputs: ComponentTopologyCandidateInputs,
) -> ComponentCandidateScanResult:
    """Build component findings from one typed theme request."""
    observed = inputs.observed
    component_role_map = inputs.component_role_map
    power_path_map = inputs.power_path_map
    oscillator_output_path_map = inputs.oscillator_output_path_map
    led_current_map = inputs.led_current_map
    reviewed_connector_references = inputs.reviewed_connector_references
    found: list[Candidate] = []
    found.extend(mosfet_gates_without_peer(observed))
    found.extend(mosfet_gates_without_visible_source_bias(observed))
    found.extend(mosfets_with_direct_output_gate_drive(observed))
    found.extend(mosfets_with_unusual_drain_source_rail_order(observed))
    found.extend(mosfets_with_drain_source_on_same_net(observed))
    found.extend(mosfets_with_gate_source_on_same_net(observed))
    found.extend(mosfets_with_gate_drain_on_same_net(observed))
    found.extend(bjts_with_unusual_collector_emitter_rail_order(observed))
    found.extend(bjts_with_collector_emitter_on_same_net(observed))
    found.extend(bjts_with_base_emitter_on_same_net(observed))
    found.extend(bjts_with_base_collector_on_same_net(observed))
    found.extend(bjts_with_direct_output_base_drive(observed))
    found.extend(bjts_without_visible_emitter_bias(observed))
    found.extend(polarized_capacitors_on_reversed_named_rails(observed))
    found.extend(diodes_with_anode_below_cathode_on_named_rails(observed))
    found.extend(component_signal_pin_net_divergences(observed, reviewed_connector_references))
    found.extend(component_repeated_signal_pin_unassigned(observed, reviewed_connector_references))
    for bridge in leds_directly_between_positive_and_return_nets(observed):
        found.append(
            LedTopologyCandidate.from_source_evidence(
                bridge,
                subject=f"{bridge.reference}: LED directly spans supply and return",
                message=(
                    "Both pins of this supported two-pin LED symbol are assigned directly to a "
                    "recognized positive rail and return net. Review whether a visible series "
                    "limiting element or a current-controlled driver is missing, and verify the "
                    "device polarity and source behavior. Netlist topology alone does not "
                    "establish operating current, off-board limiting, or physical board paths."
                ),
            )
        )

    for led in leds_directly_driven_without_visible_series_resistor(
        observed, component_role_map, power_path_map
    ):
        found.append(
            LedTopologyCandidate.from_source_evidence(
                led,
                subject=f"{led.reference}: LED directly shares an output net and a rail",
                message=(
                    "A native output-capable pin shares one LED terminal net, and the other LED "
                    "terminal is directly assigned to a recognized supply or return. Review "
                    "whether the output or assembly provides intentional current limiting or a "
                    "series element is missing. This prompt does not infer LED polarity, allowed "
                    "current, output limits, or off-board behavior."
                ),
            )
        )

    two_pin_components = two_pin_components_on_same_net(observed, component_role_map)
    found.extend(two_pin_led_same_net_candidates(two_pin_components))
    found.extend(two_pin_buzzer_same_net_candidates(two_pin_components))
    found.extend(two_pin_speaker_same_net_candidates(two_pin_components))
    found.extend(two_pin_battery_same_net_candidates(two_pin_components))
    found.extend(two_pin_motor_same_net_candidates(two_pin_components))
    found.extend(two_pin_solar_cell_same_net_candidates(two_pin_components))
    found.extend(two_pin_thermocouple_same_net_candidates(two_pin_components))
    found.extend(transformer_winding_same_net_candidates(observed))
    found.extend(transformer_winding_groups_share_net_candidates(observed))
    for component in two_pin_components:
        if component.kind in {
            "led",
            "buzzer",
            "speaker",
            "battery",
            "motor",
            "solar_cell",
            "thermocouple",
        }:
            continue
        if component.kind == "diode":
            message = (
                "Both pins of this supported fitted two-pin diode are assigned to the same "
                "schematic net, bypassing the device in that netlist. Review the intended "
                "topology, population state, and footprint pin mapping. This finding does not "
                "establish that the topology is wrong."
            )
        elif component.kind == "crystal":
            message = (
                "Both pins of this supported fitted two-pin crystal are assigned to the same "
                "schematic net, shorting its two terminals in that netlist. Review whether the "
                "crystal is intentionally bypassed or a resonator path is missing. This finding "
                "does not establish that the topology is wrong."
            )
        elif component.kind in {"fuse", "polyfuse"}:
            message = (
                "Both pins of this supported fitted two-pin fuse are assigned to the same "
                "schematic net, bypassing the protection element in that netlist. Review "
                "whether the fuse is intentionally bypassed or a series protection path is "
                "missing. This finding does not establish that the topology is wrong."
            )
        elif component.kind == "ferrite_bead":
            message = (
                "Both pins of this supported fitted two-pin ferrite bead are assigned to the same "
                "schematic net, bypassing the filter element in that netlist. Review whether the "
                "bead is intentionally bypassed or a series filter path is missing. This finding "
                "does not establish that the topology is wrong."
            )
        elif component.kind == "switch":
            message = (
                "Both pins of this supported fitted two-pin SPST switch are assigned to the same "
                "schematic net, so the switch cannot separate those nets in this netlist. Review "
                "whether the bypass is intentional. This finding does not establish that the "
                "topology is wrong."
            )
        else:
            message = (
                "Both pins of this supported fitted two-pin passive are assigned to the "
                "same schematic net, so the part is bypassed by that net assignment. "
                "Review the intended topology and whether the same-net assignment is "
                "deliberate. This finding does not establish that the topology is wrong."
            )
        found.append(
            TwoPinSameNetCandidate.from_source_evidence(
                TwoPinComponentFindingEvidence(component),
                subject=(
                    f"{component.reference} ({component.value} {component.kind}) "
                    "has both pins on one net"
                ),
                message=message,
            )
        )

    named_component_pins = unconnected_named_component_pins(observed, reviewed_connector_references)
    for pin in named_component_pins:
        if pin.category == "supply":
            found.append(
                _unconnected_named_pin_candidate(
                    pin,
                    description="supply",
                )
            )
    for pin in unconnected_component_return_pins(observed, reviewed_connector_references):
        found.append(
            _unconnected_named_pin_candidate(
                pin,
                description="return",
            )
        )
    found.extend(oscillator_output_path_candidates(observed, oscillator_output_path_map))
    found.extend(led_current_range_candidates(observed, led_current_map, inputs.netlist_sha256))
    return ComponentCandidateScanResult(tuple(found))
