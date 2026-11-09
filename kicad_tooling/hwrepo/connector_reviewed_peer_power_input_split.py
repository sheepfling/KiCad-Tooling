"""Review mapped power-input contacts split across unlike connector peers."""

from __future__ import annotations

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
from .connector_identity import pin_function_is_generic
from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate
from .netlist_contract_models import NetlistContract

RULE_ID: DesignLintRuleId = "connector.reviewed_peer_power_input_split"
_UNCLASSIFIED_ROLES = frozenset({None, "other"})


def reviewed_peer_power_input_split_candidates(
    observed: NetlistContract,
    coverage: ConnectorCoverageReport | None,
) -> tuple[Candidate, ...]:
    """Find mapped generic power inputs split across source-reviewed connector peers.

    This rule is deliberately limited to complete, current connector reviews. It
    only compares unlike, symbol-distinct connectors outside the existing exact
    symbol, PART_ID, and value/footprint peer scopes. A matching interface signal
    and voltage domain are review clues, not a requirement to join power nets.
    """
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

    candidates: list[Candidate] = []
    for group_key, references in sorted(grouped_references.items()):
        peers = tuple(sorted(set(references), key=lambda item: (item.casefold(), item)))
        if len(peers) < 2:
            continue
        for first, second in combinations(peers, 2):
            first_entry = entries_by_reference[first.casefold()]
            second_entry = entries_by_reference[second.casefold()]
            first_component = observed.components.get(first)
            second_component = observed.components.get(second)
            first_symbol = observed.component_symbols.get(first)
            second_symbol = observed.component_symbols.get(second)
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

            first_pins = _eligible_power_inputs(
                mapped_pins,
                functions,
                electrical_types,
                first,
            )
            second_pins = _eligible_power_inputs(
                mapped_pins,
                functions,
                electrical_types,
                second,
            )
            for signal_domain in sorted(first_pins.keys() & second_pins.keys()):
                left = first_pins[signal_domain]
                right = second_pins[signal_domain]
                if len(left) != 1 or len(right) != 1:
                    continue
                left_pin, right_pin = left[0], right[0]
                if (
                    len(left_pin.nets) != 1
                    or len(right_pin.nets) != 1
                    or left_pin.nets[0].casefold() == right_pin.nets[0].casefold()
                ):
                    continue
                voltage_domain = left_pin.voltage_domain or ""
                assignments = tuple(
                    sorted(
                        (
                            f"{left_pin.component_pin}={left_pin.nets[0]}",
                            f"{right_pin.component_pin}={right_pin.nets[0]}",
                        ),
                        key=lambda item: (item.casefold(), item),
                    )
                )
                candidates.append(
                    Candidate(
                        rule_id=RULE_ID,
                        subject=(
                            f"{group_names[group_key]}: {left_pin.interface_signal} "
                            f"({voltage_domain}) "
                            "generic power inputs use separate nets"
                        ),
                        message=(
                            "Unlike connector symbols in this source-reviewed peer group map a "
                            "generic native power_in contact to the same interface signal and "
                            "voltage domain, but assign it to different nets. Review whether "
                            "separate sources, filtering, or isolation are intentional. The map "
                            "does not prove these nets should be joined or that PCB copper is "
                            "continuous."
                        ),
                        evidence={
                            "peer_assignment_group": (group_names[group_key],),
                            "peer_assignment_basis": tuple(
                                sorted(
                                    group_bases[group_key], key=lambda item: (item.casefold(), item)
                                )
                            ),
                            "connectors": tuple(sorted((first, second), key=str.casefold)),
                            "symbols": tuple(
                                sorted((first_symbol, second_symbol), key=str.casefold)
                            ),
                            "values": tuple(
                                sorted(
                                    (first_component.value.strip(), second_component.value.strip()),
                                    key=lambda item: (item.casefold(), item),
                                )
                            ),
                            "footprints": tuple(
                                sorted(
                                    (
                                        first_component.footprint.strip(),
                                        second_component.footprint.strip(),
                                    ),
                                    key=lambda item: (item.casefold(), item),
                                )
                            ),
                            "interface_signals": (left_pin.interface_signal,),
                            "voltage_domains": (left_pin.voltage_domain or "",),
                            "assignments": assignments,
                        },
                    )
                )
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


def _eligible_power_inputs(
    mapped_pins: ConnectorMappedPinEvidenceByComponentPin,
    functions: dict[str, str],
    electrical_types: dict[str, str],
    reference: str,
) -> dict[tuple[str, str], list[ConnectorMappedPinEvidence]]:
    """Index current generic power inputs by authored interface signal and domain."""
    found: dict[tuple[str, str], list[ConnectorMappedPinEvidence]] = {}
    for pin in mapped_pins.values():
        if pin.component_pin.rsplit(".", 1)[0].casefold() != reference.casefold():
            continue
        function = functions.get(pin.component_pin.casefold())
        if (
            pin.role not in _UNCLASSIFIED_ROLES
            or pin.voltage_domain is None
            or not pin.interface_signal.strip()
            or electrical_types.get(pin.component_pin.casefold()) != "power_in"
            or not pin_function_is_generic(function)
        ):
            continue
        key = (pin.interface_signal.casefold(), pin.voltage_domain.casefold())
        found.setdefault(key, []).append(pin)
    return found
