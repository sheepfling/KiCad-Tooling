"""Saved voltage review separates numeric failures from missing or stale evidence."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest
from mcp import Client

from kicad_tooling.hwrepo.contracts import read_model, write_model
from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.mcp_server import create_server
from kicad_tooling.hwrepo.measured_series import import_measured_series
from kicad_tooling.hwrepo.physical_voltage import build_physical_voltage_review
from kicad_tooling.hwrepo.physical_voltage_models import (
    PhysicalVoltageReviewReport,
    VoltageCapture,
    VoltageLimit,
    VoltageRequirement,
)
from tests.mcp_parity_support import McpParityHarness, parity_workspace, run_mcp_parity

pytestmark = pytest.mark.template_checkout


def _inputs(root: Path, island: Path) -> tuple[Path, Path, Path, Path]:
    source = island / "docs/voltage.csv"
    source.write_text("time,vout\n0,4.90\n0.5,5.00\n1,5.10\n", encoding="utf-8")
    measured = import_measured_series(
        root,
        "controller",
        source,
        "time",
        "s",
        ("vout=V",),
        Path("build/measured-series/physical-voltage"),
    )
    capture = island / "docs/voltage-capture.json"
    write_model(
        capture,
        VoltageCapture(
            project_id="controller",
            test_id="startup",
            source_csv=source.relative_to(root).as_posix(),
            source_sha256=digest(source),
            channel="vout",
            unit="V",
            conditions={"load": "100 mA", "ambient": "25 C"},
            captured_at="2026-10-30T10:00:00Z",
            instrument="Synthetic bench scope",
            recorded_origin="unknown",
        ),
    )
    requirement = island / "docs/voltage-requirement.json"
    write_model(
        requirement,
        VoltageRequirement(
            project_id="controller",
            test_id="startup",
            channel="vout",
            unit="V",
            conditions={"load": "100 mA", "ambient": "25 C"},
            limit=VoltageLimit(minimum_v=Decimal("4.75"), maximum_v=Decimal("5.25")),
            basis="Synthetic requirement",
        ),
    )
    return Path(measured.output_directory) / "measured-series.json", capture, requirement, source


def _review(
    root: Path, measured: Path, capture: Path, requirement: Path | None, name: str
) -> PhysicalVoltageReviewReport:
    return build_physical_voltage_review(
        root,
        "controller",
        measured,
        capture,
        requirement,
        Path("build/physical-voltage") / name,
    )


def test_voltage_limit_control_failure_and_missing_requirement(tmp_path: Path) -> None:
    root, island, _ = parity_workspace(tmp_path)
    measured, capture, requirement, _ = _inputs(root, island)
    passed = _review(root, measured, capture, requirement, "pass")
    assert passed.status == "PASS" and passed.violation_count == 0
    assert passed.observed_min == Decimal("4.90")
    assert passed.observed_max == Decimal("5.10")
    assert passed.measured_unit == "V"
    assert passed.source_current and not passed.build_authorized
    directory = Path(passed.output_directory)
    assert read_model(directory / "physical-voltage.json", PhysicalVoltageReviewReport) == passed
    html = (directory / "index.html").read_text(encoding="utf-8")
    assert "Voltage over time" in html and "Minimum: 4.75 V" in html
    for name, checksum in passed.artifacts_sha256.items():
        assert digest(directory / name) == checksum

    authored = read_model(requirement, VoltageRequirement)
    write_model(
        requirement,
        authored.model_copy(
            update={"limit": VoltageLimit(minimum_v=Decimal("4.95"), maximum_v=Decimal("5.05"))}
        ),
    )
    failed = _review(root, measured, capture, requirement, "fail")
    assert failed.status == "FAIL" and failed.violation_count == 2
    assert failed.first_violation is not None
    assert (failed.first_violation.sample_index, failed.first_violation.time_seconds) == (
        0,
        Decimal(0),
    )
    assert failed.first_violation.value_v == Decimal("4.90")

    absent = _review(root, measured, capture, island / "docs/absent.json", "absent")
    assert absent.status == "NO_LIMIT" and absent.requirement_state == "MISSING"
    assert absent.violation_count == 0
    assert (
        _review(root, measured, capture, None, "not-selected").requirement_state == "NOT_SELECTED"
    )
    requirement.write_text("{invalid", encoding="utf-8")
    invalid = _review(root, measured, capture, requirement, "invalid")
    assert invalid.status == "NO_LIMIT" and invalid.requirement_state == "INVALID"


def test_voltage_mismatch_and_staleness_states(tmp_path: Path) -> None:
    root, island, _ = parity_workspace(tmp_path)
    measured, capture, requirement, source = _inputs(root, island)
    authored = read_model(requirement, VoltageRequirement)
    write_model(requirement, authored.model_copy(update={"unit": "mV"}))
    assert _review(root, measured, capture, requirement, "unit").status == "UNIT_MISMATCH"
    write_model(
        requirement,
        authored.model_copy(update={"conditions": {"load": "200 mA", "ambient": "25 C"}}),
    )
    assert _review(root, measured, capture, requirement, "condition").status == "CONDITION_MISMATCH"
    write_model(requirement, authored.model_copy(update={"kind": "thermal"}))
    assert _review(root, measured, capture, requirement, "kind").status == "NO_LIMIT"
    write_model(requirement, authored)
    context = read_model(capture, VoltageCapture)
    write_model(capture, context.model_copy(update={"kind": "thermal"}))
    assert _review(root, measured, capture, requirement, "unsupported").status == "UNSUPPORTED"
    write_model(capture, context)
    source.write_text("time,vout\n0,4.9\n1,5.1\n", encoding="utf-8")
    stale = _review(root, measured, capture, requirement, "stale")
    assert stale.status == "STALE" and not stale.source_current
    assert stale.violation_count == 0
    source.write_text("time,vout\n0,4.90\n0.5,5.00\n1,5.10\n", encoding="utf-8")
    (measured.parent / "data.csv").write_text("changed", encoding="utf-8")
    artifact = _review(root, measured, capture, requirement, "artifact")
    assert artifact.status == "STALE" and not artifact.artifacts_sha256.get("source.csv")


class _PhysicalVoltageParity(McpParityHarness):
    async def _case_test_cli_mcp_physical_voltage_parity(self) -> None:
        measured, capture, requirement, _ = _inputs(self.root, self.island)
        cli = await self.cli(
            "kicad_tooling.physical_voltage",
            PhysicalVoltageReviewReport,
            "--project",
            "controller",
            "--measured-receipt",
            str(measured),
            "--capture",
            str(capture),
            "--requirement",
            str(requirement),
            "--output",
            "build/physical-voltage/cli",
        )
        arguments = {
            "project_id": "controller",
            "view_id": "mcp",
            "measured_receipt": measured.relative_to(self.root).as_posix(),
            "capture": capture.relative_to(self.root).as_posix(),
            "requirement": requirement.relative_to(self.root).as_posix(),
        }
        async with Client(create_server(self.root), mode="legacy") as client:
            self.assertTrue(
                (await client.call_tool("export_physical_voltage_review", arguments)).is_error
            )
        async with Client(create_server(self.root, allow_exports=True), mode="legacy") as client:
            mcp = await self.call(
                client, "export_physical_voltage_review", PhysicalVoltageReviewReport, arguments
            )
        self.receipt_equal(cli, mcp, "output_directory")
        self.assertEqual(
            (Path(cli.output_directory) / "index.html").read_bytes(),
            (Path(mcp.output_directory) / "index.html").read_bytes(),
        )


def test_cli_mcp_physical_voltage_parity() -> None:
    run_mcp_parity(_PhysicalVoltageParity, "_case_test_cli_mcp_physical_voltage_parity")
