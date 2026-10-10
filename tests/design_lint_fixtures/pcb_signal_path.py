"""Synthetic source and native PCB inputs for signal-path rule coverage tests."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.models import (
    ContractCoachReport,
    DesignLintPolicy,
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
from kicad_tooling.hwrepo.pcb_drc_rule_coverage import compare_native_signal_path_rules

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures/design_lint/differential-pair"


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
