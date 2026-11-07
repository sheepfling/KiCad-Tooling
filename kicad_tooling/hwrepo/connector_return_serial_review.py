"""Review two-contact UART connectors with no identified reference return."""

from __future__ import annotations

from dataclasses import dataclass

from .connector_coverage import source_matched_connector_pin_evidence
from .connector_coverage_models import ConnectorCoverageReport
from .connector_identity import is_return_function
from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate, CandidateEvidenceProjection
from .netlist_contract_models import NetlistContract
from .serial_generic_connector_candidates import serial_generic_connector_pairs
from .serial_generic_connector_models import SerialGenericConnectorPair

SERIAL_CONNECTOR_RETURN_RULE_ID: DesignLintRuleId = "connector.serial_pair_without_return_review"


@dataclass(frozen=True, slots=True)
class SerialConnectorReturnEvidence:
    """A complete two-pin connector on a native UART pair without a return role."""

    pair: SerialGenericConnectorPair


def _project_evidence(
    source: SerialConnectorReturnEvidence,
) -> CandidateEvidenceProjection:
    pair = source.pair
    return CandidateEvidenceProjection(
        rule_id=SERIAL_CONNECTOR_RETURN_RULE_ID,
        evidence={
            "connector": (pair.connector_reference,),
            "connector_native_pin_count": (str(pair.connector_pin_count),),
            "connected_contact_count": ("2",),
            "TX_net": (pair.tx_net,),
            "TX_generic_connector_pins": pair.tx_connector_pins,
            "RX_net": (pair.rx_net,),
            "RX_generic_connector_pins": pair.rx_connector_pins,
            "UART_endpoint_pairs": tuple(
                f"{item.reference}:{item.channel}:TX={item.tx_pin}/{item.tx_net};"
                f"RX={item.rx_pin}/{item.rx_net}"
                for item in pair.endpoint_pairs
            ),
            "identified_connector_return_role": (),
        },
    )


@dataclass(frozen=True, slots=True)
class SerialConnectorReturnCandidate(Candidate):
    """Source-bound review prompt for a two-pin UART connector's reference."""

    source_evidence: SerialConnectorReturnEvidence

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: SerialConnectorReturnEvidence,
    ) -> SerialConnectorReturnCandidate:
        projection = _project_evidence(source_evidence)
        return cls(
            rule_id=projection.rule_id,
            subject=(
                f"{source_evidence.pair.connector_reference}: two-pin UART connector "
                "has no identified reference return"
            ),
            message=(
                "Native U/IC pin functions identify this complete two-pin connector as a "
                "generic UART TX/RX pair, and no connector pin function or current, "
                "source-matched pin map identifies a return contact. Review the approved "
                "interface design to confirm the signal reference is provided elsewhere, "
                "the interface is intentionally isolated, or the connector pinout needs a "
                "return contact. This review prompt does not require connection to board "
                "ground or establish PCB copper continuity."
            ),
            evidence=projection.evidence,
            source_evidence=source_evidence,
        )

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        projection = _project_evidence(self.source_evidence)
        if self.rule_id != projection.rule_id or self.evidence != projection.evidence:
            raise ValueError("Serial connector return evidence must match its source projection")


def serial_connector_missing_return_candidates(
    observed: NetlistContract,
    reviewed_connector_references: tuple[str, ...] = (),
    connector_coverage: ConnectorCoverageReport | None = None,
) -> tuple[Candidate, ...]:
    """Prompt on exact two-pin generic UART connectors with no return-role pin.

    This recognizes a review opportunity only. It does not require a local
    ground, infer external wiring, or convert the observation into a contract.
    """
    mapped = source_matched_connector_pin_evidence(observed, connector_coverage)
    functions = {pin.casefold(): value for pin, value in observed.pin_functions.items()}
    inventory = {
        reference.casefold(): (reference, tuple(numbers))
        for reference, numbers in observed.component_pin_numbers.items()
    }
    found: list[Candidate] = []
    for pair in serial_generic_connector_pairs(
        observed,
        reviewed_connector_references,
        connector_coverage,
    ):
        if (
            pair.connector_pin_count != 2
            or len(pair.tx_connector_pins) != 1
            or len(pair.rx_connector_pins) != 1
        ):
            continue
        reference_record = inventory.get(pair.connector_reference.casefold())
        if reference_record is None:
            continue
        reference, numbers = reference_record
        if len(numbers) != 2:
            continue
        connector_pins = tuple(f"{reference}.{number}" for number in numbers)
        if any(is_return_function(functions.get(pin.casefold(), "")) for pin in connector_pins):
            continue
        if any(
            evidence.role == "return"
            for pin in connector_pins
            if (evidence := mapped.get(pin)) is not None
        ):
            continue
        found.append(
            SerialConnectorReturnCandidate.from_source_evidence(SerialConnectorReturnEvidence(pair))
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
