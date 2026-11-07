"""Review completely mapped SPI connectors without an identified return role."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from .connector_coverage import source_matched_connector_pin_evidence
from .connector_coverage_models import (
    ConnectorCoverageReport,
    ConnectorMappedPinEvidence,
)
from .connector_identity import is_return_function
from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate, CandidateEvidenceProjection
from .netlist_contract_models import NetlistContract
from .spi_generic_connector_candidates import generic_spi_connector_triads
from .spi_generic_connector_models import SpiGenericConnectorTriad
from .spi_participants import spi_signal_role_and_channel

SPI_CONNECTOR_RETURN_RULE_ID: DesignLintRuleId = "connector.spi_triad_without_return_review"
_ROLE_LABELS = {
    "clock": "clock",
    "data_input": "controller-to-peripheral data",
    "data_output": "peripheral-to-controller data",
}


@dataclass(frozen=True, slots=True)
class SpiConnectorReturnEvidence:
    """One mapped SPI connector triad and its complete source-matched pin inventory."""

    triad: SpiGenericConnectorTriad
    mapped_pins: tuple[ConnectorMappedPinEvidence, ...]
    interface_catalog_sha256: str


def _project_evidence(source: SpiConnectorReturnEvidence) -> CandidateEvidenceProjection:
    triad = source.triad
    evidence: dict[str, tuple[str, ...]] = {
        "connector": (triad.connector_reference,),
        "connector_native_pin_count": (str(triad.connector_pin_count),),
        "interface_catalog_sha256": (source.interface_catalog_sha256,),
        "mapped_connector_pins": tuple(
            f"{item.component_pin}:{item.interface_signal}:role={item.role or 'unclassified'}:"
            f"nets={','.join(item.nets)}"
            for item in sorted(
                source.mapped_pins,
                key=lambda item: (item.component_pin.casefold(), item.component_pin),
            )
        ),
        "identified_return_contacts": (),
    }
    for role, label in _ROLE_LABELS.items():
        evidence[f"{label}_net"] = (triad.role_nets[role],)
        evidence[f"{label}_connector_pins"] = triad.role_connector_pins[role]
    evidence["SPI_endpoint_triads"] = tuple(
        f"{item.reference}:{item.channel}:clock={item.clock_pin}/{item.clock_net};"
        f"data_input={item.data_input_pin}/{item.data_input_net};"
        f"data_output={item.data_output_pin}/{item.data_output_net}"
        for item in triad.endpoint_triads
    )
    return CandidateEvidenceProjection(
        rule_id=SPI_CONNECTOR_RETURN_RULE_ID,
        evidence=evidence,
    )


@dataclass(frozen=True, slots=True)
class SpiConnectorReturnCandidate(Candidate):
    """Review prompt for a mapped SPI connector with no identified return pin."""

    source_evidence: SpiConnectorReturnEvidence

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: SpiConnectorReturnEvidence,
    ) -> SpiConnectorReturnCandidate:
        projection = _project_evidence(source_evidence)
        return cls(
            rule_id=projection.rule_id,
            subject=(
                f"{source_evidence.triad.connector_reference}: mapped SPI connector has no "
                "identified return role"
            ),
            message=(
                "The current complete connector map covers native SPI clock and both data roles, "
                "but identifies no connector return contact. Review whether the reference is "
                "provided elsewhere, the interface is intentionally isolated, or a return role "
                "is missing from the pin map. This does not require connection to board ground "
                "or establish off-board wiring or PCB continuity."
            ),
            evidence=projection.evidence,
            source_evidence=source_evidence,
        )

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        projection = _project_evidence(self.source_evidence)
        if self.rule_id != projection.rule_id or self.evidence != projection.evidence:
            raise ValueError("SPI connector return evidence must match its source projection")


def spi_connector_missing_return_candidates(
    observed: NetlistContract,
    connector_coverage: ConnectorCoverageReport | None,
    reviewed_connector_references: tuple[str, ...] = (),
) -> tuple[Candidate, ...]:
    """Prompt only for complete maps that expose one exact SPI triad and no return role.

    A source-matched pin map must account for every connector contact. Net names
    are retained as evidence but never interpreted as ground or return labels.
    """
    if connector_coverage is None or connector_coverage.interface_catalog_sha256 is None:
        return ()

    mapped = source_matched_connector_pin_evidence(observed, connector_coverage)
    mapped_by_pin = {pin.casefold(): evidence for pin, evidence in mapped.items()}
    entries = {
        entry.reference.casefold(): entry
        for entry in connector_coverage.entries
        if entry.status == "COVERED" and entry.interface_id is not None
    }
    findings: list[Candidate] = []
    for triad in generic_spi_connector_triads(
        observed,
        reviewed_connector_references,
        connector_coverage,
        include_source_mapped=True,
    ):
        if len(triad.endpoint_triads) != 1:
            continue
        connector_key = triad.connector_reference.casefold()
        entry = entries.get(connector_key)
        numbers = next(
            (
                values
                for reference, values in observed.component_pin_numbers.items()
                if reference.casefold() == connector_key
            ),
            None,
        )
        if entry is None or not numbers or len(numbers) != len(set(numbers)):
            continue
        connector_pins = tuple(f"{triad.connector_reference}.{number}" for number in numbers)
        complete_map = tuple(mapped_by_pin.get(pin.casefold()) for pin in connector_pins)
        if any(item is None for item in complete_map):
            continue
        source_pins = tuple(item for item in complete_map if item is not None)
        if any(item.role == "return" for item in source_pins) or any(
            is_return_function(observed.pin_functions.get(pin, "")) for pin in connector_pins
        ):
            continue
        if not _map_covers_spi_triad(triad, mapped_by_pin):
            continue
        findings.append(
            SpiConnectorReturnCandidate.from_source_evidence(
                SpiConnectorReturnEvidence(
                    triad=triad,
                    mapped_pins=source_pins,
                    interface_catalog_sha256=connector_coverage.interface_catalog_sha256,
                )
            )
        )
    return tuple(
        sorted(
            findings,
            key=lambda item: (item.subject.casefold(), item.subject),
        )
    )


def _map_covers_spi_triad(
    triad: SpiGenericConnectorTriad,
    mapped_by_pin: Mapping[str, ConnectorMappedPinEvidence],
) -> bool:
    """Require exact mapped roles and schematic nets for all generic SPI contacts."""
    channel = triad.endpoint_triads[0].channel
    for role in ("clock", "data_input", "data_output"):
        for pin in triad.role_connector_pins[role]:
            evidence = mapped_by_pin.get(pin.casefold())
            if evidence is None or len(evidence.nets) != 1:
                return False
            mapped_role = spi_signal_role_and_channel(evidence.interface_signal)
            if (
                mapped_role is None
                or mapped_role != (role, channel)
                or evidence.role not in (None, "signal")
                or evidence.nets[0].casefold() != triad.role_nets[role].casefold()
            ):
                return False
    return True
