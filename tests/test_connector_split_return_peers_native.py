"""Exact-version native regressions for split returns on repeated DB9 peers."""

from __future__ import annotations

import hashlib
import os
import shutil
from pathlib import Path

import pytest

from kicad_tooling.hwrepo.command_evidence_models import CommandEvidence
from kicad_tooling.hwrepo.contract_coach_models import ContractCoachReport
from kicad_tooling.hwrepo.contracts import write_model
from kicad_tooling.hwrepo.design_lint_evaluator import evaluate
from kicad_tooling.hwrepo.design_lint_policy_models import DesignLintPolicy
from kicad_tooling.hwrepo.design_lint_report_models import DesignLintReport
from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.netlist_contract_models import NetlistContract
from kicad_tooling.validate import read_netlist
from tests.native_kicad_support import execute_kicad_cli
from tests.synthetic_design_lint_project import PINNED_NATIVE_KICAD_IMAGES

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.connector_lint,
    pytest.mark.return_path_lint,
    pytest.mark.native_kicad,
    pytest.mark.slow,
    pytest.mark.skipif(
        os.environ.get("KICAD_RUN_NATIVE_CONNECTOR_FIXTURES") != "1",
        reason="native connector fixtures run in the digest-pinned package acceptance lane",
    ),
]

RULE_ID = "connector.peer_pin_assignment_divergence"
FIXTURES = Path(__file__).parent / "fixtures/design_lint/db9-peer-return-native"
EXPECTED_SOURCE_HASHES = {
    "fault.kicad_sch": "0820a52afb270ec2380b64e645fb0b2ed855c656707c0325155ca9dba0fc525d",
    "control.kicad_sch": "0e5da68212518ba76a7643c19e339a540e759baff16c43193c37a6d428389122",
}


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
            home_directory=f"db9-peer-return-{version}-{case}-{run}-{name}",
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


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
@pytest.mark.parametrize("kicad_version", tuple(PINNED_NATIVE_KICAD_IMAGES))
def test_native_four_peer_db9_split_returns_review_and_common_returns_clear(
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
        home_directory=f"db9-peer-return-version-{kicad_version}",
    )
    assert version_command.returncode == 0
    assert version_command.stdout.strip() == kicad_version

    reports: dict[str, DesignLintReport] = {}
    for case in ("fault", "control"):
        fixture_name = f"{case}.kicad_sch"
        fixture = FIXTURES / fixture_name
        source_hash = hashlib.sha256(fixture.read_bytes()).hexdigest()
        assert source_hash == EXPECTED_SOURCE_HASHES[fixture_name]
        source = fixture_dir / fixture_name
        shutil.copyfile(fixture, source)

        first_netlist, first_hash = _export_netlist(
            image=image,
            version=kicad_version,
            work=work,
            source=source,
            output=output_dir / f"{case}.first.netlist.xml",
            case=case,
            run="first",
        )
        repeat_netlist, repeat_hash = _export_netlist(
            image=image,
            version=kicad_version,
            work=work,
            source=source,
            output=output_dir / f"{case}.repeat.netlist.xml",
            case=case,
            run="repeat",
        )
        assert first_netlist == repeat_netlist
        assert len(repeat_hash) == 64
        project_id = f"synthetic-db9-peer-return-{case}-{kicad_version}"
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
    assert {item.subject for item in fault_findings} == {
        "Connector:DB9_ReturnPair pin 7",
        "Connector:DB9_ReturnPair pin 9",
    }
    for pin in ("7", "9"):
        finding = next(item for item in fault_findings if item.subject.endswith(f"pin {pin}"))
        assert {
            reference: finding.evidence[f"{reference}.{pin}"]
            for reference in ("J1", "J2", "J3", "J4")
        } == {f"J{index}": (f"SYNTHETIC_PEER_PIN_{pin}_PORT_{index}",) for index in range(1, 5)}
        assert "does not establish a required connection" in finding.message

    control = reports["control"]
    assert control.status == "PASS"
    assert not any(item.rule_id == RULE_ID for item in control.findings)
