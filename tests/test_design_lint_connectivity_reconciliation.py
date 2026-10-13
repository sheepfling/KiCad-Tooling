"""Pin-level connectivity changes remain visible across source-bound lint baselines."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.design_lint import rule_catalog
from kicad_tooling.hwrepo.design_lint_connectivity_snapshot import (
    capture_connectivity_snapshot,
)
from kicad_tooling.hwrepo.design_lint_connectivity_snapshot_models import (
    DesignLintConnectivitySnapshot,
    NetlistPinConnectivityState,
)
from kicad_tooling.hwrepo.design_lint_reconciliation import reconcile_design_lint_reports
from kicad_tooling.hwrepo.design_lint_reconciliation_text import reconciliation_text
from kicad_tooling.hwrepo.design_lint_report_models import DesignLintReport
from kicad_tooling.hwrepo.models import ComponentContract, NetlistContract

pytestmark = [pytest.mark.design_lint, pytest.mark.evidence_lint]


def _netlist(*, split_return: bool = False, return_net_name: str = "GND") -> NetlistContract:
    return NetlistContract(
        components={
            "J1": ComponentContract(value="Synthetic DB9", footprint="Connector:DB9"),
            "U1": ComponentContract(value="Synthetic controller", footprint="Package:QFN"),
        },
        nets={
            "DATA": ("J1.2", "U1.3"),
            return_net_name: ("U1.2",) if split_return else ("J1.9", "U1.2"),
            **({"0V_PORT": ("J1.9",)} if split_return else {}),
        },
        component_pin_numbers={"J1": ("2", "9"), "U1": ("2", "3")},
    )


def _snapshot(
    netlist: NetlistContract,
    *,
    source_hash: str = "a" * 64,
    netlist_hash: str = "b" * 64,
    kicad_version: str = "10.0.5",
) -> DesignLintConnectivitySnapshot:
    return capture_connectivity_snapshot(
        project_id="synthetic-board",
        observed=netlist,
        source_hashes={"board.kicad_sch": source_hash},
        netlist_sha256=netlist_hash,
        kicad_version=kicad_version,
        toolchain_image="registry.example/kicad@sha256:" + "c" * 64,
    )


def _report(snapshot: DesignLintConnectivitySnapshot | None) -> DesignLintReport:
    return DesignLintReport(
        status="PASS",
        project_id="synthetic-board",
        source_hashes={} if snapshot is None else snapshot.source_hashes,
        netlist_sha256=None if snapshot is None else snapshot.netlist_sha256,
        connectivity_snapshot=snapshot,
        rule_catalog=rule_catalog(),
    )


def test_split_return_mutation_lists_each_changed_pin_and_peer_set() -> None:
    baseline = _report(_snapshot(_netlist()))
    current = _report(
        _snapshot(
            _netlist(split_return=True, return_net_name="0V_CONTROLLER"),
            source_hash="d" * 64,
            netlist_hash="e" * 64,
        )
    )

    report = reconcile_design_lint_reports(baseline, current)

    assert report.status == "REVIEW"
    assert report.connectivity_comparison == "COMPLETE"
    assert tuple((item.kind, item.pin) for item in report.connectivity_changes) == (
        ("ASSIGNMENT_CHANGED", "J1.9"),
        ("ASSIGNMENT_CHANGED", "U1.2"),
    )
    assert report.connectivity_changes[0].baseline == NetlistPinConnectivityState(
        net="GND", peers=("U1.2",)
    )
    assert report.connectivity_changes[0].current == NetlistPinConnectivityState(
        net="0V_PORT", peers=()
    )
    rendered = reconciliation_text(report)
    assert "Native pin connectivity changed for 2 pin(s)" in rendered
    assert "ASSIGNMENT_CHANGED J1.9" in rendered
    assert "peers=U1.2" in rendered


def test_native_net_rename_is_reviewed_as_an_assignment_change() -> None:
    baseline = _report(_snapshot(_netlist(return_net_name="GND")))
    current = _report(
        _snapshot(
            _netlist(return_net_name="RETURN"),
            source_hash="d" * 64,
            netlist_hash="e" * 64,
        )
    )

    report = reconcile_design_lint_reports(baseline, current)

    assert report.status == "REVIEW"
    assert len(report.connectivity_changes) == 2
    assert {item.baseline.net for item in report.connectivity_changes if item.baseline} == {"GND"}
    assert {item.current.net for item in report.connectivity_changes if item.current} == {"RETURN"}


def test_incomplete_pin_inventory_is_retained_as_partial_coverage() -> None:
    observed = _netlist().model_copy(update={"component_pin_numbers": {"J1": ("2", "9")}})

    snapshot = _snapshot(observed)

    assert snapshot.coverage == "PARTIAL"
    assert snapshot.issue is not None
    assert "missing for one or more components" in snapshot.issue
    assert snapshot.pin_states["J1.9"].net == "GND"


def test_partial_snapshot_does_not_report_unknown_pins_as_removed() -> None:
    baseline = _report(_snapshot(_netlist()))
    ambiguous = _netlist().model_copy(
        update={"nets": {"DATA": ("J1.2", "U1.3"), "GND": ("J1.9", "U1.2"), "OTHER": ("U1.2",)}}
    )
    current = _report(_snapshot(ambiguous, source_hash="d" * 64, netlist_hash="e" * 64))

    report = reconcile_design_lint_reports(baseline, current)

    assert report.status == "REVIEW"
    assert report.connectivity_comparison == "PARTIAL"
    assert report.connectivity_changes == ()
    assert any("comparison is partial" in item for item in report.context_changes)


def test_partial_snapshot_still_reports_changes_between_known_pins() -> None:
    baseline = _report(_snapshot(_netlist()))
    split = _netlist(split_return=True).model_copy(
        update={"component_pin_numbers": {"J1": ("2", "9")}}
    )
    current = _report(_snapshot(split, source_hash="d" * 64, netlist_hash="e" * 64))

    report = reconcile_design_lint_reports(baseline, current)

    assert report.status == "REVIEW"
    assert report.connectivity_comparison == "PARTIAL"
    assert tuple(item.pin for item in report.connectivity_changes) == ("J1.9", "U1.2")
    assert all(item.kind == "ASSIGNMENT_CHANGED" for item in report.connectivity_changes)


def test_ambiguous_pin_assignment_does_not_create_a_complete_snapshot() -> None:
    observed = _netlist().model_copy(
        update={"nets": {"DATA": ("J1.2", "U1.3"), "GND": ("U1.2",), "OTHER": ("U1.2",)}}
    )

    snapshot = _snapshot(observed)

    assert snapshot.coverage == "PARTIAL"
    assert snapshot.pin_states == {}
    assert "assigns one or more pins ambiguously" in (snapshot.issue or "")


def test_old_baseline_without_snapshot_requires_review_before_reuse() -> None:
    old_baseline = _report(_snapshot(_netlist())).model_copy(update={"connectivity_snapshot": None})
    report = reconcile_design_lint_reports(
        old_baseline,
        _report(_snapshot(_netlist(), source_hash="d" * 64, netlist_hash="e" * 64)),
    )

    assert report.status == "REVIEW"
    assert report.connectivity_comparison == "UNAVAILABLE"
    assert any("baseline report lacks" in change for change in report.context_changes)


def test_different_exact_native_toolchains_block_connectivity_comparison() -> None:
    baseline = _report(_snapshot(_netlist()))
    current = _report(
        _snapshot(_netlist(), source_hash="d" * 64, netlist_hash="e" * 64, kicad_version="10.0.0")
    )

    report = reconcile_design_lint_reports(baseline, current)

    assert report.status == "BLOCKED"
    assert report.connectivity_comparison == "INCOMPATIBLE"
    assert report.issue is not None
    assert "different exact KiCad versions" in report.issue
