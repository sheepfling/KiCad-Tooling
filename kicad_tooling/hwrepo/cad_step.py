"""Source-bound, native STEP-versus-WRL review for one exact CAD bundle.

This produces disposable boards and paired views. It never installs STEP or
asserts manufacturer dimensions, pad contact, or mechanical approval.
"""
from __future__ import annotations

import hashlib
import os
import re
from html import escape
from pathlib import Path

from .cad_library import _native_footprint, inspect_bundle  # pyright: ignore[reportPrivateUsage]
from .cad_source import _cached  # pyright: ignore[reportPrivateUsage]
from .contracts import parse_easyeda_identity, repo_path, write_model
from .discovery import load_config
from .models import CadSourceReport, CadStepReport, CommandEvidence
from .part_cad import _nodes, _quote, _root, _tokens  # pyright: ignore[reportPrivateUsage]
from .parts_workflow import selected_project
from .three_d import _command, _valid_artifact  # pyright: ignore[reportPrivateUsage]

_IMAGE = re.compile(r"[^@\s]+@sha256:[a-f0-9]{64}\Z")
_POSES = ("top", "turned", "bottom", "angled")
_STYLE = """
:root{font-family:system-ui,-apple-system,sans-serif;color:#19372d;background:#f1f5f2;line-height:1.5}
*{box-sizing:border-box}body{margin:0}main{max-width:1200px;margin:auto;padding:28px 18px 50px}
h1{line-height:1.15}p{max-width:85ch}table{width:100%;table-layout:fixed;border-spacing:0 12px}
thead th{text-align:left}thead th:first-child{width:75px}tbody th{text-align:left;vertical-align:top;padding:12px 4px}
td{vertical-align:top;background:white;padding:5px}td a{display:block}td img{display:block;width:100%;height:auto}
a{color:#155a43}@media(max-width:600px){main{padding:18px 8px}thead th:first-child{width:52px}}
"""
_FIXTURE = '''"""Disposable paired KiCad boards for STEP alignment review."""
import sys
from pathlib import Path
import pcbnew

output = Path('/output')
name = sys.argv[1]

def edge(board, size):
    points = ((5, 5), (size-5, 5), (size-5, size-5), (5, size-5))
    for start, end in zip(points, (*points[1:], points[0])):
        shape = pcbnew.PCB_SHAPE()
        shape.SetShape(pcbnew.SHAPE_T_SEGMENT)
        shape.SetLayer(pcbnew.Edge_Cuts)
        shape.SetStart(pcbnew.VECTOR2I(pcbnew.FromMM(start[0]), pcbnew.FromMM(start[1])))
        shape.SetEnd(pcbnew.VECTOR2I(pcbnew.FromMM(end[0]), pcbnew.FromMM(end[1])))
        shape.SetWidth(pcbnew.FromMM(0.05))
        board.Add(shape)

for kind in ('wrl', 'step'):
    for pose, angle, bottom in (('top', 0, False), ('turned', 90, False),
                                ('bottom', 180, True), ('angled', 0, False)):
        footprint = pcbnew.FootprintLoad(str(output / (kind + '.pretty')), name)
        if footprint is None:
            raise RuntimeError('KiCad could not load the paired ' + kind + ' footprint')
        width = pcbnew.ToMM(footprint.GetBoundingBox().GetWidth())
        height = pcbnew.ToMM(footprint.GetBoundingBox().GetHeight())
        size = max(18, int(max(width, height) + 13))
        board = pcbnew.BOARD()
        footprint.SetReference('U1')
        footprint.SetValue(kind.upper())
        footprint.SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(size/2), pcbnew.FromMM(size/2)))
        footprint.SetOrientationDegrees(angle)
        board.Add(footprint)
        if bottom:
            footprint.Flip(footprint.GetPosition(), False)
        edge(board, size)
        target = output / (kind + '-' + pose + '.kicad_pcb')
        if not pcbnew.SaveBoard(str(target), board):
            raise RuntimeError('KiCad did not save ' + target.name)
        print(target.name, flush=True)
'''


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _fixture_footprint(source: str, name: str, model: str) -> str:
    native = _native_footprint(source, name)
    models = _nodes(native, _root(native, "footprint"), "model")
    if len(models) != 1:
        raise ValueError("STEP review requires one paired footprint model")
    token = _tokens(native, models[0])[1]
    return native[:token.start] + _quote(model) + native[token.end:]


