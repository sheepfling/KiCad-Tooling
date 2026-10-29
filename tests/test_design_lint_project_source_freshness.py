"""Project lint must not return stale findings after source changes mid-run."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from pathlib import Path

import pytest

from kicad_tooling.hwrepo import contract_coach, design_lint_project_inspection
from kicad_tooling.hwrepo.contracts import read_model, write_model
from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.design_lint_connectivity_snapshot_models import (
    DesignLintConnectivitySnapshot,
)
from kicad_tooling.hwrepo.design_lint_project_inspection import inspect_design_lint_summary
from kicad_tooling.hwrepo.models import (
    ContractCoachReport,
    DesignLintPolicy,
    NetlistContract,
    ToolchainsCatalog,
)
from tests.mcp_parity_support import parity_design_lint_policy
from tests.synthetic_design_lint_project import synthetic_design_lint_project

pytestmark = [pytest.mark.design_lint, pytest.mark.evidence_lint]


def _change_after_capture(monkeypatch: pytest.MonkeyPatch, change: Callable[[], None]) -> None:
    capture = design_lint_project_inspection.capture_connectivity_snapshot

    def capture_then_change(
        project_id: str,
        observed: NetlistContract,
        source_hashes: Mapping[str, str],
        netlist_sha256: str,
        kicad_version: str,
        toolchain_image: str,
    ) -> DesignLintConnectivitySnapshot:
        snapshot = capture(
            project_id, observed, source_hashes, netlist_sha256, kicad_version, toolchain_image
        )
        change()
        return snapshot

    monkeypatch.setattr(
        design_lint_project_inspection, "capture_connectivity_snapshot", capture_then_change
    )


@pytest.mark.parametrize("change", ("edit", "add", "remove", "manifest", "policy"))
def test_source_change_after_evaluation_blocks_project_inspection(
    tmp_path: Path, change: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, native = synthetic_design_lint_project(
        tmp_path, parity_design_lint_policy(DesignLintPolicy())
    )
    source = root / "projects/controller/kicad/controller.kicad_sch"

    def change_source() -> None:
        if change == "edit":
            source.write_text("changed while evaluating\n", encoding="utf-8")
        elif change == "add":
            (source.parent / "added.kicad_sch").write_text("new source\n", encoding="utf-8")
        elif change == "remove":
            source.unlink()
        else:
            path = (
                root
                / "projects/controller"
                / ("project.json" if change == "manifest" else "tests/contract.json")
            )
            path.write_text(path.read_text(encoding="utf-8") + "\n", encoding="utf-8")

    _change_after_capture(monkeypatch, change_source)
    report = inspect_design_lint_summary(root, "controller", native, evaluate)
    assert report.status == "BLOCKED"
    expected = (
        "Project manifest or lint policy changed during inspection"
        if change in {"manifest", "policy"}
        else "Declared project source changed during design-lint inspection"
    )
    assert any(expected in issue for issue in report.issues)
    assert report.connectivity_snapshot is None


@pytest.mark.parametrize("filename", ("summary.json", "netlist.xml", "netlist.command.json"))
@pytest.mark.parametrize("remove", (False, True), ids=("changed", "removed"))
def test_native_evidence_change_during_lint_blocks_report(
    tmp_path: Path, filename: str, remove: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, native = synthetic_design_lint_project(
        tmp_path, parity_design_lint_policy(DesignLintPolicy())
    )
    artifact = native.parent / filename

    def change_artifact() -> None:
        if remove:
            artifact.unlink()
        else:
            artifact.write_bytes(artifact.read_bytes() + b" ")

    _change_after_capture(monkeypatch, change_artifact)
    report = inspect_design_lint_summary(root, "controller", native, evaluate)
    assert report.status == "BLOCKED"
    assert "Native netlist evidence changed during design-lint inspection" in report.issues
    assert report.connectivity_snapshot is None


@pytest.mark.parametrize("filename", ("summary.json", "netlist.xml", "netlist.command.json"))
def test_native_evidence_change_while_coach_reads_is_blocked(
    tmp_path: Path, filename: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, native = synthetic_design_lint_project(
        tmp_path, parity_design_lint_policy(DesignLintPolicy())
    )
    read = contract_coach.read_netlist

    def read_then_change(path: Path) -> NetlistContract:
        observed = read(path)
        artifact = native.parent / filename
        artifact.write_bytes(artifact.read_bytes() + b" ")
        return observed

    monkeypatch.setattr(contract_coach, "read_netlist", read_then_change)
    report = contract_coach.inspect_summary(root, "controller", native)
    assert report.status == "BLOCKED"
    assert any("Native netlist evidence changed while reading" in issue for issue in report.issues)


@pytest.mark.parametrize("stage", ("after_coach", "after_snapshot"))
@pytest.mark.parametrize("field", ("version", "image"))
def test_toolchain_change_during_inspection_is_blocked(
    tmp_path: Path, stage: str, field: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, native = synthetic_design_lint_project(
        tmp_path, parity_design_lint_policy(DesignLintPolicy())
    )
    path = root / "catalog/toolchains.json"

    def change_toolchain() -> None:
        catalog = read_model(path, ToolchainsCatalog)
        record = catalog.toolchains[0]
        update = (
            {"kicad_version": "10.0.0"}
            if field == "version"
            else {"image": "registry.invalid/kicad@sha256:" + "b" * 64}
        )
        write_model(
            path, catalog.model_copy(update={"toolchains": (record.model_copy(update=update),)})
        )

    if stage == "after_coach":
        inspect = design_lint_project_inspection.inspect_contract_summary

        def inspect_then_change(
            root: Path, project_id: str, native_summary: Path
        ) -> ContractCoachReport:
            report = inspect(root, project_id, native_summary)
            change_toolchain()
            return report

        monkeypatch.setattr(
            design_lint_project_inspection, "inspect_contract_summary", inspect_then_change
        )
    else:
        _change_after_capture(monkeypatch, change_toolchain)
    report = inspect_design_lint_summary(root, "controller", native, evaluate)
    assert report.status == "BLOCKED"
    assert any("toolchain" in issue.lower() for issue in report.issues)
    assert report.connectivity_snapshot is None


def test_unchanged_source_keeps_project_inspection_available(tmp_path: Path) -> None:
    root, native = synthetic_design_lint_project(
        tmp_path, parity_design_lint_policy(DesignLintPolicy())
    )
    report = inspect_design_lint_summary(root, "controller", native, evaluate)
    assert report.status != "BLOCKED", report.issues
    assert report.connectivity_snapshot is not None
