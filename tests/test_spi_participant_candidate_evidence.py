"""Unmapped SPI findings retain their typed endpoint and roster scope."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.design_lint_spi_participant_candidate_evidence import (
    UnmappedSpiParticipantCandidate,
    UnmappedSpiParticipantFindingEvidence,
    project_unmapped_spi_participant_evidence,
)
from kicad_tooling.hwrepo.spi_participants import SpiRosterContext, UnmappedSpiParticipant


def _participant() -> UnmappedSpiParticipant:
    return UnmappedSpiParticipant(
        reference="U4",
        clock_pins=("U4.1",),
        input_data_pins=("U4.2",),
        output_data_pins=("U4.3",),
        chip_select_pins=("U4.4",),
        signal_assignments=("U4.1=SPI_CLK", "U4.2=SPI_COPI", "U4.3=SPI_CIPO"),
    )


def test_spi_participant_projection_preserves_roster_source_and_endpoint() -> None:
    source = UnmappedSpiParticipantFindingEvidence(
        _participant(),
        SpiRosterContext(
            state="required",
            source_path="contracts/electrical.json",
            source_sha256="a" * 64,
        ),
    )
    candidate = UnmappedSpiParticipantCandidate.from_source_evidence(
        source,
        subject="U4: SPI roster coverage",
        message="Review the endpoint classification.",
    )

    assert dict(project_unmapped_spi_participant_evidence(source).evidence) == {
        "SCK_pins": ("U4.1",),
        "input_data_pins": ("U4.2",),
        "output_data_pins": ("U4.3",),
        "chip_select_pins": ("U4.4",),
        "assigned_signal_pins": ("U4.1=SPI_CLK", "U4.2=SPI_COPI", "U4.3=SPI_CIPO"),
        "SPI_roster_state": ("required",),
        "electrical_contract_path": ("contracts/electrical.json",),
        "electrical_contract_sha256": ("a" * 64,),
    }
    assert candidate.source_evidence is source


def test_spi_participant_projection_does_not_fabricate_pending_source_identity() -> None:
    source = UnmappedSpiParticipantFindingEvidence(
        _participant(),
        SpiRosterContext(state="pending"),
    )

    evidence = project_unmapped_spi_participant_evidence(source).evidence

    assert evidence["SPI_roster_state"] == ("pending",)
    assert "electrical_contract_path" not in evidence
    assert "electrical_contract_sha256" not in evidence


def test_spi_participant_candidate_rejects_a_projection_mismatch() -> None:
    source = UnmappedSpiParticipantFindingEvidence(
        _participant(),
        SpiRosterContext(state="required"),
    )

    with pytest.raises(ValueError, match="typed source projection"):
        UnmappedSpiParticipantCandidate(
            rule_id="bus.spi_unmapped_participant",
            subject="review",
            message="inspect",
            evidence={"SCK_pins": ("wrong",)},
            source_evidence=source,
        )
