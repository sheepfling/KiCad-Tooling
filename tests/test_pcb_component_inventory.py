"""Synthetic regressions for schematic-to-PCB component inventory review."""

from __future__ import annotations

import hashlib

import pytest
from pydantic import ValidationError

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.design_lint_candidate_aggregation import fingerprint
from kicad_tooling.hwrepo.design_lint_pcb_component_inventory_candidates import (
    pcb_component_inventory_candidates,
)
from kicad_tooling.hwrepo.design_lint_pcb_report import pcb_coverage_report_lines
from kicad_tooling.hwrepo.models import (
    ComponentContract,
    ContractCoachReport,
    DesignLintIgnore,
    DesignLintPolicy,
    DesignLintRuleOverride,
    NetlistContract,
    PcbConnectivitySnapshot,
    PcbFootprintPlacementObservation,
)
from kicad_tooling.hwrepo.pcb_component_inventory import (
    compare_fitted_schematic_pcb_inventory,
    evaluate_native_component_inventory_coverage,
    missing_fitted_footprint_placements,
)
from kicad_tooling.hwrepo.pcb_component_inventory_models import (
    PcbComponentInventoryCoverageReport,
    PcbFootprintIdentityMismatch,
    PcbMissingFootprintPlacement,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.pcb_lint]

RULE = "pcb.schematic_component_inventory"
NETLIST_SHA256 = "a" * 64
BOARD_SHA256 = "b" * 64
SNAPSHOT_SHA256 = "c" * 64
PROBE_SHA256 = "d" * 64
IMAGE = "registry.example/kicad:10.0.5@sha256:" + "e" * 64


def netlist(
    *,
    components: dict[str, str] | None = None,
    dnp: tuple[str, ...] = (),
) -> NetlistContract:
    assignments = components or {"U1": "Package_QFP:TQFP-48", "J1": "Connector:USB_B"}
    return NetlistContract(
        components={
            reference: ComponentContract(value="synthetic", footprint=footprint)
            for reference, footprint in assignments.items()
        },
        nets={},
        dnp_components=dnp,
    )


def snapshot(
    *references: str,
    schema_version: str = "12",
    footprint_by_reference: dict[str, str] | None = None,
) -> PcbConnectivitySnapshot:
    identity_by_reference = {
        reference.casefold(): footprint
        for reference, footprint in (footprint_by_reference or {}).items()
    }
    return PcbConnectivitySnapshot(
        schema_version=schema_version,
        board_sha256=BOARD_SHA256,
        kicad_version="10.0.5",
        image=IMAGE,
        probe_sha256=PROBE_SHA256,
        zones_refilled=True,
        pads=(),
        net_ties=(),
        zones=(),
        vias=(),
        access_probe_observations=(),
        access_probe_requests_sha256=None,
        tracks=(),
        copper_layers=("F.Cu", "B.Cu"),
        rule_areas=(),
        footprints=tuple(
            PcbFootprintPlacementObservation(
                reference=reference,
                footprint=identity_by_reference.get(reference.casefold(), "Synthetic:Footprint"),
                dnp=False,
                position_nm=(0, 0),
                orientation_microdegrees=0,
                side="F.Cu",
            )
            for reference in references
        ),
    )


def complete_report(
    observed: NetlistContract,
    board: PcbConnectivitySnapshot,
    *,
    mode: str = "review",
) -> PcbComponentInventoryCoverageReport:
    comparison = compare_fitted_schematic_pcb_inventory(observed, board)
    return PcbComponentInventoryCoverageReport(
        status="COMPLETE",
        mode=mode,
        netlist_sha256=NETLIST_SHA256,
        board_path="synthetic/controller.kicad_pcb",
        board_sha256=BOARD_SHA256,
        snapshot_path="build/design-lint/native/snapshot.json",
        snapshot_sha256=SNAPSHOT_SHA256,
        snapshot_schema="12",
        kicad_version=board.kicad_version,
        image=board.image,
        probe_sha256=board.probe_sha256,
        missing_placements=comparison.missing_placements,
        footprint_mismatches=comparison.footprint_mismatches,
    )


def coach(observed: NetlistContract) -> ContractCoachReport:
    return ContractCoachReport(
        status="READY_FOR_REVIEW",
        project_id="synthetic-component-inventory",
        observed=observed,
        netlist_sha256=NETLIST_SHA256,
    )


