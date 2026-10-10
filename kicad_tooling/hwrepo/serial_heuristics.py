"""Authored UART peer maps checked against a source-bound KiCad netlist."""

from __future__ import annotations

from .models import ElectricalCheck, NetlistContract
from .reference_bonds import reference_bond_issues
from .serial_logic_models import SerialLogicInputLimits, SerialLogicOutputLimits
from .serial_peer_models import (
    SerialBridgeRequirement,
    SerialDirectPeerRequirement,
    SerialEndpointRequirement,
    SerialExternalPeerRequirement,
    SerialPeerAnalysis,
    SerialShiftedPeerRequirement,
)


def logic_direction_check(
    check_id: str,
    direction: str,
    output: SerialLogicOutputLimits,
    receiver: SerialLogicInputLimits,
) -> ElectricalCheck:
    low_margin = min(
        output.low_minimum_v - receiver.absolute_minimum_v,
        receiver.low_maximum_v - output.low_maximum_v,
    )
    high_margin = min(
        output.high_minimum_v - receiver.high_minimum_v,
        receiver.absolute_maximum_v - output.high_maximum_v,
    )
    margin = min(low_margin, high_margin)
    return ElectricalCheck(
        id=check_id,
        status="PASS" if margin >= 0 else "FAIL",
        observed=margin,
        unit="V",
        detail=(
            f"{direction}: guaranteed output low [{output.low_minimum_v:g}, "
            f"{output.low_maximum_v:g}] V and high [{output.high_minimum_v:g}, "
            f"{output.high_maximum_v:g}] V compared with receiver low maximum "
            f"{receiver.low_maximum_v:g} V, high minimum {receiver.high_minimum_v:g} V, "
            f"and absolute input range [{receiver.absolute_minimum_v:g}, "
            f"{receiver.absolute_maximum_v:g}] V. Minimum margin={margin:g} V; "
            f"output source={output.source} ({output.conditions}); "
            f"receiver source={receiver.source} ({receiver.conditions})."
        ),
    )


def _serial_logic_voltage_checks(
    link_id: str,
    local: SerialEndpointRequirement,
    remote: SerialEndpointRequirement | None,
    *,
    mode: str,
) -> tuple[ElectricalCheck, ...]:
    if mode != "direct" or remote is None:
        return (
            ElectricalCheck(
                id=f"serial/{link_id}/logic-voltage",
                status="NOT_APPLICABLE",
                detail=(
                    "Direct endpoint voltage compatibility is not evaluated for an external peer "
                    "or across a level-shifter device. Its remote ratings or internal behavior "
                    "need separate reviewed evidence."
                ),
            ),
        )

    if local.logic_limits is None or remote.logic_limits is None:
        missing = [endpoint.id for endpoint in (local, remote) if endpoint.logic_limits is None]
        reason = (
            "Missing reviewed logic voltage limits for endpoint(s) "
            f"{', '.join(missing)}; cite guaranteed TX ranges, RX thresholds, absolute input "
            "limits, and their conditions."
        )
        return tuple(
            ElectricalCheck(
                id=f"serial/{link_id}/logic-voltage/{direction}",
                status="NOT_CONFIGURED",
                detail=reason,
            )
            for direction in ("a_tx_to_b_rx", "b_tx_to_a_rx")
        )

    return (
        logic_direction_check(
            f"serial/{link_id}/logic-voltage/a_tx_to_b_rx",
            "A TX to B RX",
            local.logic_limits.output,
            remote.logic_limits.input,
        ),
        logic_direction_check(
            f"serial/{link_id}/logic-voltage/b_tx_to_a_rx",
            "B TX to A RX",
            remote.logic_limits.output,
            local.logic_limits.input,
        ),
    )


