"""Review unanchored connector alias splits when comparison scope is absent."""

from __future__ import annotations

from collections import defaultdict

from .connector_coverage import source_matched_connector_pin_evidence
from .connector_coverage_models import (
    ConnectorCoverageEntry,
    ConnectorCoverageReport,
    ConnectorMappedPinEvidence,
)
from .connector_footprint_peer_pin_types import (
    ConnectorFootprintPeerPinDivergence,
    ConnectorFootprintPeerPinScan,
)
from .connector_identity import pin_function_is_generic
from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate
from .models import NetlistContract

RULE_ID: DesignLintRuleId = "connector.footprint_peer_unanchored_scope_unreviewed"


def unreviewed_unanchored_connector_alias_scope(
    scan: ConnectorFootprintPeerPinScan,
    observed: NetlistContract,
    coverage: ConnectorCoverageReport | None,
) -> tuple[Candidate, ...]:
    """Prompt once per alias cohort with current pin maps but no peer decision."""
    if (
        coverage is None
        or coverage.status != "COMPLETE"
        or coverage.inventory_review_basis is None
        or coverage.interface_catalog_sha256 is None
    ):
        return ()

    current_pin_evidence = source_matched_connector_pin_evidence(observed, coverage)
    entries_by_reference: dict[str, list[ConnectorCoverageEntry]] = defaultdict(list)
    for entry in coverage.entries:
        entries_by_reference[entry.reference.casefold()].append(entry)

    cohorts: dict[
        tuple[str, str, tuple[str, ...], tuple[str, ...]],
        list[ConnectorFootprintPeerPinDivergence],
    ] = defaultdict(list)
    for divergence in scan.unanchored_divergences:
        if (
            divergence.peer_assignment_group is not None
            or divergence.common_anchor_pin_numbers
            or not pin_function_is_generic(divergence.pin_function)
            or len(divergence.assignments) < 2
            or any(len(nets) != 1 for nets in divergence.assignments.values())
            or len({nets[0] for nets in divergence.assignments.values()}) < 2
        ):
            continue
        references = tuple(
            sorted(
                {pin.rsplit(".", 1)[0] for pin in divergence.assignments},
                key=lambda reference: (reference.casefold(), reference),
            )
        )
        if not _all_references_have_current_unscoped_maps(
            references,
            entries_by_reference,
            current_pin_evidence,
        ):
            continue
        cohort_key = (
            divergence.value.casefold(),
            divergence.footprint.casefold(),
            tuple(reference.casefold() for reference in references),
            tuple(symbol.casefold() for symbol in divergence.symbols),
        )
        cohorts[cohort_key].append(divergence)

    return tuple(
        _candidate(divergences, coverage, entries_by_reference)
        for _, divergences in sorted(cohorts.items())
    )


def _all_references_have_current_unscoped_maps(
    references: tuple[str, ...],
    entries_by_reference: dict[str, list[ConnectorCoverageEntry]],
    current_pin_evidence: dict[str, ConnectorMappedPinEvidence],
) -> bool:
    for reference in references:
        matches = entries_by_reference.get(reference.casefold(), ())
        if len(matches) != 1:
            return False
        entry = matches[0]
        if (
            entry.status != "COVERED"
            or entry.interface_id is None
            or entry.basis is None
            or entry.peer_assignment_group is not None
            or entry.peer_assignment_basis is not None
            or not entry.mapped_pins
            or any(current_pin_evidence.get(pin.component_pin) != pin for pin in entry.mapped_pins)
        ):
            return False
    return True


def _candidate(
    divergences: list[ConnectorFootprintPeerPinDivergence],
    coverage: ConnectorCoverageReport,
    entries_by_reference: dict[str, list[ConnectorCoverageEntry]],
) -> Candidate:
    first = divergences[0]
    references = tuple(
        sorted(
            {pin.rsplit(".", 1)[0] for pin in first.assignments},
            key=lambda reference: (reference.casefold(), reference),
        )
    )
    interface_reviews = tuple(
        f"{reference}: {entries_by_reference[reference.casefold()][0].interface_id}; "
        f"{entries_by_reference[reference.casefold()][0].basis}"
        for reference in references
    )
    pin_assignments = tuple(
        f"pin {item.pin_number}: "
        + "; ".join(
            f"{pin}={nets[0]}"
            for pin, nets in sorted(
                item.assignments.items(), key=lambda pair: (pair[0].casefold(), pair[0])
            )
        )
        for item in sorted(
            divergences,
            key=lambda item: (item.pin_number.casefold(), item.pin_number),
        )
    )
    evidence: dict[str, tuple[str, ...]] = {
        "value": (first.value,),
        "footprint": (first.footprint,),
        "references": references,
        "symbols": first.symbols,
        "unanchored_generic_pin_numbers": tuple(
            item.pin_number
            for item in sorted(
                divergences,
                key=lambda item: (item.pin_number.casefold(), item.pin_number),
            )
        ),
        "pin_assignments": pin_assignments,
        "interface_reviews": interface_reviews,
        "inventory_review_basis": (coverage.inventory_review_basis or "",),
        "interface_catalog_sha256": (str(coverage.interface_catalog_sha256),),
    }
    if coverage.interface_catalog_path is not None:
        evidence["interface_catalog_path"] = (str(coverage.interface_catalog_path),)
    return Candidate(
        rule_id=RULE_ID,
        subject=(
            f"{first.value} [{first.footprint}]: unanchored connector aliases lack a reviewed peer scope"
        ),
        message=(
            "Fitted connector aliases have source-matched complete pin maps and divergent generic "
            "contacts without a common-net anchor, but no reviewed peer-assignment scope. Review "
            "whether these references should be compared as peers or remain separate. A peer group "
            "only scopes comparison; it does not require matching nets or joining the contacts."
        ),
        evidence=evidence,
    )
