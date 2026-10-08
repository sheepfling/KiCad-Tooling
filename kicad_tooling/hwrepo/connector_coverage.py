"""Source-bound coverage checks for project-authored connector/interface reviews."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Literal

from .connector_pins import connector_candidate_references
from .models import (
    ConnectorCoverageEntry,
    ConnectorCoverageReport,
    ConnectorInterfaceReview,
    ConnectorInventoryReview,
    ConnectorMappedPinEvidence,
    InterfacePin,
    InterfaceRecord,
    NetlistContract,
    RepositoryPath,
)

_SCOPE = (
    "Symbol-backed references matching J, P, X, or CN followed by digits, plus symbols from "
    "standard Connector libraries except Connector:TestPoint symbols; this candidate scan does "
    "not prove that every physical interface was found. Exact project-reviewed interface "
    "references can extend connector-pin heuristics to custom symbols. A project-owned inventory "
    "review is required before connector coverage is complete."
)


def evaluate(
    observed: NetlistContract,
    project_interfaces: tuple[str, ...],
    reviews: tuple[ConnectorInterfaceReview, ...],
    interfaces: Mapping[str, InterfaceRecord] | None = None,
    interface_catalog_path: RepositoryPath | None = None,
    interface_catalog_sha256: str | None = None,
    catalog_issues: tuple[str, ...] = (),
    inventory_review: ConnectorInventoryReview | None = None,
) -> ConnectorCoverageReport:
    """Compare declared review coverage with exact interface and exported pin inventories."""
    nets_by_pin: dict[str, set[str]] = {}
    for net, pins in observed.nets.items():
        for pin in pins:
            nets_by_pin.setdefault(pin, set()).add(net)
    review_by_reference = {item.reference: item for item in reviews}
    review_references = set(review_by_reference)
    candidates = set(
        connector_candidate_references(
            observed,
            tuple(review_references),
            include_exact_symbol_peers=True,
        )
    )
    all_references = candidates | review_references
    entries: list[ConnectorCoverageEntry] = []
    bound_interfaces: set[str] = set()

    for reference in sorted(all_references):
        review = review_by_reference.get(reference)
        if reference not in observed.component_symbols and reference not in observed.components:
            entries.append(
                ConnectorCoverageEntry(
                    reference=reference,
                    status="STALE",
                    interface_id=None if review is None else review.interface_id,
                    basis=None if review is None else review.basis,
                    peer_assignment_group=(
                        None if review is None else review.peer_assignment_group
                    ),
                    peer_assignment_basis=(
                        None if review is None else review.peer_assignment_basis
                    ),
                    issues=("Reviewed reference is not present in the exported symbol inventory",),
                )
            )
            continue
        if reference not in observed.component_symbols:
            entries.append(
                ConnectorCoverageEntry(
                    reference=reference,
                    status="INCOMPLETE",
                    interface_id=None if review is None else review.interface_id,
                    basis=None if review is None else review.basis,
                    peer_assignment_group=(
                        None if review is None else review.peer_assignment_group
                    ),
                    peer_assignment_basis=(
                        None if review is None else review.peer_assignment_basis
                    ),
                    issues=("Exported component has no symbol definition for pin inventory",),
                )
            )
            continue
        if review is None:
            entries.append(
                ConnectorCoverageEntry(
                    reference=reference,
                    status="UNDECLARED",
                    issues=("No project-owned interface or not-applicable review is declared",),
                )
            )
            continue
        if review.disposition == "not_applicable":
            entries.append(
                ConnectorCoverageEntry(
                    reference=reference,
                    status="NOT_APPLICABLE",
                    basis=review.basis,
                )
            )
            continue

        interface_id = review.interface_id
        assert interface_id is not None
        bound_interfaces.add(interface_id)
        issues: list[str] = []
        interface = None if interfaces is None else interfaces.get(interface_id)
        interface_pins: dict[str, InterfacePin] = {}
        if interface is None:
            issues.append(f"Interface catalog has no record for {interface_id}")
            interface_pin_numbers: set[str] = set()
        else:
            interface_pins = {pin.number: pin for pin in interface.pins}
            interface_pin_numbers = set(interface_pins)

        mapped_interface_pins = set(review.pin_map)
        interface_pins_unmapped = tuple(sorted(interface_pin_numbers - mapped_interface_pins))
        unknown_interface_pins = tuple(sorted(mapped_interface_pins - interface_pin_numbers))
        if interface_pins_unmapped:
            issues.append("One or more catalogued interface pins have no component pin mapping")
        if unknown_interface_pins:
            issues.append(
                "Pin map includes numbers absent from the selected interface catalog record"
            )
        mapped_pins = tuple(
            ConnectorMappedPinEvidence(
                interface_pin_number=interface_pin_number,
                interface_signal=interface_pins[interface_pin_number].signal,
                component_pin=f"{reference}.{component_pin_number}",
                role=interface_pins[interface_pin_number].role,
                voltage_domain=interface_pins[interface_pin_number].voltage_domain,
                symbol_function=observed.pin_functions.get(f"{reference}.{component_pin_number}"),
                nets=tuple(sorted(nets_by_pin.get(f"{reference}.{component_pin_number}", ()))),
            )
            for interface_pin_number, component_pin_number in sorted(review.pin_map.items())
            if interface_pin_number in interface_pins
        )

        known_component_pins = observed.component_pin_numbers.get(reference)
        if known_component_pins is None:
            component_pins: set[str] = set()
            issues.append("Native netlist has no complete pin-number inventory for this reference")
            component_pins_unaccounted: tuple[str, ...] = ()
            component_pins_unknown = tuple(
                sorted(set(review.pin_map.values()) | set(review.unlisted_pin_reasons))
            )
        else:
            component_pins = set(known_component_pins)
            accounted = set(review.pin_map.values()) | set(review.unlisted_pin_reasons)
            component_pins_unaccounted = tuple(sorted(component_pins - accounted))
            component_pins_unknown = tuple(sorted(accounted - component_pins))
            if component_pins_unaccounted:
                issues.append("One or more exported component pins have no review disposition")
            if component_pins_unknown:
                issues.append("Review names component pins absent from the exported symbol")

        entry_status: Literal["COVERED", "INCOMPLETE"] = "INCOMPLETE" if issues else "COVERED"
        entries.append(
            ConnectorCoverageEntry(
                reference=reference,
                status=entry_status,
                interface_id=interface_id,
                basis=review.basis,
                peer_assignment_group=review.peer_assignment_group,
                peer_assignment_basis=review.peer_assignment_basis,
                interface_pin_map=dict(sorted(review.pin_map.items())),
                unlisted_pin_reasons=dict(sorted(review.unlisted_pin_reasons.items())),
                mapped_pins=mapped_pins,
                interface_pins_unmapped=interface_pins_unmapped,
                interface_pins_unknown=unknown_interface_pins,
                component_pins_unaccounted=component_pins_unaccounted,
                component_pins_unknown=component_pins_unknown,
                issues=tuple(issues),
            )
        )

    unbound_interfaces = tuple(sorted(set(project_interfaces) - bound_interfaces))
    if not candidates and not reviews and not project_interfaces and not catalog_issues:
        coverage_status: Literal[
            "COMPLETE", "INCOMPLETE", "UNDECLARED", "UNASSESSED", "SCOPE_UNREVIEWED"
        ] = "UNASSESSED" if inventory_review is None else "COMPLETE"
    elif catalog_issues or any(item.status in {"INCOMPLETE", "STALE"} for item in entries):
        coverage_status = "INCOMPLETE"
    elif any(item.status == "UNDECLARED" for item in entries) or unbound_interfaces:
        coverage_status = "UNDECLARED"
    elif inventory_review is None:
        coverage_status = "SCOPE_UNREVIEWED"
    else:
        coverage_status = "COMPLETE"

    return ConnectorCoverageReport(
        status=coverage_status,
        scope=_SCOPE,
        project_interfaces=tuple(sorted(project_interfaces)),
        unbound_interface_ids=unbound_interfaces,
        inventory_review_basis=None if inventory_review is None else inventory_review.basis,
        interface_catalog_path=interface_catalog_path,
        interface_catalog_sha256=interface_catalog_sha256,
        entries=tuple(entries),
        catalog_issues=catalog_issues,
    )


def source_matched_connector_pin_evidence(
    observed: NetlistContract,
    coverage: ConnectorCoverageReport | None,
) -> dict[str, ConnectorMappedPinEvidence]:
    """Return complete interface mappings only when their evidence matches this netlist."""
    if coverage is None or coverage.interface_catalog_sha256 is None:
        return {}

    nets_by_pin: dict[str, set[str]] = {}
    for net, pins in observed.nets.items():
        for pin in pins:
            nets_by_pin.setdefault(pin, set()).add(net)

    result: dict[str, ConnectorMappedPinEvidence] = {}
    for entry in coverage.entries:
        if entry.status != "COVERED" or entry.interface_id is None:
            continue
        component_pin_numbers = observed.component_pin_numbers.get(entry.reference)
        if component_pin_numbers is None or len(component_pin_numbers) != len(
            set(component_pin_numbers)
        ):
            continue
        component_pin_set = set(component_pin_numbers)
        mapped_component_pins = tuple(entry.interface_pin_map.values())
        if len(mapped_component_pins) != len(set(mapped_component_pins)) or set(
            mapped_component_pins
        ) & set(entry.unlisted_pin_reasons):
            continue

        accounted_pins = set(mapped_component_pins) | set(entry.unlisted_pin_reasons)
        if component_pin_set != accounted_pins:
            continue
        if len(entry.mapped_pins) != len(entry.interface_pin_map) or {
            item.interface_pin_number for item in entry.mapped_pins
        } != set(entry.interface_pin_map):
            continue

        source_matches = True
        for item in entry.mapped_pins:
            component_reference, separator, component_pin_number = item.component_pin.rpartition(
                "."
            )
            if (
                not separator
                or component_reference != entry.reference
                or entry.interface_pin_map.get(item.interface_pin_number) != component_pin_number
                or component_pin_number not in component_pin_set
                or observed.pin_functions.get(item.component_pin) != item.symbol_function
                or tuple(sorted(nets_by_pin.get(item.component_pin, ()))) != item.nets
            ):
                source_matches = False
                break
        if not source_matches:
            continue
        result.update({item.component_pin: item for item in entry.mapped_pins})
    return result


def source_matched_connector_peer_assignment_groups(
    observed: NetlistContract,
    coverage: ConnectorCoverageReport | None,
) -> dict[str, tuple[str, str]]:
    """Return reviewed comparison scopes only when their connector maps still match."""
    if coverage is None:
        return {}
    pin_evidence = source_matched_connector_pin_evidence(observed, coverage)
    result: dict[str, tuple[str, str]] = {}
    for entry in coverage.entries:
        if (
            entry.status != "COVERED"
            or entry.interface_id is None
            or entry.peer_assignment_group is None
            or entry.peer_assignment_basis is None
            or not entry.mapped_pins
        ):
            continue
        if all(pin_evidence.get(pin.component_pin) == pin for pin in entry.mapped_pins):
            result[entry.reference] = (
                entry.peer_assignment_group,
                entry.peer_assignment_basis,
            )
    return result
