"""Synthetic tests for project-mapped PCB path and bundle DRC coverage."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

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
    PcbDrcConstraintCoverage,
    PcbDrcMaximumRequirement,
    PcbDrcMinMaxRequirement,
    PcbPadConnectivityObservation,
    PcbSignalPathBundleRequirement,
    PcbSignalPathRequirement,
    PcbSignalPathRuleCoverageEntry,
    PcbSignalPathRuleCoverageReport,
    PcbSignalPathRuleMap,
)
from kicad_tooling.hwrepo.pcb_drc_coverage import (
    compare_native_signal_path_rules,
    read_native_pcb_drc_fixture_report,
)


def path_map() -> PcbSignalPathRuleMap:
    return PcbSignalPathRuleMap(
        basis="Synthetic reviewed signal-path and bus-skew requirement",
        paths=(
            PcbSignalPathRequirement(
                id="clock",
                basis="Synthetic clock route requirement",
                net="SYNTH_CLK",
                from_pad="J1.1",
                to_pad="U1.1",
                length=PcbDrcMinMaxRequirement(max_nm=20_000_000),
            ),
            PcbSignalPathRequirement(
                id="data",
                basis="Synthetic data route requirement",
                net="SYNTH_DATA",
                from_pad="J1.2",
                to_pad="U1.2",
                length=PcbDrcMinMaxRequirement(max_nm=20_000_000),
            ),
        ),
        bundles=(
            PcbSignalPathBundleRequirement(
                id="serial-bundle",
                basis="Synthetic timing-matched serial bundle",
                path_ids=("clock", "data"),
                from_pad_pattern="J1-*",
                to_pad_pattern="U1-*",
                max_skew=PcbDrcMaximumRequirement(max_nm=100_000),
            ),
        ),
    )


def native_rules() -> str:
    return """(version 1)
(rule "synthetic-clock-length"
  (condition "A.fromTo('J1-1', 'U1-1')")
  (constraint length (max 20mm)))
(rule "synthetic-data-length"
  (condition "A.fromTo('J1-2', 'U1-2')")
  (constraint length (max 20mm)))
(rule "synthetic-serial-skew"
  (condition "A.fromTo('J1-*', 'U1-*')")
  (constraint skew (max 0.1mm)))
