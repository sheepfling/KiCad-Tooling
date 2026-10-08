"""Deterministic comparisons for project-reviewed native PCB keepout intent."""

from __future__ import annotations

import hashlib
from hashlib import sha256

import pytest

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.models import (
    ContractCoachReport,
    DesignLintIgnore,
    DesignLintPolicy,
    DesignLintRuleOverride,
    NetlistContract,
    PcbConnectivitySnapshot,
    PcbKeepoutCoverageReport,
    PcbKeepoutMap,
    PcbKeepoutRequirement,
    PcbRuleAreaObservation,
    PcbRuleAreaPolygonObservation,
)
from kicad_tooling.hwrepo.pcb_keepouts import pcb_keepout_entries, pcb_rule_area_geometry_sha256


def area(
    *,
    name: str = "ANTENNA_NO_COPPER",
    layers: tuple[str, ...] = ("F.Cu", "B.Cu"),
    outline: tuple[tuple[int, int], ...] = (
        (0, 0),
        (0, 2_000_000),
        (3_000_000, 2_000_000),
        (3_000_000, 0),
    ),
    forbids_tracks: bool = True,
    forbids_vias: bool = True,
    forbids_pads: bool = True,
    forbids_zone_fills: bool = True,
    forbids_footprints: bool = False,
    uuid: str = "12345678-1234-5678-1234-567812345678",
) -> PcbRuleAreaObservation:
    return PcbRuleAreaObservation(
        uuid=uuid,
        name=name,
        layers=layers,
        net=None,
        polygons=(PcbRuleAreaPolygonObservation(outline_nm=outline),),
        forbids_tracks=forbids_tracks,
        forbids_vias=forbids_vias,
        forbids_pads=forbids_pads,
        forbids_zone_fills=forbids_zone_fills,
        forbids_footprints=forbids_footprints,
    )


def snapshot(
    areas: tuple[PcbRuleAreaObservation, ...] = (), *, schema_version: str = "11"
) -> PcbConnectivitySnapshot:
    values = {
        "schema_version": schema_version,
        "board_sha256": "a" * 64,
        "kicad_version": "10.0.5",
        "image": "registry.example/kicad:10.0.5@sha256:" + "b" * 64,
        "probe_sha256": "c" * 64,
        "zones_refilled": True,
        "pads": (),
        "net_ties": (),
        "zones": (),
        "vias": (),
        "access_probe_observations": (),
        "access_probe_requests_sha256": None,
        "tracks": (),
        "copper_layers": ("F.Cu", "In1.Cu", "B.Cu"),
    }
    if schema_version == "11":
        values["rule_areas"] = areas
    return PcbConnectivitySnapshot.model_validate(values)


def mapping_for(
    expected_area: PcbRuleAreaObservation | None = None,
    *,
    name: str = "ANTENNA_NO_COPPER",
) -> PcbKeepoutMap:
    expected = expected_area or area(name=name)
    return PcbKeepoutMap(
        basis="Synthetic antenna keepout signature, reviewed from its source requirement",
        requirements=(
            PcbKeepoutRequirement(
                id="antenna-window",
                basis="Synthetic datasheet keepout drawing reference",
                name=name,
                geometry_sha256=pcb_rule_area_geometry_sha256(expected),
                layers=("F.Cu", "B.Cu"),
                forbids_tracks=True,
                forbids_vias=True,
                forbids_pads=True,
                forbids_zone_fills=True,
                forbids_footprints=False,
            ),
        ),
    )


def coverage_report(
    mapping: PcbKeepoutMap | None = None,
    native_snapshot: PcbConnectivitySnapshot | None = None,
) -> PcbKeepoutCoverageReport:
    mapping = mapping or mapping_for()
    native_snapshot = native_snapshot or snapshot()
    entries = pcb_keepout_entries(mapping, native_snapshot)
    status = "COMPLETE" if all(item.status == "COMPLETE" for item in entries) else "INCOMPLETE"
    return PcbKeepoutCoverageReport(
        status=status,
        mode="review",
        map_sha256=hashlib.sha256(mapping.model_dump_json().encode("utf-8")).hexdigest(),
        board_path="kicad/synthetic.kicad_pcb",
        board_sha256="a" * 64,
        snapshot_path="build/native/synthetic-pcb.json",
        snapshot_sha256="b" * 64,
        probe_sha256="c" * 64,
        kicad_version="10.0.5",
        image="registry.example/kicad:10.0.5@sha256:" + "d" * 64,
        netlist_sha256="e" * 64,
        entries=entries,
    )


