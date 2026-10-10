"""Project-authored RS-485 endpoint, termination, and bias requirements."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, model_validator

from .model_primitives import (
    ElectricalPositive,
    Identifier,
    NetName,
    NonEmptyText,
    Reference,
    ResistorReference,
    StrictModel,
)


class Rs485EndpointPinRequirement(StrictModel):
    """One reviewed differential-line, control, or reference pin assignment."""

    role: Literal[
        "bus_line_1",
        "bus_line_2",
        "driver_input",
        "receiver_output",
        "driver_enable",
        "receiver_enable",
        "reference",
    ]
    pin: Reference
    net: NetName
    pair_id: Identifier | None = None

    @model_validator(mode="after")
    def line_roles_name_pair(self) -> Rs485EndpointPinRequirement:
        if "." not in self.pin:
            raise ValueError("RS-485 pin mappings must use COMPONENT.PIN form")
        if self.role in {"bus_line_1", "bus_line_2"} and self.pair_id is None:
            raise ValueError("RS-485 differential line pins must name a pair_id")
        if self.role not in {"bus_line_1", "bus_line_2"} and self.pair_id is not None:
            raise ValueError("Only RS-485 differential line pins can name a pair_id")
        return self


class Rs485EndpointRequirement(StrictModel):
    """Exact local symbol identity and pin roles for one bus participant."""

    id: Identifier
    kind: Literal["transceiver", "connector", "other"]
    reference: Identifier
    symbol: NonEmptyText
    footprint: NonEmptyText
    pins: Annotated[tuple[Rs485EndpointPinRequirement, ...], Field(min_length=2)]

    @model_validator(mode="after")
    def endpoint_pin_roles(self) -> Rs485EndpointRequirement:
        if any(
            requirement.pin.rsplit(".", 1)[0].casefold() != self.reference.casefold()
            for requirement in self.pins
        ):
            raise ValueError("RS-485 endpoint pins must belong to the declared component")
        pin_names = [item.pin.casefold() for item in self.pins]
        if len(set(pin_names)) != len(pin_names):
            raise ValueError("RS-485 endpoint pin assignments must be unique")
        role_keys = [
            (item.role, item.pair_id, item.pin.casefold() if item.role == "reference" else None)
            for item in self.pins
        ]
        if len(set(role_keys)) != len(role_keys):
            raise ValueError("RS-485 endpoint pin roles must be unique")
        pair_roles: dict[str, set[str]] = {}
        for item in self.pins:
            if item.pair_id is not None:
                pair_roles.setdefault(item.pair_id, set()).add(item.role)
        if any(roles != {"bus_line_1", "bus_line_2"} for roles in pair_roles.values()):
            raise ValueError("Each RS-485 endpoint pair needs one pin for each bus line")
        if self.kind == "transceiver":
            roles = {item.role for item in self.pins}
            if not {"driver_input", "receiver_output"} <= roles:
                raise ValueError(
                    "RS-485 transceivers need mapped driver_input and receiver_output pins"
                )
            if not pair_roles:
                raise ValueError("RS-485 transceivers need at least one mapped differential pair")
        return self


class Rs485TerminationResistorRequirement(StrictModel):
    reference: ResistorReference
    symbol: NonEmptyText
    footprint: NonEmptyText
    first_net: NetName
    second_net: NetName
    minimum_ohms: ElectricalPositive
    maximum_ohms: ElectricalPositive

    @model_validator(mode="after")
    def valid_path_and_range(self) -> Rs485TerminationResistorRequirement:
        if self.first_net == self.second_net:
            raise ValueError("An RS-485 termination resistor must connect distinct nets")
        if self.maximum_ohms < self.minimum_ohms:
            raise ValueError("RS-485 termination maximum resistance is below its minimum")
        return self


class Rs485DnpResistorRequirement(StrictModel):
    reference: ResistorReference
    symbol: NonEmptyText
    footprint: NonEmptyText
    first_net: NetName
    second_net: NetName

    @model_validator(mode="after")
    def distinct_option_nets(self) -> Rs485DnpResistorRequirement:
        if self.first_net == self.second_net:
            raise ValueError("An RS-485 DNP resistor option must connect distinct nets")
        return self


class Rs485TerminationEndpointRequirement(StrictModel):
    id: Identifier
    basis: NonEmptyText
    topology: Literal["direct", "split", "external", "not_required"]
    resistors: tuple[Rs485TerminationResistorRequirement, ...] = ()
    midpoint_net: NetName | None = None
    expected_dnp_resistors: tuple[Rs485DnpResistorRequirement, ...] = ()

    @model_validator(mode="after")
    def topology_has_matching_paths(self) -> Rs485TerminationEndpointRequirement:
        refs = [item.reference.casefold() for item in self.resistors]
        dnp_refs = [item.reference.casefold() for item in self.expected_dnp_resistors]
        if len(set(refs)) != len(refs) or len(set(dnp_refs)) != len(dnp_refs):
            raise ValueError("RS-485 termination resistor references must be unique")
        if set(refs) & set(dnp_refs):
            raise ValueError("An RS-485 resistor cannot be both fitted and DNP")
        if self.topology == "direct":
            if len(self.resistors) != 1 or self.midpoint_net is not None:
                raise ValueError("Direct RS-485 termination needs one resistor and no midpoint")
            if self.expected_dnp_resistors:
                raise ValueError("A fitted direct termination cannot require DNP resistors")
        elif self.topology == "split":
            if len(self.resistors) != 2 or self.midpoint_net is None:
                raise ValueError("Split RS-485 termination needs two resistors and a midpoint")
            if self.expected_dnp_resistors:
                raise ValueError("A fitted split termination cannot require DNP resistors")
        elif self.resistors or self.midpoint_net is not None:
            raise ValueError(
                "External or not-required termination cannot claim fitted resistor paths"
            )
        return self


class Rs485BiasResistorRequirement(StrictModel):
    reference: ResistorReference
    symbol: NonEmptyText
    footprint: NonEmptyText
    bus_net: NetName
    rail_net: NetName
    minimum_ohms: ElectricalPositive
    maximum_ohms: ElectricalPositive

    @model_validator(mode="after")
    def valid_bias_path(self) -> Rs485BiasResistorRequirement:
        if self.bus_net == self.rail_net:
            raise ValueError("An RS-485 bias resistor must connect distinct nets")
        if self.maximum_ohms < self.minimum_ohms:
            raise ValueError("RS-485 bias maximum resistance is below its minimum")
        return self


class Rs485LocalBiasRequirement(StrictModel):
    mode: Literal["local"]
    basis: NonEmptyText
    pull_up: Rs485BiasResistorRequirement
    pull_down: Rs485BiasResistorRequirement

    @model_validator(mode="after")
    def distinct_bias_components(self) -> Rs485LocalBiasRequirement:
        if self.pull_up.reference.casefold() == self.pull_down.reference.casefold():
            raise ValueError("RS-485 pull-up and pull-down must be separate components")
        if self.pull_up.bus_net == self.pull_down.bus_net:
            raise ValueError("RS-485 bias resistors must apply to different bus lines")
        if self.pull_up.rail_net == self.pull_down.rail_net:
            raise ValueError("RS-485 pull-up rail and pull-down reference must be distinct")
        return self


class Rs485RemoteBiasRequirement(StrictModel):
    mode: Literal["remote"]
    basis: NonEmptyText
    reason: NonEmptyText


class Rs485InternalFailSafeRequirement(StrictModel):
    mode: Literal["internal_failsafe"]
    basis: NonEmptyText
    transceiver_references: Annotated[tuple[Identifier, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def unique_transceivers(self) -> Rs485InternalFailSafeRequirement:
        if len({reference.casefold() for reference in self.transceiver_references}) != len(
            self.transceiver_references
        ):
            raise ValueError("RS-485 internal-failsafe transceivers must be unique")
        return self


class Rs485NoBiasRequirement(StrictModel):
    mode: Literal["not_required"]
    basis: NonEmptyText
    reason: NonEmptyText


Rs485BiasRequirement = Annotated[
    Rs485LocalBiasRequirement
    | Rs485RemoteBiasRequirement
    | Rs485InternalFailSafeRequirement
    | Rs485NoBiasRequirement,
    Field(discriminator="mode"),
]


class Rs485SignalPairRequirement(StrictModel):
    id: Identifier
    basis: NonEmptyText
    purpose: Literal["bidirectional", "board_to_peer", "peer_to_board"]
    line_1_net: NetName
    line_2_net: NetName
    terminations: Annotated[tuple[Rs485TerminationEndpointRequirement, ...], Field(min_length=1)]
    bias: Rs485BiasRequirement

    @model_validator(mode="after")
    def distinct_pair_nets_and_topology_ids(self) -> Rs485SignalPairRequirement:
        if self.line_1_net == self.line_2_net:
            raise ValueError("RS-485 differential pair line nets must be distinct")
        if len({item.id.casefold() for item in self.terminations}) != len(self.terminations):
            raise ValueError("RS-485 termination endpoint IDs must be unique within a pair")
        return self


class Rs485BusRequirement(StrictModel):
    id: Identifier
    basis: NonEmptyText
    topology: Literal["two_wire_half_duplex", "four_wire_full_duplex"]
    pairs: Annotated[tuple[Rs485SignalPairRequirement, ...], Field(min_length=1)]
    endpoints: Annotated[tuple[Rs485EndpointRequirement, ...], Field(min_length=1)]
    external_peers: tuple[NonEmptyText, ...] = ()

    @model_validator(mode="after")
    def topology_and_endpoint_maps(self) -> Rs485BusRequirement:
        if self.topology == "two_wire_half_duplex":
            if len(self.pairs) != 1 or self.pairs[0].purpose != "bidirectional":
                raise ValueError("Two-wire RS-485 needs one bidirectional differential pair")
        elif len(self.pairs) != 2 or {item.purpose for item in self.pairs} != {
            "board_to_peer",
            "peer_to_board",
        }:
            raise ValueError("Four-wire RS-485 needs board-to-peer and peer-to-board pairs")
        pair_by_id = {item.id: item for item in self.pairs}
        if len(pair_by_id) != len(self.pairs):
            raise ValueError("RS-485 pair IDs must be unique within a bus")
        nets = [net for pair in self.pairs for net in (pair.line_1_net, pair.line_2_net)]
        if len(set(nets)) != len(nets):
            raise ValueError("RS-485 bus pair nets must be distinct")
        if len({item.id.casefold() for item in self.endpoints}) != len(self.endpoints):
            raise ValueError("RS-485 endpoint IDs must be unique within a bus")
        pin_assignments: list[str] = []
        transceiver_references = {
            item.reference.casefold() for item in self.endpoints if item.kind == "transceiver"
        }
        covered_pairs: set[str] = set()
        for endpoint in self.endpoints:
            for pin in endpoint.pins:
                pin_assignments.append(pin.pin.casefold())
                if pin.pair_id is None:
                    continue
                pair = pair_by_id.get(pin.pair_id)
                if pair is None:
                    raise ValueError(f"RS-485 endpoint references unknown pair {pin.pair_id}")
                expected_net = pair.line_1_net if pin.role == "bus_line_1" else pair.line_2_net
                if pin.net != expected_net:
                    raise ValueError("RS-485 endpoint line pins must use their declared pair nets")
                if endpoint.kind == "transceiver":
                    covered_pairs.add(pair.id)
        if len(set(pin_assignments)) != len(pin_assignments):
            raise ValueError("An RS-485 endpoint pin cannot be assigned more than once")
        if covered_pairs != set(pair_by_id):
            raise ValueError("Every RS-485 signal pair needs mapped local transceiver pins")
        termination_refs: list[str] = []
        bias_refs: list[str] = []
        for pair in self.pairs:
            line_nets = {pair.line_1_net, pair.line_2_net}
            for endpoint in pair.terminations:
                termination_refs.extend(
                    item.reference.casefold()
                    for item in (*endpoint.resistors, *endpoint.expected_dnp_resistors)
                )
                paths = tuple(
                    frozenset((item.first_net, item.second_net)) for item in endpoint.resistors
                )
                if endpoint.topology == "direct" and paths != (frozenset(line_nets),):
                    raise ValueError("Direct RS-485 termination must bridge the declared pair")
                if endpoint.topology == "split":
                    midpoint = endpoint.midpoint_net
                    assert midpoint is not None
                    if midpoint in line_nets:
                        raise ValueError("RS-485 termination midpoint must differ from pair nets")
                    if set(paths) != {
                        frozenset((pair.line_1_net, midpoint)),
                        frozenset((pair.line_2_net, midpoint)),
                    }:
                        raise ValueError(
                            "Split RS-485 termination must connect each pair line to one midpoint"
                        )
                for option in endpoint.expected_dnp_resistors:
                    if {option.first_net, option.second_net} != line_nets:
                        raise ValueError("Expected DNP termination options must bridge the pair")
            if isinstance(pair.bias, Rs485LocalBiasRequirement):
                up, down = pair.bias.pull_up, pair.bias.pull_down
                if {up.bus_net, down.bus_net} != line_nets:
                    raise ValueError(
                        "Local RS-485 bias must declare one resistor on each pair line"
                    )
                if up.rail_net in line_nets or down.rail_net in line_nets:
                    raise ValueError("RS-485 bias supply/reference nets must differ from pair nets")
                bias_refs.extend((up.reference.casefold(), down.reference.casefold()))
            elif isinstance(pair.bias, Rs485InternalFailSafeRequirement):
                if {item.casefold() for item in pair.bias.transceiver_references} != (
                    transceiver_references
                ):
                    raise ValueError(
                        "Internal-failsafe declaration must name every local RS-485 transceiver"
                    )
        all_resistor_refs = [*termination_refs, *bias_refs]
        if len(set(all_resistor_refs)) != len(all_resistor_refs):
            raise ValueError("An RS-485 resistor cannot be reused across termination or bias roles")
        endpoint_refs = {item.reference.casefold() for item in self.endpoints}
        if endpoint_refs & set(all_resistor_refs):
            raise ValueError("RS-485 endpoint and resistor components must be distinct")
        return self


class Rs485Analysis(StrictModel):
    """Project-authored termination, bias, and endpoint maps for RS-485."""

    mode: Literal["required"] = "required"
    basis: NonEmptyText
    buses: Annotated[tuple[Rs485BusRequirement, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def unique_bus_ids_and_resistors(self) -> Rs485Analysis:
        if len({bus.id.casefold() for bus in self.buses}) != len(self.buses):
            raise ValueError("RS-485 bus IDs must be unique")
        pair_nets = [
            net
            for bus in self.buses
            for pair in bus.pairs
            for net in (pair.line_1_net, pair.line_2_net)
        ]
        if len(set(pair_nets)) != len(pair_nets):
            raise ValueError("RS-485 pair nets cannot be reused across buses")
        resistor_references = [
            item.reference.casefold()
            for bus in self.buses
            for pair in bus.pairs
            for termination in pair.terminations
            for item in (*termination.resistors, *termination.expected_dnp_resistors)
        ]
        resistor_references.extend(
            resistor.reference.casefold()
            for bus in self.buses
            for pair in bus.pairs
            if isinstance(pair.bias, Rs485LocalBiasRequirement)
            for resistor in (pair.bias.pull_up, pair.bias.pull_down)
        )
        if len(set(resistor_references)) != len(resistor_references):
            raise ValueError("RS-485 resistor references cannot be reused across buses")
        return self
