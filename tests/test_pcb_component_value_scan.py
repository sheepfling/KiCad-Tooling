"""Source-bound design-lint scan regressions for PCB component values."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from kicad_tooling.hwrepo import design_lint_pcb_geometry_capture, design_lint_pcb_geometry_scan
from kicad_tooling.hwrepo.contracts import write_model
from kicad_tooling.hwrepo.electrical import selected_config
from kicad_tooling.hwrepo.models import (
    CommandEvidence,
    ContractCoachReport,
    DesignLintPolicy,
    DesignLintRuleOverride,
)
from kicad_tooling.hwrepo.pcb_component_inventory_models import (
    PcbComponentInventoryCoverageReport,
    PcbVariantPopulationCoverage,
)
from kicad_tooling.hwrepo.pcb_return_path_capture import NativePcbConnectivityCapture
from kicad_tooling.hwrepo.pcb_variant_population_capture import PcbVariantPopulationCapture
from kicad_tooling.validate import hashes
from tests.design_lint_fixtures.pcb_component_inventory import (
    NETLIST_SHA256,
    PROBE_SHA256,
    netlist,
    snapshot,
)
from tests.synthetic_design_lint_project import synthetic_design_lint_project

pytestmark = [pytest.mark.design_lint, pytest.mark.pcb_lint]
RULE_ID = "pcb.schematic_pcb_value_mismatch"
FOOTPRINT = "Synthetic:Probe_Module"


@pytest.mark.parametrize("changed_receipt", [None, "snapshot.json", "native.command.json"])
def test_value_only_policy_captures_and_compares_native_footprint_values(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, changed_receipt: str | None
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
        return NativePcbConnectivityCapture(command=command, snapshot=native_snapshot)

    original_layout = design_lint_pcb_geometry_scan.layout_coverage_reports

    def evaluate_then_change_receipt(**kwargs):
        reports = original_layout(**kwargs)
        if changed_receipt is not None:
            target = kwargs["evidence"].snapshot_path.parent / changed_receipt
            target.write_bytes(target.read_bytes() + b" ")
        return reports

    monkeypatch.setattr(
        design_lint_pcb_geometry_scan, "layout_coverage_reports", evaluate_then_change_receipt
    )
    monkeypatch.setattr(
        design_lint_pcb_geometry_capture,
        "capture_native_pcb_connectivity_result",
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
    monkeypatch.setattr(
        "kicad_tooling.hwrepo.design_lint_pcb_component_inventory_scan.capture_variant_population",
        lambda *_args, **_kwargs: PcbVariantPopulationCapture(
            sources=(),
            coverage=PcbVariantPopulationCoverage(status="NOT_APPLICABLE"),
        ),
    )

    reports = design_lint_pcb_geometry_scan.scan_pcb_geometry(
        root,
        config,
        coach_report,
        policy,
        native_summary,
    )
    coverage = next(
        item for item in reports if isinstance(item, PcbComponentInventoryCoverageReport)
    )

    if changed_receipt is not None:
        assert coverage.status == "BLOCKED"
        assert "differs from source-bound evidence" in (coverage.issue or "")
        return
    assert coverage.status == "COMPLETE"
    assert coverage.value_comparison_status == "COMPLETE"
    assert tuple(
        (item.reference, item.schematic_value, item.board_value)
        for item in coverage.value_mismatches
    ) == (("R1", "10k", "10K"),)
