"""Named native population changes in saved BOM-to-board navigation."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from mcp import Client

from kicad_tooling.hwrepo.command_evidence_models import CommandEvidence
from kicad_tooling.hwrepo.contracts import read_model, write_model
from kicad_tooling.hwrepo.cross_probe import build_cross_probe
from kicad_tooling.hwrepo.cross_probe_models import CrossProbeReport
from kicad_tooling.hwrepo.design_lint_report_models import DesignLintReport
from kicad_tooling.hwrepo.discovery import load_config
from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.findings_view import build_findings_view
from kicad_tooling.hwrepo.findings_view_models import FindingsViewReport
from kicad_tooling.hwrepo.mcp_server import create_server
from kicad_tooling.hwrepo.models import PurchasingReport
from kicad_tooling.hwrepo.pcb_component_inventory_models import (
    PcbComponentInventoryCoverageReport,
    PcbVariantPopulationCoverage,
    PcbVariantPopulationEvidence,
)
from kicad_tooling.validate import hashes
from tests.mcp_parity_support import McpParityHarness, parity_workspace, run_mcp_parity
from tests.test_cross_probe import saved_inputs

pytestmark = pytest.mark.template_checkout


def _variant_files(root: Path, variant: str, netlist: bytes, fitted: str) -> PcbVariantPopulationEvidence:
    config = load_config(root, "examples/projects/controller/project.json")
    directory = root / "build/design-lint/variant-evidence"
    directory.mkdir(parents=True, exist_ok=True)
    token = variant.lower()
    netlist_path = directory / f"{token}.netlist.xml"
    netlist_path.write_bytes(netlist)
    all_path = directory / f"{token}.board-all.csv"
    all_path.write_text("Ref,Val\nR1,1k\nR2,2k\nJ9,header\n", encoding="utf-8")
    fitted_path = directory / f"{token}.board-fitted.csv"
    fitted_path.write_text(f"Ref,Val\n{fitted},1k\nJ9,header\n", encoding="utf-8")
    commands: list[Path] = []
    for label, source, target, kind in (
        ("netlist", ".kicad_sch", netlist_path, ("sch", "export", "netlist")),
        ("board-all", ".kicad_pcb", all_path, ("pcb", "export", "pos")),
        ("board-fitted", ".kicad_pcb", fitted_path, ("pcb", "export", "pos")),
    ):
        command_path = directory / f"{token}.{label}.command.json"
        write_model(
            command_path,
            CommandEvidence(
                argv=(
                    "docker",
                    "run",
                    config.image,
                    *kind,
                    "--format",
                    "kicadxml" if label == "netlist" else "csv",
                    *(("--side", "both") if label != "netlist" else ()),
                    *(("--exclude-dnp",) if label == "board-fitted" else ()),
                    "--variant",
                    variant,
                    "--output",
                    f"/output/{target.name}",
                    f"/work/{Path(config.project).with_suffix(source).as_posix()}",
                ),
                started_utc="2026-10-30T00:00:00+00:00",
                returncode=0,
            ),
        )
        commands.append(command_path)

    def relative(path: Path) -> str:
        return path.relative_to(root).as_posix()

    return PcbVariantPopulationEvidence(
        variant=variant,
        netlist_path=relative(netlist_path),
        netlist_sha256=digest(netlist_path),
        netlist_command_path=relative(commands[0]),
        netlist_command_sha256=digest(commands[0]),
        board_all_positions_path=relative(all_path),
        board_all_positions_sha256=digest(all_path),
        board_all_command_path=relative(commands[1]),
        board_all_command_sha256=digest(commands[1]),
        board_fitted_positions_path=relative(fitted_path),
        board_fitted_positions_sha256=digest(fitted_path),
        board_fitted_command_path=relative(commands[2]),
        board_fitted_command_sha256=digest(commands[2]),
    )


def _inputs(root: Path, island: Path) -> tuple[Path, Path, Path]:
    project = island / "kicad/controller.kicad_pro"
    document = json.loads(project.read_text(encoding="utf-8"))
    document.setdefault("schematic", {})["variants"] = [
        {"name": "STANDARD"},
        {"name": "ALT"},
    ]
    project.write_text(json.dumps(document), encoding="utf-8")
    parts, old_findings = saved_inputs(root, island)
    old_view = read_model(old_findings, FindingsViewReport)
    native = root / old_view.native_summary
    config = load_config(root, "examples/projects/controller/project.json")
    current = hashes(root, config.source_roots)
    base_netlist = (native.parent / "netlist.xml").read_bytes()
    standard = base_netlist.replace(
        b'<comp ref="R2"><value>',
        b'<comp ref="R2"><property name="dnp"/><value>',
    )
    alternate = base_netlist.replace(
        b'<comp ref="R1"><value>',
        b'<comp ref="R1"><property name="dnp"/><value>',
    ).replace(b"resistor-1k", b"resistor-alt")
    standard_evidence = _variant_files(root, "STANDARD", standard, "R1")
    alternate_evidence = _variant_files(root, "ALT", alternate, "R2")
    directory = root / "build/design-lint/variant-evidence"
    probe = directory / "probe.py"
    probe.write_text("# retained native probe\n", encoding="utf-8")
    request = directory / "request.json"
    request.write_text('{"variants":["STANDARD","ALT"]}\n', encoding="utf-8")
    probe_command = directory / "probe.command.json"
    write_model(
        probe_command,
        CommandEvidence(
            argv=("docker", "run", config.image, "probe"),
            started_utc="2026-10-30T00:00:00+00:00",
            returncode=0,
        ),
    )
    coverage = PcbVariantPopulationCoverage(
        status="COMPLETE",
        project_path=project.relative_to(root).as_posix(),
        project_sha256=current[project.relative_to(root).as_posix()],
        schematic_path=Path(config.project).with_suffix(".kicad_sch").as_posix(),
        schematic_sha256=current[Path(config.project).with_suffix(".kicad_sch").as_posix()],
        board_path=Path(config.project).with_suffix(".kicad_pcb").as_posix(),
        board_sha256=current[Path(config.project).with_suffix(".kicad_pcb").as_posix()],
        kicad_version=config.kicad_version,
        image=config.image,
        board_variant_probe_path=probe.relative_to(root).as_posix(),
        board_variant_probe_sha256=digest(probe),
        board_variant_request_path=request.relative_to(root).as_posix(),
        board_variant_request_sha256=digest(request),
        board_variant_command_path=probe_command.relative_to(root).as_posix(),
        board_variant_command_sha256=digest(probe_command),
        evidence=(standard_evidence, alternate_evidence),
    )
    lint_path = directory / "report.json"
    write_model(
        lint_path,
        DesignLintReport(
            status="BLOCKED",
            project_id="controller",
            source_hashes=current,
            netlist_sha256=digest(native.parent / "netlist.xml"),
            native_summary=native.relative_to(root).as_posix(),
            pcb_component_inventory=PcbComponentInventoryCoverageReport(
                variant_population=coverage
            ),
        ),
    )
    findings = build_findings_view(
        root,
        "controller",
        native,
        Path("build/findings-view/variant-evidence"),
        lint_path,
    )
    return parts, Path(findings.output_directory) / "review.json", lint_path


def test_named_variants_show_different_population_and_withhold_board_markers(
    tmp_path: Path,
) -> None:
    root, island, _ = parity_workspace(tmp_path)
    parts, findings, _ = _inputs(root, island)
    standard = build_cross_probe(root, "controller", parts, findings, assembly_variant="STANDARD")
    alternate = build_cross_probe(root, "controller", parts, findings, assembly_variant="ALT")
    assert standard.variant_scope == alternate.variant_scope == "NAMED_OBSERVED"
    assert standard.variant_board_only == ("J9",)
    assert standard.entries[0].variant_board == "FITTED" and standard.entries[0].board
    assert standard.entries[1].variant_board == "DNP" and not standard.entries[1].board
    assert alternate.entries[0].variant_schematic == "DNP"
    assert alternate.entries[0].variant_board == "DNP" and not alternate.entries[0].board
    assert alternate.entries[1].variant_board == "FITTED"
    assert alternate.entries[1].variant_part_id == "resistor-alt"
    assert "part identities differ" in " ".join(alternate.entries[1].issues)
    assert "fits a parts-plan excluded reference" in " ".join(alternate.entries[1].issues)
    html = (Path(alternate.output_directory) / "index.html").read_text(encoding="utf-8")
    assert "Selected native variant: ALT" in html
    assert 'id="marker-1-pcb-1"' not in html
    assert "J9" in html
    assert read_model(Path(alternate.output_directory) / "cross-probe.json", CrossProbeReport) == alternate


def test_changed_or_missing_variant_evidence_is_rejected(tmp_path: Path) -> None:
    root, island, _ = parity_workspace(tmp_path)
    parts, findings, lint_path = _inputs(root, island)
    with pytest.raises(ValueError, match="No complete native population evidence"):
        build_cross_probe(root, "controller", parts, findings, assembly_variant="UNKNOWN")
    stale = lint_path.parent / "standard.board-fitted.csv"
    stale.write_text("Ref,Val\nR2,2k\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Named variant evidence changed"):
        build_cross_probe(root, "controller", parts, findings, assembly_variant="STANDARD")


def test_selected_native_fitted_reference_can_navigate_when_parts_marks_dnp(
    tmp_path: Path,
) -> None:
    root, island, _ = parity_workspace(tmp_path)
    parts, findings, _ = _inputs(root, island)
    saved = read_model(parts, PurchasingReport)
    assert saved.plan is not None
    components = saved.plan.components
    plan = saved.plan.model_copy(
        update={
            "components": (
                components[0].model_copy(update={"dnp": True}),
                *components[1:],
            )
        }
    )
    write_model(parts, saved.model_copy(update={"plan": plan}))
    report = build_cross_probe(root, "controller", parts, findings, assembly_variant="STANDARD")
    r1 = report.entries[0]
    assert r1.population == "DNP" and r1.variant_board == "FITTED"
    assert r1.board[0].drawing_file == "pcb.svg"
    assert r1.schematic[0].drawing_file == "schematic-1.svg"
    assert "excluded reference" in " ".join(r1.issues)


def test_retagged_command_with_wrong_native_input_is_rejected(tmp_path: Path) -> None:
    root, island, _ = parity_workspace(tmp_path)
    parts, findings, lint_path = _inputs(root, island)
    lint = read_model(lint_path, DesignLintReport)
    coverage = lint.pcb_component_inventory.variant_population
    selected = coverage.evidence[0]
    command_path = root / selected.board_fitted_command_path
    command = read_model(command_path, CommandEvidence)
    write_model(
        command_path,
        command.model_copy(
            update={
                "argv": tuple(
                    "/work/another-board.kicad_pcb" if arg.endswith("/controller.kicad_pcb") else arg
                    for arg in command.argv
                )
            }
        ),
    )
    revised = selected.model_copy(update={"board_fitted_command_sha256": digest(command_path)})
    inventory = lint.pcb_component_inventory.model_copy(
        update={
            "variant_population": coverage.model_copy(
                update={"evidence": (revised, *coverage.evidence[1:])}
            )
        }
    )
    write_model(lint_path, lint.model_copy(update={"pcb_component_inventory": inventory}))
    view = read_model(findings, FindingsViewReport)
    write_model(findings, view.model_copy(update={"lint_report_sha256": digest(lint_path)}))
    with pytest.raises(ValueError, match="command is not bound"):
        build_cross_probe(root, "controller", parts, findings, assembly_variant="STANDARD")


class _VariantParity(McpParityHarness):
    async def _case_variant_cli_mcp(self) -> None:
        parts, findings, _ = _inputs(self.root, self.island)
        cli = await self.cli(
            "kicad_tooling.cross_probe",
            CrossProbeReport,
            "--project",
            "controller",
            "--parts-report",
            str(parts),
            "--findings-view",
            str(findings),
            "--assembly-variant",
            "ALT",
            "--output",
            "build/cross-probe/variant-cli",
        )
        arguments = {
            "project_id": "controller",
            "view_id": "variant-mcp",
            "parts_report": parts.relative_to(self.root).as_posix(),
            "findings_view": findings.relative_to(self.root).as_posix(),
            "assembly_variant": "ALT",
        }
        async with Client(create_server(self.root, allow_exports=True), mode="legacy") as client:
            mcp = await self.call(client, "export_bom_cross_probe", CrossProbeReport, arguments)
        self.receipt_equal(cli, mcp, "output_directory")
        self.assertEqual(
            (Path(cli.output_directory) / "index.html").read_bytes(),
            (Path(mcp.output_directory) / "index.html").read_bytes(),
        )


def test_named_variant_cli_mcp_parity() -> None:
    run_mcp_parity(_VariantParity, "_case_variant_cli_mcp")
