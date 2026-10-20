"""Validation integration for custom DRC compilation evidence."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from types import SimpleNamespace

import pytest

from kicad_tooling.hwrepo.models import (
    CommandEvidence,
    ComponentIdentity,
    IgnoredChecks,
    NetlistIdentityReport,
    PcbValidationContract,
    ProjectConfig,
    ProjectKind,
)
from kicad_tooling.validate import validate
from tests.support import initialize_git

pytestmark = [pytest.mark.design_lint, pytest.mark.pcb_lint]


@pytest.mark.parametrize(("emit_sentinel", "expected_status"), ((True, "PASS"), (False, "FAIL")))
def test_project_validation_requires_compilation_proof_when_rules_file_exists(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    emit_sentinel: bool,
    expected_status: str,
) -> None:
    root = tmp_path / "repository"
    source_dir = root / "projects/fixture/kicad"
    source_dir.mkdir(parents=True)
    project = "projects/fixture/kicad/board.kicad_pro"
    rules_relative = "projects/fixture/kicad/board.kicad_dru"
    schematic = "projects/fixture/kicad/board.kicad_sch"
    board = "projects/fixture/kicad/board.kicad_pcb"
    for relative in (project, schematic, board, rules_relative):
        (root / relative).write_text("synthetic source\n", encoding="utf-8")
    initialize_git(root)

    config = ProjectConfig(
        schema_version="1",
        kind=ProjectKind.PCB,
        assurance_profile="development",
        not_for_manufacture=True,
        project_id="fixture",
        component_identity=ComponentIdentity(required=False, part_ids=()),
        toolchain_id="kicad-10.0.5",
        kicad_version="10.0.5",
        image="ghcr.io/example/kicad:10.0.5@sha256:" + "a" * 64,
        project=project,
        source_roots=("projects/fixture/kicad",),
        required_inputs=(project, schematic, board, rules_relative),
        validation=PcbValidationContract(
            kind=ProjectKind.PCB,
            components={},
            nets={},
            expected_ignored_checks=IgnoredChecks(erc=(), drc=()),
        ),
    )
    source_hashes = {
        name: hashlib.sha256((root / name).read_bytes()).hexdigest()
        for name in config.required_inputs
    }

    def execute(argv: tuple[str, ...], _cwd: Path, output: Path, name: str) -> CommandEvidence:
        if name == "version":
            return CommandEvidence(
                argv=argv,
                started_utc="2026-10-19T00:00:00+00:00",
                returncode=0,
                stdout="10.0.5\n",
            )
        if name == "native-command":
            staged_board = Path(argv[-1])
            staged_rules = staged_board.with_suffix(".kicad_dru").read_text(encoding="utf-8")
            match = re.findall(
                r'\(rule "(KTT_DRC_RULE_COMPILE_SENTINEL_[A-Za-z0-9_]+)"', staged_rules
            )
            assert len(match) == 1
            violations = (
                [
                    {
                        "type": "clearance",
                        "description": f"Custom rule {match[0]} violated",
                        "severity": "error",
                        "items": [],
                    }
                ]
                if emit_sentinel
                else []
            )
            Path(argv[argv.index("--output") + 1]).write_text(
                json.dumps(
                    {
                        "source": str(staged_board),
                        "kicad_version": "10.0.5",
                        "violations": violations,
                    }
                ),
                encoding="utf-8",
            )
            command = CommandEvidence(
                argv=argv,
                started_utc="2026-10-19T00:00:00+00:00",
                returncode=5 if emit_sentinel else 0,
            )
        elif name in {"erc", "drc"}:
            report: dict[str, object] = {
                "$schema": f"https://schemas.kicad.org/{name}.v1.json",
                "kicad_version": "10.0.5",
                "included_severities": ["error", "warning", "exclusion"],
                "ignored_checks": [],
            }
            if name == "erc":
                report["sheets"] = [{"violations": []}]
            else:
                report.update({"violations": [], "unconnected_items": [], "schematic_parity": []})
            (output / f"{name}.json").write_text(json.dumps(report), encoding="utf-8")
            command = CommandEvidence(
                argv=argv,
                started_utc="2026-10-19T00:00:00+00:00",
                returncode=0,
            )
        elif name == "schematic_svg":
            directory = output / "schematic"
            directory.mkdir()
            (directory / "sheet.svg").write_text(
                '<svg xmlns="http://www.w3.org/2000/svg"/>', encoding="utf-8"
            )
            command = CommandEvidence(
                argv=argv,
                started_utc="2026-10-19T00:00:00+00:00",
                returncode=0,
            )
        elif name == "pcb_svg":
            (output / "pcb.svg").write_text(
                '<svg xmlns="http://www.w3.org/2000/svg"/>', encoding="utf-8"
            )
            command = CommandEvidence(
                argv=argv,
                started_utc="2026-10-19T00:00:00+00:00",
                returncode=0,
            )
        elif name == "netlist":
            (output / "netlist.xml").write_text("<export/>", encoding="utf-8")
            command = CommandEvidence(
                argv=argv,
                started_utc="2026-10-19T00:00:00+00:00",
                returncode=0,
            )
        else:
            raise AssertionError(f"Unexpected validation command: {name}")
        if name == "native-command":
            (output / f"{name}.command.json").write_text(
                command.model_dump_json(indent=2), encoding="utf-8"
            )
        return command

    monkeypatch.setattr("kicad_tooling.validate.load_config", lambda *_args: config)
    monkeypatch.setattr("kicad_tooling.validate.cli_executable", lambda _cli: "fake-kicad-cli")
    monkeypatch.setattr("kicad_tooling.validate.execute", execute)
    monkeypatch.setattr("kicad_tooling.validate.hashes", lambda *_args: source_hashes)
    monkeypatch.setattr("kicad_tooling.validate.check_netlist", lambda *_args: None)
    monkeypatch.setattr(
        "kicad_tooling.hwrepo.product.check_project_netlist",
        lambda *_args: NetlistIdentityReport(status="PASS"),
    )
    monkeypatch.setattr(
        "kicad_tooling.hwrepo.product.check",
        lambda *_args, **_kwargs: SimpleNamespace(status="PASS", issues=()),
    )
    monkeypatch.setattr(
        "kicad_tooling.hwrepo.repository.check_repository",
        lambda *_args: SimpleNamespace(status="PASS", issues=()),
    )
    monkeypatch.setattr(
        "kicad_tooling.lint_registry.lint", lambda *_args: SimpleNamespace(status="PASS", issues=())
    )
    monkeypatch.setattr("kicad_tooling.validate.toolchain", lambda *_args: config)
    monkeypatch.setattr("kicad_tooling.validate.require_cli_profile", lambda *_args: None)

    result = validate(
        root,
        root / "build/native/fixture",
        "fake-kicad-cli",
        Path("projects/fixture/project.json"),
    )

    assert "drc_rule_compilation" in result.checks, {
        name: (check.status, check.error) for name, check in result.checks.items()
    }
    check = result.checks["drc_rule_compilation"]
    assert result.status == expected_status
    assert check.status == expected_status
    assert check.findings == int(emit_sentinel)
    assert check.source_hashes[rules_relative] == source_hashes[rules_relative]
    if not emit_sentinel:
        assert "terminal sentinel rule" in (check.error or "")
