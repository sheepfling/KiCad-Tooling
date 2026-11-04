"""Source ownership regressions for PCB measurement review candidates."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.design_lint_candidate_aggregation import fingerprint
from kicad_tooling.hwrepo.design_lint_pcb_decoupling_candidate_evidence import (
    PcbDecouplingCandidate,
)
from kicad_tooling.hwrepo.design_lint_pcb_measurement_candidates import (
    pcb_measurement_coverage_candidates,
)
from kicad_tooling.hwrepo.design_lint_pcb_protection_path_candidate_evidence import (
    PcbProtectionPathCandidate,
)
from kicad_tooling.hwrepo.design_lint_pcb_reference_plane_candidate_evidence import (
    PcbReferencePlaneCandidate,
)
from kicad_tooling.hwrepo.design_lint_pcb_track_width_candidate_evidence import (
    PcbTrackWidthCandidate,
)
from kicad_tooling.hwrepo.design_lint_types import Candidate
from tests import pcb_decoupling_support as decoupling
from tests import test_pcb_protection_path as protection
from tests import test_pcb_track_width as track_width
from tests.design_lint_fixtures import pcb_reference_planes as reference_plane

pytestmark = [pytest.mark.design_lint, pytest.mark.pcb_lint, pytest.mark.evidence_lint]


def test_measurement_findings_retain_source_reports_and_stable_wire_identity() -> None:
    decoupling_map = decoupling.mapping(decoupling.requirement(maximum_um=None))
    decoupling_report = decoupling.coverage_report(
        decoupling_map,
        decoupling.snapshot(),
        netlist_sha256="f" * 64,
    )

    protection_map = protection.mapping(protection.requirement(max_entry_distance_um=99))
    protection_report = protection.coverage_report(
        protection_map,
        protection.snapshot(entry_distance_nm=100_000),
    )

    track_width_map = track_width.mapping(track_width.requirement(minimum_um=251))
    track_width_report = track_width.coverage(
        track_width_map, track_width.snapshot(track_width.track("001", "VDD", 250_000))
    )

    reference_map = reference_plane.mapping(reference_plane.requirement(minimum_fraction=0.9))
    reference_report = reference_plane.report(
        reference_map,
        reference_plane.snapshot(
            reference_plane.track("1"),
            zones=(
                reference_plane.zone(
                    reference_plane.ZONE_GND,
                    outline=((0, 0), (5_000_000, 0), (5_000_000, 10_000_000), (0, 10_000_000)),
                ),
            ),
        ),
    )

    candidates = pcb_measurement_coverage_candidates(
        pcb_decoupling_coverage=decoupling_report,
        pcb_protection_path_coverage=protection_report,
        pcb_track_width_coverage=track_width_report,
        pcb_reference_plane_coverage=reference_report,
    )
    by_rule = {candidate.rule_id: candidate for candidate in candidates}

    assert len(candidates) == 4
    decoupling_candidate = by_rule["pcb.decoupling_proximity"]
    assert isinstance(decoupling_candidate, PcbDecouplingCandidate)
    assert decoupling_candidate.source_evidence.report is decoupling_report
    assert decoupling_candidate.source_evidence.entry is decoupling_report.entries[0]
    assert decoupling_candidate.evidence["maximum_center_distance_um"] == ("not configured",)

    protection_candidate = by_rule["pcb.protection_entry_path"]
    assert isinstance(protection_candidate, PcbProtectionPathCandidate)
    assert protection_candidate.source_evidence.report is protection_report
    assert protection_candidate.source_evidence.entry is protection_report.entries[0]
    assert protection_candidate.evidence["connector_to_protection_pad_center_distance"] == (
        "100000 nm",
    )

    track_candidate = by_rule["pcb.minimum_track_width"]
    assert isinstance(track_candidate, PcbTrackWidthCandidate)
    assert track_candidate.source_evidence.report is track_width_report
    assert track_candidate.source_evidence.entry is track_width_report.entries[0]
    assert track_candidate.evidence["below_minimum_track_uuids"] == (
        track_width_report.entries[0].tracks[0].track_uuid,
    )

    reference_candidate = by_rule["pcb.reference_plane_coverage"]
    assert isinstance(reference_candidate, PcbReferencePlaneCandidate)
    assert reference_candidate.source_evidence.report is reference_report
    assert reference_candidate.source_evidence.entry is reference_report.entries[0]
    assert reference_candidate.evidence["below_threshold_track_uuids"] == (
        reference_report.entries[0].tracks[0].track_uuid,
    )

    for candidate in candidates:
        legacy_projection = Candidate(
            rule_id=candidate.rule_id,
            subject=candidate.subject,
            message=candidate.message,
            evidence=candidate.evidence,
        )
        assert fingerprint(candidate) == fingerprint(legacy_projection)
