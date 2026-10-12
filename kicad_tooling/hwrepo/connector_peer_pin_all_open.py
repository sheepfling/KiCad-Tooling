"""Low-confidence review prompts for generic connector contacts open on every peer."""

from __future__ import annotations

from collections.abc import Mapping

from .connector_identity import (
    connector_candidate_references,
    partition_peer_assignments,
    pin_function_is_generic,
)
from .connector_peer_pin_scan import (
    ConnectorPartIdPeerPinGroup,
    scan_connector_part_id_peer_pins,
)
from .design_lint_types import Candidate
from .models import ConnectorMappedPinEvidence, NetlistContract


def all_open_generic_connector_peer_pin_candidates(
    observed: NetlistContract,
    declared_references: tuple[str, ...] = (),
    reviewed_connector_pins: Mapping[str, ConnectorMappedPinEvidence] | None = None,
    peer_assignment_groups: Mapping[str, tuple[str, str]] | None = None,
) -> tuple[Candidate, ...]:
    """Prompt on generic passive pins open across exact-symbol peers with a shared anchor.

    The candidate is deliberately narrower than a general unconnected-pin rule:
    every fitted peer must expose the same complete pin inventory, the pin's
    native function must be absent or generic, its electrical type must be
    passive, and another pin must have one common exact net assignment across
    the same peer group. This context does not identify the open pin's role or
    establish that it must be connected.
    """
    reviewed_connector_pins = reviewed_connector_pins or {}
    reviewed_pins = {pin.casefold(): evidence for pin, evidence in reviewed_connector_pins.items()}
    connector_references = {
        reference.casefold()
        for reference in connector_candidate_references(observed, declared_references)
    }
    dnp = {reference.casefold() for reference in observed.dnp_components}
    symbols_by_reference = {
        reference.casefold(): (reference, symbol)
        for reference, symbol in observed.component_symbols.items()
    }
    functions = {pin.casefold(): value for pin, value in observed.pin_functions.items()}
    electrical_types = {
        pin.casefold(): value.strip().casefold()
        for pin, value in observed.pin_electrical_types.items()
    }
    nets_by_pin: dict[str, set[str]] = {}
    for net, pins in observed.nets.items():
        for pin in pins:
            nets_by_pin.setdefault(pin.casefold(), set()).add(net)

    inventory_by_reference = {
        reference.casefold(): tuple(numbers)
        for reference, numbers in observed.component_pin_numbers.items()
    }
    observed_pin_numbers: dict[str, set[str]] = {}
    for pin in observed.pin_functions:
        reference, pin_number = pin.rsplit(".", 1)
        observed_pin_numbers.setdefault(reference.casefold(), set()).add(pin_number.casefold())
    for assignments in (*observed.nets.values(), *observed.unconnected_nets.values()):
        for pin in assignments:
            reference, pin_number = pin.rsplit(".", 1)
            observed_pin_numbers.setdefault(reference.casefold(), set()).add(pin_number.casefold())
    references_by_symbol: dict[str, list[tuple[str, str]]] = {}
    for reference_key, (reference, symbol) in symbols_by_reference.items():
        if (
            reference_key in connector_references
            and reference_key not in dnp
            and reference_key in inventory_by_reference
        ):
            references_by_symbol.setdefault(symbol.casefold(), []).append((reference, symbol))

    candidates: list[Candidate] = []
    for peer_symbols in references_by_symbol.values():
        peers = tuple(sorted(peer_symbols, key=lambda item: (item[0].casefold(), item[0])))
        if len(peers) < 2:
            continue
        references = tuple(reference for reference, _ in peers)
        raw_inventories = {
            reference.casefold(): inventory_by_reference[reference.casefold()]
            for reference in references
        }
        folded_inventories = {
            reference: tuple(number.casefold() for number in numbers)
            for reference, numbers in raw_inventories.items()
        }
        inventory_sets = {frozenset(numbers) for numbers in folded_inventories.values()}
        if (
            len(inventory_sets) != 1
            or any(not numbers for numbers in folded_inventories.values())
            or any(len(set(numbers)) != len(numbers) for numbers in folded_inventories.values())
            or any(
                not observed_pin_numbers.get(reference.casefold(), set()).issubset(
                    set(folded_inventories[reference.casefold()])
                )
                for reference in references
            )
        ):
            continue

        pin_numbers = tuple(
            sorted(next(iter(inventory_sets)), key=lambda item: (item.casefold(), item))
        )
        displayed_numbers = {
            reference.casefold(): {
                number.casefold(): number for number in raw_inventories[reference.casefold()]
            }
            for reference in references
        }
        for pin_number in pin_numbers:
            assignments = {
                f"{reference}.{displayed_numbers[reference.casefold()][pin_number]}": tuple(
                    sorted(
                        nets_by_pin.get(
                            f"{reference}.{displayed_numbers[reference.casefold()][pin_number]}".casefold(),
                            (),
                        ),
                        key=lambda item: (item.casefold(), item),
                    )
                )
                for reference in references
            }
            if any(assignments.values()):
                continue

            pin_keys = tuple(pin.casefold() for pin in assignments)
            if not all(pin_function_is_generic(functions.get(pin)) for pin in pin_keys):
                continue
            if not all(electrical_types.get(pin) == "passive" for pin in pin_keys):
                continue
            if any(
                (reviewed := reviewed_pins.get(pin)) is not None
                and reviewed.role in {"return", "supply"}
                for pin in pin_keys
            ):
                continue

            for peer_group, scoped_assignments, peer_review in partition_peer_assignments(
                assignments,
                peer_assignment_groups,
            ):
                scoped_references = tuple(
                    sorted(
                        {pin.rsplit(".", 1)[0] for pin in scoped_assignments},
                        key=lambda item: (item.casefold(), item),
                    )
                )
                if len(scoped_references) < 2 or any(scoped_assignments.values()):
                    continue
                shared_anchors: list[str] = []
                for anchor_number in pin_numbers:
                    if anchor_number == pin_number:
                        continue
                    anchor_assignments = tuple(
                        tuple(
                            sorted(
                                nets_by_pin.get(
                                    f"{reference}.{displayed_numbers[reference.casefold()][anchor_number]}".casefold(),
                                    (),
                                ),
                                key=lambda item: (item.casefold(), item),
                            )
                        )
                        for reference in scoped_references
                    )
                    if (
                        anchor_assignments
                        and len(set(anchor_assignments)) == 1
                        and len(anchor_assignments[0]) == 1
                    ):
                        shared_anchors.append(
                            " / ".join(
                                f"{reference}.{displayed_numbers[reference.casefold()][anchor_number]}"
                                for reference in scoped_references
                            )
                            + f" -> {anchor_assignments[0][0]}"
                        )
                if not shared_anchors:
                    continue

                symbol = peers[0][1]
                evidence = {
                    **scoped_assignments,
                    "symbol": (symbol,),
                    "pin_number": (pin_number,),
                    "shared_anchor_contacts": tuple(
                        sorted(shared_anchors, key=lambda item: (item.casefold(), item))
                    ),
                }
                if peer_group is not None:
                    evidence["peer_assignment_group"] = (peer_group,)
                    evidence["peer_assignment_basis"] = peer_review
                candidates.append(
                    Candidate(
                        rule_id="connector.generic_peer_pin_all_open",
                        subject=f"{symbol} pin {pin_number}: generic passive contact is open on every peer",
                        message=(
                            "This generic passive connector pin is unassigned on every fitted "
                            "peer of the exact symbol, while another pin has the same assigned "
                            "net across those peers. Review the approved pinout for an "
                            "intentionally unused contact or a missing connection. The generic "
                            "pin metadata does not identify this contact as signal, return, or "
                            "power, and peer similarity does not establish that it must connect."
                            + (
                                " The comparison is scoped by a source-reviewed "
                                "peer-assignment group."
                                if peer_group is not None
                                else ""
                            )
                        ),
                        evidence=evidence,
                    )
                )

    part_id_scan = scan_connector_part_id_peer_pins(
        observed,
        declared_references,
        peer_assignment_groups,
    )
    part_id_groups_by_scope: dict[
        tuple[str, str, frozenset[str]], list[ConnectorPartIdPeerPinGroup]
    ] = {}
    for group in part_id_scan.pin_groups:
        references = frozenset(pin.rsplit(".", 1)[0].casefold() for pin in group.assignments)
        scope = (
            group.part_id.casefold(),
            (group.peer_assignment_group or "").casefold(),
            references,
        )
        part_id_groups_by_scope.setdefault(scope, []).append(group)

    part_id_candidates: list[Candidate] = []
    for scope, peer_pin_groups in part_id_groups_by_scope.items():
        for group in peer_pin_groups:
            if any(group.assignments.values()):
                continue
            if not pin_function_is_generic(group.pin_function):
                continue
            if group.pin_electrical_type.strip().casefold() != "passive":
                continue
            pin_keys = tuple(pin.casefold() for pin in group.assignments)
            if any(
                (reviewed := reviewed_pins.get(pin)) is not None
                and reviewed.role in {"return", "supply"}
                for pin in pin_keys
            ):
                continue

            shared_anchor_groups = tuple(
                anchor
                for anchor in peer_pin_groups
                if anchor.pin_number.casefold() != group.pin_number.casefold()
                and anchor.assignments
                and len(set(anchor.assignments.values())) == 1
                and len(next(iter(anchor.assignments.values()))) == 1
            )
            if not shared_anchor_groups:
                continue

            anchor_contacts = tuple(
                sorted(
                    (
                        " / ".join(anchor.assignments)
                        + f" -> {next(iter(anchor.assignments.values()))[0]}"
                    )
                    for anchor in shared_anchor_groups
                )
            )
            evidence = {
                **group.assignments,
                "symbol": ("multiple connector symbols",),
                "pin_number": (group.pin_number,),
                "shared_anchor_contacts": anchor_contacts,
                "peer_identity_basis": ("part_id",),
                "peer_identity": (group.part_id,),
                "peer_symbols": group.symbols,
            }
            if group.peer_assignment_group is not None:
                evidence["peer_assignment_group"] = (group.peer_assignment_group,)
                evidence["peer_assignment_basis"] = group.peer_assignment_basis
            part_id_candidates.append(
                Candidate(
                    rule_id="connector.generic_peer_pin_all_open",
                    subject=(
                        f"PART_ID {group.part_id} pin {group.pin_number}: generic passive "
                        "contact is open on every peer"
                    ),
                    message=(
                        "This generic passive connector pin is unassigned on every fitted peer "
                        "with the same reviewed PART_ID, while another pin has the same exact "
                        "assigned net across those peers. Review the approved pinout for an "
                        "intentionally unused contact or a missing connection. The generic pin "
                        "metadata does not identify this contact as signal, return, or power, and "
                        "peer similarity does not establish that it must connect."
                        + (
                            " The comparison is scoped by a source-reviewed peer-assignment group."
                            if group.peer_assignment_group is not None
                            else ""
                        )
                    ),
                    evidence=evidence,
                )
            )

    def is_subsumed_by_part_id(exact: Candidate) -> bool:
        exact_evidence = exact.evidence
        exact_pin_keys = {
            key
            for key in exact_evidence
            if "." in key and key.rsplit(".", 1)[0].casefold() in symbols_by_reference
        }
        if not exact_pin_keys:
            return False
        exact_symbol = next(iter(exact_evidence.get("symbol", ())), "").casefold()
        exact_pin_number = next(iter(exact_evidence.get("pin_number", ())), "").casefold()
        for alias in part_id_candidates:
            alias_evidence = alias.evidence
            if next(
                iter(alias_evidence.get("pin_number", ())), ""
            ).casefold() != exact_pin_number or exact_symbol not in {
                symbol.casefold() for symbol in alias_evidence.get("peer_symbols", ())
            }:
                continue
            if all(alias_evidence.get(pin) == exact_evidence[pin] for pin in exact_pin_keys):
                return True
        return False

    candidates = [
        *(candidate for candidate in candidates if not is_subsumed_by_part_id(candidate)),
        *part_id_candidates,
    ]
    return tuple(
        sorted(
            candidates, key=lambda item: (item.rule_id, item.subject, tuple(sorted(item.evidence)))
        )
    )
