"""Review power-input contacts across source-reviewed connector peers."""

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
from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate
from .netlist_contract_models import NetlistContract

RULE_ID: DesignLintRuleId = "connector.reviewed_peer_power_input_split"
PASSIVE_OPEN_RULE_ID: DesignLintRuleId = "connector.reviewed_peer_passive_power_input_open"
_UNCLASSIFIED_ROLES = frozenset({None, "other"})
_POWER_INPUT_ELECTRICAL_TYPES = frozenset({"power_in", "passive"})


@dataclass(frozen=True, slots=True)
class _ReviewedPeerPowerInputPair:
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


def reviewed_peer_power_input_split_candidates(
    observed: NetlistContract,
    coverage: ConnectorCoverageReport | None,
) -> tuple[Candidate, ...]:
    """Find mapped power contacts split across unlike reviewed peers.

    A matching interface signal and voltage domain are review clues, not a
    requirement to join the power nets. Generic unclassified contacts and
    source-mapped supply contacts with unlike named native functions are
    separate evidence classes; same-category named contacts stay with the
    repeated-function check.
    """
    candidates: list[Candidate] = []
    for pair in _reviewed_peer_power_input_pairs(observed, coverage):
        left, right = pair.pins
        if (
            len(left.nets) != 1
            or len(right.nets) != 1
            or left.nets[0].casefold() == right.nets[0].casefold()
        ):
            continue
        assignments = (
            f"{left.component_pin}={left.nets[0]}",
            f"{right.component_pin}={right.nets[0]}",
        )
        candidates.append(
            Candidate(
                rule_id=RULE_ID,
                subject=(
                    f"{pair.group}: {pair.interface_signal} ({pair.voltage_domain}) "
                    f"{pair.classification} use separate nets"
                ),
                message=_finding_message(pair),
                evidence=_pair_evidence(pair, assignments),
            )
        )
    return _sorted_candidates(candidates)


def reviewed_peer_passive_power_input_open_candidates(
    observed: NetlistContract,
    coverage: ConnectorCoverageReport | None,
) -> tuple[Candidate, ...]:
    """Review an open generic passive contact beside an assigned reviewed peer.

    Native ``power_in`` contacts retain their existing unconnected-pin rule.
    This predicate adds the mapped context needed for generic passive contacts
    whose role is still unclassified in the project pin map.
    """
    candidates: list[Candidate] = []
    for pair in _reviewed_peer_power_input_pairs(observed, coverage):
        for opened_index, assigned_index in ((0, 1), (1, 0)):
            opened = pair.pins[opened_index]
            assigned = pair.pins[assigned_index]
            if (
                pair.electrical_types[opened_index] != "passive"
                or opened.role is not None
                or assigned.role is not None
                or opened.nets
                or opened.unconnected_reason is not None
                or len(assigned.nets) != 1
            ):
                continue
            assignments = (
                f"{opened.component_pin}=<unassigned>",
                f"{assigned.component_pin}={assigned.nets[0]}",
            )
            candidates.append(
                Candidate(
                    rule_id=PASSIVE_OPEN_RULE_ID,
                    subject=(
                        f"{pair.group}: {pair.interface_signal} ({pair.voltage_domain}) "
                        "generic passive power-input contact is open beside its peer"
                    ),
                    message=(
                        "Unlike connector symbols in this source-reviewed peer group map "
                        "generic contacts to the same interface signal and voltage domain, "
                        "but one passive contact has no net while its peer has one assigned "
                        "net. Review whether the open is intentional or a connection is "
                        "missing. The map does not require tying the contacts, select a target "
                        "net, or prove PCB copper continuity."
                    ),
                    evidence=_pair_evidence(pair, assignments),
                )
            )
    return _sorted_candidates(candidates)


def _reviewed_peer_power_input_pairs(
    observed: NetlistContract,
    coverage: ConnectorCoverageReport | None,
) -> tuple[_ReviewedPeerPowerInputPair, ...]:
    """Return exact mapped power contacts in unlike reviewed peer pairs."""
    if coverage is None or coverage.status != "COMPLETE":
        return ()

    mapped_pins = source_matched_connector_pin_evidence(observed, coverage)
    peer_scopes = source_matched_connector_peer_assignment_groups(observed, coverage)
    entries_by_reference = {
        entry.reference.casefold(): entry for entry in coverage.entries if entry.status == "COVERED"
    }
    functions = {pin.casefold(): value for pin, value in observed.pin_functions.items()}
    electrical_types = {
        pin.casefold(): value.strip().casefold()
        for pin, value in observed.pin_electrical_types.items()
    }
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

    pairs: list[_ReviewedPeerPowerInputPair] = []
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

            first_pins = _eligible_power_inputs(mapped_pins, functions, electrical_types, first)
            second_pins = _eligible_power_inputs(mapped_pins, functions, electrical_types, second)
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
                        # Same named category and generic mapped supplies already
                        # have a more direct source in the repeated-function scan.
                        continue
                    classification = (
                        "named power contacts"
                        if all(category is not None for category in categories)
                        else "mapped power contacts"
                    )
                else:
                    continue
                pairs.append(
                    _ReviewedPeerPowerInputPair(
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
                            electrical_types[left_pin.component_pin.casefold()],
                            electrical_types[right_pin.component_pin.casefold()],
                        ),
                        native_functions=native_functions,
                        power_categories=categories,
                        classification=classification,
                    )
                )
    return tuple(pairs)


def _eligible_power_inputs(
    mapped_pins: ConnectorMappedPinEvidenceByComponentPin,
    functions: dict[str, str],
    electrical_types: dict[str, str],
    reference: str,
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
            or electrical_types.get(pin.component_pin.casefold())
            not in _POWER_INPUT_ELECTRICAL_TYPES
            or not (
                (pin.role in _UNCLASSIFIED_ROLES and generic_function)
                or (pin.role == "supply" and (generic_function or named_power_function))
            )
        ):
            continue
        key = (pin.interface_signal.casefold(), pin.voltage_domain.casefold())
        found.setdefault(key, []).append(pin)
    return found


def _pair_evidence(
    pair: _ReviewedPeerPowerInputPair,
    assignments: tuple[str, str],
) -> dict[str, tuple[str, ...]]:
    """Build stable source evidence shared by peer power-input findings."""
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


def _finding_message(pair: _ReviewedPeerPowerInputPair) -> str:
    """Describe the evidence class without turning the map into a net requirement."""
    if pair.classification == "generic power inputs":
        contact = "generic native power contacts (power_in or passive)"
    elif pair.classification == "named power contacts":
        contact = "named native power contacts with different recognized supply functions"
    else:
        contact = "mapped power contacts with one generic and one named supply function"
    return (
        "Unlike connector symbols in this source-reviewed peer group map "
        f"{contact} to the same interface signal and voltage domain, but assign them to "
        "different nets. Review whether separate sources, filtering, or isolation are "
        "intentional. The map does not prove these nets should be joined or that PCB copper "
        "is continuous."
    )


def _sorted_candidates(candidates: list[Candidate]) -> tuple[Candidate, ...]:
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
