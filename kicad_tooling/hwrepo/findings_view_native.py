"""Read source-bound native drawing and report artifacts for visual review."""

from __future__ import annotations

import hashlib
import tempfile
from collections import Counter
from collections.abc import Mapping
from pathlib import Path, PureWindowsPath
from typing import Literal

from ..validate import check_report
from .artifact_access import read_regular_bytes
from .command_evidence_models import CommandEvidence
from .contracts import parse_model_text, read_kicad_drc_findings, read_kicad_erc_report, repo_path
from .findings_view_mapping import (
    DRC_MAPPING_VERSIONS,
    SCHEMATIC_MAPPING_VERSIONS,
    drc_finding,
    erc_finding,
)
from .findings_view_models import ReviewDrawing, ReviewFinding
from .findings_view_svg import prepare_drawing
from .models import ValidationSummary
from .project_models import (
    ProjectConfig,
    ProjectKind,
)

_MAX_ARTIFACT = 32 * 1024 * 1024


class NativeArtifacts:
    """Track exactly the retained files consumed by one export."""

    def __init__(self, root: Path, directory: Path, summary: ValidationSummary) -> None:
        self.root = root
        self.directory = directory
        self.summary = summary
        self.used: dict[str, str] = {}

    def read(self, name: str) -> bytes:
        expected = self.summary.artifacts_sha256.get(name)
        if expected is None:
            raise ValueError(f"Native summary does not bind {name}")
        path = repo_path(self.directory, name)
        content, _ = read_regular_bytes(path, maximum=_MAX_ARTIFACT)
        actual = hashlib.sha256(content).hexdigest()
        if actual != expected:
            raise ValueError(f"Native artifact changed or is missing: {name}")
        self.used[name] = expected
        return content

    def verify(self) -> None:
        for name, expected in tuple(self.used.items()):
            if hashlib.sha256(self.read(name)).hexdigest() != expected:
                raise ValueError(f"Native artifact changed during review: {name}")


def _command(artifacts: NativeArtifacts, config: ProjectConfig, name: str) -> None:
    filename = f"{name}.command.json"
    evidence = parse_model_text(artifacts.read(filename).decode("utf-8"), CommandEvidence)
    prefix: tuple[str, ...]
    if name == "schematic_svg":
        prefix, extension, target = ("sch", "export", "svg"), ".kicad_sch", "schematic"
    elif name == "pcb_svg":
        prefix, extension, target = (
            ("pcb", "export", "svg", "--layers", "F.Cu,F.SilkS,Edge.Cuts,Cmts.User"),
            ".kicad_pcb",
            "pcb.svg",
        )
    else:
        prefix = (
            "sch" if name == "erc" else "pcb",
            name,
            "--format",
            "json",
            "--severity-all",
            "--exit-code-violations",
        )
        extension, target = (
            (".kicad_sch", "erc.json") if name == "erc" else (".kicad_pcb", "drc.json")
        )
        if name == "drc":
            if config.kind is not ProjectKind.PCB_ONLY:
                prefix += ("--schematic-parity",)
            prefix += ("--refill-zones",)
    source = artifacts.root / Path(config.project).with_suffix(extension)
    output = artifacts.directory / target
    source_paths = {
        str(source).replace("\\", "/"),
        "/work/" + source.relative_to(artifacts.root).as_posix(),
    }
    output_paths = {
        str(output).replace("\\", "/"),
        "/work/" + output.relative_to(artifacts.root).as_posix(),
    }
    argv = evidence.argv
    start = next((i for i in range(len(argv)) if argv[i : i + len(prefix)] == prefix), None)
    tail = () if start is None else argv[start + len(prefix) :]
    if (
        evidence.error is not None
        or evidence.returncode not in ({0, 5} if name in {"erc", "drc"} else {0})
        or len(tail) != 3
        or tail[0] != "--output"
        or tail[1].replace("\\", "/") not in output_paths
        or tail[2].replace("\\", "/") not in source_paths
    ):
        raise ValueError(f"Native {name} command does not match the selected source/export")
    check = artifacts.summary.checks.get(name)
    if check is None or check.returncode != evidence.returncode:
        raise ValueError(f"Native {name} check and command return codes disagree")