def _docker(output: Path, image: str, entrypoint: str, arguments: tuple[str, ...],
            timeout: int = 180) -> CommandEvidence:
    if _IMAGE.fullmatch(image) is None:
        raise ValueError("STEP review requires the project's digest-pinned KiCad image")
    user: tuple[str, ...] = () if os.name == "nt" else (
        "--user", f"{os.getuid()}:{os.getgid()}",
    )
    command = ("docker", "run", "--rm", "--platform", "linux/amd64", "--network", "none",
               *user, "--entrypoint", entrypoint, "-e", "HOME=/tmp/kicad-step-review",
               "-v", f"{output}:/output:rw", "-w", "/output", image, *arguments)
    return _command(output, command, timeout)


def _gallery(report: CadStepReport) -> str:
    title = escape(f"STEP alignment review · {report.supplier_id}")
    rows = "".join(
        f'<tr><th scope="row">{escape(pose.title())}</th>'
        f'<td><a href="wrl-{pose}.png"><img src="wrl-{pose}.png" alt="WRL {pose} placement"></a></td>'
        f'<td><a href="step-{pose}.png"><img src="step-{pose}.png" alt="STEP {pose} placement"></a></td></tr>'
        for pose in _POSES
    )
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>{title}</title><link rel="stylesheet" href="index.css"></head>'
            f'<body><main><h1>{title}</h1>'
            '<p>Compare the body, contacts, pin-one mark, height and position relative to the pads '
            'in every view. Select an image to inspect it full size. These are disposable '
            'test boards, not the project PCB.</p>'
            '<p>A STEP export and matching view do not certify manufacturer dimensions or physical fit. '
            'Keep STEP out of the project library until this particular source is reviewed.</p>'
            '<table><thead><tr><th>View</th><th>Paired WRL</th><th>Raw STEP</th></tr></thead>'
            f'<tbody>{rows}</tbody></table>'
            '<p><a href="assembly.step">Download disposable STEP assembly</a></p>'
            '<p><a href="../">Back to parts assistant</a></p></main></body></html>\n')


