"""Synthetic regressions for schematic-to-PCB pad net assignment consistency."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from kicad_tooling.hwrepo import design_lint_pcb_geometry_scan
from kicad_tooling.hwrepo.contracts import write_model
from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.design_lint_candidate_aggregation import fingerprint
from kicad_tooling.hwrepo.design_lint_pcb_pad_net_candidates import pcb_pad_net_candidates
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
from kicad_tooling.hwrepo.pcb_pad_net_comparison import compare_schematic_pcb_pad_nets
from kicad_tooling.validate import hashes
from tests.design_lint_fixtures.pcb_component_inventory import (
    BOARD_SHA256,
    NETLIST_SHA256,
    PROBE_SHA256,
    SNAPSHOT_SHA256,
    coach,
    netlist,
    snapshot,
)
from tests.synthetic_design_lint_project import synthetic_design_lint_project

pytestmark = [pytest.mark.design_lint, pytest.mark.pcb_lint]
RULE_ID = "pcb.schematic_pcb_pad_net_mismatch"
FOOTPRINT = "Synthetic:Probe_Module"


def _coverage(observed, board, *, mode="review", pad_net_mode="review"):
    return evaluate_native_component_inventory_coverage(
        observed,
        board,
        mode=mode,
        pad_net_mode=pad_net_mode,
        netlist_sha256=NETLIST_SHA256,
        board_path="synthetic/controller.kicad_pcb",
        board_sha256=BOARD_SHA256,
        snapshot_path="build/design-lint/native/snapshot.json",
        snapshot_sha256=SNAPSHOT_SHA256,
        probe_sha256=PROBE_SHA256,
    )


def test_connected_pin_board_pad_net_differences_are_reviewable_and_configurable() -> None:
    observed = netlist(
        components={"U1": FOOTPRINT},
        nets={"SIGNAL": ("U1.1",)},
        component_pin_numbers={"U1": ("1",)},
    )
    cases = (
        (None, False, "board_pad_missing"),
        (None, True, "board_pad_unassigned"),
        ("OTHER_SIGNAL", True, "net_assignment_differs"),
    )
    for board_net, include_pad, expected_mismatch in cases:
        pad_assignments = {"U1.1": board_net} if include_pad else {}
        coverage = _coverage(
            observed,
            snapshot(
                "U1",
                footprint_by_reference={"U1": FOOTPRINT},
                pad_net_by_reference=pad_assignments,
            ),
        )
        (mismatch,) = coverage.pad_net_mismatches
        assert mismatch.mismatch == expected_mismatch
        (candidate,) = pcb_pad_net_candidates(coverage)
        assert candidate.rule_id == RULE_ID
        assert candidate.evidence["reference"] == ("U1",)
        assert candidate.evidence["pin"] == ("1",)
        assert candidate.evidence["netlist_sha256"] == (NETLIST_SHA256,)
        assert candidate.evidence["board_sha256"] == (BOARD_SHA256,)
        assert candidate.evidence["snapshot_sha256"] == (SNAPSHOT_SHA256,)

        reviewed = evaluate(
            "synthetic-pad-nets",
            coach(observed),
            DesignLintPolicy(),
            pcb_component_inventory_coverage=coverage,
        )
        assert reviewed.status == "REVIEW"
        assert tuple(item.rule_id for item in reviewed.findings) == (RULE_ID,)
        assert reviewed.findings[0].mode == "review"

        blocked = evaluate(
            "synthetic-pad-nets",
            coach(observed),
            DesignLintPolicy(
                rules=(DesignLintRuleOverride(rule_id=RULE_ID, mode="block", reason="release"),)
            ),
            pcb_component_inventory_coverage=coverage,
        )
        assert blocked.status == "FAIL"
        assert blocked.findings[0].mode == "block"

        disabled = evaluate(
            "synthetic-pad-nets",
            coach(observed),
            DesignLintPolicy(
                rules=(
                    DesignLintRuleOverride(
                        rule_id=RULE_ID,
                        mode="off",
                        reason="approved alternate footprint mapping",
                    ),
                )
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
                    reason="reviewed alternate pin mapping",
                ),
            )
        )
        ignored_report = evaluate(
            "synthetic-pad-nets",
            coach(observed),
            ignored,
            pcb_component_inventory_coverage=coverage,
        )
        assert ignored_report.findings[0].disposition == "IGNORED"

        changed = coverage.model_copy(
            update={"snapshot_sha256": hashlib.sha256(b"changed board pad net").hexdigest()}
        )
        stale = evaluate(
            "synthetic-pad-nets",
            coach(observed),
            ignored,
            pcb_component_inventory_coverage=changed,
        )
        assert stale.findings[0].disposition == "OPEN"
        assert tuple(item.rule_id for item in stale.stale_ignores) == (RULE_ID,)


def test_board_assignment_on_schematic_unconnected_pin_is_reviewable() -> None:
    observed = netlist(
        components={"U1": FOOTPRINT},
        unconnected_nets={"unconnected-(U1-NC-Pad1)": ("U1.1",)},
        component_pin_numbers={"U1": ("1",)},
    )
    board = snapshot(
        "U1",
        footprint_by_reference={"U1": FOOTPRINT},
        pad_net_by_reference={"U1.1": "BOARD_SIGNAL"},
    )

    (mismatch,) = compare_schematic_pcb_pad_nets(observed, board)
    assert mismatch.mismatch == "schematic_unconnected_board_assigned"
    assert mismatch.schematic_net is None
    assert mismatch.board_net == "BOARD_SIGNAL"


def test_matching_assignments_and_noncomparable_components_are_controls() -> None:
    observed = netlist(
        components={"U1": FOOTPRINT, "U2": FOOTPRINT, "U3": "", "U4": FOOTPRINT},
        nets={"SIGNAL": ("U1.1", "U2.1", "U3.1", "U4.1")},
        component_pin_numbers={
            "U1": ("1",),
            "U2": ("1",),
            "U3": ("1",),
            "U4": ("1",),
        },
    )
    board = snapshot(
        "U1",
        "U2",
        "U3",
        "U4",
        footprint_by_reference={
            "U1": FOOTPRINT,
            "U2": FOOTPRINT,
            "U3": FOOTPRINT,
            "U4": "Synthetic:Alternate_Module",
        },
        pad_net_by_reference={"U1.1": "SIGNAL", "U2.1": None, "U4.1": "OTHER"},
    )

    assert tuple(
        (item.reference, item.mismatch) for item in compare_schematic_pcb_pad_nets(observed, board)
    ) == (("U2", "board_pad_unassigned"),)
    assert pcb_pad_net_candidates(_coverage(observed, board))[0].evidence["reference"] == ("U2",)


def test_pad_net_comparison_is_order_independent_and_net_names_are_exact() -> None:
    first = compare_schematic_pcb_pad_nets(
        netlist(
            components={"U2": FOOTPRINT, "U1": FOOTPRINT},
            nets={"Signal": ("U1.1",), "GROUND": ("U2.1",)},
        ),
        snapshot(
            "U2",
            "U1",
            footprint_by_reference={"U1": FOOTPRINT, "U2": FOOTPRINT},
            pad_net_by_reference={"U1.1": "signal", "U2.1": "GROUND"},
        ),
    )
    reordered = compare_schematic_pcb_pad_nets(
        netlist(
            components={"U1": FOOTPRINT, "U2": FOOTPRINT},
            nets={"GROUND": ("U2.1",), "Signal": ("U1.1",)},
        ),
        snapshot(
            "U1",
            "U2",
            footprint_by_reference={"U2": FOOTPRINT, "U1": FOOTPRINT},
            pad_net_by_reference={"U2.1": "GROUND", "U1.1": "signal"},
        ),
    )

    assert tuple((item.reference, item.schematic_net, item.board_net) for item in first) == (
        ("U1", "Signal", "signal"),
    )
    assert reordered == first


def test_pad_net_comparison_rejects_ambiguous_native_assignments() -> None:
    observed = netlist(
        components={"U1": FOOTPRINT},
        nets={"NET_A": ("U1.1",), "NET_B": ("U1.1",)},
    )

    with pytest.raises(ValueError, match="multiple electrical states"):
        compare_schematic_pcb_pad_nets(
            observed,
            snapshot("U1", footprint_by_reference={"U1": FOOTPRINT}),
        )


def test_missing_comparison_inputs_block_pad_net_coverage() -> None:
    coverage = evaluate_native_component_inventory_coverage(
        None,
        snapshot("U1", footprint_by_reference={"U1": FOOTPRINT}),
        mode="review",
        pad_net_mode="review",
        netlist_sha256=None,
        board_path="synthetic/controller.kicad_pcb",
        board_sha256=BOARD_SHA256,
        snapshot_path="build/design-lint/native/snapshot.json",
        snapshot_sha256=SNAPSHOT_SHA256,
        probe_sha256=PROBE_SHA256,
    )

    assert coverage.status == "BLOCKED"
    assert coverage.pad_net_comparison_status == "BLOCKED"
    (candidate,) = pcb_pad_net_candidates(coverage)
    assert candidate.rule_id == RULE_ID
    assert "unavailable" in candidate.evidence["coverage_issue"][0].casefold()


def test_pad_net_predicate_error_blocks_only_its_own_coverage() -> None:
    observed = netlist(
        components={"U1": FOOTPRINT},
        nets={"NET_A": ("U1.1",), "NET_B": ("U1.1",)},
    )
    coverage = _coverage(
        observed,
        snapshot("U1", footprint_by_reference={"U1": FOOTPRINT}),
    )

    assert coverage.status == "COMPLETE"
    assert coverage.pad_net_comparison_status == "BLOCKED"
    (candidate,) = pcb_pad_net_candidates(coverage)
    assert candidate.rule_id == RULE_ID
    assert "multiple electrical states" in candidate.evidence["coverage_issue"][0]


def test_pad_net_only_policy_captures_and_compares_native_pad_assignments(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    policy = DesignLintPolicy(
        rules=tuple(
            DesignLintRuleOverride(rule_id=rule_id, mode="off", reason="isolated rule test")
            for rule_id in (
                "pcb.schematic_component_inventory",
                "pcb.schematic_pcb_dnp_mismatch",
                "pcb.schematic_pcb_value_mismatch",
            )
        )
        + (DesignLintRuleOverride(rule_id=RULE_ID, mode="review", reason="test pad parity"),)
    )
    root, native_summary = synthetic_design_lint_project(tmp_path, policy)
    config = selected_config(root, "controller")
    observed = netlist(components={"U1": FOOTPRINT}, nets={"SCHEMATIC_NET": ("U1.1",)})
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
        "U1",
        footprint_by_reference={"U1": FOOTPRINT},
        pad_net_by_reference={"U1.1": "BOARD_NET"},
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

    def capture_snapshot(_root, _config, output, _access_probe_requests=None):
        output.mkdir(parents=True)
        write_model(output / "native.command.json", command)
        return command, native_snapshot

    monkeypatch.setattr(
        design_lint_pcb_geometry_scan,
        "capture_native_pcb_connectivity",
        capture_snapshot,
    )
    monkeypatch.setattr(
        design_lint_pcb_geometry_scan,
        "expected_probe_sha256",
        lambda: PROBE_SHA256,
    )
    monkeypatch.setattr(
        design_lint_pcb_geometry_scan,
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
    assert coverage.pad_net_comparison_status == "COMPLETE"
    assert tuple(
        (item.reference, item.schematic_net, item.board_net) for item in coverage.pad_net_mismatches
    ) == (("U1", "SCHEMATIC_NET", "BOARD_NET"),)