def test_fitted_assigned_footprint_missing_from_board_is_reviewable_and_configurable() -> None:
    observed = netlist(components={"U1": "Package_QFP:TQFP-48"})
    coverage = complete_report(observed, snapshot())

    (candidate,) = pcb_component_inventory_candidates(coverage)
    assert candidate.rule_id == RULE
    assert candidate.subject == "U1: schematic footprint absent from PCB"
    assert candidate.evidence["assigned_footprint"] == ("Package_QFP:TQFP-48",)
    assert candidate.evidence["board_sha256"] == (BOARD_SHA256,)
    assert candidate.evidence["snapshot_sha256"] == (SNAPSHOT_SHA256,)

    blocked = evaluate(
        "synthetic-component-inventory",
        coach(observed),
        DesignLintPolicy(
            rules=(DesignLintRuleOverride(rule_id=RULE, mode="block", reason="handoff gate"),)
        ),
        pcb_component_inventory_coverage=coverage,
    )
    assert blocked.status == "FAIL"
    assert blocked.findings[0].rule_id == RULE
    assert blocked.findings[0].mode == "block"

    ignored = DesignLintPolicy(
        ignores=(
            DesignLintIgnore(
                rule_id=RULE,
                fingerprint=fingerprint(candidate),
                reason="reviewed off-board component",
            ),
        )
    )
    reviewed = evaluate(
        "synthetic-component-inventory",
        coach(observed),
        ignored,
        pcb_component_inventory_coverage=coverage,
    )
    assert reviewed.status == "PASS"
    assert reviewed.findings[0].disposition == "IGNORED"

    off = evaluate(
        "synthetic-component-inventory",
        coach(observed),
        DesignLintPolicy(
            rules=(DesignLintRuleOverride(rule_id=RULE, mode="off", reason="not in scope"),)
        ),
        pcb_component_inventory_coverage=coverage,
    )
    assert off.status == "PASS"
    assert off.findings[0].disposition == "RULE_OFF"

    changed_evidence = coverage.model_copy(
        update={"snapshot_sha256": hashlib.sha256(b"new exact native snapshot").hexdigest()}
    )
    stale = evaluate(
        "synthetic-component-inventory",
        coach(observed),
        ignored,
        pcb_component_inventory_coverage=changed_evidence,
    )
    assert stale.findings[0].disposition == "OPEN"
    assert tuple(item.rule_id for item in stale.stale_ignores) == (RULE,)


def test_placed_reference_dnp_empty_assignment_and_board_extras_are_controls() -> None:
    observed = netlist(
        components={
            "U1": "Package_QFP:TQFP-48",
            "R1": "Resistor_SMD:R_0603_1608Metric",
            "H1": "",
            "u3": "Package_SO:SOIC-8",
        },
        dnp=("R1",),
    )
    board = snapshot(
        "U1",
        "U3",
        "H_MOUNT1",
        footprint_by_reference={
            "U1": "Package_QFP:TQFP-48",
            "U3": "Package_SO:SOIC-8",
        },
    )

    assert missing_fitted_footprint_placements(observed, board) == ()
    report = complete_report(observed, board)
    assert report.status == "COMPLETE"
    assert report.missing_placements == ()
    assert report.footprint_mismatches == ()
    assert pcb_component_inventory_candidates(report) == ()


def test_reference_and_inventory_order_do_not_change_comparison() -> None:
    observed = netlist(
        components={
            "J2": "Connector:USB_B",
            "U1": "Package_QFP:TQFP-48",
            "J1": "Connector:DB9",
        }
    )
    first = compare_fitted_schematic_pcb_inventory(
        observed,
        snapshot(
            "J2",
            "U1",
            footprint_by_reference={
                "J2": "Connector:USB_B",
                "U1": "Package_SO:SOIC-8",
            },
        ),
    )
    reordered = compare_fitted_schematic_pcb_inventory(
        netlist(
            components={
                "J1": "Connector:DB9",
                "U1": "Package_QFP:TQFP-48",
                "J2": "Connector:USB_B",
            }
        ),
        snapshot(
            "u1",
            "j2",
            footprint_by_reference={
                "u1": "Package_SO:SOIC-8",
                "j2": "Connector:USB_B",
            },
        ),
    )

    assert tuple(item.reference for item in first.missing_placements) == ("J1",)
    assert tuple(item.reference for item in first.footprint_mismatches) == ("U1",)
    assert reordered == first


