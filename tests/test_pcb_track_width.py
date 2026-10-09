"""Synthetic deterministic regressions for mapped PCB track-width screens."""

from __future__ import annotations

import hashlib

import pytest
from pydantic import ValidationError

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.models import (
    ContractCoachReport,
    DesignLintIgnore,
    DesignLintPolicy,
    DesignLintRuleOverride,
    NetlistContract,
    PcbConnectivitySnapshot,
    PcbTrackObservation,
    PcbTrackWidthCoverageReport,
    PcbTrackWidthMap,
    PcbTrackWidthRequirement,
)
from kicad_tooling.hwrepo.pcb_track_width import pcb_track_width_entries

RULE = "pcb.minimum_track_width"
IMAGE = "ghcr.io/example/kicad:10.0.5@sha256:" + "b" * 64


def requirement(net: str = "VDD", minimum_um: int = 250, id: str = "core-rail"):
    return PcbTrackWidthRequirement(
        id=id,
        basis="Synthetic project copper-width screen",
        net=net,
        minimum_width_um=minimum_um,
    )


def mapping(*items: PcbTrackWidthRequirement) -> PcbTrackWidthMap:
    return PcbTrackWidthMap(
        basis="Synthetic authored net-width review",
        requirements=items or (requirement(),),
    )


def track(uuid_tail: str, net: str, width_nm: int, y_nm: int = 0) -> PcbTrackObservation:
    return PcbTrackObservation(
        uuid=f"00000000-0000-0000-0000-{int(uuid_tail):012d}",
        net=net,
        layer="F.Cu",
        width_nm=width_nm,
        start_nm=(10_000_000, y_nm),
        end_nm=(25_000_000, y_nm),
    )


def snapshot(*tracks: PcbTrackObservation) -> PcbConnectivitySnapshot:
    return PcbConnectivitySnapshot(
        schema_version="6",
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
        tracks=tracks,
    )


def coverage(specification: PcbTrackWidthMap, observed: PcbConnectivitySnapshot):
    entries = pcb_track_width_entries(specification, observed)
    return PcbTrackWidthCoverageReport(
        status="COMPLETE" if all(item.status == "COMPLETE" for item in entries) else "INCOMPLETE",
        mode="review",
        map_sha256=hashlib.sha256(specification.model_dump_json().encode("utf-8")).hexdigest(),
        board_path="projects/synthetic/board.kicad_pcb",
        board_sha256=observed.board_sha256,
        snapshot_path="build/design-lint/snapshot.json",
        snapshot_sha256=hashlib.sha256(observed.model_dump_json().encode("utf-8")).hexdigest(),
        probe_sha256=observed.probe_sha256,
        kicad_version=observed.kicad_version,
        image=observed.image,
        netlist_sha256="f" * 64,
        entries=entries,
    )


def coach() -> ContractCoachReport:
    return ContractCoachReport(
        status="READY_FOR_REVIEW",
        project_id="synthetic-width",
        observed=NetlistContract(components={}, nets={}),
        netlist_sha256="f" * 64,
    )


def test_below_minimum_width_is_exactly_measured() -> None:
    spec = mapping(requirement(minimum_um=251))
    observed = snapshot(track("001", "VDD", 250_000))
    measured = coverage(spec, observed)

    assert measured.status == "COMPLETE"
    entry = measured.entries[0]
    assert entry.tracks[0].width_nm == 250_000
    assert entry.tracks[0].minimum_width_um == 251
    assert entry.tracks[0].below_minimum
    report = evaluate(
        "synthetic-width",
        coach(),
        DesignLintPolicy(pcb_track_width_map=spec),
        pcb_track_width_coverage=measured,
    )
    finding = next(item for item in report.findings if item.rule_id == RULE)
    assert report.status == "REVIEW"
    assert finding.evidence["below_minimum_track_uuids"] == (entry.tracks[0].track_uuid,)
    assert "does not calculate current capacity" in finding.message


def test_exact_boundary_passes_and_other_nets_are_excluded() -> None:
    spec = mapping(requirement(minimum_um=250))
    observed = snapshot(
        track("001", "VDD", 250_000),
        track("002", "GND", 100_000, y_nm=1_000_000),
    )

    measured = coverage(spec, observed)
    report = evaluate(
        "synthetic-width",
        coach(),
        DesignLintPolicy(pcb_track_width_map=spec),
        pcb_track_width_coverage=measured,
    )

    assert report.status == "PASS"
    assert len(measured.entries[0].tracks) == 1
    assert not measured.entries[0].tracks[0].below_minimum
    assert not any(item.rule_id == RULE for item in report.findings)


