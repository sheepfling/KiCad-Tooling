"""Review SWD debug connectors without an identified reference return."""

from __future__ import annotations

from dataclasses import dataclass

from .bus_swd_generic_connector import generic_swd_connector_pairs
from .casefold_mapping_lookup import casefolded_unique_index
from .connector_coverage import source_matched_connector_pin_evidence
from .connector_coverage_models import ConnectorCoverageReport
from .connector_return_pins import connector_pin_group_has_return_role
from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate, CandidateEvidenceProjection
from .netlist_contract_models import NetlistContract
from .swd_generic_connector_models import SwdGenericConnector

SWD_CONNECTOR_RETURN_RULE_ID: DesignLintRuleId = "connector.swd_pair_without_return_review"


@dataclass(frozen=True, slots=True)
class SwdConnectorReturnEvidence:
    """Complete connector inventory and exact source-bound SWD pair."""

    pair: SwdGenericConnector
    connector_pins: tuple[str, ...]


def _project_evidence(
    source: SwdConnectorReturnEvidence,
) -> CandidateEvidenceProjection:
    pair = source.pair
    return CandidateEvidenceProjection(
        rule_id=SWD_CONNECTOR_RETURN_RULE_ID,
        evidence={
            "connector": (pair.connector_reference,),
            "connector_native_pin_count": (str(pair.connector_pin_count),),
            "connector_native_pins": source.connector_pins,
            "SWDIO_net": (pair.swdio_net,),
            "SWDIO_generic_connector_pins": pair.swdio_connector_pins,
            "SWCLK_net": (pair.swclk_net,),
            "SWCLK_generic_connector_pins": pair.swclk_connector_pins,
            "SWD_endpoint_pairs": tuple(
                f"{item.reference}:{item.swdio_pin}={item.swdio_function}/"
                f"{item.swdio_electrical_type}/{item.swdio_net};"
                f"{item.swclk_pin}={item.swclk_function}/"
                f"{item.swclk_electrical_type}/{item.swclk_net}"
                for item in pair.endpoints
            ),
            "identified_connector_return_role": (),
        },
    )


@dataclass(frozen=True, slots=True)
class SwdConnectorReturnCandidate(Candidate):
    """Review prompt for an SWD connector without an identified return."""

    source_evidence: SwdConnectorReturnEvidence

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: SwdConnectorReturnEvidence,
    ) -> SwdConnectorReturnCandidate:
        projection = _project_evidence(source_evidence)
        return cls(
            rule_id=projection.rule_id,
            subject=(
                f"{source_evidence.pair.connector_reference}: SWD connector "
                "has no identified reference return"
            ),
            message=(
                "Native U/IC pin functions identify generic connector contacts on the exact "
                "SWDIO/SWCLK pair, and no connector contact function or current, source-matched "
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
            raise ValueError("SWD connector return evidence must match its source projection")


def swd_connector_missing_return_candidates(
    observed: NetlistContract,
    reviewed_connector_references: tuple[str, ...] = (),
    connector_coverage: ConnectorCoverageReport | None = None,
) -> tuple[Candidate, ...]:
    """Prompt when a complete SWD-mapped connector has no reviewed return role."""
    inventories = casefolded_unique_index(observed.component_pin_numbers)
    mapped_pins = source_matched_connector_pin_evidence(observed, connector_coverage)
    findings: list[Candidate] = []
    for pair in generic_swd_connector_pairs(
        observed,
        reviewed_connector_references,
        connector_coverage,
    ):
        reference_key = pair.connector_reference.casefold()
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
            SwdConnectorReturnCandidate.from_source_evidence(
                SwdConnectorReturnEvidence(
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
