"""Synthetic tests for the custom DRC rule compilation sentinel."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import pytest

from kicad_tooling.hwrepo.contracts import write_model
from kicad_tooling.hwrepo.models import CommandEvidence
from kicad_tooling.hwrepo.pcb_dru_compilation import (
    PcbDruCompilationReport,
    _append_sentinel,
    _sentinel_name,
    run_pcb_dru_compilation_probe,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.pcb_lint]

FIXTURES = Path(__file__).parent / "fixtures/design_lint/pcb-dru-rule-compilation"


def _command(
    argv: tuple[str, ...],
    *,
    returncode: int = 5,
    version: str = "10.0.5",
    include_sentinel: bool = True,
    output: Path,
    name: str,
    work: Path,
) -> CommandEvidence:
    board = work / "pcb-dru-rule-compilation-probe.kicad_pcb"
    staged_rules = board.with_suffix(".kicad_dru").read_text(encoding="utf-8")
    match = re.findall(r'\(rule "(KTT_DRC_RULE_COMPILE_SENTINEL_[A-Za-z0-9_]+)"', staged_rules)
    assert len(match) == 1
    violations = (
        [
            {
                "type": "track_width",
                "description": f"Custom rule {match[0]} violated",
                "severity": "error",
                "items": [],
            }
        ]
        if include_sentinel
        else []
    )
    report_path = Path(argv[argv.index("--output") + 1])
    report_path.write_text(
        json.dumps(
            {
                "source": str(board),
                "kicad_version": version,
                "violations": violations,
            }
        ),
        encoding="utf-8",
    )
    command = CommandEvidence(
        argv=argv,
        started_utc="2026-10-19T00:00:00+00:00",
        returncode=returncode,
    )
    write_model(output / f"{name}.command.json", command)
    return command


def _run(
    tmp_path: Path,
    *,
    source: bytes | None = None,
    include_sentinel: bool = True,
    version: str = "10.0.5",
    returncode: int = 5,
) -> PcbDruCompilationReport:
    root = tmp_path / "repository"
    root.mkdir()
    rules_path = root / "controller.kicad_dru"
    rules_path.write_bytes(source or (FIXTURES / "control.kicad_dru").read_bytes())
    project_path = root / "controller.kicad_pro"
    project_path.write_text('{"text_variables": {"SYNTHETIC": "value"}}', encoding="utf-8")
    output = root / "build/native/controller"
    output.mkdir(parents=True)

    def execute(argv: tuple[str, ...], work: Path, command_output: Path, name: str):
        return _command(
            argv,
            returncode=returncode,
            version=version,
            include_sentinel=include_sentinel,
            output=command_output,
            name=name,
            work=work,
        )

    return run_pcb_dru_compilation_probe(
        rules_path=rules_path,
        project_path=project_path,
        repository_root=root,
        output=output,
        cli="kicad-cli",
        expected_kicad_version="10.0.5",
        image="ghcr.io/example/kicad:10.0.5@sha256:" + "a" * 64,
        execute=execute,
    )


def test_sentinel_name_and_appended_rule_are_stable_and_terminal() -> None:
    source = (FIXTURES / "control.kicad_dru").read_text(encoding="utf-8")
    first = _sentinel_name(source)
    assert _sentinel_name(source) == first
    assert first not in source
    appended = _append_sentinel(source, first)
    assert appended.startswith(source)
    assert appended.rstrip().endswith("(constraint track_width (min 10mm)))")
    assert appended.rfind(f'(rule "{first}"') == appended.rfind("(rule ")


def test_native_sentinel_violation_proves_source_rules_reached_the_last_rule(
    tmp_path: Path,
) -> None:
    source = (FIXTURES / "control.kicad_dru").read_bytes()
    report = _run(tmp_path, source=source)

    assert report.status == "PASS"
    assert report.sentinel_matches == 1
    assert report.native_returncode == 5
    assert report.expected_kicad_version == report.observed_kicad_version == "10.0.5"
    assert report.rules_sha256 == hashlib.sha256(source).hexdigest()
    assert report.project_sha256 is not None
    assert report.probe_sha256
    assert report.native_report_sha256


@pytest.mark.parametrize(
    ("version", "returncode", "include_sentinel", "expected_issue"),
    (
        ("10.0.4", 5, True, "Expected KiCad 10.0.5"),
        ("10.0.5", 0, False, "terminal sentinel rule"),
        ("10.0.5", 6, True, "failed with 6"),
    ),
)
def test_probe_fails_closed_without_exact_version_and_sentinel_evidence(
    tmp_path: Path,
    version: str,
    returncode: int,
    include_sentinel: bool,
    expected_issue: str,
) -> None:
    report = _run(
        tmp_path,
        version=version,
        returncode=returncode,
        include_sentinel=include_sentinel,
    )

    assert report.status == "FAIL"
    assert expected_issue in (report.issue or "")


def test_report_parser_rejects_malformed_native_output(tmp_path: Path) -> None:
    output = tmp_path / "malformed.json"
    output.write_text("[]", encoding="utf-8")
    from kicad_tooling.hwrepo.pcb_dru_compilation import _native_identity_and_matches

    with pytest.raises(TypeError, match="root must be an object"):
        _native_identity_and_matches(output, "sentinel")