def serial_peer_checks(
    spec: SerialPeerAnalysis, observed: NetlistContract
) -> tuple[ElectricalCheck, ...]:
    """Check explicit UART endpoint roles, references, identities, and declared paths."""
    pin_nets: dict[str, set[str]] = {}
    for net, pins in observed.nets.items():
        for pin in pins:
            pin_nets.setdefault(pin.casefold(), set()).add(net)

    known_pins = {
        f"{reference}.{number}".casefold()
        for reference, numbers in observed.component_pin_numbers.items()
        for number in numbers
    }
    known_pins.update(pin.casefold() for pin in observed.pin_functions)
    known_pins.update(pin.casefold() for pins in observed.nets.values() for pin in pins)
    components = {
        reference.casefold(): (reference, component)
        for reference, component in observed.components.items()
    }
    symbols = {
        reference.casefold(): symbol for reference, symbol in observed.component_symbols.items()
    }
    dnp = {reference.casefold() for reference in observed.dnp_components}

    def pin_issue(pin: str, expected_net: str) -> str | None:
        key = pin.casefold()
        if key not in known_pins:
            return f"{pin} is absent from the native symbol pin inventory"
        actual = pin_nets.get(key, set())
        if actual != {expected_net}:
            assigned = ", ".join(sorted(actual)) if actual else "unconnected"
            return f"{pin} is assigned to {assigned}; expected {expected_net}"
        return None

    def identity_issues(reference: str, symbol: str, footprint: str) -> list[str]:
        key = reference.casefold()
        entry = components.get(key)
        if entry is None:
            return [f"{reference} is absent from the netlist"]
        actual_reference, component = entry
        issues: list[str] = []
        if key in dnp:
            issues.append(f"{actual_reference} is marked DNP")
        actual_symbol = symbols.get(key)
        if actual_symbol != symbol:
            issues.append(
                f"{actual_reference} symbol is {actual_symbol or 'unknown'}; expected {symbol}"
            )
        if component.footprint != footprint:
            issues.append(
                f"{actual_reference} footprint is {component.footprint or 'empty'}; expected {footprint}"
            )
        return issues

    def endpoint_checks(
        link_id: str, endpoint: SerialEndpointRequirement
    ) -> tuple[list[ElectricalCheck], bool, bool]:
        base = f"serial/{link_id}/endpoint/{endpoint.id}"
        identity_failures = identity_issues(endpoint.reference, endpoint.symbol, endpoint.footprint)
        identity_ok = not identity_failures
        rows = [
            ElectricalCheck(
                id=f"{base}/identity",
                status="FAIL" if identity_failures else "PASS",
                detail=(
                    "; ".join(identity_failures)
                    if identity_failures
                    else f"{endpoint.reference} matches the declared serial endpoint symbol and footprint."
                ),
            )
        ]
        requirements = (endpoint.tx, endpoint.rx, *endpoint.reference_pins)
        failures = [
            issue
            for requirement in requirements
            if (issue := pin_issue(requirement.pin, requirement.net)) is not None
        ]
        rows.append(
            ElectricalCheck(
                id=f"{base}/pins",
                status="FAIL" if failures else "PASS",
                detail=(
                    "; ".join(failures)
                    if failures
                    else f"Declared TX, RX, and {len(endpoint.reference_pins)} reference pin assignments match."
                ),
            )
        )
        return rows, identity_ok, not failures

    results: list[ElectricalCheck] = []
    for link in spec.links:
        link_id = link.id
        if isinstance(link.peer, SerialDirectPeerRequirement):
            results.extend(
                _serial_logic_voltage_checks(
                    link_id,
                    link.endpoint,
                    link.peer.endpoint,
                    mode="direct",
                )
            )
        elif isinstance(link.peer, SerialShiftedPeerRequirement):
            results.extend(
                _serial_logic_voltage_checks(
                    link_id,
                    link.endpoint,
                    link.peer.endpoint,
                    mode="level_shifted",
                )
            )
        else:
            results.extend(
                _serial_logic_voltage_checks(
                    link_id,
                    link.endpoint,
                    None,
                    mode="external",
                )
            )
        local_rows, local_identity_ok, local_pins_ok = endpoint_checks(link_id, link.endpoint)
        results.extend(local_rows)

        if isinstance(link.peer, SerialExternalPeerRequirement):
            results.extend(
                (
                    ElectricalCheck(
                        id=f"serial/{link_id}/peer-map",
                        status="NOT_APPLICABLE",
                        detail=f"Remote TX/RX mapping is outside the local netlist: {link.peer.reason}",
                    ),
                    ElectricalCheck(
                        id=f"serial/{link_id}/voltage-domain",
                        status="NOT_APPLICABLE",
                        detail="Remote endpoint voltage domain and tolerance are not available in this project netlist.",
                    ),
                    ElectricalCheck(
                        id=f"serial/{link_id}/reference",
                        status="NOT_APPLICABLE",
                        detail=(
                            "Local reference pins are mapped, but continuity to the external peer is unverified."
                            if link.reference_policy == "external_unverified"
                            else "Reference relationship is explicitly not applicable."
                        ),
                    ),
                )
            )
            continue

        remote = link.peer.endpoint
        remote_rows, remote_identity_ok, remote_pins_ok = endpoint_checks(link_id, remote)
        results.extend(remote_rows)
        bridge_rows: list[ElectricalCheck] = []
        bridge_paths_ok: dict[tuple[str, str, str, str], bool] = {}
        if isinstance(link.peer, SerialShiftedPeerRequirement):
            for bridge in link.peer.bridges:
                bridge_key = bridge.reference.casefold()
                bridge_identity_failures = identity_issues(
                    bridge.reference, bridge.symbol, bridge.footprint
                )
                bridge_identity_ok = not bridge_identity_failures
                bridge_rows.append(
                    ElectricalCheck(
                        id=f"serial/{link_id}/bridge/{bridge.reference}/identity",
                        status="FAIL" if bridge_identity_failures else "PASS",
                        detail=(
                            "; ".join(bridge_identity_failures)
                            if bridge_identity_failures
                            else f"{bridge.reference} matches the declared serial bridge symbol and footprint."
                        ),
                    )
                )
                failures: list[str] = []
                for path in bridge.paths:
                    from_issue = pin_issue(path.from_pin, path.from_net)
                    to_issue = pin_issue(path.to_pin, path.to_net)
                    bridge_paths_ok[(bridge_key, path.direction, path.from_net, path.to_net)] = (
                        bridge_identity_ok and from_issue is None and to_issue is None
                    )
                    if from_issue is not None:
                        failures.append(f"{path.direction} input: {from_issue}")
                    if to_issue is not None:
                        failures.append(f"{path.direction} output: {to_issue}")
                bridge_rows.append(
                    ElectricalCheck(
                        id=f"serial/{link_id}/bridge/{bridge.reference}/pins",
                        status="FAIL" if failures else "PASS",
                        detail=(
                            "; ".join(failures)
                            if failures
                            else f"All {len(bridge.paths)} declared bridge endpoint assignments match. Internal conversion behavior is not verified."
                        ),
                    )
                )
        results.extend(bridge_rows)

        def route_matches(
            direction: str,
            source: str,
            destination: str,
            *,
            bridges: tuple[SerialBridgeRequirement, ...] = (
                link.peer.bridges if isinstance(link.peer, SerialShiftedPeerRequirement) else ()
            ),
            valid_paths: dict[tuple[str, str, str, str], bool] = bridge_paths_ok,
        ) -> bool:
            if source == destination:
                return True
            graph: dict[str, set[str]] = {}
            for bridge in bridges:
                bridge_key = bridge.reference.casefold()
                for path in bridge.paths:
                    if path.direction != direction:
                        continue
                    key = (bridge_key, path.direction, path.from_net, path.to_net)
                    if not valid_paths.get(key, False):
                        continue
                    graph.setdefault(path.from_net, set()).add(path.to_net)
                    graph.setdefault(path.to_net, set()).add(path.from_net)
            pending = [source]
            reached: set[str] = set()
            while pending:
                net = pending.pop()
                if net == destination:
                    return True
                if net in reached:
                    continue
                reached.add(net)
                pending.extend(graph.get(net, ()))
            return False

        for direction, source, destination, source_pin, destination_pin in (
            (
                "a_tx_to_b_rx",
                link.endpoint.tx.net,
                remote.rx.net,
                link.endpoint.tx,
                remote.rx,
            ),
            (
                "b_tx_to_a_rx",
                remote.tx.net,
                link.endpoint.rx.net,
                remote.tx,
                link.endpoint.rx,
            ),
        ):
            passed = (
                local_identity_ok
                and local_pins_ok
                and remote_identity_ok
                and remote_pins_ok
                and route_matches(direction, source, destination)
                and pin_issue(source_pin.pin, source) is None
                and pin_issue(destination_pin.pin, destination) is None
            )
            results.append(
                ElectricalCheck(
                    id=f"serial/{link_id}/route/{direction}",
                    status="PASS" if passed else "FAIL",
                    detail=(
                        f"Declared route {source_pin.pin} to {destination_pin.pin} matches {source} to {destination}."
                        if passed and link.peer.mode == "direct"
                        else (
                            f"Declared level-shifted route {source} to {destination} has matching bridge endpoint assignments; internal conversion behavior is not verified."
                            if passed
                            else f"Serial route {direction} lacks matching endpoint or bridge net assignments from {source} to {destination}."
                        )
                    ),
                )
            )

        if link.reference_policy in {"common_net", "separate_nets", "bonded"}:
            reference_issues = [
                issue
                for endpoint in (link.endpoint, remote)
                for pin in endpoint.reference_pins
                if (issue := pin_issue(pin.pin, pin.net)) is not None
            ]
            if link.reference_policy == "bonded" and link.reference_bond is not None:
                reference_issues.extend(reference_bond_issues(observed, link.reference_bond))
            references_ok = not reference_issues
            results.append(
                ElectricalCheck(
                    id=f"serial/{link_id}/reference",
                    status="PASS" if references_ok else "FAIL",
                    detail=(
                        f"Both endpoints match the authored {link.reference_policy} reference pin map."
                        if references_ok
                        else "; ".join(reference_issues)
                    ),
                )
            )
        else:
            results.append(
                ElectricalCheck(
                    id=f"serial/{link_id}/reference",
                    status="NOT_APPLICABLE",
                    detail="The project explicitly declares that no endpoint reference relationship applies.",
                )
            )

        same_domain = link.endpoint.logic_domain == remote.logic_domain
        shifted_routes = all(
            route_matches(direction, source, destination)
            for direction, source, destination in (
                ("a_tx_to_b_rx", link.endpoint.tx.net, remote.rx.net),
                ("b_tx_to_a_rx", remote.tx.net, link.endpoint.rx.net),
            )
        )
        domain_ok = (same_domain and link.peer.mode == "direct") or (
            link.peer.mode == "level_shifted"
            and shifted_routes
            and local_pins_ok
            and remote_pins_ok
        )
        results.append(
            ElectricalCheck(
                id=f"serial/{link_id}/voltage-domain",
                status="PASS" if domain_ok else "FAIL",
                detail=(
                    f"Both endpoints declare the same logic domain {link.endpoint.logic_domain}."
                    if same_domain and link.peer.mode == "direct"
                    else (
                        f"Endpoint domains {link.endpoint.logic_domain} and {remote.logic_domain} use the declared level-shifted path; electrical tolerance and conversion behavior are not verified."
                        if domain_ok
                        else "Different declared logic domains require a level-shifted peer map with matching bridge endpoint assignments."
                    )
                ),
            )
        )
    return tuple(results)
