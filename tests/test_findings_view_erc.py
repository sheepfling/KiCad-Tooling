"""Source-bound ERC placement and mapped CLI/MCP review parity."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from mcp import Client

from kicad_tooling.hwrepo.contracts import read_model, write_model
from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.findings_view import build_findings_view
from kicad_tooling.hwrepo.findings_view_models import FindingsViewReport
from kicad_tooling.hwrepo.mcp_server import create_server
from kicad_tooling.hwrepo.models import ProjectManifest, ToolchainsCatalog, ValidationSummary
from kicad_tooling.hwrepo.schematic_geometry_source import schematic_root, schematic_scalar
from tests.findings_view_support import add_native_review
from tests.mcp_parity_support import (
    McpParityHarness,
    parity_native_evidence,
    parity_workspace,
    run_mcp_parity,
)

pytestmark = pytest.mark.template_checkout


def _mapped_native(root: Path, island: Path) -> Path:
    catalog_path = root / "catalog/toolchains.json"
    catalog = read_model(catalog_path, ToolchainsCatalog)
    write_model(
        catalog_path,
        catalog.model_copy(
            update={
                "toolchains": (
                    *catalog.toolchains,
                    catalog.toolchains[-1].model_copy(
                        update={
                            "id": "kicad-10.0.6",
                            "kicad_version": "10.0.6",
                            "image": "ghcr.io/kicad/kicad:10.0.6@sha256:" + "a" * 64,
                        }
                    ),
                )
            }
        ),
    )
    manifest_path = island / "project.json"
    manifest = read_model(manifest_path, ProjectManifest)
    write_model(manifest_path, manifest.model_copy(update={"toolchain_id": "kicad-10.0.6"}))
    native = parity_native_evidence(root, island)
    add_native_review(root, native)
    schematic = island / "kicad/controller.kicad_sch"
    text, node = schematic_root(schematic.read_bytes())
    sheet_uuid = "/" + schematic_scalar(text, node, "uuid")
    erc_path = native.parent / "erc.json"
    erc = json.loads(erc_path.read_text(encoding="utf-8"))
    erc["sheets"][0]["uuid_path"] = sheet_uuid
    erc_path.write_text(json.dumps(erc), encoding="utf-8")
    svg = native.parent / "schematic/controller.svg"
    raw = svg.read_text(encoding="utf-8")
    svg.write_text(
        raw.replace(
            "</svg>",
            '<text text-anchor="start" opacity="0" stroke-opacity="0">'
            "File: controller.kicad_sch</text>"
            '<text text-anchor="start" opacity="0" stroke-opacity="0">'
            "Sheet: /</text></svg>",
        ),
        encoding="utf-8",
    )
    summary = read_model(native, ValidationSummary)
    write_model(
        native,
        summary.model_copy(
            update={
                "artifacts_sha256": {
                    **summary.artifacts_sha256,
                    "erc.json": digest(erc_path),
                    "schematic/controller.svg": digest(svg),
                }
            }
        ),
    )
    return native


def test_erc_marker_requires_exact_saved_sheet_identity(tmp_path: Path) -> None:
    root, island, _ = parity_workspace(tmp_path)
    native = _mapped_native(root, island)
    report = build_findings_view(root, "controller", native, Path("build/findings-view/erc"))
    erc = next(item for item in report.findings if item.origin == "ERC")
    assert erc.unmapped_reason is None and len(erc.markers) == 1
    assert (erc.markers[0].x_mm, erc.markers[0].y_mm) == pytest.approx((76.2, 71.12))
    assert erc.markers[0].drawing_file == "schematic-1.svg"
    assert erc.evidence["coordinate_conversion"] == (
        "KiCad 10.0.6 ERC position ×100 to schematic mm",
    )
    html = (Path(report.output_directory) / "index.html").read_text(encoding="utf-8")
    assert 'id="marker-1-1"' in html

    erc_path = native.parent / "erc.json"
    payload = json.loads(erc_path.read_text(encoding="utf-8"))
    payload["sheets"][0]["uuid_path"] = "/wrong-sheet"
    erc_path.write_text(json.dumps(payload), encoding="utf-8")
    summary = read_model(native, ValidationSummary)
    write_model(
        native,
        summary.model_copy(
            update={"artifacts_sha256": {**summary.artifacts_sha256, "erc.json": digest(erc_path)}}
        ),
    )
    wrong = build_findings_view(root, "controller", native, Path("build/findings-view/wrong"))
    finding = next(item for item in wrong.findings if item.origin == "ERC")
    assert not finding.markers and finding.unmapped_reason
    assert len(wrong.findings) == len(report.findings)

    payload["sheets"][0]["uuid_path"] = erc.markers[0].sheet_instance_path
    payload["sheets"][0]["violations"][0]["items"][0]["pos"]["x"] = None
    erc_path.write_text(json.dumps(payload), encoding="utf-8")
    summary = read_model(native, ValidationSummary)
    write_model(
        native,
        summary.model_copy(
            update={"artifacts_sha256": {**summary.artifacts_sha256, "erc.json": digest(erc_path)}}
        ),
    )
    partial = build_findings_view(root, "controller", native, Path("build/findings-view/partial"))
    partial_erc = next(item for item in partial.findings if item.origin == "ERC")
    assert not partial_erc.markers and partial_erc.unmapped_reason


class _ErcParity(McpParityHarness):
    async def _case_test_cli_mcp_mapped_erc_parity(self) -> None:
        native = _mapped_native(self.root, self.island)
        cli = await self.cli(
            "kicad_tooling.findings_view",
            FindingsViewReport,
            "--project",
            "controller",
            "--native-summary",
            str(native),
            "--output",
            "build/findings-view/erc-cli",
        )
        arguments = {
            "project_id": "controller",
            "native_summary": native.relative_to(self.root).as_posix(),
            "view_id": "erc-mcp",
        }
        async with Client(create_server(self.root, allow_exports=True), mode="legacy") as client:
            mcp = await self.call(client, "export_findings_view", FindingsViewReport, arguments)
        self.receipt_equal(cli, mcp, "output_directory")
        self.assertEqual(
            (Path(cli.output_directory) / "index.html").read_text(),
            (Path(mcp.output_directory) / "index.html").read_text(),
        )


@pytest.mark.parity_lint
def test_cli_mcp_mapped_erc_parity() -> None:
    run_mcp_parity(_ErcParity, "_case_test_cli_mcp_mapped_erc_parity")