"""


def source_netlist() -> NetlistContract:
    return NetlistContract(
        components={},
        nets={
            "SYNTH_CLK": ("J1.1", "U1.1"),
            "SYNTH_DATA": ("J1.2", "U1.2"),
        },
    )


def pcb_snapshot() -> PcbConnectivitySnapshot:
    pads = (
        PcbPadConnectivityObservation(
            pad="J1.1",
            net="SYNTH_CLK",
            footprint="Synthetic:Connector",
            dnp=False,
            connected_pads=("J1.1", "U1.1"),
            connected_zones=(),
            connected_islands=(),
            connected_vias=(),
            positions_nm=((1_000_000, 1_000_000),),
        ),
        PcbPadConnectivityObservation(
            pad="U1.1",
            net="SYNTH_CLK",
            footprint="Synthetic:Receiver",
            dnp=False,
            connected_pads=("J1.1", "U1.1"),
            connected_zones=(),
            connected_islands=(),
            connected_vias=(),
            positions_nm=((4_000_000, 1_000_000),),
        ),
        PcbPadConnectivityObservation(
            pad="J1.2",
            net="SYNTH_DATA",
            footprint="Synthetic:Connector",
            dnp=False,
            connected_pads=("J1.2", "U1.2"),
            connected_zones=(),
            connected_islands=(),
            connected_vias=(),
            positions_nm=((1_000_000, 2_000_000),),
        ),
        PcbPadConnectivityObservation(
            pad="U1.2",
            net="SYNTH_DATA",
            footprint="Synthetic:Receiver",
            dnp=False,
            connected_pads=("J1.2", "U1.2"),
            connected_zones=(),
            connected_islands=(),
            connected_vias=(),
            positions_nm=((4_000_000, 2_000_000),),
        ),
    )
    return PcbConnectivitySnapshot(
        schema_version="10",
        board_sha256="a" * 64,
        kicad_version="10.0.5",
        image="ghcr.io/kicad/kicad:10.0.5@sha256:" + "b" * 64,
        probe_sha256="c" * 64,
        zones_refilled=True,
        pads=pads,
        net_ties=(),
        zones=(),
        vias=(),
        access_probe_observations=(),
        access_probe_requests_sha256=None,
        tracks=(),
        copper_layers=("F.Cu", "B.Cu"),
    )


def compare(
    *,
    rules: str | None = None,
    ignored: frozenset[str] = frozenset(),
    netlist: NetlistContract | None = None,
    snapshot: PcbConnectivitySnapshot | None = None,
    requirements: PcbSignalPathRuleMap | None = None,
) -> tuple[PcbSignalPathRuleCoverageEntry, ...]:
    return compare_native_signal_path_rules(
        requirements or path_map(),
        native_rules() if rules is None else rules,
        ignored,
        netlist or source_netlist(),
        snapshot or pcb_snapshot(),
    )


def design_lint_report(*, fault: bool):
    """Build a complete synthetic design-lint report for hash-seed coverage."""
    requirements = path_map()
    observed_netlist = source_netlist()
    observed_snapshot = pcb_snapshot()
    rules = native_rules()
    if fault:
        rules = rules.replace("(max 20mm)", "(max 19mm)", 1)
    entries = compare(
        rules=rules,
        netlist=observed_netlist,
        snapshot=observed_snapshot,
        requirements=requirements,
    )

    def digest(value: str) -> str:
        return hashlib.sha256(value.encode("utf-8")).hexdigest()

    netlist_sha256 = digest(observed_netlist.model_dump_json())
    snapshot_sha256 = digest(observed_snapshot.model_dump_json())
    map_sha256 = digest(requirements.model_dump_json())
    coverage = PcbSignalPathRuleCoverageReport(
        status="INCOMPLETE" if fault else "COMPLETE",
        mode="review",
        map_sha256=map_sha256,
        source_inventory_sha256=digest(
            json.dumps(
                {
                    "map_sha256": map_sha256,
                    "netlist_sha256": netlist_sha256,
                    "rules_sha256": digest(rules),
                    "snapshot_sha256": snapshot_sha256,
                },
                sort_keys=True,
                separators=(",", ":"),
            )
        ),
        project_path="hardware/synthetic-paths.kicad_pro",
        project_sha256=digest("synthetic project source"),
        rules_path="hardware/synthetic-paths.kicad_dru",
        rules_sha256=digest(rules),
        board_path="hardware/synthetic-paths.kicad_pcb",
        board_sha256=observed_snapshot.board_sha256,
        native_summary_path="build/native/synthetic-paths/summary.json",
        native_summary_sha256=digest("synthetic native summary"),
        native_drc_path="build/native/synthetic-paths/drc.json",
        native_drc_sha256=digest("synthetic native DRC report"),
        pcb_snapshot_path="build/native/synthetic-paths/pcb-snapshot.json",
        pcb_snapshot_sha256=snapshot_sha256,
        pcb_command_path="build/native/synthetic-paths/pcb-command.json",
        pcb_command_sha256=digest("synthetic successful PCB export command"),
        pcb_probe_sha256=observed_snapshot.probe_sha256,
        kicad_version=observed_snapshot.kicad_version,
        image=observed_snapshot.image,
        entries=entries,
    )
    netlist_sha256 = digest(observed_netlist.model_dump_json())
    coach = ContractCoachReport(
        status="READY_FOR_REVIEW",
        project_id="synthetic-paths",
        source_hashes={},
        netlist_sha256=netlist_sha256,
        observed=observed_netlist,
    )
    return evaluate(
        "synthetic-path-coverage-fault" if fault else "synthetic-path-coverage-control",
        coach,
        DesignLintPolicy(pcb_signal_path_rule_map=requirements),
        pcb_signal_path_coverage=coverage,
    )


def test_exact_path_and_bundle_rules_cover_reviewed_map() -> None:
    entries = compare()

    assert [entry.id for entry in entries] == ["clock", "data", "serial-bundle"]
    assert {entry.status for entry in entries} == {"COMPLETE"}
    assert [constraint.constraint for entry in entries for constraint in entry.constraints] == [
        "length",
        "length",
        "skew",
    ]
    assert [
        constraint.observed_max_nm for entry in entries for constraint in entry.constraints
    ] == [
        20_000_000,
        20_000_000,
        100_000,
    ]


def test_design_lint_reports_wrong_native_path_bound_and_complete_control() -> None:
    fault = design_lint_report(fault=True)
    control = design_lint_report(fault=False)

    assert fault.status == "REVIEW"
    assert fault.pcb_signal_path_rules.status == "INCOMPLETE"
    assert {finding.rule_id for finding in fault.findings} == {"pcb.signal_path_rule_coverage"}
    assert control.status == "PASS"
    assert control.pcb_signal_path_rules.status == "COMPLETE"
    assert control.findings == ()


def test_missing_wrong_duplicate_and_ignored_native_rules_are_incomplete() -> None:
    source = native_rules()
    data_rule = """(rule "synthetic-data-length"
  (condition "A.fromTo('J1-2', 'U1-2')")
  (constraint length (max 20mm)))
