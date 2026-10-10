"""Focused contract PCB reference-plane lint regressions."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.models import (
    DesignLintPolicy,
    DesignLintRuleOverride,
    PcbReferencePlaneCoverageEntry,
    PcbReferencePlaneTrackMeasurement,
)
from tests.design_lint_fixtures.pcb_reference_planes import (
    RULE,
    ZONE_GND,
    coach,
    mapping,
    report,
    requirement,
    snapshot,
    track,
    zone,
)

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.pcb_lint,
    pytest.mark.return_path_lint,
    pytest.mark.pcb_reference_lint,
]


class PcbReferencePlaneContractTests:
    def test_exactly_mapped_fault_is_reviewable_and_control_is_quiet(self) -> None:
        hole = (
            (4_000_000, 4_000_000),
            (6_000_000, 4_000_000),
            (6_000_000, 6_000_000),
            (4_000_000, 6_000_000),
        )
        spec = mapping()
        fault = evaluate(
            "synthetic-plane",
            coach(),
            DesignLintPolicy(pcb_reference_plane_map=spec),
            pcb_reference_plane_coverage=report(
                spec, snapshot(track(), zones=(zone(ZONE_GND, holes=(hole,)),))
            ),
        )
        finding = next(item for item in fault.findings if item.rule_id == RULE)
        assert fault.status == "REVIEW"
        assert track().uuid in finding.evidence["below_threshold_track_uuids"]
        assert "does not establish a continuous return-current path" in finding.message

        control = evaluate(
            "synthetic-plane",
            coach(),
            DesignLintPolicy(pcb_reference_plane_map=spec),
            pcb_reference_plane_coverage=report(spec, snapshot(track())),
        )
        assert control.status == "PASS"
        assert not any(item.rule_id == RULE for item in control.findings)

        blocking = evaluate(
            "synthetic-plane",
            coach(),
            DesignLintPolicy(
                pcb_reference_plane_map=spec,
                rules=(
                    DesignLintRuleOverride(rule_id=RULE, mode="block", reason="synthetic gate"),
                ),
            ),
            pcb_reference_plane_coverage=report(
                spec, snapshot(track(), zones=(zone(ZONE_GND, holes=(hole,)),))
            ),
        )
        assert blocking.status == "FAIL"

    def test_map_scope_is_unique_and_threshold_is_bounded(self) -> None:
        with pytest.raises(ValidationError, match="only one reference-plane screen"):
            mapping(requirement(), requirement(id="duplicate-scope"))
        with pytest.raises(ValidationError):
            requirement(minimum_fraction=1.1)

    def test_report_rejects_unreduced_fraction_and_underlength_measurement(self) -> None:
        with pytest.raises(ValidationError, match="must be reduced"):
            PcbReferencePlaneTrackMeasurement(
                track_uuid=track().uuid,
                signal_layer="F.Cu",
                reference_layer="In1.Cu",
                reference_zone_uuids=(),
                segment_length_nm=1_000,
                covered_fraction_numerator=2,
                covered_fraction_denominator=4,
                below_minimum=True,
            )
        measurement = PcbReferencePlaneTrackMeasurement(
            track_uuid=track().uuid,
            signal_layer="F.Cu",
            reference_layer="In1.Cu",
            reference_zone_uuids=(),
            segment_length_nm=999,
            covered_fraction_numerator=0,
            covered_fraction_denominator=1,
            below_minimum=True,
        )
        with pytest.raises(ValidationError, match="meet the authored length"):
            PcbReferencePlaneCoverageEntry(
                id="data-reference",
                status="COMPLETE",
                basis="Synthetic source-bound validation",
                signal_net="DATA",
                signal_layers=("F.Cu",),
                reference_net="GND",
                minimum_track_length_um=1,
                minimum_referenced_fraction=0.9,
                tracks=(measurement,),
            )
