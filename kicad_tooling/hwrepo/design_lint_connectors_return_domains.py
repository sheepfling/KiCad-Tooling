"""Review source-mapped same-domain connector returns assigned to split nets."""

from __future__ import annotations

from collections import defaultdict

from .connector_coverage import source_matched_connector_pin_evidence
from .connector_coverage_models import ConnectorCoverageReport
from .design_lint_return_domain_split_candidate_evidence import (
    MappedReturnDomainSplit,
    MappedReturnDomainSplitAssignment,
    MappedReturnDomainSplitCandidate,
    MappedReturnDomainSplitFindingEvidence,
)
from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate
from .netlist_contract_models import NetlistContract

_SAME_DOMAIN_RETURNS_SPLIT: DesignLintRuleId = "connector.mapped_same_domain_return_split_nets"


def mapped_same_domain_return_split_net_candidates(
    observed: NetlistContract,
    coverage: ConnectorCoverageReport | None,
) -> tuple[Candidate, ...]:
    """Review same-domain mapped returns split across nets on one connector.

    A project map's exact return role and voltage-domain values are a review
    clue; they do not state that the contacts must be shorted together.
    """
    if coverage is None or coverage.status != "COMPLETE" or not coverage.interface_catalog_sha256:
        return ()

    dnp_references = {reference.casefold() for reference in observed.dnp_components}
    assignments_by_connector_domain: dict[
        tuple[str, str], list[MappedReturnDomainSplitAssignment]
    ] = defaultdict(list)
    for component_pin, mapped in sorted(
        source_matched_connector_pin_evidence(observed, coverage).items()
    ):
        reference, separator, _pin_number = component_pin.rpartition(".")
        if (
            not separator
            or reference.casefold() in dnp_references
            or mapped.role != "return"
            or not mapped.voltage_domain
            or mapped.unconnected_reason is not None
            or len(mapped.nets) != 1
        ):
            continue
        assignments_by_connector_domain[(reference, mapped.voltage_domain)].append(
            MappedReturnDomainSplitAssignment(
                component_pin=component_pin,
                native_net=mapped.nets[0],
                voltage_domain=mapped.voltage_domain,
                mapped_pin=mapped,
            )
        )

    candidates: list[Candidate] = []
    for (reference, voltage_domain), assignments in sorted(
        assignments_by_connector_domain.items(),
        key=lambda item: (
            item[0][0].casefold(),
            item[0][1].casefold(),
            item[0][0],
            item[0][1],
        ),
    ):
        ordered_assignments = tuple(sorted(assignments, key=lambda item: item.component_pin))
        if len({item.native_net for item in ordered_assignments}) < 2:
            continue
        split = MappedReturnDomainSplit(
            component_reference=reference,
            voltage_domain=voltage_domain,
            assignments=ordered_assignments,
        )
        source_evidence = MappedReturnDomainSplitFindingEvidence(
            observed=observed,
            coverage=coverage,
            split=split,
        )
        candidates.append(
            MappedReturnDomainSplitCandidate.from_source_evidence(
                source_evidence,
                subject=(
                    f"{reference}: mapped return contacts in voltage domain "
                    f"{voltage_domain} use separate native nets"
                ),
                message=(
                    "Complete, source-matched connector entries classify these fitted return "
                    f"contacts in one voltage_domain ({voltage_domain}), but their native nets "
                    "are separate. Review whether the split is intentional or whether the map "
                    "needs correction. A shared domain label does not require common nets or "
                    "prove equal potential, an electrical defect, or PCB copper continuity."
                ),
            )
        )
    return tuple(candidates)
