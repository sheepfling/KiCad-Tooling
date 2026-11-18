"""Synthetic artifact connectivity, policy, and analyzer-owner regressions."""

from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace

import pytest

from kicad_tooling.hwrepo import exports, models
from kicad_tooling.hwrepo.command_evidence_models import CommandEvidence
from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.fabrication_artwork import (
    UnsupportedFabricationFormat,
    classify_copper_files,
)
from kicad_tooling.hwrepo.fabrication_connectivity import analyze_fabrication_connectivity
from kicad_tooling.hwrepo.fabrication_connectivity_models import (
    FabricationConnectivityIgnore,
    FabricationConnectivitySettings,
    FabricationConnectivitySummary,
)
from kicad_tooling.hwrepo.project_models import ProjectKind, ReleaseExportSettings
from kicad_tooling.hwrepo.release_contract_models import EvidenceFile
from kicad_tooling.hwrepo.source_state_models import SourceState
from tests.fabrication_connectivity_support import (
    format_ipc_contact,
    write_synthetic_fabrication,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.evidence_lint, pytest.mark.pcb_lint]

_ROOT = Path(__file__).parents[1]
_OWNERS = (
    "fabrication_artwork.py",
    "fabrication_contact_geometry.py",
    "fabrication_contact_inventory.py",
    "fabrication_contact_layers.py",
    "fabrication_contact_source.py",
    "fabrication_drill_files.py",
    "fabrication_excellon.py",
    "fabrication_gerber_codes.py",
    "fabrication_connectivity_models.py",
    "fabrication_connectivity.py",
    "fabrication_connectivity_raster.py",
    "fabrication_pad_drill_binding.py",
    "fabrication_via_binding.py",
    "fabrication_via_drill_binding.py",
    "pcb_board_net_inventory.py",
)


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
    board, fabrication = write_synthetic_fabrication(tmp_path, **kwargs)
    settings = FabricationConnectivitySettings()

    report = analyze_fabrication_connectivity(board, fabrication, settings)
    repeated = analyze_fabrication_connectivity(board, fabrication, settings)

    assert report == repeated
    assert {item.code for item in report.findings} == expected
    assert not report.unsupported_reasons, report.unsupported_reasons
    assert report.status == status
    assert report.analyzer_version == "30"
    assert report.board_sha256
    assert "fabrication/board.d356" in report.artifact_sha256


def test_configured_block_mode_and_exact_ignore_are_deterministic(tmp_path: Path) -> None:
    board, fabrication = write_synthetic_fabrication(tmp_path, connected=False)
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


@pytest.mark.parametrize(
    ("replacement", "message"),
    [
        ("Plated,1,1,PTH", "full source copper stack"),
        ("Plated,1,2,PTH,Blind", "blind or buried"),
        (None, "no explicit layer span"),
        ("Plated,1,2,PTH,Microvia", "unsupported FileFunction suffix"),
        ("Plated,one,2,PTH", "malformed layer span"),
        (
            "Plated,1,2,PTH\n; #@! TF.FileFunction,Plated,1,2,PTH",
            "multiple FileFunction attributes",
        ),
    ],
)
def test_plated_drill_span_must_match_the_full_source_stack(
    tmp_path: Path, replacement: str | None, message: str
) -> None:
    board, fabrication = write_synthetic_fabrication(tmp_path, through=True)
    drill = fabrication / "board-PTH.drl"
    source = drill.read_text(encoding="utf-8")
    if replacement is None:
        source = source.replace("; #@! TF.FileFunction,Plated,1,2,PTH\n", "")
    else:
        source = source.replace("Plated,1,2,PTH", replacement)
    drill.write_text(source, encoding="utf-8")

    report = analyze_fabrication_connectivity(board, fabrication, FabricationConnectivitySettings())
    repeated = analyze_fabrication_connectivity(
        board, fabrication, FabricationConnectivitySettings()
    )

    assert report == repeated
    assert report.status == "UNSUPPORTED"
    assert report.unsupported_reasons
    assert message in report.unsupported_reasons[0]
    assert not report.findings


def test_inner_copper_layer_fails_closed_and_exposes_stale_ignores(tmp_path: Path) -> None:
    board, fabrication = write_synthetic_fabrication(tmp_path, inner_layer=True)
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
    assert "mismatch" in unsupported.unsupported_reasons[0]
    assert stale.status == "UNSUPPORTED"


def test_multilayer_gerbers_follow_the_source_stack_and_missing_layers_block(
    tmp_path: Path,
) -> None:
    stack = ("F.Cu", "In1.Cu", "In2.Cu", "B.Cu")
    paths: list[Path] = []
    positions = ("Top", "Inr", "Inr", "Bot")
    for index, (layer, position) in enumerate(zip(stack, positions, strict=True), start=1):
        path = tmp_path / f"board-{layer.replace('.', '_')}.gbr"
        path.write_text(
            f"%TF.FileFunction,Copper,L{index},{position}*%\n"
            "%FSLAX46Y46*%\n%MOMM*%\n%LPD*%\nM02*\n",
            encoding="utf-8",
        )
        paths.append(path)

    classified = classify_copper_files(tuple(reversed(paths)), stack)
    assert tuple(layer for _, layer in classified) == stack

    with pytest.raises(UnsupportedFabricationFormat, match="every source copper layer"):
        classify_copper_files(tuple(paths[:-1]), stack)


def test_stale_ignore_on_supported_board_fails_policy(tmp_path: Path) -> None:
    board, fabrication = write_synthetic_fabrication(tmp_path)
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
    board, fabrication = write_synthetic_fabrication(tmp_path)
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


def test_ipc356_via_without_source_board_via_fails_before_rasterization(
    tmp_path: Path,
) -> None:
    board, fabrication = write_synthetic_fabrication(tmp_path)
    ipc = fabrication / "board.d356"
    ipc.write_text(
        ipc.read_text(encoding="utf-8").replace(
            "999\n", format_ipc_contact("317", "SIGNAL", "VIA", "", 0, 5.0) + "\n999\n"
        ),
        encoding="utf-8",
    )

    result = analyze_fabrication_connectivity(board, fabrication, FabricationConnectivitySettings())

    assert result.status == "UNSUPPORTED"
    assert "VIA contact count differs from source PCB vias" in result.unsupported_reasons[0]


@pytest.mark.parametrize(
    ("mismatch", "expected_reason"),
    (
        ("artifact", "layer classification differs from source PCB pad"),
        ("ambiguous-source", "unsupported or ambiguous copper-layer classification"),
    ),
)
def test_ipc356_contact_layer_mismatch_fails_before_rasterization(
    tmp_path: Path, mismatch: str, expected_reason: str
) -> None:
    board, fabrication = write_synthetic_fabrication(tmp_path)
    if mismatch == "artifact":
        ipc = fabrication / "board.d356"
        ipc.write_text(ipc.read_text(encoding="utf-8").replace("327", "317"), encoding="utf-8")
    else:
        board.write_text(
            board.read_text(encoding="utf-8").replace(
                '"F.Cu" "F.Mask"', '"F.Cu" "B.Cu" "F.Mask" "B.Mask"'
            ),
            encoding="utf-8",
        )

    result = analyze_fabrication_connectivity(board, fabrication, FabricationConnectivitySettings())

    assert result.status == "UNSUPPORTED"
    assert expected_reason in result.unsupported_reasons[0]
