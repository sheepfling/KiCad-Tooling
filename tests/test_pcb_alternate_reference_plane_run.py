"""Project-scoped heuristic for mapped routes over alternate copper-zone nets."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.design_lint_finding_models import DesignLintRuleOverride
from kicad_tooling.hwrepo.models import DesignLintPolicy
from kicad_tooling.hwrepo.pcb_reference_plane_transitions import (
    alternate_reference_plane_run_candidates,
)
from kicad_tooling.hwrepo.pcb_reference_planes import pcb_reference_plane_entries
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

RULE = "pcb.alternate_reference_plane_run"
ZONE_ALT_A = "00000000-0000-0000-0000-000000000011"
ZONE_ALT_B = "00000000-0000-0000-0000-000000000012"
ZONE_REMOTE_LAYER = "00000000-0000-0000-0000-000000000013"


def alternate_plane_snapshot(*, reverse_zones: bool = False):
    zones = (
        zone(
            ZONE_GND,
            net="GND",
            outline=((0, 0), (4_000_000, 0), (4_000_000, 10_000_000), (0, 10_000_000)),
        ),
        zone(
            ZONE_ALT_A,
            net="VCC",
            outline=(
                (4_000_000, 0),
                (6_000_000, 0),
                (6_000_000, 10_000_000),
                (4_000_000, 10_000_000),
            ),
        ),
        zone(
            ZONE_ALT_B,
            net="VCC",
            outline=(
                (6_000_000, 0),
                (8_000_000, 0),
                (8_000_000, 10_000_000),
                (6_000_000, 10_000_000),
            ),
        ),
        zone(
            ZONE_REMOTE_LAYER,
            layer="B.Cu",
            net="AUX",
            outline=(
                (0, 0),
                (10_000_000, 0),
                (10_000_000, 10_000_000),
                (0, 10_000_000),
            ),
        ),
    )
    return snapshot(track(), zones=tuple(reversed(zones)) if reverse_zones else zones)


def evaluated_report(*, threshold_um: int | None, reverse_zones: bool = False):
    spec = mapping(
        requirement(
            minimum_fraction=0,
            minimum_alternate_reference_length_um=threshold_um,
        )
    )
    observed = alternate_plane_snapshot(reverse_zones=reverse_zones)
    return spec, observed, report(spec, observed)


def test_authored_alternate_net_threshold_emits_exact_review_candidate() -> None:
    spec, observed, coverage = evaluated_report(threshold_um=4_000)

    entry = pcb_reference_plane_entries(spec, observed)[0]
    alternate = entry.tracks[0].alternate_reference_coverages
    assert [
        (
            item.net,
            item.zone_uuids,
            item.covered_fraction_numerator,
            item.covered_fraction_denominator,
        )
        for item in alternate
    ] == [
        (
            "VCC",
            (ZONE_ALT_A, ZONE_ALT_B),
            2,
            5,
        )
    ]
    assert len(alternate_reference_plane_run_candidates(coverage)) == 1

    result = evaluate(
        "synthetic-alternate-plane",
        coach("synthetic-alternate-plane"),
        DesignLintPolicy(pcb_reference_plane_map=spec),
        pcb_reference_plane_coverage=coverage,
    )
    finding = next(item for item in result.findings if item.rule_id == RULE)
    assert result.status == "REVIEW"
    assert finding.mode == "review"
    assert finding.evidence["observed_alternate_reference_coverage_nm"] == ("4000000",)
    assert finding.evidence["alternate_net"] == ("VCC",)
    assert finding.evidence["adjacent_reference_layer"] == ("In1.Cu",)
    assert finding.evidence["contributing_tracks"] == (f"{entry.tracks[0].track_uuid}:4000000nm",)
    assert "does not establish copper continuity" in finding.message


def test_alternate_net_review_is_opt_in_and_threshold_boundary_is_exact() -> None:
    unconfigured_spec, _, unconfigured = evaluated_report(threshold_um=None)
    over_spec, _, over_threshold = evaluated_report(threshold_um=4_001)
    at_spec, _, at_threshold = evaluated_report(threshold_um=4_000)

    unconfigured_finding = evaluate(
        "synthetic-alternate-plane",
        coach("synthetic-alternate-plane"),
        DesignLintPolicy(pcb_reference_plane_map=unconfigured_spec),
        pcb_reference_plane_coverage=unconfigured,
    )
    over_result = evaluate(
        "synthetic-alternate-plane",
        coach("synthetic-alternate-plane"),
        DesignLintPolicy(pcb_reference_plane_map=over_spec),
        pcb_reference_plane_coverage=over_threshold,
    )
    at_result = evaluate(
        "synthetic-alternate-plane",
        coach("synthetic-alternate-plane"),
        DesignLintPolicy(pcb_reference_plane_map=at_spec),
        pcb_reference_plane_coverage=at_threshold,
    )
    assert not any(item.rule_id == RULE for item in unconfigured_finding.findings)
    assert not any(item.rule_id == RULE for item in over_result.findings)
    assert any(item.rule_id == RULE for item in at_result.findings)


def test_alternate_plane_evidence_is_stable_under_zone_order_and_policy_can_disable() -> None:
    spec, _, first_report = evaluated_report(threshold_um=3_000)
    _, _, reordered_report = evaluated_report(threshold_um=3_000, reverse_zones=True)
    policy = DesignLintPolicy(
        pcb_reference_plane_map=spec,
        rules=(DesignLintRuleOverride(rule_id=RULE, mode="off", reason="Synthetic opt out"),),
    )
    first = evaluate(
        "synthetic-alternate-plane",
        coach("synthetic-alternate-plane"),
        DesignLintPolicy(pcb_reference_plane_map=spec),
        pcb_reference_plane_coverage=first_report,
    )
    reordered = evaluate(
        "synthetic-alternate-plane",
        coach("synthetic-alternate-plane"),
        DesignLintPolicy(pcb_reference_plane_map=spec),
        pcb_reference_plane_coverage=reordered_report,
    )
    disabled = evaluate(
        "synthetic-alternate-plane",
        coach("synthetic-alternate-plane"),
        policy,
        pcb_reference_plane_coverage=first_report,
    )
    first_finding = next(item for item in first.findings if item.rule_id == RULE)
    reordered_finding = next(item for item in reordered.findings if item.rule_id == RULE)
    disabled_finding = next(item for item in disabled.findings if item.rule_id == RULE)
    assert first_finding.fingerprint == reordered_finding.fingerprint
    assert disabled_finding.disposition == "RULE_OFF"
    assert disabled_finding.mode == "off"
