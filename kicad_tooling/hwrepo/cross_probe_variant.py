"""Read one named PCB population from retained, source-bound design-lint evidence."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from .artifact_access import artifact_file, read_regular_bytes
from .command_evidence_models import CommandEvidence
from .contracts import kicad_variant_names, parse_model_text, repo_path
from .design_lint_report_models import DesignLintReport
from .findings_view_models import FindingsViewReport
from .native_report_parsing import read_netlist
from .pcb_variant_population_capture import position_references
from .project_models import ComponentContract, ProjectConfig
from .review_overview_evidence import read_receipt, selected_receipt


@dataclass(frozen=True, slots=True)
class VariantObservation:
    name: str
    netlist_path: Path
    lint_path: Path
    lint_sha256: str
    evidence_sha256: dict[str, str]
    schematic: dict[str, ComponentContract]
    schematic_references: dict[str, str]
    schematic_dnp: frozenset[str]
    board_all: dict[str, str]
    board_fitted: frozenset[str]


def _verified_artifact(root: Path, name: str, expected: str) -> Path:
    path = artifact_file(root, name)
    content, _ = read_regular_bytes(path, maximum=32 * 1024 * 1024)
    if hashlib.sha256(content).hexdigest() != expected:
        raise ValueError(f"Named variant evidence changed: {name}")
    return path


def _reference_map(references: tuple[str, ...], label: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for reference in references:
        key = reference.casefold()
        if not reference or key in result:
            raise ValueError(f"Named variant {label} has blank or duplicate references")
        result[key] = reference
    return result


def _verified_command(
    path: Path,
    *,
    variant: str | None,
    image: str,
    source: str | None = None,
    output: str | None = None,
    kind: tuple[str, ...] = (),
    exclude_dnp: bool | None = None,
) -> None:
    content, _ = read_regular_bytes(path, maximum=8 * 1024 * 1024)
    command = parse_model_text(content.decode("utf-8"), CommandEvidence)
    argv = command.argv
    if command.returncode != 0 or command.error is not None or image not in argv:
        raise ValueError(f"Named variant command failed or used another image: {path.name}")
    if variant is None:
        return
    expected_format = "kicadxml" if kind[0] == "sch" else "csv"
    if (
        "--variant" not in argv
        or argv.index("--variant") + 1 >= len(argv)
        or argv[argv.index("--variant") + 1] != variant
        or source is None
        or f"/work/{source}" not in argv
        or output is None
        or "--output" not in argv
        or argv.index("--output") + 1 >= len(argv)
        or argv[argv.index("--output") + 1] != f"/output/{Path(output).name}"
        or not any(argv[index : index + len(kind)] == kind for index in range(len(argv)))
        or "--format" not in argv
        or argv.index("--format") + 1 >= len(argv)
        or argv[argv.index("--format") + 1] != expected_format
        or (
            kind[0] == "pcb"
            and (
                "--side" not in argv
                or argv.index("--side") + 1 >= len(argv)
                or argv[argv.index("--side") + 1] != "both"
            )
        )
        or (exclude_dnp is not None and ("--exclude-dnp" in argv) != exclude_dnp)
    ):
        raise ValueError(f"Named variant command is not bound to {variant!r}: {path.name}")


def read_variant_observation(
    root: Path,
    config: ProjectConfig,
    current: dict[str, str],
    findings: FindingsViewReport,
    requested: str,
    native_netlist_sha256: str | None,
) -> VariantObservation:
    """Verify selected native exports before using their population for navigation."""
    if not requested.strip() or findings.lint_report is None or findings.lint_report_sha256 is None:
        raise ValueError("Named variant navigation needs a selected design-lint receipt")
    lint_path = selected_receipt(root, Path(findings.lint_report), "report.json")
    lint, lint_sha = read_receipt(lint_path, DesignLintReport)
    if (
        lint_sha != findings.lint_report_sha256
        or lint.project_id != findings.project_id
        or dict(lint.source_hashes) != current
        or lint.netlist_sha256 is None
        or lint.netlist_sha256 != native_netlist_sha256
        or lint.native_summary is None
        or selected_receipt(root, Path(lint.native_summary), "summary.json")
        != selected_receipt(root, Path(findings.native_summary), "summary.json")
    ):
        raise ValueError("Named variant design-lint receipt differs from selected source evidence")
    coverage = lint.pcb_component_inventory.variant_population
    project_path = Path(config.project).with_suffix(".kicad_pro").as_posix()
    schematic_path = Path(config.project).with_suffix(".kicad_sch").as_posix()
    board_path = Path(config.project).with_suffix(".kicad_pcb").as_posix()
    if (
        coverage.status != "COMPLETE"
        or coverage.kicad_version != config.kicad_version
        or coverage.image != config.image
        or coverage.project_path != project_path
        or coverage.schematic_path != schematic_path
        or coverage.board_path != board_path
        or coverage.project_sha256 != current.get(project_path)
        or coverage.schematic_sha256 != current.get(schematic_path)
        or coverage.board_sha256 != current.get(board_path)
    ):
        raise ValueError("Named variant population is not complete for this PCB source")
    names = kicad_variant_names(repo_path(root, project_path))
    selected = next((name for name in names if name.casefold() == requested.casefold()), None)
    evidence = next((item for item in coverage.evidence if item.variant == selected), None)
    if selected is None or evidence is None:
        raise ValueError(f"No complete native population evidence for variant {requested!r}")
    expected = {
        coverage.board_variant_probe_path: coverage.board_variant_probe_sha256,
        coverage.board_variant_request_path: coverage.board_variant_request_sha256,
        coverage.board_variant_command_path: coverage.board_variant_command_sha256,
        evidence.netlist_path: evidence.netlist_sha256,
        evidence.netlist_command_path: evidence.netlist_command_sha256,
        evidence.board_all_positions_path: evidence.board_all_positions_sha256,
        evidence.board_all_command_path: evidence.board_all_command_sha256,
        evidence.board_fitted_positions_path: evidence.board_fitted_positions_sha256,
        evidence.board_fitted_command_path: evidence.board_fitted_command_sha256,
    }
    if len(expected) != 9 or any(name is None or sha is None for name, sha in expected.items()):
        raise ValueError("Named variant evidence has an incomplete artifact inventory")
    hashes = {str(name): str(sha) for name, sha in expected.items()}
    paths = {name: _verified_artifact(root, name, sha) for name, sha in hashes.items()}
    assert coverage.board_variant_command_path is not None
    _verified_command(paths[coverage.board_variant_command_path], variant=None, image=config.image)
    for name, source, output, kind, exclude_dnp in (
        (
            evidence.netlist_command_path,
            schematic_path,
            evidence.netlist_path,
            ("sch", "export", "netlist"),
            False,
        ),
        (
            evidence.board_all_command_path,
            board_path,
            evidence.board_all_positions_path,
            ("pcb", "export", "pos"),
            False,
        ),
        (
            evidence.board_fitted_command_path,
            board_path,
            evidence.board_fitted_positions_path,
            ("pcb", "export", "pos"),
            True,
        ),
    ):
        _verified_command(
            paths[name],
            variant=selected,
            image=config.image,
            source=source,
            output=output,
            kind=kind,
            exclude_dnp=exclude_dnp,
        )
    netlist = read_netlist(paths[evidence.netlist_path])
    schematic_references = _reference_map(tuple(netlist.components), "schematic netlist")
    schematic = {
        key: netlist.components[reference] for key, reference in schematic_references.items()
    }
    all_board = _reference_map(
        position_references(paths[evidence.board_all_positions_path]), "PCB positions"
    )
    fitted_board = _reference_map(
        position_references(paths[evidence.board_fitted_positions_path]), "fitted PCB positions"
    )
    if not fitted_board.keys() <= all_board.keys():
        raise ValueError("Named variant fitted PCB positions are absent from its full positions")
    for name, sha in hashes.items():
        _verified_artifact(root, name, sha)
    return VariantObservation(
        name=selected,
        netlist_path=paths[evidence.netlist_path],
        lint_path=lint_path,
        lint_sha256=lint_sha,
        evidence_sha256=hashes,
        schematic=schematic,
        schematic_references=schematic_references,
        schematic_dnp=frozenset(item.casefold() for item in netlist.dnp_components),
        board_all=all_board,
        board_fitted=frozenset(fitted_board),
    )
