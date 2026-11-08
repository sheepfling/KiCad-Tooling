"""Exact-version KiCad exports for the generic I3C connector review."""

from __future__ import annotations

import hashlib
import os
import shutil
from pathlib import Path

import pytest

from kicad_tooling.hwrepo.command_evidence_models import CommandEvidence
from kicad_tooling.hwrepo.contract_coach_models import ContractCoachReport
from kicad_tooling.hwrepo.contracts import write_model
from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.design_lint_policy_models import DesignLintPolicy
from kicad_tooling.hwrepo.design_lint_report_models import DesignLintReport
from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.netlist_contract_models import NetlistContract
from kicad_tooling.validate import read_netlist
from tests.i3c_generic_connector_fixture_support import (
    I3C_GENERIC_CONNECTOR_SOURCE_HASHES,
    i3c_generic_connector_fixture_sources,
)
from tests.native_kicad_support import execute_kicad_cli
from tests.synthetic_design_lint_project import PINNED_NATIVE_KICAD_IMAGES

RULE_ID = "bus.i3c_generic_connector_pair_review"

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.interface_lint,
    pytest.mark.native_kicad,
    pytest.mark.slow,
    pytest.mark.skipif(
        os.environ.get("KICAD_RUN_NATIVE_I3C_GENERIC_CONNECTOR_FIXTURES") != "1",
        reason="native I3C connector fixtures run in the digest-pinned interface lane",
    ),
]


def _export_netlist(
    *,
    image: str,
    version: str,
    work: Path,
    source: Path,
    output: Path,
    case: str,
    run: str,
) -> tuple[NetlistContract, str]:
    command_output = output.parent / "commands"
    command_output.mkdir(parents=True, exist_ok=True)

    def execute(
        argv: tuple[str, ...],
        command_work: Path,
        retained: Path,
        name: str,
    ) -> CommandEvidence:
        result = execute_kicad_cli(
            image,
            argv,
            command_work,
            home_directory=f"i3c-generic-connector-{version}-{case}-{run}-{name}",
        )
        write_model(retained / f"{case}.{run}.{name}.command.json", result)
        return result

    command = execute(
        (
            "kicad-cli",
            "sch",
            "export",
            "netlist",
            "--format",
            "kicadxml",
            "--output",
            str(output),
            str(source),
        ),
        work,
        command_output,
        "netlist",
    )
    assert command.returncode == 0, command.model_dump_json(indent=2)
    assert output.is_file()
    return read_netlist(output), digest(output)


@pytest.mark.parametrize("kicad_version", tuple(PINNED_NATIVE_KICAD_IMAGES))
@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_native_generic_connector_fault_and_named_control(
    tmp_path: Path,
    kicad_version: str,
) -> None:
    image = PINNED_NATIVE_KICAD_IMAGES[kicad_version]
    work = tmp_path / "native-work"
    work.mkdir()
    fixture_dir = work / "fixtures"
    fixture_dir.mkdir()
    output_dir = work / "outputs"
    output_dir.mkdir()

    version_command = execute_kicad_cli(
        image,
        ("kicad-cli", "version"),
        work,
        home_directory=f"i3c-generic-connector-version-{kicad_version}",
    )
    assert version_command.returncode == 0
    assert version_command.stdout.strip() == kicad_version

    reports: dict[str, DesignLintReport] = {}
    for case, source_fixture in i3c_generic_connector_fixture_sources().items():
        fixture_name = source_fixture.name
        assert (
            hashlib.sha256(source_fixture.read_bytes()).hexdigest()
            == (I3C_GENERIC_CONNECTOR_SOURCE_HASHES[fixture_name])
        )
        source = fixture_dir / fixture_name
        shutil.copyfile(source_fixture, source)

        first_netlist, first_hash = _export_netlist(
            image=image,
            version=kicad_version,
            work=work,
            source=source,
            output=output_dir / f"{case}.first.netlist.xml",
            case=case,
            run="first",
        )
        repeated_netlist, repeated_hash = _export_netlist(
            image=image,
            version=kicad_version,
            work=work,
            source=source,
            output=output_dir / f"{case}.repeat.netlist.xml",
            case=case,
            run="repeat",
        )
        assert first_netlist == repeated_netlist
        assert len(repeated_hash) == 64
        project_id = f"synthetic-i3c-generic-connector-{case}-{kicad_version}"
        coach = ContractCoachReport(
            status="READY_FOR_REVIEW",
            project_id=project_id,
            observed=first_netlist,
            netlist_sha256=first_hash,
        )
        reports[case] = evaluate(project_id, coach, DesignLintPolicy())

    fault = reports["fault"]
    fault_findings = [item for item in fault.findings if item.rule_id == RULE_ID]
    assert fault.status == "REVIEW"
    assert len(fault.findings) == 1
    assert len(fault_findings) == 1
    assert fault_findings[0].subject == "J1: generic pins match I3C SDA/SCL bus nets"

    control = reports["control"]
    assert control.status == "PASS"
    assert not any(item.rule_id == RULE_ID for item in control.findings)
