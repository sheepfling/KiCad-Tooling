"""Pytest-style design-lint regression cases for reference-plane coverage."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.models import DesignLintPolicy, DesignLintReport
from tests.design_lint_fixtures.pcb_reference_planes import (
    ZONE_GND,
    coach,
    mapping,
    report,
    snapshot,
    track,
    zone,
)

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.pcb_lint,
    pytest.mark.return_path_lint,
]


RULE = "pcb.reference_plane_coverage"


def design_lint_report(*, fault: bool) -> DesignLintReport:
    specification = mapping()
    if fault:
        gap = (
            (4_000_000, 4_000_000),
            (6_000_000, 4_000_000),
            (6_000_000, 6_000_000),
            (4_000_000, 6_000_000),
        )
        observed = snapshot(track(), zones=(zone(ZONE_GND, holes=(gap,)),))
    else:
        observed = snapshot(track())
    return evaluate(
        "synthetic-plane",
        coach(),
        DesignLintPolicy(pcb_reference_plane_map=specification),
        pcb_reference_plane_coverage=report(specification, observed),
    )


def test_mapped_reference_plane_gap_is_reviewable() -> None:
    result = design_lint_report(fault=True)

    finding = next(item for item in result.findings if item.rule_id == RULE)
    measurement = result.pcb_reference_plane.entries[0].tracks[0]
    assert result.status == "REVIEW"
    assert result.pcb_reference_plane.status == "COMPLETE"
    assert measurement.below_minimum
    assert measurement.covered_fraction_numerator == 4
    assert measurement.covered_fraction_denominator == 5
    assert finding.evidence["below_threshold_track_uuids"] == (measurement.track_uuid,)


def test_complete_reference_plane_control_is_quiet() -> None:
    result = design_lint_report(fault=False)

    measurement = result.pcb_reference_plane.entries[0].tracks[0]
    assert result.status == "PASS"
    assert result.pcb_reference_plane.status == "COMPLETE"
    assert measurement.covered_fraction_numerator == 1
    assert measurement.covered_fraction_denominator == 1
    assert not any(item.rule_id == RULE for item in result.findings)
