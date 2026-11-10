"""Source-matched power contacts shared by connector peer heuristics."""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations

from .connector_coverage import (
    source_matched_connector_peer_assignment_groups,
    source_matched_connector_pin_evidence,
)
from .connector_coverage_models import (
    ConnectorCoverageReport,
    ConnectorMappedPinEvidence,
    ConnectorMappedPinEvidenceByComponentPin,
)
from .connector_identity import connector_power_function_key, pin_function_is_generic
from .design_lint_types import Candidate
from .netlist_contract_models import NetlistContract

_UNCLASSIFIED_ROLES = frozenset({None, "other"})


@dataclass(frozen=True, slots=True)
class ReviewedPeerPowerContactPair:
    """Current map and netlist evidence shared by reviewed-peer predicates."""

    group: str
    group_basis: tuple[str, ...]
    references: tuple[str, str]
    symbols: tuple[str, str]
    values: tuple[str, str]
    footprints: tuple[str, str]
    interface_signal: str
    voltage_domain: str
    pins: tuple[ConnectorMappedPinEvidence, ConnectorMappedPinEvidence]
    electrical_types: tuple[str, str]
    native_functions: tuple[str, str]
    power_categories: tuple[str | None, str | None]
    classification: str


def reviewed_peer_power_contact_pairs(
    observed: NetlistContract,
    coverage: ConnectorCoverageReport | None,
    *,
    electrical_types: frozenset[str],
) -> tuple[ReviewedPeerPowerContactPair, ...]:
    """Return exact mapped power contacts in unlike reviewed peer pairs."""
    if coverage is None or coverage.status != "COMPLETE":
        return ()

    mapped_pins = source_matched_connector_pin_evidence(observed, coverage)
    peer_scopes = source_matched_connector_peer_assignment_groups(observed, coverage)
    entries_by_reference = {
        entry.reference.casefold(): entry for entry in coverage.entries if entry.status == "COVERED"
    }
    functions = {pin.casefold(): value for pin, value in observed.pin_functions.items()}
    native_electrical_types = {
        pin.casefold(): value.strip().casefold()
        for pin, value in observed.pin_electrical_types.items()
    }
    allowed_electrical_types = frozenset(item.strip().casefold() for item in electrical_types)
    dnp = {reference.casefold() for reference in observed.dnp_components}
    grouped_references: dict[str, list[str]] = {}
    group_names: dict[str, str] = {}
    group_bases: dict[str, set[str]] = {}
    for reference, scope in peer_scopes.items():
        reference_key = reference.casefold()
        if reference_key in dnp or reference_key not in entries_by_reference:
            continue
        group_key = scope.group.casefold()
        grouped_references.setdefault(group_key, []).append(reference)
        group_names[group_key] = scope.group
        group_bases.setdefault(group_key, set()).add(scope.basis)

    pairs: list[ReviewedPeerPowerContactPair] = []
    for group_key, references in sorted(grouped_references.items()):
        peers = tuple(sorted(set(references), key=lambda item: (item.casefold(), item)))
        for first, second in combinations(peers, 2):
            first_component = observed.components.get(first)
            second_component = observed.components.get(second)
            first_symbol = observed.component_symbols.get(first)
            second_symbol = observed.component_symbols.get(second)
            first_entry = entries_by_reference[first.casefold()]
            second_entry = entries_by_reference[second.casefold()]
            if (
                first_component is None
                or second_component is None
                or first_symbol is None
                or second_symbol is None
                or first_symbol.casefold() == second_symbol.casefold()
                or first_component.part_id
                or second_component.part_id
                or not first_component.value.strip()
                or not second_component.value.strip()
                or not first_component.footprint.strip()
                or not second_component.footprint.strip()
                or (
                    first_component.value.strip().casefold()
                    == second_component.value.strip().casefold()
                    and first_component.footprint.strip().casefold()
                    == second_component.footprint.strip().casefold()
                )
                or first_entry.interface_id is None
                or second_entry.interface_id is None
            ):
                continue

            first_pins = _eligible_reviewed_peer_power_contacts(
                mapped_pins,
                functions,
                native_electrical_types,
                first,
                allowed_electrical_types,
            )
            second_pins = _eligible_reviewed_peer_power_contacts(
                mapped_pins,
                functions,
                native_electrical_types,
                second,
                allowed_electrical_types,
            )
            for signal_domain in sorted(first_pins.keys() & second_pins.keys()):
                left, right = first_pins[signal_domain], second_pins[signal_domain]
                if len(left) != 1 or len(right) != 1:
                    continue
                left_pin, right_pin = left[0], right[0]
                native_functions = (
                    functions.get(left_pin.component_pin.casefold(), ""),
                    functions.get(right_pin.component_pin.casefold(), ""),
                )
                categories: tuple[str | None, str | None] = (
                    connector_power_function_key(native_functions[0])
                    if native_functions[0]
                    else None,
                    connector_power_function_key(native_functions[1])
                    if native_functions[1]
                    else None,
                )
                if (
                    left_pin.role in _UNCLASSIFIED_ROLES
                    and right_pin.role in _UNCLASSIFIED_ROLES
                    and all(pin_function_is_generic(function) for function in native_functions)
                ):
                    classification = "generic power inputs"
                elif left_pin.role == right_pin.role == "supply":
                    if categories[0] == categories[1]:
                        # Same-category and generic mapped supplies have a more
                        # direct source in the repeated-function scan.
                        continue
                    classification = (
                        "named power contacts"
                        if all(category is not None for category in categories)
                        else "mapped power contacts"
                    )
                else:
                    continue
                pairs.append(
                    ReviewedPeerPowerContactPair(
                        group=group_names[group_key],
                        group_basis=tuple(
                            sorted(group_bases[group_key], key=lambda item: (item.casefold(), item))
                        ),
                        references=(first, second),
                        symbols=(first_symbol, second_symbol),
                        values=(first_component.value.strip(), second_component.value.strip()),
                        footprints=(
                            first_component.footprint.strip(),
                            second_component.footprint.strip(),
                        ),
                        interface_signal=left_pin.interface_signal,
                        voltage_domain=left_pin.voltage_domain or "",
                        pins=(left_pin, right_pin),
                        electrical_types=(
                            native_electrical_types[left_pin.component_pin.casefold()],
                            native_electrical_types[right_pin.component_pin.casefold()],
                        ),
                        native_functions=native_functions,
                        power_categories=categories,
                        classification=classification,
                    )
                )
    return tuple(pairs)


