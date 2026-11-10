"""Exact-version native regressions for named mapped signal contacts."""

from __future__ import annotations

import hashlib
import os
import shutil
from pathlib import Path

import pytest

from kicad_tooling.ci_hosted_support import normalized_netlist_bytes
from kicad_tooling.hwrepo.contract_coach_models import ContractCoachReport
from kicad_tooling.hwrepo.design_lint_evaluator import evaluate
from kicad_tooling.hwrepo.design_lint_policy_models import DesignLintPolicy
from kicad_tooling.hwrepo.design_lint_report_models import DesignLintReport
from kicad_tooling.hwrepo.netlist_contract_models import NetlistContract
from kicad_tooling.validate import read_netlist
from tests.connector_mapped_interface_support import interface_coverage
from tests.native_kicad_support import execute_kicad_cli
from tests.synthetic_design_lint_project import PINNED_NATIVE_KICAD_IMAGES

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.connector_lint,
    pytest.mark.interface_lint,
]

RULE_ID = "connector.mapped_interface_signal_unassigned"
PROJECT_ID = "synthetic-mapped-named-signal"
FIXTURES = Path(__file__).parent / "fixtures/design_lint/mapped-named-signal-native"
EXPECTED_SOURCE_HASHES = {
    "fault.kicad_sch": "172d10ace020dfb0fcbff975d68fedf6e43eee5f31b9fb0701c4c25f336d67ad",
    "control.kicad_sch": "08ecca570767c4b289bbc671a94566ed36ac7b31e0fb482eae7313d99653cb32",
}


@pytest.mark.native_kicad
@pytest.mark.slow
@pytest.mark.design_lint_rule(rule_id=RULE_ID)
@pytest.mark.skipif(
    os.environ.get("KICAD_RUN_NATIVE_CONNECTOR_FIXTURES") != "1",
    reason="digest-pinned native connector fixtures run in package acceptance",
)
@pytest.mark.parametrize("version", tuple(PINNED_NATIVE_KICAD_IMAGES))
def test_native_named_mapped_signal_fault_and_control_repeat(
    tmp_path: Path,
    version: str,
) -> None:
    image = PINNED_NATIVE_KICAD_IMAGES[version]
    work = tmp_path / version.replace(".", "-")
    fixtures = work / "fixtures"
    outputs = work / "outputs"
    fixtures.mkdir(parents=True)
    outputs.mkdir()
    version_command = execute_kicad_cli(
        image,
        ("kicad-cli", "version"),
        work,
        home_directory=f"mapped-named-signal-version-{version}",
    )
    assert version_command.returncode == 0
    assert version_command.stdout.strip() == version

    for case in ("fault", "control"):
        filename = f"{case}.kicad_sch"
        source = FIXTURES / filename
        assert hashlib.sha256(source.read_bytes()).hexdigest() == EXPECTED_SOURCE_HASHES[filename]
        mounted_source = fixtures / filename
        shutil.copyfile(source, mounted_source)
        exports: list[tuple[NetlistContract, str, str]] = []
        for repeat in ("first", "repeat"):
            output = outputs / f"{case}-{repeat}.netlist.xml"
            command = execute_kicad_cli(
                image,
                (
                    "kicad-cli",
                    "sch",
                    "export",
                    "netlist",
                    "--format",
                    "kicadxml",
                    "--output",
                    str(output),
                    str(mounted_source),
                ),
                work,
                home_directory=f"mapped-named-signal-{version}-{case}-{repeat}",
                fixture_directory=fixtures,
                output_directory=outputs,
            )
            assert command.returncode == 0, command.model_dump_json(indent=2)
            assert output.is_file()
            observed = read_netlist(output)
            exports.append(
                (
                    observed,
                    hashlib.sha256(output.read_bytes()).hexdigest(),
                    hashlib.sha256(normalized_netlist_bytes(observed)).hexdigest(),
                )
            )

        first, repeated = exports
        assert first[0] == repeated[0]
        assert first[2] == repeated[2]
        observed, netlist_sha256, _normalized_sha256 = first
        assert observed.pin_functions["J1.2"] == "PWM_SYNC"
        coverage = interface_coverage(
            observed,
            pin_numbers=("1", "2"),
            target_signal="PWM_SYNC",
        )
        assert coverage.status == "COMPLETE"
        report: DesignLintReport = evaluate(
            PROJECT_ID,
            ContractCoachReport(
                status="READY_FOR_REVIEW",
                project_id=PROJECT_ID,
                observed=observed,
                netlist_sha256=netlist_sha256,
            ),
            DesignLintPolicy(),
            connector_coverage=coverage,
        )
        findings = tuple(item for item in report.findings if item.rule_id == RULE_ID)
        if case == "fault":
            assert len(findings) == 1
            assert findings[0].evidence["interface_signal"] == ("PWM_SYNC",)
            assert findings[0].evidence["native_pin_function"] == ("PWM_SYNC",)
            assert findings[0].evidence["assigned_nets"] == ()
        else:
            assert not findings
