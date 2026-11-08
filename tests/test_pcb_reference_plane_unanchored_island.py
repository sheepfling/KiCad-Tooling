"""Project-scoped review for mapped reference-zone islands without pad anchors."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.design_lint_finding_models import DesignLintRuleOverride
from kicad_tooling.hwrepo.models import DesignLintPolicy
from kicad_tooling.hwrepo.pcb_connectivity_observations import (
    PcbPadConnectivityObservation,
    PcbZoneIdentity,
    PcbZoneIslandIdentity,
)
from kicad_tooling.hwrepo.pcb_reference_plane_islands import (
    unanchored_reference_zone_island_candidates,
)
from tests.design_lint_fixtures.pcb_reference_planes import (
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
]

RULE = "pcb.reference_plane_unanchored_island"


def reference_map(*, review: bool = True):
    return mapping(
        requirement(
            net="DATA",
            layer="B.Cu",
            reference_net="RETURN",
            minimum_fraction=1,
            review_unanchored_islands=review,
        )
    )


def reference_zone(*, anchored: bool = False, uuid: str = ZONE_GND):
    return zone(
        uuid,
        layer="F.Cu",
        net="RETURN",
        outline=(
            (1_000_000, 1_000_000),
            (19_000_000, 1_000_000),
            (19_000_000, 19_000_000),
            (1_000_000, 19_000_000),
        ),
        unanchored_pad_island_indexes=() if anchored else (0,),
    )


def pad_anchored_to_reference_zone() -> PcbPadConnectivityObservation:
    identity = PcbZoneIdentity(uuid=ZONE_GND, layer="F.Cu")
    island = PcbZoneIslandIdentity(uuid=ZONE_GND, layer="F.Cu", island_index=0)
    return PcbPadConnectivityObservation(
        pad="J1.1",
        net="RETURN",
        footprint="Synthetic:TestPad",
        dnp=False,
        connected_pads=("J1.1",),
        connected_zones=(identity,),
        connected_islands=(island,),
        connected_vias=(),
        positions_nm=((5_000_000, 5_000_000),),
    )


def test_mapped_unanchored_island_emits_source_bound_review_candidate() -> None:
    specification = reference_map()
    observed = snapshot(
        track(
            net="DATA", layer="B.Cu", start=(2_000_000, 15_000_000), end=(18_000_000, 15_000_000)
        ),
        zones=(reference_zone(),),
        copper_layers=("F.Cu", "B.Cu"),
    )
    coverage = report(specification, observed)
    entry = coverage.entries[0]

    assert entry.status == "COMPLETE"
    assert (
        entry.tracks[0].covered_fraction_numerator == entry.tracks[0].covered_fraction_denominator
    )
    assert entry.unanchored_reference_islands[0].island.island_index == 0
    candidates = unanchored_reference_zone_island_candidates(coverage)
    assert len(candidates) == 1
    assert candidates[0].rule_id == RULE
    assert candidates[0].evidence["zone_uuid"] == (ZONE_GND,)
    assert candidates[0].evidence["reference_layer"] == ("F.Cu",)
    assert "does not establish electrical isolation" in candidates[0].message

    result = evaluate(
        "synthetic-reference-island",
        coach("synthetic-reference-island"),
        DesignLintPolicy(pcb_reference_plane_map=specification),
        pcb_reference_plane_coverage=coverage,
    )
    finding = next(item for item in result.findings if item.rule_id == RULE)
    assert result.status == "REVIEW"
    assert finding.mode == "review"
    assert finding.evidence["snapshot_sha256"] == (coverage.snapshot_sha256,)
    assert finding.evidence["island_index"] == ("0",)


def test_review_requires_map_opt_in_and_direct_pad_anchor_is_a_control() -> None:
    track_item = track(
        net="DATA",
        layer="B.Cu",
        start=(2_000_000, 15_000_000),
        end=(18_000_000, 15_000_000),
    )
    fault_snapshot = snapshot(
        track_item,
        zones=(reference_zone(),),
        copper_layers=("F.Cu", "B.Cu"),
    )
    control_snapshot = snapshot(
        track_item,
        zones=(reference_zone(anchored=True),),
        pads=(pad_anchored_to_reference_zone(),),
        copper_layers=("F.Cu", "B.Cu"),
    )
    fault = report(reference_map(), fault_snapshot)
    unconfigured = report(reference_map(review=False), fault_snapshot)
    control = report(reference_map(), control_snapshot)

    assert fault.entries[0].tracks[0].covered_fraction_numerator == 1
    assert control.entries[0].tracks[0].covered_fraction_numerator == 1
    assert len(unanchored_reference_zone_island_candidates(fault)) == 1
    assert unanchored_reference_zone_island_candidates(unconfigured) == ()
    assert unanchored_reference_zone_island_candidates(control) == ()

    result = evaluate(
        "synthetic-reference-island-control",
        coach("synthetic-reference-island-control"),
        DesignLintPolicy(pcb_reference_plane_map=reference_map()),
        pcb_reference_plane_coverage=control,
    )
    assert not any(item.rule_id == RULE for item in result.findings)


def test_island_review_order_is_stable_and_policy_can_disable_or_block() -> None:
    specification = reference_map()
    signal = track(
        net="DATA",
        layer="B.Cu",
        start=(2_000_000, 15_000_000),
        end=(18_000_000, 15_000_000),
    )
    zones = (
        reference_zone(uuid=ZONE_GND),
        reference_zone(uuid="00000000-0000-0000-0000-000000000009"),
    )
    first = report(
        specification,
        snapshot(signal, zones=zones, copper_layers=("F.Cu", "B.Cu")),
    )
    reordered = report(
        specification,
        snapshot(signal, zones=tuple(reversed(zones)), copper_layers=("F.Cu", "B.Cu")),
    )
    first_candidates = unanchored_reference_zone_island_candidates(first)
    reordered_candidates = unanchored_reference_zone_island_candidates(reordered)
    assert tuple(item.subject for item in first_candidates) == tuple(
        item.subject for item in reordered_candidates
    )
    assert len(first_candidates) == 2

    for mode, expected_status in (("off", "PASS"), ("block", "FAIL")):
        policy = DesignLintPolicy(
            pcb_reference_plane_map=specification,
            rules=(
                DesignLintRuleOverride(
                    rule_id=RULE,
                    mode=mode,
                    reason="Synthetic rule-mode boundary",
                ),
            ),
        )
        result = evaluate(
            "synthetic-reference-island-policy",
            coach("synthetic-reference-island-policy"),
            policy,
            pcb_reference_plane_coverage=first,
        )
        assert result.status == expected_status
        rule_findings = tuple(item for item in result.findings if item.rule_id == RULE)
        assert len(rule_findings) == 2
        assert all(item.mode == mode for item in rule_findings)
        if mode == "off":
            assert all(item.disposition == "RULE_OFF" for item in rule_findings)
