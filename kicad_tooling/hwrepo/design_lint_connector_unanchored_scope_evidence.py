"""Source-bound evidence for unanchored connector peer-scope findings."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from .connector_coverage import source_matched_connector_pin_evidence
from .connector_coverage_models import ConnectorCoverageEntry, ConnectorCoverageReport
from .connector_footprint_peer_pin_types import (
    ConnectorFootprintPeerPinDivergence,
    ConnectorFootprintPeerPinOpenOutlier,
    ConnectorFootprintPeerPinScan,
)
from .design_lint_connector_unanchored_source_evidence import (
    connector_footprint_peer_unanchored_references,
    validate_current_unanchored_peer_contacts,
)
from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate, CandidateEvidenceProjection
from .netlist_contract_models import NetlistContract

RULE_ID: DesignLintRuleId = "connector.footprint_peer_unanchored_scope_unreviewed"


def references_have_current_unscoped_maps(
    observed: NetlistContract,
    references: tuple[str, ...],
    coverage: ConnectorCoverageReport,
) -> bool:
    """Require one complete, source-matched interface map for every peer."""
    entries_by_reference: dict[str, list[ConnectorCoverageEntry]] = defaultdict(list)
    for entry in coverage.entries:
        entries_by_reference[entry.reference.casefold()].append(entry)
    current_pin_evidence = source_matched_connector_pin_evidence(observed, coverage)
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


@dataclass(frozen=True, slots=True)
class ConnectorUnanchoredPeerScopeEvidence:
    """Current native alias scan and complete coverage behind one scope prompt."""

    scan: ConnectorFootprintPeerPinScan
    observed: NetlistContract
    coverage: ConnectorCoverageReport
    divergences: tuple[ConnectorFootprintPeerPinDivergence, ...]
    partial_opens: tuple[ConnectorFootprintPeerPinOpenOutlier, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "divergences", tuple(self.divergences))
        object.__setattr__(self, "partial_opens", tuple(self.partial_opens))
        _validate_current_unanchored_scope_evidence(self)

    @classmethod
    def from_scan(
        cls,
        *,
        scan: ConnectorFootprintPeerPinScan,
        observed: NetlistContract,
        coverage: ConnectorCoverageReport,
        divergences: tuple[ConnectorFootprintPeerPinDivergence, ...],
        partial_opens: tuple[ConnectorFootprintPeerPinOpenOutlier, ...] = (),
    ) -> ConnectorUnanchoredPeerScopeEvidence:
        """Capture one selected alias cohort from the current peer scan."""
        return cls(
            scan=scan,
            observed=observed,
            coverage=coverage,
            divergences=divergences,
            partial_opens=partial_opens,
        )


def _validate_current_unanchored_scope_evidence(
    evidence: ConnectorUnanchoredPeerScopeEvidence,
) -> None:
    observed = evidence.scan.source.observed
    coverage = evidence.coverage
    if evidence.observed != observed:
        raise ValueError("Unanchored peer scope scan and observed netlist must be identical")
    if (
        coverage.status != "COMPLETE"
        or coverage.inventory_review_basis is None
        or coverage.interface_catalog_sha256 is None
    ):
        raise ValueError("Unanchored peer scope requires complete reviewed connector coverage")
    references, group_references = validate_current_unanchored_peer_contacts(
        scan=evidence.scan,
        divergences=evidence.divergences,
        partial_opens=evidence.partial_opens,
    )
    if tuple(reference.casefold() for reference in references) != tuple(
        reference.casefold() for reference in group_references
    ):
        raise ValueError("Unanchored peer scope must include the complete current alias group")
    if not references_have_current_unscoped_maps(observed, references, coverage):
        raise ValueError(
            "Unanchored peer scope requires complete current maps without authored scope"
        )


def project_connector_unanchored_peer_scope_evidence(
    source: ConnectorUnanchoredPeerScopeEvidence,
) -> CandidateEvidenceProjection:
    """Project the established review fields from a current typed source."""
    _validate_current_unanchored_scope_evidence(source)
    items = (*source.divergences, *source.partial_opens)
    first = items[0]
    references = connector_footprint_peer_unanchored_references(first)
    entries_by_reference: dict[str, list[ConnectorCoverageEntry]] = defaultdict(list)
    for entry in source.coverage.entries:
        entries_by_reference[entry.reference.casefold()].append(entry)
    ordered = tuple(
        sorted(source.divergences, key=lambda item: (item.pin_number.casefold(), item.pin_number))
    )
    evidence: dict[str, tuple[str, ...]] = {
        "value": (first.value,),
        "footprint": (first.footprint,),
        "references": references,
        "symbols": first.symbols,
        "unanchored_generic_pin_numbers": tuple(item.pin_number for item in ordered),
        "pin_assignments": tuple(
            f"pin {item.pin_number}: "
            + "; ".join(
                f"{pin}={nets[0]}"
                for pin, nets in sorted(
                    item.assignments.items(), key=lambda pair: (pair[0].casefold(), pair[0])
                )
            )
            for item in ordered
        ),
        "interface_reviews": tuple(
            f"{reference}: {entries_by_reference[reference.casefold()][0].interface_id}; "
            f"{entries_by_reference[reference.casefold()][0].basis}"
            for reference in references
        ),
        "inventory_review_basis": (source.coverage.inventory_review_basis or "",),
        "interface_catalog_sha256": (str(source.coverage.interface_catalog_sha256),),
    }
    if source.coverage.interface_catalog_path is not None:
        evidence["interface_catalog_path"] = (str(source.coverage.interface_catalog_path),)
    if source.partial_opens:
        partial_opens = tuple(
            sorted(
                source.partial_opens,
                key=lambda item: (item.pin_number.casefold(), item.pin_number),
            )
        )
        evidence["unanchored_partial_open_pin_numbers"] = tuple(
            item.pin_number for item in partial_opens
        )
        evidence["partial_open_pin_assignments"] = tuple(
            f"pin {item.pin_number}: "
            + "; ".join(
                f"{pin}={nets[0] if nets else '<unassigned>'}"
                for pin, nets in sorted(
                    item.assignments.items(), key=lambda pair: (pair[0].casefold(), pair[0])
                )
            )
            for item in partial_opens
        )
    return CandidateEvidenceProjection(rule_id=RULE_ID, evidence=evidence)


@dataclass(frozen=True, slots=True)
class ConnectorUnanchoredPeerScopeCandidate(Candidate):
    """Review candidate whose evidence stays bound to current connector sources."""

    source_evidence: ConnectorUnanchoredPeerScopeEvidence

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: ConnectorUnanchoredPeerScopeEvidence,
        *,
        subject: str,
        message: str,
    ) -> ConnectorUnanchoredPeerScopeCandidate:
        projection = project_connector_unanchored_peer_scope_evidence(source_evidence)
        return cls(
            rule_id=projection.rule_id,
            subject=subject,
            message=message,
            evidence=projection.evidence,
            source_evidence=source_evidence,
        )

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        projection = project_connector_unanchored_peer_scope_evidence(self.source_evidence)
        if self.rule_id != projection.rule_id or self.evidence != projection.evidence:
            raise ValueError(
                "Unanchored peer scope fields must match their current source projection"
            )