def test_track_order_preserves_measurement_and_finding_but_boundary_repair_clears_it() -> None:
    spec = mapping(requirement(minimum_um=251))
    narrow = track("001", "VDD", 250_000)
    wide = track("002", "VDD", 260_000)
    source = snapshot(narrow, wide)
    reordered_source = snapshot(wide, narrow)
    source_coverage = coverage(spec, source)
    reordered_coverage = coverage(spec, reordered_source)
    assert source_coverage.entries == reordered_coverage.entries
    assert source_coverage.map_sha256 == reordered_coverage.map_sha256
    assert source_coverage.snapshot_sha256 != reordered_coverage.snapshot_sha256

    original = evaluate(
        "synthetic-width",
        coach(),
        DesignLintPolicy(pcb_track_width_map=spec),
        pcb_track_width_coverage=source_coverage,
    )
    reordered = evaluate(
        "synthetic-width",
        coach(),
        DesignLintPolicy(pcb_track_width_map=spec),
        pcb_track_width_coverage=reordered_coverage,
    )
    original_finding = next(item for item in original.findings if item.rule_id == RULE)
    reordered_finding = next(item for item in reordered.findings if item.rule_id == RULE)
    assert (original_finding.subject, original_finding.fingerprint, original_finding.evidence) == (
        reordered_finding.subject,
        reordered_finding.fingerprint,
        reordered_finding.evidence,
    )

    repaired_source = snapshot(track("001", "VDD", 251_000), wide)
    repaired_coverage = coverage(spec, repaired_source)
    repaired = evaluate(
        "synthetic-width",
        coach(),
        DesignLintPolicy(pcb_track_width_map=spec),
        pcb_track_width_coverage=repaired_coverage,
    )
    assert repaired_coverage.entries[0].status == "COMPLETE"
    assert not any(item.rule_id == RULE for item in repaired.findings)


def test_missing_track_inventory_remains_incomplete_review() -> None:
    spec = mapping(requirement(net="ZONE_ONLY"))
    measured = coverage(spec, snapshot(track("001", "VDD", 250_000)))
    report = evaluate(
        "synthetic-width",
        coach(),
        DesignLintPolicy(pcb_track_width_map=spec),
        pcb_track_width_coverage=measured,
    )

    assert measured.status == "INCOMPLETE"
    assert "zone-only" in measured.entries[0].issues[0]
    assert report.status == "REVIEW"
    assert report.findings[0].evidence["coverage_status"] == ("INCOMPLETE",)


def test_project_policy_can_review_block_disable_or_exactly_ignore() -> None:
    spec = mapping(requirement(minimum_um=251))
    measured = coverage(spec, snapshot(track("001", "VDD", 250_000)))
    policy = DesignLintPolicy(pcb_track_width_map=spec)
    reviewed = evaluate("synthetic-width", coach(), policy, pcb_track_width_coverage=measured)
    finding = next(item for item in reviewed.findings if item.rule_id == RULE)
    blocking = evaluate(
        "synthetic-width",
        coach(),
        policy.model_copy(
            update={
                "rules": (
                    DesignLintRuleOverride(
                        rule_id=RULE,
                        mode="block",
                        reason="Synthetic authored gate",
                    ),
                )
            }
        ),
        pcb_track_width_coverage=measured,
    )
    disabled = evaluate(
        "synthetic-width",
        coach(),
        policy.model_copy(
            update={
                "rules": (
                    DesignLintRuleOverride(
                        rule_id=RULE,
                        mode="off",
                        reason="Synthetic explicit disable",
                    ),
                )
            }
        ),
        pcb_track_width_coverage=measured,
    )
    ignored = evaluate(
        "synthetic-width",
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
        pcb_track_width_coverage=measured,
    )

    assert reviewed.status == "REVIEW"
    assert blocking.status == "FAIL"
    assert disabled.status == "PASS"
    assert disabled.findings[0].disposition == "RULE_OFF"
    assert ignored.status == "PASS"
    assert ignored.findings[0].disposition == "IGNORED"


def test_duplicate_net_requirement_and_invalid_snapshot_contract_are_rejected() -> None:
    with pytest.raises(ValidationError):
        mapping(requirement(id="first"), requirement(id="second"))
    data = snapshot(track("001", "VDD", 250_000)).model_dump(mode="python")
    del data["tracks"]
    with pytest.raises(ValidationError, match="explicit track inventory"):
        PcbConnectivitySnapshot.model_validate(data)
