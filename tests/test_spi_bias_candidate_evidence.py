"""SPI bias projection keeps its exact heuristic scan result."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.design_lint_spi_bias_candidate_evidence import (
    SpiBiasCandidate,
    SpiBiasFindingEvidence,
    project_spi_bias_evidence,
)
from kicad_tooling.hwrepo.spi_bias_heuristics import SpiChipSelectBiasGap


def test_spi_bias_projection_preserves_the_current_report_fields() -> None:
    gap = SpiChipSelectBiasGap(
        net="SPI_CS_N",
        pins=("U1.4", "U2.7"),
        positive_rails=("+3V3", "VDD_IO"),
    )
    source = SpiBiasFindingEvidence(gap)
    candidate = SpiBiasCandidate.from_source_evidence(
        source,
        subject="SPI_CS_N: active-low SPI chip-select bias",
        message="Review reset-time chip-select bias.",
    )

    assert dict(project_spi_bias_evidence(source).evidence) == {
        "net": ("SPI_CS_N",),
        "active_low_chip_select_pins": ("U1.4", "U2.7"),
        "recognized_positive_rails": ("+3V3", "VDD_IO"),
        "visible_pullup_paths": (),
    }
    assert candidate.source_evidence is source


def test_spi_bias_candidate_rejects_a_projection_mismatch() -> None:
    source = SpiBiasFindingEvidence(SpiChipSelectBiasGap("SPI_CS_N", ("U1.4",), ("+3V3",)))

    with pytest.raises(ValueError, match="typed source projection"):
        SpiBiasCandidate(
            rule_id="bus.spi_active_low_chip_select_without_pullup",
            subject="review",
            message="inspect",
            evidence={"net": ("wrong",)},
            source_evidence=source,
        )
