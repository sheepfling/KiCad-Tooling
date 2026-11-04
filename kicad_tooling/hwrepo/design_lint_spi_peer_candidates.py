"""Translate mapped SPI participant coverage observations."""

from __future__ import annotations

from .design_lint_spi_participant_candidate_evidence import (
    UnmappedSpiParticipantCandidate,
    UnmappedSpiParticipantFindingEvidence,
)
from .design_lint_types import Candidate
from .netlist_contract_models import NetlistContract
from .spi_participants import SpiRosterContext, unmapped_spi_participants


def spi_participant_candidates(
    observed: NetlistContract,
    spi_scope: SpiRosterContext,
) -> tuple[Candidate, ...]:
    """Build coverage prompts for SPI-like participants missing from the roster."""
    found: list[Candidate] = []
    for participant in unmapped_spi_participants(observed, spi_scope):
        if spi_scope.state == "required":
            scope_text = "is not listed in the project SPI device map"
        elif spi_scope.state == "pending":
            scope_text = "is a candidate while the project SPI review remains pending"
        elif spi_scope.state == "not_applicable":
            scope_text = "is a candidate despite the project SPI review being marked not applicable"
        else:
            scope_text = "has no configured project SPI device map"
        found.append(
            UnmappedSpiParticipantCandidate.from_source_evidence(
                UnmappedSpiParticipantFindingEvidence(participant, spi_scope),
                subject=f"{participant.reference}: SPI roster coverage",
                message=(
                    f"{participant.reference} has assigned SPI-like clock/data pin functions and "
                    f"a named chip-select function, and {scope_text}. Review whether it is an "
                    "omitted device, an SPI controller, or a pin-function match for another "
                    "interface. This is a coverage prompt, not a finding that the design must "
                    "connect or include the device."
                ),
            )
        )
    return tuple(found)