def review(root: Path, project_id: str, source: CadSourceReport, output: Path) -> CadStepReport:
    """Prepare an exact-source comparison in a fresh ignored receipt using pinned KiCad."""
    root = root.resolve()
    output = output if output.is_absolute() else root / output
    output = repo_path(root, output.relative_to(root).as_posix())
    if not output.is_relative_to(root / "build") or output == root / "build":
        raise ValueError("STEP review receipts must be under ignored build/")
    if not output.is_dir() or any(output.iterdir()):
        raise ValueError("STEP review needs a fresh empty receipt directory")
    commands: dict[str, CommandEvidence] = {}
    artifacts: dict[str, str] = {}
    bundle_sha256: str | None = None
    step_sha256: str | None = None
    image: str | None = None
    version: str | None = None
    issues: tuple[str, ...] = ()
    status = "BLOCKED"
    try:
        if source.status != "READY" or source.bundle is None or source.bundle_directory is None:
            raise ValueError("Find an exact CAD part before checking STEP alignment")
        bundle = source.bundle
        directory = repo_path(root, Path(source.bundle_directory).relative_to(root).as_posix())
        parent = repo_path(root, f"build/cad-source-cache/easyeda-{bundle.converter_version}/{bundle.supplier_id}")
        if directory.name != "bundle" or directory.parent.parent != parent:
            raise ValueError("STEP review requires its source-bound local CAD cache")
        if _cached(directory.parent, bundle.supplier_id, bundle.mpn) != bundle:
            raise ValueError("CAD source cache changed after the reviewed lookup")
        check = inspect_bundle(directory, bundle)
        if check.status != "READY":
            raise ValueError("CAD library is not internally consistent: " + "; ".join(check.issues))
        raw = repo_path(directory.parent, f"source/{bundle.supplier_id}.json")
        identity = parse_easyeda_identity(raw.read_text(encoding="utf-8"))
        if identity.supplier_id != bundle.supplier_id or identity.model_title != Path(bundle.model_file).stem:
            raise ValueError("Frozen STEP identity differs from the paired WRL model")
        step = repo_path(directory.parent, f"source/{identity.model_uuid}.step")
        if step.stat().st_size == 0:
            raise ValueError("This exact part has no source STEP file; compare WRL only")
        with step.open("rb") as stream:
            if not stream.read(15).startswith(b"ISO-10303-21;"):
                raise ValueError("The source STEP file is not an ISO 10303-21 model")
        footprint = repo_path(directory, bundle.footprint_file)
        wrl = repo_path(directory, bundle.model_file)
        source_paths = (directory / "bundle.json", raw, step, footprint, wrl)
        before = {str(path): _sha(path) for path in source_paths}
        bundle_sha256, step_sha256 = before[str(directory / "bundle.json")], before[str(step)]
        record = selected_project(root, project_id)
        config = load_config(root, record.config)
        image, version = config.image, config.kicad_version
        (output / "model.wrl").write_bytes(wrl.read_bytes())
        (output / "model.step").write_bytes(step.read_bytes())
        for kind in ("wrl", "step"):
            library = output / f"{kind}.pretty"
            library.mkdir()
            target = library / f"{bundle.footprint_name}.kicad_mod"
            target.write_text(_fixture_footprint(footprint.read_text(encoding="utf-8"),
                              bundle.footprint_name, f"/output/model.{kind}"), encoding="utf-8")
        (output / "make_boards.py").write_text(_FIXTURE, encoding="utf-8")
        specifications = [
            ("version", "kicad-cli", ("version",), 30),
            ("boards", "python3", ("-B", "/output/make_boards.py", bundle.footprint_name), 120),
        ]
        for name, entrypoint, args, timeout in specifications:
            result = _docker(output, config.image, entrypoint, args, timeout)
            commands[name] = result
            write_model(output / f"{name}.command.json", result)
            if result.returncode != 0 or result.error:
                raise ValueError(f"Pinned KiCad {name} failed; inspect {name}.command.json")
            if name == "version" and result.stdout.strip() != config.kicad_version:
                raise ValueError(f"KiCad version {result.stdout.strip()} differs from {config.kicad_version}")
        for kind in ("wrl", "step"):
            for pose in _POSES:
                name = f"{kind}-{pose}"
                side = "bottom" if pose == "bottom" else "top"
                args = ("pcb", "render", "--width", "1200", "--height", "900",
                        "--side", side, "--zoom", "2.5", *(("--rotate", "45,0,45") if pose == "angled" else ()) ,
                        "-o", f"/output/{name}.png", f"/output/{name}.kicad_pcb")
                result = _docker(output, config.image, "kicad-cli", args, 180)
                commands[name] = result
                write_model(output / f"{name}.command.json", result)
                image_path = output / f"{name}.png"
                if result.returncode != 0 or result.error or not _valid_artifact(image_path, "png"):
                    raise ValueError(f"KiCad could not render {name}; inspect {name}.command.json")
                artifacts[image_path.name] = _sha(image_path)
        export = _docker(output, config.image, "kicad-cli", (
            "pcb", "export", "step", "-o", "/output/assembly.step", "/output/step-top.kicad_pcb",
        ), 180)
        commands["assembly"] = export
        write_model(output / "assembly.command.json", export)
        assembly = output / "assembly.step"
        if export.returncode != 0 or export.error or not _valid_artifact(assembly, "step"):
            raise ValueError("KiCad STEP assembly export failed; inspect assembly.command.json")
        if assembly.read_text(encoding="utf-8", errors="ignore").count("MANIFOLD_SOLID_BREP") < 2:
            raise ValueError("KiCad assembly STEP lacks an identifiable component solid")
        artifacts[assembly.name] = _sha(assembly)
        if {str(path): _sha(path) for path in source_paths} != before:
            raise ValueError("CAD source changed while STEP evidence was generated; discard the receipt")
        status = "REVIEW"
        issues = ("Compare every STEP and WRL view against the same pads before accepting alignment.",
                  "The STEP model is not installed by this check; manufacturer fit is unverified.")
    except (OSError, ValueError, UnicodeError) as error:
        issues = (str(error),)
    report = CadStepReport(status=status, project_id=project_id, supplier_id=source.supplier_id,
        source_bundle_sha256=bundle_sha256, source_step_sha256=step_sha256,
        kicad_version=version, image=image, artifacts_sha256=artifacts,
        commands=commands, issues=issues, receipt_directory=str(output))
    if status == "REVIEW":
        (output / "index.html").write_text(_gallery(report), encoding="utf-8")
        (output / "index.css").write_text(_STYLE, encoding="utf-8")
        report = report.model_copy(update={"artifacts_sha256": {
            **artifacts, "index.html": _sha(output / "index.html"),
            "index.css": _sha(output / "index.css")}})
    write_model(output / "cad-step-report.json", report)
    return report