def reviewed_peer_power_pair_evidence(
    pair: ReviewedPeerPowerContactPair,
    assignments: tuple[str, str],
) -> dict[str, tuple[str, ...]]:
    """Build stable source evidence shared by peer power-contact findings."""
    evidence = {
        "peer_assignment_group": (pair.group,),
        "peer_assignment_basis": pair.group_basis,
        "connectors": tuple(sorted(pair.references, key=lambda item: (item.casefold(), item))),
        "symbols": tuple(sorted(pair.symbols, key=lambda item: (item.casefold(), item))),
        "values": tuple(sorted(pair.values, key=lambda item: (item.casefold(), item))),
        "footprints": tuple(sorted(pair.footprints, key=lambda item: (item.casefold(), item))),
        "interface_signals": (pair.interface_signal,),
        "voltage_domains": (pair.voltage_domain,),
        "assignments": tuple(sorted(assignments, key=lambda item: (item.casefold(), item))),
    }
    if pair.classification != "generic power inputs":
        evidence["native_pin_functions"] = tuple(
            sorted(
                (
                    f"{pin.component_pin}={function or '<unnamed>'}"
                    for pin, function in zip(pair.pins, pair.native_functions, strict=True)
                ),
                key=lambda item: (item.casefold(), item),
            )
        )
        evidence["power_role_categories"] = tuple(
            sorted(
                {category for category in pair.power_categories if category is not None},
                key=lambda item: (item.casefold(), item),
            )
        )
    return evidence


def sort_reviewed_peer_power_candidates(
    candidates: list[Candidate],
) -> tuple[Candidate, ...]:
    """Return source-order-independent peer findings."""
    return tuple(
        sorted(
            candidates,
            key=lambda item: (
                item.subject.casefold(),
                item.subject,
                tuple(sorted(item.evidence)),
            ),
        )
    )


def _eligible_reviewed_peer_power_contacts(
    mapped_pins: ConnectorMappedPinEvidenceByComponentPin,
    functions: dict[str, str],
    electrical_types: dict[str, str],
    reference: str,
    allowed_electrical_types: frozenset[str],
) -> dict[tuple[str, str], list[ConnectorMappedPinEvidence]]:
    """Index eligible current power contacts by authored signal and domain."""
    found: dict[tuple[str, str], list[ConnectorMappedPinEvidence]] = {}
    for pin in mapped_pins.values():
        if pin.component_pin.rsplit(".", 1)[0].casefold() != reference.casefold():
            continue
        function = functions.get(pin.component_pin.casefold())
        generic_function = pin_function_is_generic(function)
        named_power_function = (
            not generic_function and connector_power_function_key(function or "") is not None
        )
        if (
            pin.role not in _UNCLASSIFIED_ROLES | {"supply"}
            or pin.voltage_domain is None
            or not pin.interface_signal.strip()
            or electrical_types.get(pin.component_pin.casefold()) not in allowed_electrical_types
            or not (
                (pin.role in _UNCLASSIFIED_ROLES and generic_function)
                or (pin.role == "supply" and (generic_function or named_power_function))
            )
        ):
            continue
        key = (pin.interface_signal.casefold(), pin.voltage_domain.casefold())
        found.setdefault(key, []).append(pin)
    return found
