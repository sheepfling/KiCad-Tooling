"""Review named mapped peer returns in one voltage domain assigned to split nets."""

from __future__ import annotations

from collections import defaultdict

from .connector_coverage import (
    source_matched_connector_pin_evidence,
    source_matched_connector_return_comparison_groups,
)
from .connector_coverage_models import ConnectorCoverageReport
from .connector_identity import is_return_function, pin_function_is_generic
from .design_lint_connector_named_peer_return_split_candidate_evidence import (
    MappedNamedPeerReturnSplit,
    MappedNamedPeerReturnSplitCandidate,
    MappedNamedPeerReturnSplitFindingEvidence,
    source_matched_legacy_return_peer_group_pins,
)
from .design_lint_return_domain_split_candidate_evidence import (
    MappedReturnDomainSplitAssignment,
)
from .design_lint_types import Candidate
from .netlist_contract_models import NetlistContract


def mapped_named_peer_return_split_net_candidates(
    observed: NetlistContract,
    coverage: ConnectorCoverageReport | None,
) -> tuple[Candidate, ...]:
    """Review explicitly grouped same-domain mapped returns with distinct native nets.

    The rule handles named native functions that the ordinary repeated-return
    comparison cannot classify as return peers. When that existing comparison
    already covers a pin, its candidate is retained and this rule stays quiet.
    """
    if coverage is None or coverage.status != "COMPLETE" or not coverage.interface_catalog_sha256:
        return ()

    mapped_pins = source_matched_connector_pin_evidence(observed, coverage)
    return_scopes = source_matched_connector_return_comparison_groups(observed, coverage)
    dnp_references = {reference.casefold() for reference in observed.dnp_components}
    participants_by_domain: dict[str, set[str]] = defaultdict(set)
    eligible_by_scope_domain: dict[tuple[str, str], list[MappedReturnDomainSplitAssignment]] = (
        defaultdict(list)
    )
    for component_pin, mapped in sorted(mapped_pins.items()):
        reference, separator, _pin_number = component_pin.rpartition(".")
        if (
            not separator
            or reference.casefold() in dnp_references
            or mapped.role != "return"
            or not mapped.voltage_domain
        ):
            continue
        participants_by_domain[mapped.voltage_domain].add(reference)
        scope = return_scopes.get(reference)
        if scope is None:
            continue
        function = mapped.symbol_function
        if (
            mapped.unconnected_reason is not None
            or len(mapped.nets) != 1
            or function is None
            or pin_function_is_generic(function)
            or is_return_function(function)
        ):
            continue
        eligible_by_scope_domain[(scope.group, mapped.voltage_domain)].append(
            MappedReturnDomainSplitAssignment(
                component_pin=component_pin,
                native_net=mapped.nets[0],
                voltage_domain=mapped.voltage_domain,
                mapped_pin=mapped,
            )
        )

    legacy_return_pins = source_matched_legacy_return_peer_group_pins(
        observed,
        coverage,
        mapped_pins,
        return_scopes,
    )
    candidates: list[Candidate] = []
    for (group, domain), assignments in sorted(
        eligible_by_scope_domain.items(),
        key=lambda item: (item[0][0].casefold(), item[0][1].casefold(), *item[0]),
    ):
        if any(
            reference not in return_scopes for reference in participants_by_domain.get(domain, ())
        ):
            continue
        ordered = tuple(sorted(assignments, key=lambda item: item.component_pin))
        references = {item.component_pin.rpartition(".")[0] for item in ordered}
        if (
            len(references) < 2
            or len({item.native_net for item in ordered}) < 2
            or any(item.component_pin in legacy_return_pins for item in ordered)
        ):
            continue
        split = MappedNamedPeerReturnSplit(
            return_comparison_group=group,
            voltage_domain=domain,
            assignments=ordered,
        )
        source = MappedNamedPeerReturnSplitFindingEvidence(
            observed=observed,
            coverage=coverage,
            split=split,
        )
        candidates.append(
            MappedNamedPeerReturnSplitCandidate.from_source_evidence(
                source,
                subject=(
                    f"{group}: mapped peer returns in voltage domain {domain} "
                    "use separate native nets"
                ),
                message=(
                    "Complete, source-matched connector entries place these fitted contacts in "
                    f"one return_comparison_group ({group}) and voltage_domain ({domain}), "
                    "but their exact native nets are separate. Review whether the split is "
                    "intentional or whether the map needs correction. Group and domain labels "
                    "do not require common nets or prove PCB copper continuity."
                ),
            )
        )
    return tuple(candidates)