def design_lint_report(*, fault: bool):
    """Build a complete synthetic design-lint report for hash-seed coverage."""
    mapping = mapping_for()
    observed_area = area(forbids_tracks=not fault)
    observed_snapshot = snapshot((observed_area,))
    observed_netlist = NetlistContract(components={}, nets={})
    netlist_sha256 = hashlib.sha256(observed_netlist.model_dump_json().encode("utf-8")).hexdigest()
    snapshot_sha256 = hashlib.sha256(
        observed_snapshot.model_dump_json().encode("utf-8")
    ).hexdigest()
    coverage = coverage_report(mapping, observed_snapshot).model_copy(
        update={"snapshot_sha256": snapshot_sha256, "netlist_sha256": netlist_sha256}
    )
    coach = ContractCoachReport(
        status="READY_FOR_REVIEW",
        project_id="synthetic-keepout",
        source_hashes={},
        netlist_sha256=netlist_sha256,
        observed=observed_netlist,
    )
    return evaluate(
        "synthetic-keepout-fault" if fault else "synthetic-keepout-control",
        coach,
        DesignLintPolicy(pcb_keepout_map=mapping),
        pcb_keepout_coverage=coverage,
    )


def incomplete_report(mapping: PcbKeepoutMap | None = None) -> PcbKeepoutCoverageReport:
    return coverage_report(mapping, snapshot())


def test_exact_keepout_signature_matches_one_named_native_area() -> None:
    expected = area()

    entries = pcb_keepout_entries(mapping_for(expected), snapshot((expected,)))

    assert len(entries) == 1
    assert entries[0].status == "COMPLETE"
    assert entries[0].observed_uuid == expected.uuid
    assert entries[0].observed_geometry_sha256 == entries[0].expected_geometry_sha256
    assert entries[0].observed_layers == ("F.Cu", "B.Cu")


def test_design_lint_reports_missing_track_restriction_and_complete_control() -> None:
    fault = design_lint_report(fault=True)
    control = design_lint_report(fault=False)

    assert fault.status == "REVIEW"
    assert fault.pcb_keepout_coverage.status == "INCOMPLETE"
    assert {finding.rule_id for finding in fault.findings} == {"pcb.keepout_intent_coverage"}
    assert control.status == "PASS"
    assert control.pcb_keepout_coverage.status == "COMPLETE"
    assert control.findings == ()


@pytest.mark.parametrize(
    ("observed", "expected_issue"),
    (
        (
            area(outline=((0, 0), (0, 2_000_001), (3_000_000, 2_000_001), (3_000_000, 0))),
            "geometry",
        ),
        (area(layers=("F.Cu",)), "copper layers"),
        (area(forbids_tracks=False), "restriction for tracks"),
        (area(forbids_vias=False), "restriction for vias"),
        (area(forbids_pads=False), "restriction for pads"),
        (area(forbids_zone_fills=False), "restriction for zone fills"),
        (area(forbids_footprints=True), "restriction for footprints"),
    ),
)
def test_geometry_layer_and_restriction_changes_are_incomplete(
    observed: PcbRuleAreaObservation, expected_issue: str
) -> None:
    entries = pcb_keepout_entries(mapping_for(), snapshot((observed,)))

    assert entries[0].status == "INCOMPLETE"
    assert any(expected_issue in issue for issue in entries[0].issues)


def test_missing_or_duplicate_named_areas_are_not_credited() -> None:
    missing = pcb_keepout_entries(mapping_for(), snapshot())
    duplicate = pcb_keepout_entries(
        mapping_for(),
        snapshot(
            (
                area(uuid="12345678-1234-5678-1234-567812345678"),
                area(uuid="12345678-1234-5678-1234-567812345679"),
            )
        ),
    )

    assert missing[0].status == "INCOMPLETE"
    assert "No native rule area" in missing[0].issues[0]
    assert duplicate[0].status == "INCOMPLETE"
    assert "ambiguous" in duplicate[0].issues[0]


def test_snapshot_schema_before_rule_area_evidence_is_incomplete() -> None:
    entries = pcb_keepout_entries(mapping_for(), snapshot(schema_version="10"))

    assert entries[0].status == "INCOMPLETE"
    assert "schema 11" in entries[0].issues[0]


