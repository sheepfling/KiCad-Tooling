"""Synthetic artifact connectivity, policy, and analyzer-owner regressions."""

from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace

import pytest

from kicad_tooling.hwrepo import exports, models
from kicad_tooling.hwrepo.command_evidence_models import CommandEvidence
from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.fabrication_connectivity import analyze_fabrication_connectivity
from kicad_tooling.hwrepo.fabrication_connectivity_models import (
    FabricationConnectivityIgnore,
    FabricationConnectivitySettings,
    FabricationConnectivitySummary,
)
from kicad_tooling.hwrepo.project_models import ProjectKind, ReleaseExportSettings
from kicad_tooling.hwrepo.release_contract_models import EvidenceFile
from kicad_tooling.hwrepo.source_state_models import SourceState

pytestmark = [pytest.mark.design_lint, pytest.mark.evidence_lint, pytest.mark.pcb_lint]

_ROOT = Path(__file__).parents[1]
_OWNERS = (
    "fabrication_artwork.py",
    "fabrication_connectivity_models.py",
    "fabrication_connectivity.py",
    "fabrication_connectivity_raster.py",
)


def _record(code: str, net: str, reference: str, pin: str, access: int, x_mm: float) -> str:
    x = round(x_mm / 0.00254)
    y = round(5.0 / 0.00254)
    return (
        f"{code}{net:<14}   {reference:<6} {pin:<4} "
        f"A{access:02d}X{x:+07d}Y{-y:+07d}X0197Y0000R000S2"
    )


def _gerber(side: str, features: str) -> str:
    level, label = ("L1", "Top") if side == "top" else ("L2", "Bot")
    return (
        f"%TF.FileFunction,Copper,{level},{label}*%\n"
        "%FSLAX46Y46*%\n%MOMM*%\n%LPD*%\n"
        "%ADD10C,0.500000*%\n%ADD11C,0.300000*%\n"
        f"{features}M02*\n"
    )


def _export(
    directory: Path,
    *,
    connected: bool = True,
    second_net: str = "SIGNAL",
    through: bool = False,
    plated_drill: bool = True,
    inner_layer: bool = False,
) -> tuple[Path, Path]:
    board = directory / "board.kicad_pcb"
    board.write_bytes(
        (_ROOT / "tests/fixtures/fabrication-connectivity/clean.kicad_pcb").read_bytes()
    )
    fabrication = directory / "fabrication"
    fabrication.mkdir()
    if through:
        top_features = "D10*X6000000Y-5000000D03*\n"
        bottom_features = "D10*X6000000Y-5000000D03*\n"
        contacts = (_record("317", "SIGNAL", "VIA", "", 0, 6.0),)
    else:
        top_features = "D10*X5000000Y-5000000D03*X7000000Y-5000000D03*\n" + (
            "D11*X5000000Y-5000000D02*X7000000Y-5000000D01*\n" if connected else ""
        )
        bottom_features = ""
        contacts = (
            _record("327", "SIGNAL", "J1", "1", 1, 5.0),
            _record("327", second_net, "J1", "2", 1, 7.0),
        )
    (fabrication / "board-F_Cu.gbr").write_text(_gerber("top", top_features), encoding="utf-8")
    (fabrication / "board-B_Cu.gbr").write_text(
        _gerber("bottom", bottom_features), encoding="utf-8"
    )
    (fabrication / "board.d356").write_text(
        "P  UNITS CUST 0\n" + "\n".join(contacts) + "\n999\n", encoding="utf-8"
    )
    drill = fabrication / "board-PTH.drl"
    if through and plated_drill:
        drill.write_text(
            "M48\n; #@! TF.FileFunction,Plated,1,2,PTH\nFMAT,2\nMETRIC\n%\n"
            "G90\nG05\nT1C0.3\nT1\nX6.0Y-5.0\nM30\n",
            encoding="utf-8",
        )
    elif not through:
        drill.write_text(
            "M48\n; #@! TF.FileFunction,Plated,1,2,PTH\nFMAT,2\nMETRIC\n%\nM30\n",
            encoding="utf-8",
        )
    if inner_layer:
        (fabrication / "board-In1_Cu.gbr").write_text(
            "%TF.FileFunction,Copper,L2,Inr*%\nM02*\n", encoding="utf-8"
        )
    return board, fabrication


def test_release_export_connectivity_is_an_identity_compatible_opt_in() -> None:
    assert models.ReleaseExportSettings is ReleaseExportSettings
    base = {
        "gerber_layers": ("F.Cu", "B.Cu"),
        "supplier_formats": ("ipcd356",),
    }
    with pytest.raises(ValueError, match="requires the ipcd356"):
        ReleaseExportSettings(gerber_layers=("F.Cu", "B.Cu"), fabrication_connectivity={})
    with pytest.raises(ValueError, match="absolute coordinates"):
        ReleaseExportSettings(**base, coordinate_origin="plot", fabrication_connectivity={})


