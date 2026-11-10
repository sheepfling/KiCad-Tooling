"""Exact-version native regressions for named mapped signals on rail labels."""

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

RULE_ID = "connector.mapped_interface_signal_on_named_rail"
PROJECT_ID = "synthetic-mapped-named-signal-rail"
FIXTURES = Path(__file__).parent / "fixtures/design_lint/mapped-named-signal-rail-native"
EXPECTED_SOURCE_HASHES = {
    "fault.kicad_sch": "7300c5b82f3fbe1f07f0364aa96506a8b65cbd885dd29f075adfc6904f41a63c",
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
def test_native_named_mapped_signal_rail_fault_and_control_repeat(
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
        home_directory=f"mapped-named-signal-rail-version-{version}",
    )
    assert version_command.returncode == 0
    assert version_command.stdout.strip() == version

    for case in ("fault", "control"):
        filename = f"{case}.kicad_sch"
        source = FIXTURES / filename
        assert hashlib.sha256(source.read_bytes()).hexdigest() == EXPECTED_SOURCE_HASHES[filename]
        mounted_source = fixtures / filename
        shutil.copyfile(source, mounted_source)
        exports: list[tuple[NetlistContract, str]] = []
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
                home_directory=f"mapped-named-signal-rail-{version}-{case}-{repeat}",
                fixture_directory=fixtures,
                output_directory=outputs,
            )
            assert command.returncode == 0, command.model_dump_json(indent=2)
            assert output.is_file()
            observed = read_netlist(output)
            exports.append(
                (
                    observed,
                    hashlib.sha256(normalized_netlist_bytes(observed)).hexdigest(),
                )
            )

        first, repeated = exports
        assert first[0] == repeated[0]
        assert first[1] == repeated[1]
        observed = first[0]
        assert observed.pin_functions["J1.2"] == "PWM_SYNC"
        expected_net = "GND" if case == "fault" else "PWM_SYNC"
        assert "J1.2" in observed.nets[expected_net]
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
                netlist_sha256=hashlib.sha256(normalized_netlist_bytes(observed)).hexdigest(),
            ),
            DesignLintPolicy(),
            connector_coverage=coverage,
        )
        findings = tuple(item for item in report.findings if item.rule_id == RULE_ID)
        if case == "fault":
            assert len(findings) == 1
            assert findings[0].evidence["interface_signal"] == ("PWM_SYNC",)
            assert findings[0].evidence["native_pin_function"] == ("PWM_SYNC",)
            assert findings[0].evidence["assigned_nets"] == ("GND",)
        else:
            assert not findings
