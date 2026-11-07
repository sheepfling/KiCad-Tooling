"""Review two-contact CAN connectors with no identified reference return."""

from __future__ import annotations

from dataclasses import dataclass

from .can_generic_connector_candidates import generic_can_connector_pairs
from .can_generic_connector_models import CanGenericConnectorPair
from .connector_coverage import source_matched_connector_pin_evidence
from .connector_coverage_models import ConnectorCoverageReport
from .connector_return_pins import connector_pin_group_has_return_role
from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate, CandidateEvidenceProjection
from .netlist_contract_models import NetlistContract

CAN_CONNECTOR_RETURN_RULE_ID: DesignLintRuleId = "connector.can_pair_without_return_review"


@dataclass(frozen=True, slots=True)
class CanConnectorReturnEvidence:
    """One complete two-pin connector on a recognized native CANH/CANL pair."""

    pair: CanGenericConnectorPair


def _project_evidence(source: CanConnectorReturnEvidence) -> CandidateEvidenceProjection:
    pair = source.pair
    return CandidateEvidenceProjection(
        rule_id=CAN_CONNECTOR_RETURN_RULE_ID,
        evidence={
            "connector": (pair.connector_reference,),
            "connector_native_pin_count": (str(pair.connector_pin_count),),
            "connected_contact_count": ("2",),
            "CANH_net": (pair.canh_net,),
            "CANH_generic_connector_pins": pair.canh_connector_pins,
            "CANL_net": (pair.canl_net,),
            "CANL_generic_connector_pins": pair.canl_connector_pins,
            "CAN_endpoint_pairs": tuple(
                f"{item.reference}:{item.canh_pin}=CANH/{item.canh_net};"
                f"{item.canl_pin}=CANL/{item.canl_net}"
                for item in pair.endpoint_pairs
            ),
            "identified_connector_return_role": (),
        },
    )


@dataclass(frozen=True, slots=True)
class CanConnectorReturnCandidate(Candidate):
    """Source-bound review prompt for a two-pin CAN connector's reference."""

    source_evidence: CanConnectorReturnEvidence

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: CanConnectorReturnEvidence,
    ) -> CanConnectorReturnCandidate:
        projection = _project_evidence(source_evidence)
        return cls(
            rule_id=projection.rule_id,
            subject=(
                f"{source_evidence.pair.connector_reference}: two-pin CAN connector "
                "has no identified reference return"
            ),
            message=(
                "Native U/IC pin functions identify this complete two-pin connector as a "
                "generic CANH/CANL pair, and no connector pin function or current, "
                "source-matched pin map identifies a return. Review the approved interface "
                "to confirm the signal reference is provided elsewhere, the interface is "
                "intentionally isolated, or the connector pinout needs a documented return. "
                "This prompt does not require connection to board ground or establish bus "
                "termination, off-board wiring, or PCB copper continuity."
            ),
            evidence=projection.evidence,
            source_evidence=source_evidence,
        )

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        projection = _project_evidence(self.source_evidence)
        if self.rule_id != projection.rule_id or self.evidence != projection.evidence:
            raise ValueError("CAN connector return evidence must match its source projection")


def can_connector_missing_return_candidates(
    observed: NetlistContract,
    reviewed_connector_references: tuple[str, ...] = (),
    connector_coverage: ConnectorCoverageReport | None = None,
) -> tuple[Candidate, ...]:
    """Prompt on exact two-pin generic CAN connectors without a return role.

    The recognized CAN endpoint pair and generic connector contacts provide a
    bounded review opportunity. This does not require a local ground or infer
    the connector's purpose, off-board wiring, or PCB continuity.
    """
    mapped = source_matched_connector_pin_evidence(observed, connector_coverage)
    found: list[Candidate] = []
    for pair in generic_can_connector_pairs(
        observed,
        reviewed_connector_references,
        connector_coverage,
    ):
        if (
            pair.connector_pin_count != 2
            or len(pair.canh_connector_pins) != 1
            or len(pair.canl_connector_pins) != 1
        ):
            continue
        connector_pins = (*pair.canh_connector_pins, *pair.canl_connector_pins)
        if connector_pin_group_has_return_role(
            connector_pins,
            observed.pin_functions,
            mapped,
        ):
            continue
        found.append(
            CanConnectorReturnCandidate.from_source_evidence(CanConnectorReturnEvidence(pair))
        )

    return tuple(
        sorted(
            found,
            key=lambda item: (
                item.subject.casefold(),
                item.subject,
                tuple(sorted((key, value) for key, value in item.evidence.items())),
            ),
        )
    )
