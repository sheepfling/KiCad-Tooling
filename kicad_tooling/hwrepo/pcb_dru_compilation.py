"""Prove that a project's custom PCB rules reach KiCad's DRC engine."""

from __future__ import annotations

import hashlib
import shutil
from collections.abc import Callable, Sequence
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Literal

from .contracts import write_model
from .model_primitives import Digest, NonEmptyText, NonNegativeCount, RepositoryPath, StrictModel
from .models import CommandEvidence
from .pcb_dru_compilation_native_report import (
    PROBE_BOARD_NAME,
)
from .pcb_dru_compilation_native_report import (
    native_identity_and_matches as _native_identity_and_matches,
)

_PROBE_BOARD = Path(__file__).parent / "fixtures" / PROBE_BOARD_NAME
_PROBE_RULE_NAME = "KTT_DRC_RULE_COMPILE_SENTINEL"
_PROBE_CONDITION = "A.Type == 'Track'"
_PROBE_CONSTRAINT = "(constraint track_width (min 10mm))"

NativeExecutor = Callable[[Sequence[str], Path, Path, str], CommandEvidence]


class PcbDruCompilationReport(StrictModel):
    """Source-bound result for the temporary native sentinel probe."""

    schema_version: Literal["1"] = "1"
    status: Literal["PASS", "FAIL"]
    rules_path: RepositoryPath
    rules_sha256: Digest
    project_path: RepositoryPath | None = None
    project_sha256: Digest | None = None
    probe_sha256: Digest
    image: NonEmptyText
    expected_kicad_version: NonEmptyText
    observed_kicad_version: NonEmptyText | None = None
    sentinel_rule_name: NonEmptyText
    sentinel_matches: NonNegativeCount = 0
    native_returncode: int | None = None
    native_report_sha256: Digest | None = None
    issue: NonEmptyText | None = None


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sentinel_name(source: str) -> str:
    """Choose a stable sentinel name that cannot collide with authored text."""
    counter = 0
    while True:
        suffix = "" if counter == 0 else f"_{counter}"
        name = f"{_PROBE_RULE_NAME}_{_sha256(source.encode('utf-8'))[:16]}{suffix}"
        if name not in source:
            return name
        counter += 1


def _append_sentinel(source: str, name: str) -> str:
    """Append a rule that must match the tooling-owned probe track."""
    rule = (
        f'(rule "{name}"\n'
        f'  (condition "{_PROBE_CONDITION}")\n'
        "  (severity error)\n"
        f"  {_PROBE_CONSTRAINT})\n"
    )
    return f"{source.rstrip()}\n\n{rule}"


def run_pcb_dru_compilation_probe(
    *,
    rules_path: Path,
    project_path: Path,
    repository_root: Path,
    output: Path,
    cli: str,
    expected_kicad_version: str,
    image: str,
    execute: NativeExecutor,
) -> PcbDruCompilationReport:
    """Run DRC on a synthetic board with the source rules plus a final sentinel.

    The source project files are copied only into a temporary directory and are
    removed when the native command finishes. The retained report contains the
    probe result and source hashes, not a copy of the project rule file.
    """
    repository = repository_root.resolve()
    if rules_path.is_symlink():
        raise ValueError("Custom DRC rule file cannot be a symlink")
    rules_relative = rules_path.resolve().relative_to(repository).as_posix()
    source_bytes = rules_path.read_bytes()
    source_text = source_bytes.decode("utf-8")
    sentinel_name = _sentinel_name(source_text)
    project_relative: str | None = None
    project_bytes: bytes | None = None
    if project_path.is_symlink():
        raise ValueError("Project file for custom DRC rules cannot be a symlink")
    if project_path.is_file():
        project_relative = project_path.resolve().relative_to(repository).as_posix()
        project_bytes = project_path.read_bytes()

    probe_bytes = _PROBE_BOARD.read_bytes()
    command_output = output / "drc-rule-compilation"
    command_output.mkdir(parents=True, exist_ok=True)
    retained_report_path = command_output / "probe-drc.json"
    issue: str | None = None
    observed_version: str | None = None
    sentinel_matches = 0
    returncode: int | None = None
    native_report_hash: str | None = None

    with TemporaryDirectory(prefix="kicad-dru-compile-", dir=output) as temporary:
        work = Path(temporary)
        board_copy = work / _PROBE_BOARD.name
        rules_copy = board_copy.with_suffix(".kicad_dru")
        project_copy = board_copy.with_suffix(".kicad_pro")
        report_path = work / "probe-drc.json"
        shutil.copyfile(_PROBE_BOARD, board_copy)
        rules_copy.write_text(_append_sentinel(source_text, sentinel_name), encoding="utf-8")
        if project_bytes is not None:
            project_copy.write_bytes(project_bytes)

        command = execute(
            (
                cli,
                "pcb",
                "drc",
                "--format",
                "json",
                "--severity-all",
                "--exit-code-violations",
                "--output",
                str(report_path),
                str(board_copy),
            ),
            work,
            command_output,
            "native-command",
        )
        returncode = command.returncode
        if command.error:
            issue = command.error
        elif not report_path.is_file():
            issue = "Native DRC did not produce a sentinel probe report"
        else:
            shutil.copyfile(report_path, retained_report_path)
            native_report_hash = _sha256(report_path.read_bytes())
            try:
                observed_version, sentinel_matches = _native_identity_and_matches(
                    report_path, sentinel_name
                )
            except (OSError, TypeError, ValueError) as exc:
                issue = str(exc)
            if issue is None and observed_version != expected_kicad_version:
                issue = (
                    f"Expected KiCad {expected_kicad_version} for DRC rule compilation; "
                    f"observed {observed_version!r}"
                )
            if issue is None and returncode not in {0, 5}:
                issue = f"Native DRC rule-compilation command failed with {returncode}"
            if issue is None and sentinel_matches == 0:
                issue = "Native DRC did not report the appended terminal sentinel rule"

    report = PcbDruCompilationReport(
        status="PASS" if issue is None else "FAIL",
        rules_path=rules_relative,
        rules_sha256=_sha256(source_bytes),
        project_path=project_relative,
        project_sha256=None if project_bytes is None else _sha256(project_bytes),
        probe_sha256=_sha256(probe_bytes),
        image=image,
        expected_kicad_version=expected_kicad_version,
        observed_kicad_version=observed_version,
        sentinel_rule_name=sentinel_name,
        sentinel_matches=sentinel_matches,
        native_returncode=returncode,
        native_report_sha256=native_report_hash,
        issue=issue,
    )
    write_model(output / "drc-rule-compilation.json", report)
    return report
