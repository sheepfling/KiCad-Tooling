"""Deterministic source-bound checks for pair transition reference vias."""

from __future__ import annotations

import hashlib

import pytest
from pydantic import ValidationError

from kicad_tooling.hwrepo.design_lint_pcb_reference_via_candidate import RULE_ID
from kicad_tooling.hwrepo.design_lint_pcb_reference_via_policy import (
    normalize_reference_via_stitching_policy,
)
from kicad_tooling.hwrepo.design_lint_pcb_requirement_candidates import (
    pcb_requirement_coverage_candidates,
)
from kicad_tooling.hwrepo.pcb_connectivity_observations import PcbViaObservation
from kicad_tooling.hwrepo.pcb_connectivity_snapshot import PcbConnectivitySnapshot
from kicad_tooling.hwrepo.pcb_differential_pair_reference_via_models import (
    PcbDifferentialPairReferenceViaReport,
)
from kicad_tooling.hwrepo.pcb_differential_pair_reference_via_stitching import (
    measure_differential_pair_reference_via_stitching,
)
from kicad_tooling.hwrepo.pcb_drc_models import (
    PcbSignalPathBundleRequirement,
    PcbSignalPathRuleCoverageReport,
)
from tests.design_lint_fixtures.pcb_differential_pair_reference_via import (
    stitching_map,
    stitching_netlist,
)
from tests.design_lint_fixtures.pcb_differential_pair_route_skew import (
    geometry_evidence,
    route_snapshot,
    source_hashes,
)

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.pcb_lint,
    pytest.mark.design_lint_rule(rule_id=RULE_ID),
]


def _snapshot_with_reference_via(
    *,
    distance_nm: int,
    y_offset_nm: int = 0,
    net: str = "GND",
) -> PcbConnectivitySnapshot:
    base = route_snapshot(
        positive_length_nm=1_000_000,
        negative_length_nm=1_000_000,
        negative_layer_transition=True,
    )
    reference_via = PcbViaObservation(
        id="0" * 63 + "2",
        net=net,
        x_nm=500_000 + distance_nm,
        y_nm=100_000 + y_offset_nm,
        start_layer="F.Cu",
        end_layer="B.Cu",
        diameter_nm=600_000,
        drill_nm=300_000,
        kind="through",
        multiplicity=1,
    )
    observed = base.model_dump()
    observed["vias"] = (*observed["vias"], reference_via)
    return PcbConnectivitySnapshot.model_validate(observed)


def _measure(tmp_path, snapshot, *, include_reference: bool = True):
    requirements = stitching_map()
    observed = stitching_netlist(include_reference=include_reference)
    evidence = geometry_evidence(tmp_path, snapshot)
    netlist_sha256 = hashlib.sha256(observed.model_dump_json().encode("utf-8")).hexdigest()
    assert not requirements.has_native_drc_requirements()
    report = measure_differential_pair_reference_via_stitching(
        requirements,
        observed,
        evidence,
        source_hashes(),
        netlist_sha256,
        "review",
    )
    return report


def test_reference_via_within_inclusive_project_distance_is_quiet(tmp_path) -> None:
    report = _measure(tmp_path, _snapshot_with_reference_via(distance_nm=1_000_000))

    assert report.status == "COMPLETE"
    transition = report.entries[0].transitions[0]
    assert transition.status == "WITHIN_LIMIT"
    assert transition.nearest_distance_nm == 1_000_000
    assert transition.nearest_distance_squared_nm2 == 1_000_000_000_000
    candidates = pcb_requirement_coverage_candidates(
        pcb_signal_path_coverage=PcbSignalPathRuleCoverageReport(reference_via_stitching=report)
    )
    assert all(item.rule_id != RULE_ID for item in candidates)


def test_reference_via_beyond_authored_distance_requests_review(tmp_path) -> None:
    report = _measure(tmp_path, _snapshot_with_reference_via(distance_nm=1_000_001))

    assert report.status == "INCOMPLETE"
    entry = report.entries[0]
    assert entry.status == "MISSING_REFERENCE_VIA"
    assert entry.transitions[0].nearest_distance_nm == 1_000_001
    findings = pcb_requirement_coverage_candidates(
        pcb_signal_path_coverage=PcbSignalPathRuleCoverageReport(reference_via_stitching=report)
    )
    finding = next(item for item in findings if item.rule_id == RULE_ID)
    assert finding.evidence["reference_net"] == ("GND",)
    assert finding.evidence["maximum_distance_nm"] == ("1000000",)
    assert "does not prove reference-plane connection" in finding.message