"""
    missing = compare(rules=source.replace(data_rule, ""))
    assert next(entry for entry in missing if entry.id == "data").constraints[0].status == "MISSING"

    wrong = compare(rules=source.replace("(max 20mm)", "(max 19mm)", 1))
    assert next(entry for entry in wrong if entry.id == "clock").constraints[0].status == "MISMATCH"

    duplicate = (
        source
        + """
(rule "duplicate-clock-length"
  (condition "A.fromTo('J1-1', 'U1-1')")
  (constraint length (max 20mm)))
"""
    )
    ambiguous = compare(rules=duplicate)
    assert (
        next(entry for entry in ambiguous if entry.id == "clock").constraints[0].status
        == "AMBIGUOUS"
    )

    ignored = compare(ignored=frozenset({"length_out_of_range", "skew_out_of_range"}))
    assert {item.status for entry in ignored for item in entry.constraints} == {"IGNORED"}


def test_custom_rule_ignore_severity_is_not_credited_for_a_path_or_bundle() -> None:
    ignored_rules = native_rules().replace(
        '(rule "synthetic-clock-length"',
        '(rule "synthetic-clock-length"\n  (severity ignore)',
        1,
    )
    entries = compare(rules=ignored_rules)
    clock = next(entry for entry in entries if entry.id == "clock")
    assert clock.status == "INCOMPLETE"
    assert clock.constraints[0].status == "IGNORED"
    assert "custom-rule severity is 'ignore'" in (clock.constraints[0].issue or "")
    assert all(entry.status == "COMPLETE" for entry in entries if entry.id != "clock")


@pytest.mark.parametrize("severity", ("error", "warning", "exclusion"))
def test_supported_nonignored_custom_rule_severities_preserve_coverage(
    severity: str,
) -> None:
    rules = native_rules().replace(
        '(rule "synthetic-clock-length"',
        f'(rule "synthetic-clock-length"\n  (severity {severity})',
        1,
    )
    clock = next(entry for entry in compare(rules=rules) if entry.id == "clock")
    assert clock.status == "COMPLETE"
    assert clock.constraints[0].status == "COVERED"


def test_source_net_and_copper_faults_remain_incomplete() -> None:
    missing_source_pad = NetlistContract(
        components={},
        nets={
            "SYNTH_CLK": ("J1.1",),
            "SYNTH_DATA": ("J1.2", "U1.2"),
        },
    )
    source_entries = compare(netlist=missing_source_pad)
    clock = next(entry for entry in source_entries if entry.id == "clock")
    assert clock.status == "INCOMPLETE"
    assert any("source-bound net" in issue for issue in clock.issues)

    disconnected_pads = tuple(
        pad.model_copy(update={"connected_pads": (pad.pad,)})
        if pad.pad in {"J1.1", "U1.1"}
        else pad
        for pad in pcb_snapshot().pads
    )
    disconnected = pcb_snapshot().model_copy(update={"pads": disconnected_pads})
    copper_entries = compare(snapshot=disconnected)
    clock = next(entry for entry in copper_entries if entry.id == "clock")
    assert clock.status == "INCOMPLETE"
    assert any("same native copper component" in issue for issue in clock.issues)

    misplaced_pads = tuple(
        pad.model_copy(update={"net": "SYNTH_DATA"}) if pad.pad == "U1.1" else pad
        for pad in pcb_snapshot().pads
    )
    misplaced = pcb_snapshot().model_copy(update={"pads": misplaced_pads})
    mismatch_entries = compare(snapshot=misplaced)
    clock = next(entry for entry in mismatch_entries if entry.id == "clock")
    assert clock.status == "INCOMPLETE"
    assert any("not assigned" in issue for issue in clock.issues)


def test_bundle_selector_must_not_include_unmapped_pads() -> None:
    extra = PcbPadConnectivityObservation(
        pad="J1.9",
        net="SYNTH_DATA",
        footprint="Synthetic:Connector",
        dnp=False,
        connected_pads=("J1.9",),
        connected_zones=(),
        connected_islands=(),
        connected_vias=(),
        positions_nm=((1_000_000, 9_000_000),),
    )
    snapshot = pcb_snapshot().model_copy(update={"pads": (*pcb_snapshot().pads, extra)})
    entries = compare(snapshot=snapshot)
    bundle = next(entry for entry in entries if entry.kind == "bundle")

    assert bundle.status == "INCOMPLETE"
    assert any("exactly the mapped bundle endpoints" in issue for issue in bundle.issues)


def test_native_drc_fixture_report_adapter_extracts_typed_fields(tmp_path: Path) -> None:
    violations = [
        {
            "type": "skew_out_of_range",
            "severity": "error",
            "items": [{"uuid": "synthetic-skew", "position": {"x": 10, "y": 20}}],
        },
        {
            "type": "length_out_of_range",
            "severity": "error",
            "items": [{"uuid": "synthetic-length", "position": {"x": 30, "y": 40}}],
        },
    ]
    report_path = tmp_path / "control.json"
    report_path.write_text(
        json.dumps(
            {
                "kicad_version": "10.0.5",
                "source": "/output/control.kicad_pcb",
                "violations": violations,
                "ignored_checks": [],
            }
        ),
        encoding="utf-8",
    )

    report = read_native_pcb_drc_fixture_report(report_path)

    assert report.kicad_version == "10.0.5"
    assert report.source == "/output/control.kicad_pcb"
    assert report.violation_types == ("length_out_of_range", "skew_out_of_range")
    assert len(report.violation_records_sha256) == 64

    reordered_path = tmp_path / "reordered.json"
    reordered_path.write_text(
        json.dumps(
            {
                "kicad_version": "10.0.5",
                "source": "/output/control.kicad_pcb",
                "violations": list(reversed(violations)),
            }
        ),
        encoding="utf-8",
    )
    reordered = read_native_pcb_drc_fixture_report(reordered_path)
    assert reordered.violation_records_sha256 == report.violation_records_sha256

    changed_path = tmp_path / "changed.json"
    changed_violations = [dict(item) for item in violations]
    changed_violations[0] = {
        **changed_violations[0],
        "items": [{"uuid": "synthetic-skew", "position": {"x": 11, "y": 20}}],
    }
    changed_path.write_text(
        json.dumps(
            {
                "kicad_version": "10.0.5",
                "source": "/output/control.kicad_pcb",
                "violations": changed_violations,
            }
        ),
        encoding="utf-8",
    )
    changed = read_native_pcb_drc_fixture_report(changed_path)
    assert changed.violation_records_sha256 != report.violation_records_sha256


def test_map_order_and_native_rule_order_are_stable() -> None:
    requirements = path_map()
    reordered_map = requirements.model_copy(update={"paths": tuple(reversed(requirements.paths))})
    chunks = native_rules().strip().split("\n(rule ")
    reordered_rules = chunks[0] + "\n(rule " + "\n(rule ".join(reversed(chunks[1:]))

    original = compare(requirements=requirements)
    reordered = compare(requirements=reordered_map, rules=reordered_rules)

    assert [entry.model_dump(mode="json") for entry in original] == [
        entry.model_dump(mode="json") for entry in reordered
    ]


def test_wrong_bound_and_wildcard_expansion_mutations_are_detected() -> None:
    changed_max_skew = native_rules().replace("(max 0.1mm)", "(max 0.2mm)")
    skew_entry = next(
        entry for entry in compare(rules=changed_max_skew) if entry.id == "serial-bundle"
    )
    assert skew_entry.constraints[0].status == "MISMATCH"

    narrowed_pattern_map = path_map().model_copy(
        update={"bundles": (path_map().bundles[0].model_copy(update={"from_pad_pattern": "J1-1"}),)}
    )
    with pytest.raises(ValidationError, match="must use a wildcard"):
        PcbSignalPathRuleMap.model_validate(narrowed_pattern_map.model_dump())


def test_reversed_duplicate_path_and_non_wildcard_bundle_are_rejected() -> None:
    duplicate = PcbSignalPathRequirement(
        id="reverse-clock",
        basis="Synthetic duplicate route in reverse order",
        net="SYNTH_CLK",
        from_pad="U1.1",
        to_pad="J1.1",
        length=PcbDrcMinMaxRequirement(max_nm=20_000_000),
    )
    with pytest.raises(ValidationError, match="can only be mapped once"):
        PcbSignalPathRuleMap(
            basis="Synthetic duplicate map",
            paths=(*path_map().paths, duplicate),
            bundles=path_map().bundles,
        )

    with pytest.raises(ValidationError, match="must use a wildcard"):
        PcbSignalPathBundleRequirement(
            id="bad-bundle",
            basis="Synthetic invalid bundle",
            path_ids=("a", "b"),
            from_pad_pattern="J1-1",
            to_pad_pattern="U1-*",
            max_skew=PcbDrcMaximumRequirement(max_nm=100_000),
        )


def incomplete_signal_report(requirements: PcbSignalPathRuleMap) -> PcbSignalPathRuleCoverageReport:
    entry = PcbSignalPathRuleCoverageEntry(
        id="clock",
        kind="path",
        basis="Synthetic clock route requirement",
        net="SYNTH_CLK",
        from_pad="J1.1",
        to_pad="U1.1",
        status="INCOMPLETE",
        constraints=(
            PcbDrcConstraintCoverage(
                constraint="length",
                status="MISSING",
                expected_max_nm=20_000_000,
                issue="No matching native rule",
            ),
        ),
    )
    map_sha = hashlib.sha256(requirements.model_dump_json().encode("utf-8")).hexdigest()
    return PcbSignalPathRuleCoverageReport(
        status="INCOMPLETE",
        mode="review",
        map_sha256=map_sha,
        source_inventory_sha256="d" * 64,
        project_path="hardware/synthetic.kicad_pro",
        project_sha256="e" * 64,
        rules_path="hardware/synthetic.kicad_dru",
        rules_sha256="f" * 64,
        board_path="hardware/synthetic.kicad_pcb",
        board_sha256="a" * 64,
        native_summary_path="build/native/summary.json",
        native_summary_sha256="b" * 64,
        native_drc_path="build/native/drc.json",
        native_drc_sha256="c" * 64,
        pcb_snapshot_path="build/native/pcb/snapshot.json",
        pcb_snapshot_sha256="1" * 64,
        pcb_command_path="build/native/pcb/native.command.json",
        pcb_command_sha256="2" * 64,
        pcb_probe_sha256="3" * 64,
        kicad_version="10.0.5",
        image="ghcr.io/kicad/kicad:10.0.5@sha256:" + "4" * 64,
        entries=(entry,),
    )


def test_signal_path_coverage_has_review_block_off_ignore_and_missing_evidence_modes() -> None:
    requirements = path_map()
    source = source_netlist()
    coach = ContractCoachReport(
        status="READY_FOR_REVIEW",
        project_id="synthetic-paths",
        source_hashes={},
        netlist_sha256="5" * 64,
        observed=source,
    )
    report = evaluate(
        "synthetic-paths",
        coach,
        DesignLintPolicy(pcb_signal_path_rule_map=requirements),
        pcb_signal_path_coverage=incomplete_signal_report(requirements),
    )
    finding = next(
        item for item in report.findings if item.rule_id == "pcb.signal_path_rule_coverage"
    )
    assert report.status == "REVIEW"
    assert finding.disposition == "OPEN"

    blocked = evaluate(
        "synthetic-paths",
        coach,
        DesignLintPolicy(
            pcb_signal_path_rule_map=requirements,
            rules=(
                DesignLintRuleOverride(
                    rule_id="pcb.signal_path_rule_coverage",
                    mode="block",
                    reason="Synthetic project policy",
                ),
            ),
        ),
        pcb_signal_path_coverage=incomplete_signal_report(requirements),
    )
    assert blocked.status == "FAIL"

    disabled = evaluate(
        "synthetic-paths",
        coach,
        DesignLintPolicy(
            pcb_signal_path_rule_map=requirements,
            rules=(
                DesignLintRuleOverride(
                    rule_id="pcb.signal_path_rule_coverage",
                    mode="off",
                    reason="Synthetic project policy",
                ),
            ),
        ),
        pcb_signal_path_coverage=incomplete_signal_report(requirements),
    )
    assert disabled.pcb_signal_path_rules.status == "DISABLED"
    assert not any(item.rule_id == finding.rule_id for item in disabled.findings)

    ignored = evaluate(
        "synthetic-paths",
        coach,
        DesignLintPolicy(
            pcb_signal_path_rule_map=requirements,
            ignores=(
                DesignLintIgnore(
                    rule_id=finding.rule_id,
                    fingerprint=finding.fingerprint,
                    reason="Synthetic exact review disposition",
                ),
            ),
        ),
        pcb_signal_path_coverage=incomplete_signal_report(requirements),
    )
    ignored_finding = next(item for item in ignored.findings if item.rule_id == finding.rule_id)
    assert ignored_finding.disposition == "IGNORED"

    no_evidence = evaluate(
        "synthetic-paths",
        coach,
        DesignLintPolicy(pcb_signal_path_rule_map=requirements),
    )
    assert no_evidence.status == "BLOCKED"
    assert no_evidence.pcb_signal_path_rules.status == "BLOCKED"
