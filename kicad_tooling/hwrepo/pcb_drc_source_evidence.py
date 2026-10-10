"""Bind the native DRC report to current project, rules, board, and receipts."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from ..validate import hashes
from .contracts import read_model, repo_path
from .evidence import digest
from .models import CommandEvidence, ProjectConfig, ValidationSummary


@dataclass(frozen=True, slots=True)
class BoundDrcEvidence:
    project_path: str
    project_sha256: str
    rules_path: str
    rules_sha256: str | None
    board_path: str
    board_sha256: str
    native_summary_path: str
    native_summary_sha256: str
    native_drc_path: str
    native_drc_sha256: str
    project_file: Path
    board_file: Path
    summary_file: Path
    summary_sha256_before: str
    drc_file: Path
    rules_source: str
    ignored_checks: frozenset[str]


def source_bound_drc_evidence(
    root: Path,
    config: ProjectConfig,
    source_hashes: dict[str, str],
    native_summary: Path,
) -> BoundDrcEvidence:
    root = root.resolve()
    project_file = repo_path(root, config.project)
    board_file = project_file.with_suffix(".kicad_pcb")
    rules_file = project_file.with_suffix(".kicad_dru")
    project_relative = project_file.relative_to(root).as_posix()
    board_relative = board_file.relative_to(root).as_posix()
    rules_relative = rules_file.relative_to(root).as_posix()
    project_hash = source_hashes.get(project_relative)
    board_hash = source_hashes.get(board_relative)
    if project_hash is None or board_hash is None:
        raise ValueError("Project settings or authoritative PCB is outside source-bound inputs")
    if digest(project_file) != project_hash or digest(board_file) != board_hash:
        raise ValueError("Project settings or board differs from source-bound evidence")
    if rules_file.exists():
        rules_hash = source_hashes.get(rules_relative)
        if rules_hash is None or digest(rules_file) != rules_hash:
            raise ValueError("Native DRC rules are outside or differ from source-bound inputs")
        rules_source = rules_file.read_text(encoding="utf-8")
    else:
        rules_hash = None
        rules_source = ""

    summary_file = native_summary / "summary.json" if native_summary.is_dir() else native_summary
    summary_file = summary_file.resolve()
    try:
        summary_relative = summary_file.relative_to(root).as_posix()
    except ValueError as exc:
        raise ValueError("Native summary is outside the current repository") from exc
    summary_hash_before = digest(summary_file)
    summary = read_model(summary_file, ValidationSummary)
    drc_relative = "drc.json"
    command_relative = "drc.command.json"
    if not {drc_relative, command_relative} <= summary.artifacts_sha256.keys():
        raise ValueError("Native summary does not bind both the DRC report and command")
    drc_file = summary_file.parent / drc_relative
    command_file = summary_file.parent / command_relative
    if digest(drc_file) != summary.artifacts_sha256[drc_relative]:
        raise ValueError("Native DRC report differs from its summary artifact hash")
    if digest(command_file) != summary.artifacts_sha256[command_relative]:
        raise ValueError("Native DRC command differs from its summary artifact hash")
    drc_command = read_model(command_file, CommandEvidence)
    if drc_command.error is not None or drc_command.returncode not in {0, 5}:
        raise ValueError("Native DRC command did not complete with a recognized result")
    argv = drc_command.argv
    if (
        not any(argv[index : index + 2] == ("pcb", "drc") for index in range(len(argv) - 1))
        or not any(
            argv[index : index + 2] == ("--format", "json") for index in range(len(argv) - 1)
        )
        or "--severity-all" not in argv
    ):
        raise ValueError("Native DRC command evidence does not record a JSON all-severity PCB DRC")
    try:
        output_index = argv.index("--output")
        output_argument = argv[output_index + 1]
    except (ValueError, IndexError) as exc:
        raise ValueError("Native DRC command evidence has no report output path") from exc
    output_path = Path(output_argument)
    if not output_path.is_absolute():
        output_path = root / output_path
    board_argument = Path(argv[-1])
    if not board_argument.is_absolute():
        board_argument = root / board_argument
    if (
        output_path.resolve() != drc_file.resolve()
        or board_argument.resolve() != board_file.resolve()
    ):
        raise ValueError(
            "Native DRC command does not bind the current report and authoritative board"
        )
    check = summary.checks.get("drc")
    if check is None or check.status == "NOT_RUN" or check.returncode not in {0, 5}:
        raise ValueError("Native summary does not record a completed PCB DRC check")
    raw_payload: object = json.loads(drc_file.read_text(encoding="utf-8"))
    if not isinstance(raw_payload, dict):
        raise TypeError("Native DRC report root must be a JSON object")
    payload = cast(dict[str, object], raw_payload)
    if payload.get("kicad_version") != config.kicad_version:
        raise ValueError("Native DRC report version differs from the selected project version")
    source = payload.get("source")
    if (
        not isinstance(source, str)
        or source.replace("\\", "/").rsplit("/", 1)[-1] != board_file.name
    ):
        raise ValueError("Native DRC report does not name the authoritative PCB")
    raw_ignored_rows = payload.get("ignored_checks")
    if not isinstance(raw_ignored_rows, list):
        raise TypeError("Native DRC report does not include ignored-check evidence")
    ignored: set[str] = set()
    for raw_row in cast(list[object], raw_ignored_rows):
        if not isinstance(raw_row, dict):
            raise TypeError("Native DRC report has malformed ignored-check evidence")
        key = cast(dict[str, object], raw_row).get("key")
        if not isinstance(key, str):
            raise TypeError("Native DRC report has malformed ignored-check evidence")
        ignored.add(key)
    return BoundDrcEvidence(
        project_path=project_relative,
        project_sha256=project_hash,
        rules_path=rules_relative,
        rules_sha256=rules_hash,
        board_path=board_relative,
        board_sha256=board_hash,
        native_summary_path=summary_relative,
        native_summary_sha256=summary_hash_before,
        native_drc_path=(summary_file.parent / drc_relative).relative_to(root).as_posix(),
        native_drc_sha256=digest(drc_file),
        project_file=project_file,
        board_file=board_file,
        summary_file=summary_file,
        summary_sha256_before=summary_hash_before,
        drc_file=drc_file,
        rules_source=rules_source,
        ignored_checks=frozenset(ignored),
    )


def source_inventory_sha256(source_hashes: dict[str, str]) -> str:
    return hashlib.sha256(
        "\n".join(f"{name}\0{value}" for name, value in sorted(source_hashes.items())).encode(
            "utf-8"
        )
    ).hexdigest()


def verify_source_bound_drc_unchanged(
    root: Path,
    config: ProjectConfig,
    source_hashes: dict[str, str],
    evidence: BoundDrcEvidence,
) -> None:
    if hashes(root, config.source_roots) != source_hashes:
        raise ValueError("Declared source changed while checking native DRC rule coverage")
    if digest(evidence.summary_file) != evidence.summary_sha256_before:
        raise ValueError("Native summary changed while checking DRC rule coverage")
