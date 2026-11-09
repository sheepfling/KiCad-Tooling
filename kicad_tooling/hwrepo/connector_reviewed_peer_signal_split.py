"""Review split mapped signals across source-reviewed connector peers."""

from __future__ import annotations

from collections import defaultdict

from .connector_coverage import (
    source_matched_connector_peer_assignment_groups,
    source_matched_connector_pin_evidence,
)
from .connector_coverage_models import ConnectorCoverageReport, ConnectorMappedPinEvidence
from .connector_identity import pin_function_is_generic
from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate
from .netlist_contract_models import NetlistContract

RULE_ID: DesignLintRuleId = "connector.reviewed_peer_signal_assignment_split"


def reviewed_peer_signal_assignment_splits(
    observed: NetlistContract,
    coverage: ConnectorCoverageReport | None,
) -> tuple[Candidate, ...]:
    """Review generic mapped signal pins split across unlike reviewed peers."""
    if (
        coverage is None
        or coverage.status != "COMPLETE"
        or coverage.interface_catalog_sha256 is None
    ):
        return ()

    dnp_references = {reference.casefold() for reference in observed.dnp_components}
    peer_scopes = source_matched_connector_peer_assignment_groups(observed, coverage)
    contacts: dict[
        tuple[str, str, str], dict[str, list[tuple[str, ConnectorMappedPinEvidence]]]
    ] = defaultdict(lambda: defaultdict(list))
    for component_pin, mapped in sorted(
        source_matched_connector_pin_evidence(observed, coverage).items()
    ):
        reference, separator, _pin_number = component_pin.rpartition(".")
        scope = peer_scopes.get(reference)
        if (
            not separator
            or scope is None
            or mapped.role != "signal"
            or mapped.voltage_domain is None
            or mapped.unconnected_reason is not None
            or reference.casefold() in dnp_references
            or not pin_function_is_generic(mapped.symbol_function)
            or len(mapped.nets) != 1
        ):
            continue
        key = (
            scope.group.casefold(),
            mapped.interface_signal.casefold(),
            mapped.voltage_domain.casefold(),
        )
        contacts[key][reference.casefold()].append((reference, mapped))

    candidates: list[Candidate] = []
    for (group_key, _signal_key, _domain_key), by_reference in sorted(contacts.items()):
        # A repeated contact inside one connector belongs to the existing rule.
        if len(by_reference) < 2 or any(len(items) != 1 for items in by_reference.values()):
            continue
        references = tuple(
            sorted(
                (items[0][0] for items in by_reference.values()),
                key=lambda value: (value.casefold(), value),
            )
        )
        symbols = {
            observed.component_symbols.get(reference, "").casefold() for reference in references
        }
        if "" in symbols or len(symbols) < 2:
            continue
        # Same-symbol assignment differences remain with existing connector rules.
        nets_by_symbol: dict[str, set[str]] = defaultdict(set)
        for reference in references:
            symbol = observed.component_symbols[reference].casefold()
            mapped = by_reference[reference.casefold()][0][1]
            nets_by_symbol[symbol].add(mapped.nets[0])
        if any(len(nets) > 1 for nets in nets_by_symbol.values()):
            continue

        assignments = tuple(
            sorted(
                ((reference, by_reference[reference.casefold()][0][1]) for reference in references),
                key=lambda item: (item[0].casefold(), item[0]),
            )
        )
        nets = tuple(
            sorted(
                {mapped.nets[0] for _reference, mapped in assignments},
                key=lambda value: (value.casefold(), value),
            )
        )
        if len(nets) < 2:
            continue

        scope_evidence = tuple(
            sorted(
                {
                    scope.basis
                    for reference, scope in peer_scopes.items()
                    if reference.casefold() in by_reference and scope.group.casefold() == group_key
                },
                key=lambda value: (value.casefold(), value),
            )
        )
        signal_name = min(
            (mapped.interface_signal for _reference, mapped in assignments),
            key=lambda value: (value.casefold(), value),
        )
        voltage_domain = min(
            (mapped.voltage_domain for _reference, mapped in assignments if mapped.voltage_domain),
            key=lambda value: (value.casefold(), value),
        )
        pins = tuple(
            sorted(
                (mapped.component_pin for _reference, mapped in assignments),
                key=lambda value: (value.casefold(), value),
            )
        )
        group_name = min(
            (
                scope.group
                for reference, scope in peer_scopes.items()
                if reference.casefold() in by_reference
            ),
            key=lambda value: (value.casefold(), value),
        )
        candidates.append(
            Candidate(
                rule_id=RULE_ID,
                subject=(
                    f"{group_name}: mapped peer signal {signal_name} ({voltage_domain}) "
                    f"spans native nets {', '.join(nets)}"
                ),
                message=(
                    "Unlike connector symbols in this source-reviewed peer group map generic "
                    "signal contacts to the same interface signal and voltage domain, but the "
                    "native netlist assigns them to different nets. Review whether distinct "
                    "routes or isolation are intentional. The peer map does not require direct "
                    "commoning and this check does not establish PCB copper continuity."
                ),
                evidence={
                    "component_reference": references,
                    "component_pin": pins,
                    "interface_signal": (signal_name,),
                    "interface_role": ("signal",),
                    "voltage_domain": (voltage_domain,),
                    "peer_assignment_group": (group_name,),
                    "peer_assignment_basis": scope_evidence,
                    "assigned_nets": nets,
                    "interface_catalog_sha256": (str(coverage.interface_catalog_sha256),),
                },
            )
        )
    return tuple(
        sorted(
            candidates,
            key=lambda item: (item.rule_id, item.subject.casefold(), item.subject),
        )
    )