def test_present_component_with_different_footprint_identity_is_reviewable_and_configurable() -> (
    None
):
    observed = netlist(components={"U1": "Package_SO:SOIC-8"})
    coverage = complete_report(
        observed,
        snapshot("u1", footprint_by_reference={"U1": "Package_TSSOP:TSSOP-8"}),
    )

    (candidate,) = pcb_component_inventory_candidates(coverage)
    assert candidate.rule_id == RULE
    assert candidate.subject == "U1: schematic and PCB footprint identities differ"
    assert candidate.evidence["assigned_footprint"] == ("Package_SO:SOIC-8",)
    assert candidate.evidence["placed_footprint"] == ("Package_TSSOP:TSSOP-8",)

    blocked = evaluate(
        "synthetic-component-inventory",
        coach(observed),
        DesignLintPolicy(
            rules=(DesignLintRuleOverride(rule_id=RULE, mode="block", reason="release review"),)
        ),
        pcb_component_inventory_coverage=coverage,
    )
    assert blocked.status == "FAIL"
    assert blocked.findings[0].evidence["placed_footprint"] == ("Package_TSSOP:TSSOP-8",)

    ignored = DesignLintPolicy(
        ignores=(
            DesignLintIgnore(
                rule_id=RULE,
                fingerprint=fingerprint(candidate),
                reason="approved alternate package",
            ),
        )
    )
    reviewed = evaluate(
        "synthetic-component-inventory",
        coach(observed),
        ignored,
        pcb_component_inventory_coverage=coverage,
    )
    assert reviewed.status == "PASS"
    assert reviewed.findings[0].disposition == "IGNORED"
    assert (
        "  Footprint identity mismatch: U1; schematic Package_SO:SOIC-8; PCB Package_TSSOP:TSSOP-8"
    ) in pcb_coverage_report_lines(reviewed)


def test_inventory_mismatch_model_rejects_duplicate_reference_categories() -> None:
    with pytest.raises(ValidationError, match="references must be unique"):
        PcbComponentInventoryCoverageReport(
            status="COMPLETE",
            mode="review",
            netlist_sha256=NETLIST_SHA256,
            board_path="synthetic/controller.kicad_pcb",
            board_sha256=BOARD_SHA256,
            snapshot_path="build/design-lint/native/snapshot.json",
            snapshot_sha256=SNAPSHOT_SHA256,
            snapshot_schema="12",
            kicad_version="10.0.5",
            image=IMAGE,
            probe_sha256=PROBE_SHA256,
            missing_placements=(
                PcbMissingFootprintPlacement(
                    reference="U1",
                    assigned_footprint="Package_SO:SOIC-8",
                ),
            ),
            footprint_mismatches=(
                PcbFootprintIdentityMismatch(
                    reference="u1",
                    assigned_footprint="Package_SO:SOIC-8",
                    placed_footprint="Package_TSSOP:TSSOP-8",
                ),
            ),
        )


def test_unsupported_snapshot_schema_is_a_coverage_gap() -> None:
    observed = netlist(components={"U1": "Package_QFP:TQFP-48"})

    with pytest.raises(ValueError, match="requires native footprint snapshot schema 12"):
        missing_fitted_footprint_placements(observed, snapshot(schema_version="11"))


def test_missing_native_inventory_evidence_is_not_reported_as_clean() -> None:
    observed = netlist(components={"U1": "Package_QFP:TQFP-48"})
    coverage = evaluate_native_component_inventory_coverage(
        observed,
        snapshot(schema_version="11"),
        mode="review",
        netlist_sha256=NETLIST_SHA256,
        board_path="synthetic/controller.kicad_pcb",
        board_sha256=BOARD_SHA256,
        snapshot_path="build/design-lint/native/snapshot.json",
        snapshot_sha256=SNAPSHOT_SHA256,
        probe_sha256=PROBE_SHA256,
    )

    report = evaluate(
        "synthetic-component-inventory",
        coach(observed),
        DesignLintPolicy(),
        pcb_component_inventory_coverage=coverage,
    )

    assert report.status != "PASS"
    assert coverage.status == "BLOCKED"
    assert coverage.issue == "PCB component inventory needs native footprint snapshot schema 12"
    (finding,) = tuple(item for item in report.findings if item.rule_id == RULE)
    assert finding.subject == "native PCB footprint inventory unavailable"
    assert finding.evidence["coverage_issue"] == (
        "PCB component inventory needs native footprint snapshot schema 12",
    )


def test_complete_inventory_receipt_requires_native_source_digests() -> None:
    with pytest.raises(ValidationError, match="full source receipt"):
        PcbComponentInventoryCoverageReport(status="COMPLETE", mode="review")


def test_inventory_candidate_fingerprint_changes_with_native_board_evidence() -> None:
    observed = netlist(components={"U1": "Package_QFP:TQFP-48"})
    report = complete_report(observed, snapshot())
    (candidate,) = pcb_component_inventory_candidates(report)
    relocated_receipt = report.model_copy(update={"snapshot_path": "build/new/snapshot.json"})
    (relocated_candidate,) = pcb_component_inventory_candidates(relocated_receipt)
    changed_report = report.model_copy(
        update={"snapshot_sha256": hashlib.sha256(b"new exact native snapshot").hexdigest()}
    )
    (changed_candidate,) = pcb_component_inventory_candidates(changed_report)

    assert fingerprint(candidate) == fingerprint(relocated_candidate)
    assert fingerprint(candidate) != fingerprint(changed_candidate)