def test_release_export_records_and_rechecks_opt_in_connectivity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "repository"
    project_dir = root / "projects/synthetic"
    project_dir.mkdir(parents=True)
    (project_dir / "project.json").write_text("{}", encoding="utf-8")
    (project_dir / "board.kicad_pcb").write_text("synthetic board source\n", encoding="utf-8")
    (project_dir / "board.kicad_pro").write_text("{}\n", encoding="utf-8")
    (root / "build").mkdir()
    settings = ReleaseExportSettings(
        gerber_layers=("F.Cu", "B.Cu", "Edge.Cuts"),
        supplier_formats=("ipcd356",),
        fabrication_connectivity=FabricationConnectivitySettings(mode="review"),
    )
    manifest = SimpleNamespace(kind=ProjectKind.PCB, release_exports=settings)
    config = SimpleNamespace(
        project="projects/synthetic/board.kicad_pro",
        project_id="synthetic-board",
        kicad_version="10.0.5",
        toolchain_id="kicad-10.0.5",
    )
    source = SourceState(
        commit="a" * 40,
        clean=True,
        files_sha256={"projects/synthetic/board.kicad_pcb": "b" * 64},
    )
    connectivity = FabricationConnectivitySummary(
        status="REVIEW",
        board_sha256="c" * 64,
        artifact_sha256={},
        pixel_density=50,
    )
    original_read_model = exports.read_model

    def read_model(path: Path, model_type: type) -> object:
        if model_type is exports.ProjectManifest:
            return manifest
        return original_read_model(path, model_type)

    def fake_execute(arguments: tuple[str, ...], _root: Path, _output: Path, name: str):
        if name == "version":
            return CommandEvidence(
                argv=arguments, started_utc="2026-01-01T00:00:00Z", returncode=0, stdout="10.0.5\n"
            )
        if name == "gerbers":
            destination = Path(arguments[arguments.index("--output") + 1])
            for filename in ("board-F_Cu.gbr", "board-B_Cu.gbr"):
                (destination / filename).write_text("synthetic copper\n", encoding="utf-8")
        elif name == "drill":
            destination = Path(arguments[arguments.index("--output") + 1])
            (destination / "board-PTH.drl").write_text("synthetic drill\n", encoding="utf-8")
        else:
            destination = Path(arguments[arguments.index("--output") + 1])
            destination.parent.mkdir(parents=True, exist_ok=True)
            payload = b"%PDF-1.5\n" if name in {"schematic_pdf", "pcb_pdf"} else b"{}\n"
            destination.write_bytes(payload)
        return CommandEvidence(argv=arguments, started_utc="2026-01-01T00:00:00Z", returncode=0)

    def fake_purchasing_bom(_root: Path, _native: Path, destination: Path) -> None:
        destination.write_text("synthetic purchasing BOM\n", encoding="utf-8")

    monkeypatch.setattr(exports, "load_config", lambda *_args: config)
    monkeypatch.setattr(exports, "require_cli_profile", lambda _config: None)
    monkeypatch.setattr(exports, "read_model", read_model)
    monkeypatch.setattr(exports, "source_state", lambda _root: source)
    monkeypatch.setattr(exports, "require_declared_variant", lambda *_args: None)
    monkeypatch.setattr(exports, "execute", fake_execute)
    monkeypatch.setattr(exports, "purchasing_bom", fake_purchasing_bom)
    connectivity_calls: list[tuple[Path, Path, FabricationConnectivitySettings]] = []

    def fake_connectivity(
        board: Path, fabrication: Path, policy: FabricationConnectivitySettings
    ) -> FabricationConnectivitySummary:
        connectivity_calls.append((board, fabrication, policy))
        return connectivity

    monkeypatch.setattr(exports, "analyze_fabrication_connectivity", fake_connectivity)

    output = root / "build/exports/fabrication-review"
    report = exports.export(root, "projects/synthetic/project.json", output, "fake-kicad-cli")
    assert report.status == "PASS"
    assert report.artifact_connectivity == connectivity
    evidence = EvidenceFile(
        path="build/exports/fabrication-review/exports.json",
        sha256=digest(output / "exports.json"),
    )

    verified = exports.verify_exports(
        root,
        evidence,
        source,
        "synthetic-board",
        "projects/synthetic/project.json",
    )

    assert verified == report
    assert len(connectivity_calls) == 2
    assert all(call[0] == project_dir / "board.kicad_pcb" for call in connectivity_calls)
    assert all(call[1] == output / "fabrication" for call in connectivity_calls)
    assert all(call[2] == settings.fabrication_connectivity for call in connectivity_calls)


