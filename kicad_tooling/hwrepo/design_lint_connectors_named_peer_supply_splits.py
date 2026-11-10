"""Review named mapped peer supplies in one domain assigned to split nets."""

from __future__ import annotations

from collections import defaultdict

from .connector_coverage import (
    source_matched_connector_pin_evidence,
    source_matched_connector_supply_comparison_groups,
)
from .connector_coverage_models import ConnectorCoverageReport
from .connector_identity import (
    connector_power_function_key,
    is_return_function,
    pin_function_is_generic,
)
from .design_lint_connector_named_peer_supply_split_candidate_evidence import (
    MappedNamedPeerSupplySplit,
    MappedNamedPeerSupplySplitAssignment,
    MappedNamedPeerSupplySplitCandidate,
    MappedNamedPeerSupplySplitFindingEvidence,
    source_matched_legacy_supply_peer_group_pins,
)
from .design_lint_types import Candidate
from .netlist_contract_models import NetlistContract


def mapped_named_peer_supply_split_net_candidates(
    observed: NetlistContract,
    coverage: ConnectorCoverageReport | None,
) -> tuple[Candidate, ...]:
    """Review current mapped supply peers with uncategorized names on separate nets.

    Native functions already handled by generic, repeated-function, or known
    power-category checks stay with those rules. A reviewed supply group and
    exact voltage domain define review scope; neither requires common nets.
    """
    if coverage is None or coverage.status != "COMPLETE" or not coverage.interface_catalog_sha256:
        return ()

    mapped_pins = source_matched_connector_pin_evidence(observed, coverage)
    supply_scopes = source_matched_connector_supply_comparison_groups(observed, coverage)
    dnp_references = {reference.casefold() for reference in observed.dnp_components}
    participants_by_domain: dict[str, set[str]] = defaultdict(set)
    eligible_by_scope_domain: dict[tuple[str, str], list[MappedNamedPeerSupplySplitAssignment]] = (
        defaultdict(list)
    )
    for component_pin, mapped in sorted(mapped_pins.items()):
        reference, separator, _pin_number = component_pin.rpartition(".")
        if (
            not separator
            or reference.casefold() in dnp_references
            or mapped.role != "supply"
            or not mapped.voltage_domain
        ):
            continue
        participants_by_domain[mapped.voltage_domain].add(reference)
        scope = supply_scopes.get(reference)
        if scope is None:
            continue
        function = mapped.symbol_function
        if (
            mapped.unconnected_reason is not None
            or len(mapped.nets) != 1
            or function is None
            or pin_function_is_generic(function)
            or connector_power_function_key(function) is not None
            or is_return_function(function)
        ):
            continue
        eligible_by_scope_domain[(scope.group, mapped.voltage_domain)].append(
            MappedNamedPeerSupplySplitAssignment(
                component_pin=component_pin,
                native_net=mapped.nets[0],
                voltage_domain=mapped.voltage_domain,
                mapped_pin=mapped,
            )
        )

    legacy_supply_pins = source_matched_legacy_supply_peer_group_pins(
        observed,
        coverage,
        mapped_pins,
        supply_scopes,
    )
    candidates: list[Candidate] = []
    for (group, domain), assignments in sorted(
        eligible_by_scope_domain.items(),
        key=lambda item: (item[0][0].casefold(), item[0][1].casefold(), *item[0]),
    ):
        if any(
            reference not in supply_scopes for reference in participants_by_domain.get(domain, ())
        ):
            continue
        ordered = tuple(sorted(assignments, key=lambda item: item.component_pin))
        references = {item.component_pin.rpartition(".")[0] for item in ordered}
        if (
            len(references) < 2
            or len({item.native_net for item in ordered}) < 2
            or any(item.component_pin in legacy_supply_pins for item in ordered)
        ):
            continue
        split = MappedNamedPeerSupplySplit(
            supply_comparison_group=group,
            voltage_domain=domain,
            assignments=ordered,
        )
        source = MappedNamedPeerSupplySplitFindingEvidence(
            observed=observed,
            coverage=coverage,
            split=split,
        )
        candidates.append(
            MappedNamedPeerSupplySplitCandidate.from_source_evidence(
                source,
                subject=(
                    f"{group}: mapped peer supplies in voltage domain {domain} "
                    "use separate native nets"
                ),
                message=(
                    "Complete, source-matched connector entries place these fitted contacts in "
                    f"one supply_comparison_group ({group}) and voltage_domain ({domain}), "
                    "but their exact native nets are separate. Review whether source selection, "
                    "filtering, or isolation is intentional or whether the maps need correction. "
                    "Group and domain labels do not require common nets or prove PCB copper "
                    "continuity."
                ),
            )
        )
    return tuple(candidates)