def test_exact_squared_distance_blocks_rounding_down_to_authored_limit(tmp_path) -> None:
    report = _measure(
        tmp_path,
        _snapshot_with_reference_via(distance_nm=1_000_000, y_offset_nm=1),
    )

    transition = report.entries[0].transitions[0]
    assert transition.nearest_distance_nm == 1_000_000
    assert transition.nearest_distance_squared_nm2 == 1_000_000_000_001
    assert transition.status == "MISSING_REFERENCE_VIA"


def test_nearby_via_on_another_net_does_not_satisfy_authored_reference(tmp_path) -> None:
    report = _measure(tmp_path, _snapshot_with_reference_via(distance_nm=100_000, net="SHIELD"))

    assert report.status == "INCOMPLETE"
    transition = report.entries[0].transitions[0]
    assert transition.status == "MISSING_REFERENCE_VIA"
    assert transition.nearest_reference_via_id is None
    assert transition.nearest_distance_nm is None


def test_missing_reference_net_in_source_netlist_is_incomplete_not_clean(tmp_path) -> None:
    report = _measure(
        tmp_path,
        _snapshot_with_reference_via(distance_nm=100_000),
        include_reference=False,
    )

    assert report.status == "INCOMPLETE"
    assert report.entries[0].status == "INCOMPLETE"
    assert "absent from the source netlist" in report.entries[0].issue
    assert (
        len(
            pcb_requirement_coverage_candidates(
                pcb_signal_path_coverage=PcbSignalPathRuleCoverageReport(
                    reference_via_stitching=report
                )
            )
        )
        == 1
    )


def test_pair_without_layer_transition_does_not_request_stitching_review(tmp_path) -> None:
    report = _measure(
        tmp_path,
        route_snapshot(positive_length_nm=1_000_000, negative_length_nm=1_000_000),
    )

    assert report.status == "COMPLETE"
    assert report.entries[0].status == "WITHIN_LIMIT"
    assert report.entries[0].transitions == ()


def test_reference_via_result_is_stable_when_native_items_are_reordered(tmp_path) -> None:
    snapshot = _snapshot_with_reference_via(distance_nm=100_000)
    first = _measure(tmp_path, snapshot)
    payload = snapshot.model_dump()
    payload["tracks"] = tuple(reversed(payload["tracks"]))
    payload["vias"] = tuple(reversed(payload["vias"]))
    reordered = PcbConnectivitySnapshot.model_validate(payload)
    second = _measure(tmp_path, reordered)

    assert first.entries == second.entries
    assert first.map_sha256 == second.map_sha256


def test_reference_via_contract_requires_net_and_distance_together() -> None:
    requirements = stitching_map()
    bundle = requirements.bundles[0]

    with pytest.raises(ValidationError, match="both an exact reference net"):
        PcbSignalPathBundleRequirement.model_validate(
            {
                **bundle.model_dump(),
                "max_reference_via_distance_nm": None,
            }
        )


def test_disabled_reference_via_contract_is_reported_without_findings(tmp_path) -> None:
    requirements = stitching_map()
    observed = stitching_netlist()
    evidence = geometry_evidence(tmp_path, _snapshot_with_reference_via(distance_nm=100_000))
    report = measure_differential_pair_reference_via_stitching(
        requirements,
        observed,
        evidence,
        source_hashes(),
        "d" * 64,
        "off",
    )

    assert report.status == "DISABLED"
    assert report.map_sha256 is not None
    assert (
        PcbDifferentialPairReferenceViaReport.model_validate_json(report.model_dump_json())
        == report
    )
    assert (
        pcb_requirement_coverage_candidates(
            pcb_signal_path_coverage=PcbSignalPathRuleCoverageReport(reference_via_stitching=report)
        )
        == ()
    )


def test_missing_native_reference_via_evidence_is_blocked_not_clean() -> None:
    report = normalize_reference_via_stitching_policy(
        None,
        requirements=stitching_map(),
        mode="review",
        source_hashes=source_hashes(),
    )

    assert report.status == "BLOCKED"
    findings = pcb_requirement_coverage_candidates(
        pcb_signal_path_coverage=PcbSignalPathRuleCoverageReport(reference_via_stitching=report)
    )
    assert len(findings) == 1
    assert findings[0].rule_id == RULE_ID
    assert findings[0].evidence["bundle_id"] == ("usb-data-pair",)
