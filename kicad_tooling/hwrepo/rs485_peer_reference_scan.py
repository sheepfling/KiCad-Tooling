"""Find mapped RS-485 endpoints sharing one native pair with split references."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from collections.abc import Set as AbstractSet

from .models import NetlistContract
from .rs485_models import (
    Rs485EndpointPinRequirement,
    Rs485EndpointRequirement,
    Rs485SignalPairRequirement,
)
from .rs485_peer_reference_types import (
    Rs485PeerReferenceContext,
    Rs485PeerReferenceEndpoint,
    Rs485PeerReferencePair,
    Rs485PeerReferenceScan,
    Rs485ReferencePinAssignment,
)


def scan_rs485_peer_references(
    context: Rs485PeerReferenceContext,
    observed: NetlistContract,
) -> Rs485PeerReferenceScan:
    """Evaluate only endpoint and reference pins named by the current RS-485 map.

    The map supplies bus and pair membership. Native assignments must match its
    exact line-pin map before an endpoint joins a pair. Reference pins are
    compared as observed; a difference prompts review but never implies that a
    common, bonded, or isolated topology is required.
    """
    analysis = context.analysis
    if analysis is None:
        return Rs485PeerReferenceScan(
            map_state=context.state,
            source_path=context.source_path,
            source_sha256=context.source_sha256,
            analysis_sha256=None,
            recognized_endpoint_count=0,
            pairs=(),
        )

    pin_nets = _pin_nets(observed)
    components = {
        reference.casefold(): component for reference, component in observed.components.items()
    }
    references = {reference.casefold(): reference for reference in observed.components}
    symbols = {
        reference.casefold(): symbol for reference, symbol in observed.component_symbols.items()
    }
    dnp = {reference.casefold() for reference in observed.dnp_components}

    pair_groups: list[Rs485PeerReferencePair] = []
    recognized: set[str] = set()
    for bus in analysis.buses:
        for pair in bus.pairs:
            endpoints: list[Rs485PeerReferenceEndpoint] = []
            for endpoint in bus.endpoints:
                mapped = _mapped_pair_pins(endpoint, pair)
                if mapped is None:
                    continue
                reference_key = endpoint.reference.casefold()
                if reference_key in dnp:
                    continue
                actual_reference = references.get(reference_key)
                component = components.get(reference_key)
                if (
                    actual_reference is None
                    or component is None
                    or symbols.get(reference_key) != endpoint.symbol
                    or component.footprint != endpoint.footprint
                ):
                    continue
                line_1, line_2 = mapped
                observed_line_1 = _assigned_net(pin_nets, line_1.pin)
                observed_line_2 = _assigned_net(pin_nets, line_2.pin)
                if (
                    observed_line_1 is None
                    or observed_line_2 is None
                    or observed_line_1.casefold() != pair.line_1_net.casefold()
                    or observed_line_2.casefold() != pair.line_2_net.casefold()
                ):
                    continue
                references_for_endpoint, reference_net, issue = _reference_assignments(
                    endpoint, pin_nets
                )
                endpoints.append(
                    Rs485PeerReferenceEndpoint(
                        endpoint_id=endpoint.id,
                        reference=actual_reference,
                        kind=endpoint.kind,
                        line_1_pin=line_1.pin,
                        line_2_pin=line_2.pin,
                        line_1_net=observed_line_1,
                        line_2_net=observed_line_2,
                        reference_net=reference_net,
                        reference_pins=references_for_endpoint,
                        reference_issue=issue,
                    )
                )
                recognized.add(reference_key)

            if len(endpoints) < 2:
                continue
            ordered = tuple(
                sorted(endpoints, key=lambda item: (item.reference.casefold(), item.reference))
            )
            reference_nets = {
                item.reference_net.casefold() for item in ordered if item.reference_net is not None
            }
            incomplete = tuple(
                item.reference for item in ordered if item.reference_issue is not None
            )
            if len(reference_nets) > 1:
                disposition = (
                    "PARTIAL_SPLIT_REFERENCE_REVIEW" if incomplete else "SPLIT_REFERENCE_REVIEW"
                )
            elif incomplete:
                disposition = "INCOMPLETE"
            else:
                disposition = "COMMON_REFERENCE"
            pair_groups.append(
                Rs485PeerReferencePair(
                    bus_id=bus.id,
                    pair_id=pair.id,
                    line_1_net=pair.line_1_net,
                    line_2_net=pair.line_2_net,
                    endpoints=ordered,
                    incomplete_references=incomplete,
                    disposition=disposition,
                )
            )

    pair_groups.sort(key=lambda item: (item.bus_id.casefold(), item.pair_id.casefold()))
    return Rs485PeerReferenceScan(
        map_state=context.state,
        source_path=context.source_path,
        source_sha256=context.source_sha256,
        analysis_sha256=hashlib.sha256(analysis.model_dump_json().encode("utf-8")).hexdigest(),
        recognized_endpoint_count=len(recognized),
        pairs=tuple(pair_groups),
    )


def _pin_nets(observed: NetlistContract) -> dict[str, set[str]]:
    pin_nets: dict[str, set[str]] = {}
    for net, pins in observed.nets.items():
        for pin in pins:
            pin_nets.setdefault(pin.casefold(), set()).add(net)
    return pin_nets


def _assigned_net(pin_nets: Mapping[str, AbstractSet[str]], pin: str) -> str | None:
    nets = pin_nets.get(pin.casefold(), set())
    if len({net.casefold() for net in nets}) != 1:
        return None
    return min(nets, key=lambda item: (item.casefold(), item))


def _mapped_pair_pins(
    endpoint: Rs485EndpointRequirement,
    pair: Rs485SignalPairRequirement,
) -> tuple[Rs485EndpointPinRequirement, Rs485EndpointPinRequirement] | None:
    first = tuple(
        pin for pin in endpoint.pins if pin.pair_id == pair.id and pin.role == "bus_line_1"
    )
    second = tuple(
        pin for pin in endpoint.pins if pin.pair_id == pair.id and pin.role == "bus_line_2"
    )
    if len(first) != 1 or len(second) != 1:
        return None
    return first[0], second[0]


def _reference_assignments(
    endpoint: Rs485EndpointRequirement,
    pin_nets: Mapping[str, AbstractSet[str]],
) -> tuple[tuple[Rs485ReferencePinAssignment, ...], str | None, str | None]:
    requirements = tuple(pin for pin in endpoint.pins if pin.role == "reference")
    assignments = tuple(
        Rs485ReferencePinAssignment(
            pin=requirement.pin,
            net=_assigned_net(pin_nets, requirement.pin),
            expected_net=requirement.net,
        )
        for requirement in requirements
    )
    if not assignments:
        return (), None, "no reference pin is mapped"
    if any(item.net is None for item in assignments):
        return assignments, None, "a mapped reference pin is unassigned or ambiguous"
    actual_nets = {item.net.casefold() for item in assignments if item.net is not None}
    if len(actual_nets) != 1:
        return assignments, None, "mapped reference pins occupy multiple native nets"
    if any(
        item.net is None or item.net.casefold() != item.expected_net.casefold()
        for item in assignments
    ):
        return assignments, None, "a mapped reference pin differs from its authored net"
    net = next(item.net for item in assignments if item.net is not None)
    return assignments, net, None