def test_geometry_digest_ignores_polygon_and_hole_order() -> None:
    baseline = area()
    first = PcbRuleAreaObservation(
        **baseline.model_dump(exclude={"polygons"}),
        polygons=(
            PcbRuleAreaPolygonObservation(
                outline_nm=((0, 0), (0, 2_000_000), (3_000_000, 2_000_000), (3_000_000, 0)),
                holes_nm=(
                    ((1_000, 1_000), (1_000, 2_000), (2_000, 2_000), (2_000, 1_000)),
                    ((4_000, 4_000), (4_000, 5_000), (5_000, 5_000), (5_000, 4_000)),
                ),
            ),
            PcbRuleAreaPolygonObservation(
                outline_nm=(
                    (9_000_000, 0),
                    (9_000_000, 2_000_000),
                    (12_000_000, 2_000_000),
                    (12_000_000, 0),
                )
            ),
        ),
    )
    second = first.model_copy(
        update={
            "polygons": (
                first.polygons[1],
                PcbRuleAreaPolygonObservation(
                    outline_nm=first.polygons[0].outline_nm,
                    holes_nm=tuple(reversed(first.polygons[0].holes_nm)),
                ),
            )
        }
    )

    assert pcb_rule_area_geometry_sha256(first) == pcb_rule_area_geometry_sha256(second)


def test_schema_11_requires_explicit_rule_area_inventory() -> None:
    values = snapshot().model_dump()
    values.pop("rule_areas")

    with pytest.raises(ValueError, match="requires explicit rule-area evidence"):
        PcbConnectivitySnapshot.model_validate(values)


def test_keepout_map_rejects_duplicate_names_and_duplicate_layers() -> None:
    requirement = mapping_for().requirements[0]
    with pytest.raises(ValueError, match="layers must be unique"):
        PcbKeepoutRequirement.model_validate(
            {**requirement.model_dump(), "layers": ("F.Cu", "f.cu")}
        )

    with pytest.raises(ValueError, match="mapped only once"):
        PcbKeepoutMap(
            basis="Synthetic duplicate mapping control",
            requirements=(requirement, requirement.model_copy(update={"id": "duplicate"})),
        )


def test_digest_helper_returns_sha256_format() -> None:
    value = pcb_rule_area_geometry_sha256(area())

    assert (
        value
        == sha256(
            b'[{"holes_nm":[],"outline_nm":[[0,0],[0,2000000],[3000000,2000000],[3000000,0]]}]'
        ).hexdigest()
    )


def test_keepout_lint_finding_supports_review_block_off_and_exact_ignore() -> None:
    from tests.test_design_lint import coach

    mapping = mapping_for()
    coverage = incomplete_report(mapping)
    report = evaluate(
        "synthetic-keepout",
        coach(NetlistContract(components={}, nets={})),
        DesignLintPolicy(pcb_keepout_map=mapping),
        pcb_keepout_coverage=coverage,
    )
    (finding,) = tuple(
        item for item in report.findings if item.rule_id == "pcb.keepout_intent_coverage"
    )
    assert report.status == "REVIEW"
    assert finding.disposition == "OPEN"

    blocked = evaluate(
        "synthetic-keepout",
        coach(NetlistContract(components={}, nets={})),
        DesignLintPolicy(
            pcb_keepout_map=mapping,
            rules=(
                DesignLintRuleOverride(
                    rule_id="pcb.keepout_intent_coverage",
                    mode="block",
                    reason="Synthetic test policy",
                ),
            ),
        ),
        pcb_keepout_coverage=coverage,
    )
    assert blocked.status == "FAIL"

    disabled = evaluate(
        "synthetic-keepout",
        coach(NetlistContract(components={}, nets={})),
        DesignLintPolicy(
            pcb_keepout_map=mapping,
            rules=(
                DesignLintRuleOverride(
                    rule_id="pcb.keepout_intent_coverage",
                    mode="off",
                    reason="Synthetic test policy",
                ),
            ),
        ),
        pcb_keepout_coverage=coverage,
    )
    assert disabled.pcb_keepout_coverage.status == "DISABLED"
    assert not any(item.rule_id == finding.rule_id for item in disabled.findings)

    ignored = evaluate(
        "synthetic-keepout",
        coach(NetlistContract(components={}, nets={})),
        DesignLintPolicy(
            pcb_keepout_map=mapping,
            ignores=(
                DesignLintIgnore(
                    rule_id=finding.rule_id,
                    fingerprint=finding.fingerprint,
                    reason="Synthetic review accepts this exact keepout coverage gap",
                ),
            ),
        ),
        pcb_keepout_coverage=coverage,
    )
    ignored_finding = next(item for item in ignored.findings if item.rule_id == finding.rule_id)
    assert ignored_finding.disposition == "IGNORED"
