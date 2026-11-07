"""Review JTAG connectors without an identified reference return."""

from __future__ import annotations

from dataclasses import dataclass

from .bus_jtag_generic_connector import generic_jtag_connector_pairs
from .casefold_mapping_lookup import casefolded_unique_index
from .connector_coverage import source_matched_connector_pin_evidence
from .connector_coverage_models import ConnectorCoverageReport
from .connector_return_pins import connector_pin_group_has_return_role
from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate, CandidateEvidenceProjection
from .jtag_generic_connector_models import JtagGenericConnector
from .netlist_contract_models import NetlistContract

JTAG_CONNECTOR_RETURN_RULE_ID: DesignLintRuleId = "connector.jtag_pair_without_return_review"


@dataclass(frozen=True, slots=True)
class JtagConnectorReturnEvidence:
    """One exact native JTAG connector pair and its complete pin inventory."""

    pair: JtagGenericConnector
    connector_pins: tuple[str, ...]


def _project_evidence(source: JtagConnectorReturnEvidence) -> CandidateEvidenceProjection:
    pair = source.pair
    return CandidateEvidenceProjection(
        rule_id=JTAG_CONNECTOR_RETURN_RULE_ID,
        evidence={
            "connector": (pair.connector_reference,),
            "connector_native_pin_count": (str(pair.connector_pin_count),),
            "connector_native_pins": source.connector_pins,
            "TCK_net": (pair.tck_net,),
            "TCK_generic_connector_pins": pair.tck_connector_pins,
            "TMS_net": (pair.tms_net,),
            "TMS_generic_connector_pins": pair.tms_connector_pins,
            "JTAG_endpoint_pairs": tuple(
                f"{item.reference}:{item.tck_pin}={item.tck_function}/"
                f"{item.tck_electrical_type}/{item.tck_net};"
                f"{item.tms_pin}={item.tms_function}/"
                f"{item.tms_electrical_type}/{item.tms_net}"
                for item in pair.endpoints
            ),
            "identified_connector_return_role": (),
        },
    )


@dataclass(frozen=True, slots=True)
class JtagConnectorReturnCandidate(Candidate):
    """Review prompt for a JTAG connector without an identified return."""

    source_evidence: JtagConnectorReturnEvidence

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: JtagConnectorReturnEvidence,
    ) -> JtagConnectorReturnCandidate:
        projection = _project_evidence(source_evidence)
        return cls(
            rule_id=projection.rule_id,
            subject=(
                f"{source_evidence.pair.connector_reference}: JTAG connector "
                "has no identified reference return"
            ),
            message=(
                "Native U/IC pin functions identify generic connector contacts on the exact "
                "JTAG TCK/TMS pair, and no connector contact function or current, source-matched "
                "pin map identifies a return. Review whether the signal reference is supplied "
                "elsewhere, the interface is intentionally isolated, or the reviewed pinout "
                "needs a return contact. This prompt does not require board ground or establish "
                "external wiring or PCB copper."
            ),
            evidence=projection.evidence,
            source_evidence=source_evidence,
        )

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        projection = _project_evidence(self.source_evidence)
        if self.rule_id != projection.rule_id or self.evidence != projection.evidence:
            raise ValueError("JTAG connector return evidence must match its source projection")


def jtag_connector_missing_return_candidates(
    observed: NetlistContract,
    reviewed_connector_references: tuple[str, ...] = (),
    connector_coverage: ConnectorCoverageReport | None = None,
) -> tuple[Candidate, ...]:
    """Prompt when a complete JTAG-mapped connector has no identified return role.

    The pair recognizer normally suppresses connectors already mapped to JTAG
    signal roles. This return review deliberately keeps those candidates and
    applies source-matched return-role evidence independently.
    """
    inventories = casefolded_unique_index(observed.component_pin_numbers)
    mapped_pins = source_matched_connector_pin_evidence(observed, connector_coverage)
    not_applicable = {
        entry.reference.casefold()
        for entry in (() if connector_coverage is None else connector_coverage.entries)
        if entry.status == "NOT_APPLICABLE"
    }
    findings: list[Candidate] = []
    for pair in generic_jtag_connector_pairs(observed, reviewed_connector_references):
        reference_key = pair.connector_reference.casefold()
        if reference_key in not_applicable:
            continue
        numbers = inventories.get(reference_key)
        if numbers is None or len(numbers) != pair.connector_pin_count:
            continue
        connector_pins = tuple(f"{pair.connector_reference}.{number}" for number in numbers)
        if connector_pin_group_has_return_role(
            connector_pins,
            observed.pin_functions,
            mapped_pins,
        ):
            continue
        findings.append(
            JtagConnectorReturnCandidate.from_source_evidence(
                JtagConnectorReturnEvidence(
                    pair=pair,
                    connector_pins=tuple(
                        sorted(connector_pins, key=lambda pin: (pin.casefold(), pin))
                    ),
                )
            )
        )
    return tuple(
        sorted(
            findings,
            key=lambda item: (
                item.subject.casefold(),
                item.subject,
                tuple(sorted((key, value) for key, value in item.evidence.items())),
            ),
        )
    )
