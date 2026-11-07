"""Review two-contact RS-485 connectors without an identified reference return."""

from __future__ import annotations

from dataclasses import dataclass

from .connector_coverage import source_matched_connector_pin_evidence
from .connector_coverage_models import ConnectorCoverageReport
from .connector_return_pins import connector_pin_group_has_return_role
from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate, CandidateEvidenceProjection
from .netlist_contract_models import NetlistContract
from .rs485_generic_connector_candidates import rs485_generic_connector_pairs
from .rs485_generic_connector_models import Rs485GenericConnectorPair

RS485_CONNECTOR_RETURN_RULE_ID: DesignLintRuleId = "connector.rs485_pair_without_return_review"


@dataclass(frozen=True, slots=True)
class Rs485ConnectorReturnEvidence:
    """A complete two-contact connector on a native RS-485 A/B pair."""

    pair: Rs485GenericConnectorPair


def _project_evidence(source: Rs485ConnectorReturnEvidence) -> CandidateEvidenceProjection:
    pair = source.pair
    return CandidateEvidenceProjection(
        rule_id=RS485_CONNECTOR_RETURN_RULE_ID,
        evidence={
            "connector": (pair.connector_reference,),
            "connector_native_pin_count": (str(pair.connector_pin_count),),
            "connected_contact_count": ("2",),
            "A_net": (pair.a_net,),
            "A_generic_connector_pins": pair.a_connector_pins,
            "B_net": (pair.b_net,),
            "B_generic_connector_pins": pair.b_connector_pins,
            "RS485_endpoint_pairs": tuple(
                f"{item.reference}:{item.a_pin}=A/{item.a_net};{item.b_pin}=B/{item.b_net}"
                for item in pair.endpoint_pairs
            ),
            "identified_connector_return_role": (),
        },
    )


@dataclass(frozen=True, slots=True)
class Rs485ConnectorReturnCandidate(Candidate):
    """Source-bound review prompt for an RS-485 connector's reference."""

    source_evidence: Rs485ConnectorReturnEvidence

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: Rs485ConnectorReturnEvidence,
    ) -> Rs485ConnectorReturnCandidate:
        projection = _project_evidence(source_evidence)
        return cls(
            rule_id=projection.rule_id,
            subject=(
                f"{source_evidence.pair.connector_reference}: two-pin RS-485 connector "
                "has no identified reference return"
            ),
            message=(
                "Native U/IC pin functions identify this complete two-pin connector as a "
                "generic RS-485 A/B pair, and no connector contact function or current, "
                "source-matched pin map identifies a return. Review the approved interface "
                "to confirm the reference is supplied elsewhere, the interface is intentionally "
                "isolated, or the pinout needs a documented reference contact. This prompt does "
                "not require connection to board ground or establish termination, bias, off-board "
                "wiring, or PCB copper continuity."
            ),
            evidence=projection.evidence,
            source_evidence=source_evidence,
        )

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        projection = _project_evidence(self.source_evidence)
        if self.rule_id != projection.rule_id or self.evidence != projection.evidence:
            raise ValueError("RS-485 connector return evidence must match its source projection")


def rs485_connector_missing_return_candidates(
    observed: NetlistContract,
    reviewed_connector_references: tuple[str, ...] = (),
    connector_coverage: ConnectorCoverageReport | None = None,
) -> tuple[Candidate, ...]:
    """Prompt on exact two-contact generic RS-485 connectors without a return role."""
    mapped = source_matched_connector_pin_evidence(observed, connector_coverage)
    found: list[Candidate] = []
    for pair in rs485_generic_connector_pairs(
        observed,
        reviewed_connector_references,
        connector_coverage,
    ):
        if (
            pair.connector_pin_count != 2
            or len(pair.a_connector_pins) != 1
            or len(pair.b_connector_pins) != 1
        ):
            continue
        connector_pins = (*pair.a_connector_pins, *pair.b_connector_pins)
        if connector_pin_group_has_return_role(
            connector_pins,
            observed.pin_functions,
            mapped,
        ):
            continue
        found.append(
            Rs485ConnectorReturnCandidate.from_source_evidence(Rs485ConnectorReturnEvidence(pair))
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
