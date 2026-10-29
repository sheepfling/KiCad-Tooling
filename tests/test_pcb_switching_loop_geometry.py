from __future__ import annotations

import pytest
from pydantic import ValidationError

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.models import (
    DesignLintIgnore,
    DesignLintPolicy,
    DesignLintRuleOverride,
    PcbConnectivitySnapshot,
)
from kicad_tooling.hwrepo.pcb_switching_loops import pcb_switching_loop_entries
from tests.design_lint_fixtures.pcb_switching_loop import (
    IMAGE,
    PLANE_UUID,
    coach,
    contoured_snapshot,
    coverage,
    mapping,
    requirement,
    routed_mapping,
    snapshot,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.pcb_lint, pytest.mark.return_path_lint]

RULE = "pcb.switching_loop_geometry"


def test_absent_layer_is_unsupported_and_missing_stack_is_schema_error() -> None:
    result = pcb_switching_loop_entries(
        mapping(requirement(layer="In2.Cu")), snapshot(copper_layers=("F.Cu", "B.Cu"))
    )[0]
    assert result.return_plane_status == "UNSUPPORTED"
    assert result.status == "INCOMPLETE"

    with pytest.raises(ValidationError, match="actual copper stack"):
        PcbConnectivitySnapshot(
            schema_version="7",
            board_sha256="a" * 64,
            kicad_version="10.0.5",
            image=IMAGE,
            probe_sha256="c" * 64,
            zones_refilled=True,
            pads=(),
            net_ties=(),
            zones=(),
            vias=(),
            access_probe_observations=(),
            access_probe_requests_sha256=None,
            tracks=(),
        )


def test_compact_loop_and_shared_multilayer_plane_pass_authored_geometry_screen() -> None:
    result = pcb_switching_loop_entries(mapping(), snapshot())[0]

    assert result.status == "COMPLETE"
    assert result.loop_area_twice_nm2 == 200000000000
    assert not result.area_exceeds_limit
    assert result.return_plane_status == "CONNECTED"
    assert result.return_zone_uuid == PLANE_UUID
    assert result.return_island_index == 0


def test_enlarged_loop_exceeds_project_area_limit() -> None:
    result = pcb_switching_loop_entries(mapping(), snapshot(expanded=True))[0]

    assert result.status == "INCOMPLETE"
    assert result.area_exceeds_limit
    assert "exceeds the project limit" in result.issues[0]


def test_missing_threshold_emits_review_and_policy_is_configurable() -> None:
    spec = mapping(requirement(maximum_area_um2=None))
    report = coverage(spec, snapshot())
    policy = DesignLintPolicy(pcb_switching_loop_map=spec)
    reviewed = evaluate("synthetic-loop", coach(), policy, pcb_switching_loop_coverage=report)
    finding = next(item for item in reviewed.findings if item.rule_id == RULE)
    blocking = evaluate(
        "synthetic-loop",
        coach(),
        policy.model_copy(
            update={
                "rules": (
                    DesignLintRuleOverride(
                        rule_id=RULE,
                        mode="block",
                        reason="Synthetic project release requirement",
                    ),
                )
            }
        ),
        pcb_switching_loop_coverage=report,
    )
    disabled = evaluate(
        "synthetic-loop",
        coach(),
        policy.model_copy(
            update={
                "rules": (
                    DesignLintRuleOverride(
                        rule_id=RULE,
                        mode="off",
                        reason="Synthetic project disposition",
                    ),
                )
            }
        ),
        pcb_switching_loop_coverage=report,
    )
    ignored = evaluate(
        "synthetic-loop",
        coach(),
        policy.model_copy(
            update={
                "ignores": (
                    DesignLintIgnore(
                        rule_id=RULE,
                        fingerprint=finding.fingerprint,
                        reason="Synthetic reviewed exception",
                    ),
                )
            }
        ),
        pcb_switching_loop_coverage=report,
    )

    assert reviewed.status == "REVIEW"
    assert blocking.status == "FAIL"
    assert disabled.status == "PASS"
    assert disabled.pcb_switching_loop.status == "DISABLED"
    assert ignored.status == "PASS"
    assert ignored.findings[0].disposition == "IGNORED"
    assert "polygon through authored pad centers" in finding.message
    assert finding.evidence["return_plane_status"] == ("CONNECTED",)


def test_multiple_shared_plane_islands_are_reported_as_ambiguous() -> None:
    result = pcb_switching_loop_entries(
        routed_mapping(), contoured_snapshot(duplicate_return_island=True)
    )[0]

    assert result.return_plane_status == "AMBIGUOUS"
    assert result.return_zone_uuid is None
    assert result.return_island_index is None
    plane_edge = result.route_edges[2]
    assert plane_edge.status == "INCOMPLETE"
    assert "selection is ambiguous" in plane_edge.issue


def test_pad_inventory_order_preserves_area_finding_and_compact_repair_clears_it() -> None:
    spec = mapping()
    expanded = snapshot(expanded=True)
    reordered_expanded = expanded.model_copy(
        update={
            "pads": tuple(
                pad.model_copy(
                    update={
                        "connected_pads": tuple(reversed(pad.connected_pads)),
                        "connected_islands": tuple(reversed(pad.connected_islands)),
                    }
                )
                for pad in reversed(expanded.pads)
            )
        }
    )
    measured = coverage(spec, expanded)
    reordered_measured = coverage(spec, reordered_expanded)
    assert measured.entries == reordered_measured.entries
    assert measured.map_sha256 == reordered_measured.map_sha256
    assert measured.snapshot_sha256 != reordered_measured.snapshot_sha256

    native = coach()
    policy = DesignLintPolicy(pcb_switching_loop_map=spec)
    original = evaluate("synthetic-loop", native, policy, pcb_switching_loop_coverage=measured)
    reordered = evaluate(
        "synthetic-loop", native, policy, pcb_switching_loop_coverage=reordered_measured
    )
    original_finding = next(item for item in original.findings if item.rule_id == RULE)
    reordered_finding = next(item for item in reordered.findings if item.rule_id == RULE)
    assert original.status == "REVIEW"
    assert (original_finding.subject, original_finding.fingerprint, original_finding.evidence) == (
        reordered_finding.subject,
        reordered_finding.fingerprint,
        reordered_finding.evidence,
    )

    compact_measured = coverage(spec, snapshot())
    compact = evaluate(
        "synthetic-loop", native, policy, pcb_switching_loop_coverage=compact_measured
    )
    assert compact_measured.entries[0].status == "COMPLETE"
    assert not any(item.rule_id == RULE for item in compact.findings)


def test_schema_nine_requires_valid_contours_for_every_filled_island() -> None:
    data = contoured_snapshot().model_dump()
    data["zones"][0].pop("filled_islands")
    with pytest.raises(ValidationError, match="requires explicit filled-island contour"):
        PcbConnectivitySnapshot.model_validate(data)

    data = contoured_snapshot().model_dump()
    data["zones"][0]["filled_islands"][0]["outline_nm"] = (
        (0, 0),
        (1_000_000, 1_000_000),
        (2_000_000, 2_000_000),
    )
    with pytest.raises(ValidationError, match="zero area"):
        PcbConnectivitySnapshot.model_validate(data)


def test_split_filled_return_plane_is_reported() -> None:
    result = pcb_switching_loop_entries(mapping(), snapshot(split_plane=True))[0]

    assert result.status == "INCOMPLETE"
    assert result.return_plane_status == "SPLIT"
    assert any("do not share one filled island" in item for item in result.issues)