def drawings(
    artifacts: NativeArtifacts, config: ProjectConfig
) -> tuple[tuple[ReviewDrawing, bytes], ...]:
    found: list[tuple[ReviewDrawing, bytes]] = []
    specs: tuple[tuple[Literal["schematic", "pcb"], str], ...] = (
        ("schematic", "schematic_svg"),
        ("pcb", "pcb_svg"),
    )
    for kind, check_name in specs:
        check = artifacts.summary.checks.get(check_name)
        if check is None or check.status != "PASS":
            continue
        _command(artifacts, config, check_name)
        files = check.files
        if not files:
            raise ValueError(f"Native {check_name} has no recorded output files")
        for index, name in enumerate(files, 1):
            if not (name.startswith("schematic/") if kind == "schematic" else name == "pcb.svg"):
                raise ValueError(f"Unexpected {check_name} output path: {name}")
            if not name.endswith(".svg"):
                raise ValueError(f"Unexpected {check_name} output type: {name}")
            parsed = prepare_drawing(artifacts.read(name), kind)
            output_name = f"schematic-{index}.svg" if kind == "schematic" else "pcb.svg"
            found.append(
                (
                    ReviewDrawing(
                        kind=kind,
                        file=output_name,
                        source_artifact=name,
                        sha256=hashlib.sha256(parsed.content).hexdigest(),
                        width_mm=parsed.width,
                        height_mm=parsed.height,
                        mapping_supported=parsed.can_map_mm
                        and config.kicad_version
                        in (
                            SCHEMATIC_MAPPING_VERSIONS
                            if kind == "schematic"
                            else DRC_MAPPING_VERSIONS
                        ),
                    ),
                    parsed.content,
                )
            )
    return tuple(found)


def native_findings(
    artifacts: NativeArtifacts,
    config: ProjectConfig,
    board: ReviewDrawing | None,
    schematic: tuple[ReviewDrawing, ...],
    source_hashes: Mapping[str, str],
) -> tuple[tuple[ReviewFinding, ...], tuple[str, ...]]:
    findings: list[ReviewFinding] = []
    issues: list[str] = []
    kinds: tuple[tuple[Literal["erc", "drc"], str], ...] = (
        ("erc", ".kicad_sch"),
        ("drc", ".kicad_pcb"),
    )
    counts = Counter(
        drawing.sheet_instance_path
        for drawing in schematic
        if drawing.sheet_instance_path is not None
    )
    sheet_drawings = {
        drawing.sheet_instance_path: drawing
        for drawing in schematic
        if drawing.sheet_instance_path is not None and counts[drawing.sheet_instance_path] == 1
    }
    for kind, source_extension in kinds:
        check = artifacts.summary.checks.get(kind)
        if check is None or check.status == "NOT_RUN" or check.returncode not in {0, 5}:
            issues.append(f"{kind.upper()} was not available from a completed native check.")
            continue
        source = Path(config.project).with_suffix(source_extension).as_posix()
        _command(artifacts, config, kind)
        name = f"{kind}.json"
        content = artifacts.read(name)
        # Parse the exact verified bytes, not a second read of a mutable receipt.
        with tempfile.TemporaryDirectory(prefix="kicad-findings-report-") as temporary:
            path = Path(temporary) / name
            path.write_bytes(content)
            count = check_report(path, kind, config)
            if check.findings is not None and check.findings != count:
                raise ValueError(f"Native {kind.upper()} count disagrees with its summary")
            erc = read_kicad_erc_report(path) if kind == "erc" else None
            drc = read_kicad_drc_findings(path) if kind == "drc" else None
        if erc is not None:
            if erc.kicad_version != config.kicad_version:
                raise ValueError("Native ERC version differs from the project toolchain")
            if erc.source and PureWindowsPath(erc.source).name != Path(source).name:
                raise ValueError("Native ERC source differs from the selected schematic")
            for item in erc.violations:
                findings.append(erc_finding(item, erc, source, sheet_drawings, source_hashes))
        elif drc is not None:
            if (
                drc.version != config.kicad_version
                or PureWindowsPath(drc.source).name != Path(source).name
            ):
                raise ValueError("Native DRC identity differs from the selected board/toolchain")
            findings.extend(
                drc_finding(item, board, drc.version, drc.units) for item in drc.findings
            )
    return tuple(findings), tuple(issues)
