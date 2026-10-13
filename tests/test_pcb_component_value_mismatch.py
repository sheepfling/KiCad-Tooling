"""Synthetic regressions for schematic/PCB component value consistency."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from kicad_tooling.hwrepo import design_lint_pcb_geometry_capture, design_lint_pcb_geometry_scan
from kicad_tooling.hwrepo.contracts import write_model
from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.design_lint_candidate_aggregation import fingerprint
from kicad_tooling.hwrepo.design_lint_pcb_component_inventory_candidates import (
    pcb_component_inventory_candidates,
)
from kicad_tooling.hwrepo.electrical import selected_config
from kicad_tooling.hwrepo.models import (
    CommandEvidence,
    ContractCoachReport,
    DesignLintIgnore,
    DesignLintPolicy,
    DesignLintRuleOverride,
)
from kicad_tooling.hwrepo.pcb_component_inventory import (
    evaluate_native_component_inventory_coverage,
)
from kicad_tooling.hwrepo.pcb_component_values import compare_schematic_pcb_values
from kicad_tooling.validate import hashes
from tests.design_lint_fixtures.pcb_component_inventory import (
    BOARD_SHA256,
    NETLIST_SHA256,
    PROBE_SHA256,
    SNAPSHOT_SHA256,
    coach,
    complete_report,
    netlist,
    snapshot,
)
from tests.synthetic_design_lint_project import synthetic_design_lint_project

pytestmark = [pytest.mark.design_lint, pytest.mark.pcb_lint]
RULE_ID = "pcb.schematic_pcb_value_mismatch"
FOOTPRINT = "Synthetic:Probe_Module"


def test_value_difference_is_reviewable_configurable_and_source_bound() -> None:
    observed = netlist(components={"R1": FOOTPRINT}, values={"R1": "10k"})
    coverage = complete_report(
        observed,
        snapshot(
            "R1",
            schema_version="13",
            footprint_by_reference={"R1": FOOTPRINT},
            value_by_reference={"R1": "10K"},
        ),
        value_mode="review",
    )

    (candidate,) = tuple(
        item for item in pcb_component_inventory_candidates(coverage) if item.rule_id == RULE_ID
    )
    assert candidate.subject == "R1: schematic and PCB value fields differ"
    assert candidate.evidence["schematic_value"] == ("10k",)
    assert candidate.evidence["board_value"] == ("10K",)
    assert candidate.evidence["netlist_sha256"] == ("a" * 64,)
    assert candidate.evidence["board_sha256"] == ("b" * 64,)
    assert candidate.evidence["snapshot_sha256"] == ("c" * 64,)
    assert candidate.evidence["snapshot_schema"] == ("13",)

    reviewed = evaluate(
        "synthetic-component-values",
        coach(observed),
        DesignLintPolicy(),
        pcb_component_inventory_coverage=coverage,
    )
    assert reviewed.status == "REVIEW"
    assert tuple(item.rule_id for item in reviewed.findings) == (RULE_ID,)
    assert reviewed.findings[0].mode == "review"

    blocked = evaluate(
        "synthetic-component-values",
        coach(observed),
        DesignLintPolicy(
            rules=(DesignLintRuleOverride(rule_id=RULE_ID, mode="block", reason="release gate"),)
        ),
        pcb_component_inventory_coverage=coverage,
    )
    assert blocked.status == "FAIL"
    assert blocked.findings[0].mode == "block"

    disabled = evaluate(
        "synthetic-component-values",
        coach(observed),
        DesignLintPolicy(
            rules=(DesignLintRuleOverride(rule_id=RULE_ID, mode="off", reason="reviewed format"),)
        ),
        pcb_component_inventory_coverage=coverage,
    )
    assert disabled.status == "PASS"
    assert disabled.findings[0].disposition == "RULE_OFF"

    ignored = DesignLintPolicy(
        ignores=(
            DesignLintIgnore(
                rule_id=RULE_ID,
                fingerprint=fingerprint(candidate),
                reason="the board value is an approved assembly label",
            ),
        )
    )
    ignored_report = evaluate(
        "synthetic-component-values",
        coach(observed),
        ignored,
        pcb_component_inventory_coverage=coverage,
    )
    assert ignored_report.findings[0].disposition == "IGNORED"

    changed = coverage.model_copy(
        update={"snapshot_sha256": hashlib.sha256(b"changed board value").hexdigest()}
    )
    stale = evaluate(
        "synthetic-component-values",
        coach(observed),
        ignored,
        pcb_component_inventory_coverage=changed,
    )
    assert stale.findings[0].disposition == "OPEN"
    assert tuple(item.rule_id for item in stale.stale_ignores) == (RULE_ID,)


def test_matching_trimmed_values_and_noncomparable_parts_are_controls() -> None:
    observed = netlist(
        components={"R1": FOOTPRINT, "U1": FOOTPRINT, "R2": "", "U4": FOOTPRINT},
        values={"R1": " 10k ", "U1": "DNP option", "R2": "unplaced", "U4": "missing"},
        dnp=("U1",),
    )
    board = snapshot(
        "R1",
        "U1",
        "R2",
        "U3",
        schema_version="13",
        footprint_by_reference={"R1": FOOTPRINT, "U1": FOOTPRINT, "R2": FOOTPRINT},
        value_by_reference={
            "R1": "10k",
            "U1": "stale DNP label",
            "R2": "unassigned",
            "U3": "extra",
        },
        dnp_by_reference={"U1": True},
    )

    assert compare_schematic_pcb_values(observed, board) == ()
    coverage = complete_report(observed, board, value_mode="review")
    assert not any(item.rule_id == RULE_ID for item in pcb_component_inventory_candidates(coverage))


def test_value_comparison_is_order_independent_and_values_are_case_sensitive() -> None:
    first = compare_schematic_pcb_values(
        netlist(
            components={"R2": FOOTPRINT, "R1": FOOTPRINT},
            values={"R1": "10k", "R2": "1uF"},
        ),
        snapshot(
            "R2",
            "R1",
            schema_version="13",
            footprint_by_reference={"R1": FOOTPRINT, "R2": FOOTPRINT},
            value_by_reference={"R1": "10K", "R2": "1uF-old"},
        ),
    )
    reordered = compare_schematic_pcb_values(
        netlist(
            components={"R1": FOOTPRINT, "R2": FOOTPRINT},
            values={"R1": "10k", "R2": "1uF"},
        ),
        snapshot(
            "R1",
            "R2",
            schema_version="13",
            footprint_by_reference={"R2": FOOTPRINT, "R1": FOOTPRINT},
            value_by_reference={"R2": "1uF-old", "R1": "10K"},
        ),
    )

    assert tuple((item.reference, item.schematic_value, item.board_value) for item in first) == (
        ("R1", "10k", "10K"),
        ("R2", "1uF", "1uF-old"),
    )
    assert reordered == first


def test_schema_12_remains_supported_for_inventory_but_blocks_value_comparison() -> None:
    observed = netlist(components={"R1": FOOTPRINT}, values={"R1": "10k"})
    board = snapshot("R1", footprint_by_reference={"R1": FOOTPRINT})
    coverage = evaluate_native_component_inventory_coverage(
        observed,
        board,
        mode="review",
        value_mode="review",
        netlist_sha256=NETLIST_SHA256,
        board_path="synthetic/controller.kicad_pcb",
        board_sha256=BOARD_SHA256,
        snapshot_path="build/design-lint/native/snapshot.json",
        snapshot_sha256=SNAPSHOT_SHA256,
        probe_sha256=PROBE_SHA256,
    )

    assert coverage.status == "COMPLETE"
    assert coverage.value_comparison_status == "BLOCKED"
    (candidate,) = tuple(
        item for item in pcb_component_inventory_candidates(coverage) if item.rule_id == RULE_ID
    )
    assert candidate.evidence["snapshot_schema"] == ("12",)
    assert "schema 13" in candidate.evidence["coverage_issue"][0]


def test_value_only_policy_captures_and_compares_native_footprint_values(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    policy = DesignLintPolicy(
        rules=(
            DesignLintRuleOverride(
                rule_id="pcb.schematic_component_inventory",
                mode="off",
                reason="Exercise value-only scan selection",
            ),
            DesignLintRuleOverride(
                rule_id="pcb.schematic_pcb_dnp_mismatch",
                mode="off",
                reason="Exercise value-only scan selection",
            ),
            DesignLintRuleOverride(
                rule_id=RULE_ID,
                mode="review",
                reason="Compare the value field independently",
            ),
        )
    )
    root, native_summary = synthetic_design_lint_project(tmp_path, policy)
    config = selected_config(root, "controller")
    observed = netlist(components={"R1": FOOTPRINT}, values={"R1": "10k"})
    coach_report = ContractCoachReport(
        status="READY_FOR_REVIEW",
        project_id="controller",
        project_kind=config.kind,
        source_hashes=hashes(root, config.source_roots),
        netlist_sha256=NETLIST_SHA256,
        observed=observed,
    )
    board_path = (root / config.project).with_suffix(".kicad_pcb")
    board_sha256 = hashlib.sha256(board_path.read_bytes()).hexdigest()
    native_snapshot = snapshot(
        "R1",
        schema_version="13",
        footprint_by_reference={"R1": FOOTPRINT},
        value_by_reference={"R1": "10K"},
    ).model_copy(
        update={
            "board_sha256": board_sha256,
            "kicad_version": config.kicad_version,
            "image": config.image,
            "probe_sha256": PROBE_SHA256,
        }
    )
    command = CommandEvidence(
        argv=("docker", "run", "--synthetic-native-probe"),
        started_utc="synthetic fixture",
        returncode=0,
    )

    def capture_snapshot(_root, _config, output, _access_probe_requests=None, **_kwargs):
        output.mkdir(parents=True)
        write_model(output / "native.command.json", command)
        return command, native_snapshot

    monkeypatch.setattr(
        design_lint_pcb_geometry_capture,
        "capture_native_pcb_connectivity",
        capture_snapshot,
    )
    monkeypatch.setattr(
        design_lint_pcb_geometry_capture,
        "expected_probe_sha256",
        lambda: PROBE_SHA256,
    )
    monkeypatch.setattr(
        design_lint_pcb_geometry_capture,
        "native_pcb_command_matches",
        lambda *_args, **_kwargs: True,
    )

    coverage = design_lint_pcb_geometry_scan.scan_pcb_geometry(
        root,
        config,
        coach_report,
        policy,
        native_summary,
    )[-1]

    assert coverage.status == "COMPLETE"
    assert coverage.value_comparison_status == "COMPLETE"
    assert tuple(
        (item.reference, item.schematic_value, item.board_value)
        for item in coverage.value_mismatches
    ) == (("R1", "10k", "10K"),)