@pytest.mark.parametrize(
    ("kwargs", "expected", "status"),
    [
        ({}, set(), "PASS"),
        ({"connected": False}, {"OPEN"}, "REVIEW"),
        ({"second_net": "RETURN"}, {"SHORT"}, "REVIEW"),
        ({"second_net": "RETURN", "connected": False}, set(), "PASS"),
    ],
)
def test_artifact_connectivity_reports_opens_shorts_and_intentional_isolation(
    tmp_path: Path, kwargs: dict[str, bool | str], expected: set[str], status: str
) -> None:
    board, fabrication = _export(tmp_path, **kwargs)
    settings = FabricationConnectivitySettings()

    report = analyze_fabrication_connectivity(board, fabrication, settings)
    repeated = analyze_fabrication_connectivity(board, fabrication, settings)

    assert report == repeated
    assert {item.code for item in report.findings} == expected
    assert report.status == status
    assert report.board_sha256
    assert "fabrication/board.d356" in report.artifact_sha256


def test_configured_block_mode_and_exact_ignore_are_deterministic(tmp_path: Path) -> None:
    board, fabrication = _export(tmp_path, connected=False)
    review = analyze_fabrication_connectivity(board, fabrication, FabricationConnectivitySettings())
    finding = review.findings[0]
    ignored = analyze_fabrication_connectivity(
        board,
        fabrication,
        FabricationConnectivitySettings(
            ignores=(
                FabricationConnectivityIgnore(
                    fingerprint=finding.fingerprint, reason="approved test"
                ),
            )
        ),
    )
    blocked = analyze_fabrication_connectivity(
        board, fabrication, FabricationConnectivitySettings(mode="block")
    )

    assert ignored.status == "PASS"
    assert ignored.ignored_findings == (finding,)
    assert blocked.status == "FAIL"
    assert blocked.findings == (finding,)


def test_plated_via_joins_layers_and_missing_drill_is_visible(tmp_path: Path) -> None:
    board, fabrication = _export(tmp_path, through=True)
    clean = analyze_fabrication_connectivity(board, fabrication, FabricationConnectivitySettings())
    (fabrication / "board-PTH.drl").unlink()
    missing_drill = analyze_fabrication_connectivity(
        board, fabrication, FabricationConnectivitySettings()
    )

    assert clean.status == "PASS"
    assert not clean.findings
    assert {item.code for item in missing_drill.findings} == {"NO_DRILL", "OPEN"}


def test_inner_copper_layer_fails_closed_and_exposes_stale_ignores(tmp_path: Path) -> None:
    board, fabrication = _export(tmp_path, inner_layer=True)
    unsupported = analyze_fabrication_connectivity(
        board, fabrication, FabricationConnectivitySettings()
    )
    stale = analyze_fabrication_connectivity(
        board,
        fabrication,
        FabricationConnectivitySettings(
            ignores=(FabricationConnectivityIgnore(fingerprint="a" * 64, reason="old"),)
        ),
    )

    assert unsupported.status == "UNSUPPORTED"
    assert "inner" in unsupported.unsupported_reasons[0]
    assert stale.status == "UNSUPPORTED"


def test_stale_ignore_on_supported_board_fails_policy(tmp_path: Path) -> None:
    board, fabrication = _export(tmp_path)
    result = analyze_fabrication_connectivity(
        board,
        fabrication,
        FabricationConnectivitySettings(
            ignores=(FabricationConnectivityIgnore(fingerprint="a" * 64, reason="old"),)
        ),
    )

    assert result.status == "FAIL"
    assert result.stale_ignore_fingerprints == ("a" * 64,)


@pytest.mark.parametrize("mismatch", ("stack", "net"))
def test_source_stack_or_ipc_net_mismatch_fails_closed(tmp_path: Path, mismatch: str) -> None:
    board, fabrication = _export(tmp_path)
    if mismatch == "stack":
        board.write_text(
            board.read_text(encoding="utf-8").replace(
                '(0 "F.Cu" signal) (31 "B.Cu" signal)',
                '(0 "F.Cu" signal) (2 "In1.Cu" signal) (31 "B.Cu" signal)',
            ),
            encoding="utf-8",
        )
    else:
        ipc = fabrication / "board.d356"
        ipc.write_text(ipc.read_text(encoding="utf-8").replace("SIGNAL", "OTHER"))

    result = analyze_fabrication_connectivity(board, fabrication, FabricationConnectivitySettings())

    assert result.status == "UNSUPPORTED"
    assert result.unsupported_reasons


def test_fabrication_modules_remain_theme_owned_and_bounded() -> None:
    module_root = _ROOT / "kicad_tooling/hwrepo"
    for filename in _OWNERS:
        source = (module_root / filename).read_text(encoding="utf-8")
        assert len(source.splitlines()) < 500
        assert "models" not in {
            node.module for node in ast.walk(ast.parse(source)) if isinstance(node, ast.ImportFrom)
        }
