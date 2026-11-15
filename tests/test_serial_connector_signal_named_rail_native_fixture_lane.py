"""Exact-version native exports for connector-only serial rail review."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

import pytest

from kicad_tooling.ci_hosted_support import normalized_netlist_bytes
from kicad_tooling.hwrepo.contract_coach_models import ContractCoachReport
from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.design_lint_policy_models import DesignLintPolicy
from kicad_tooling.hwrepo.design_lint_report_models import DesignLintReport
from kicad_tooling.validate import read_netlist
from tests.native_kicad_support import execute_kicad_cli
from tests.synthetic_design_lint_project import PINNED_NATIVE_KICAD_IMAGES

RULE_ID = "bus.serial_signal_on_named_rail"
FIXTURES = Path(__file__).parent / "fixtures/design_lint/serial-connector-signal-named-rail-native"
SOURCE_HASHES = {
    "control.kicad_sch": "a02c6e00f6721090b998eb0d4d38d049580e6f71246353cef054435950a4c746",
    "fault.kicad_sch": "5c4ec3e6844ca51f105dba9a5e3b422fdbecf0a7846cdfbd89ed328f6b99b0ad",
    "cts-control.kicad_sch": "73553713739249d27755c3bc1040b11ebdbe553b262af58f4a810a0e6bb24be2",
    "cts-fault.kicad_sch": "5019a069d0bafc353c8a48894a9053479dacc3129347984727d6682074efe6ac",
    "rts-control.kicad_sch": "32574617203027bca3e234317e74740746bdf4323ed64e86dc46ed79e182cd7f",
    "rts-fault.kicad_sch": "e65817db762a1aac10574ef55c913bdcbd648939cc246c987419895daf761b6d",
    "modem-control.kicad_sch": "888bd9424b3d20155da4d55eafcdd21997e1fbebfbe2a57f9897d83b7114aa67",
    "modem-fault.kicad_sch": "945d2e06455cf2616e4adb999d5a8d394a19ac0317f351b1ede2f916eb3c7645",
}
CASES = {
    "fault": (("J1.1", "UART1_RX", "GND_C", "J1.1: UART1_RX on return-like net GND_C"),),
    "control": (("J1.1", "UART1_RX", "UART_TX", None),),
    "cts-fault": (("J1.1", "UART1_CTS", "GND_C", "J1.1: UART1_CTS on return-like net GND_C"),),
    "cts-control": (("J1.1", "UART1_CTS", "UART_TX", None),),
    "rts-fault": (("J1.2", "UART1_RTS", "+3V3", "J1.2: UART1_RTS on supply-like net +3V3"),),
    "rts-control": (("J1.2", "UART1_RTS", "UART_RX", None),),
    "modem-fault": (
        ("J1.1", "DTR", "GND_MODEM_DTR", "J1.1: DTR on return-like net GND_MODEM_DTR"),
        ("J1.2", "DSR", "+3V3", "J1.2: DSR on supply-like net +3V3"),
        ("J1.3", "DCD", "GND_MODEM_DCD", "J1.3: DCD on return-like net GND_MODEM_DCD"),
        ("J1.4", "RI", "+5V", "J1.4: RI on supply-like net +5V"),
    ),
    "modem-control": (
        ("J1.1", "DTR", "MODEM_DTR", None),
        ("J1.2", "DSR", "MODEM_DSR", None),
        ("J1.3", "DCD", "MODEM_DCD", None),
        ("J1.4", "RI", "MODEM_RI", None),
    ),
}

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.interface_lint,
    pytest.mark.native_kicad,
    pytest.mark.slow,
    pytest.mark.skipif(
        os.environ.get("KICAD_RUN_NATIVE_SERIAL_TX_RX_LABEL_MISMATCH_FIXTURES") != "1",
        reason="native serial named-rail fixtures run in the digest-pinned interface lane",
    ),
]


@pytest.mark.parametrize(("version", "image"), tuple(PINNED_NATIVE_KICAD_IMAGES.items()))
@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_native_connector_serial_named_rail_fault_and_control_repeat(
    tmp_path: Path,
    version: str,
    image: str,
) -> None:
    work = tmp_path / version.replace(".", "-")
    outputs = work / "outputs"
    outputs.mkdir(parents=True)
    version_command = execute_kicad_cli(
        image,
        ("kicad-cli", "version"),
        work,
        home_directory=f"serial-connector-named-rail-version-{version}",
    )
    assert version_command.returncode == 0
    assert version_command.stdout.strip() == version

    for filename, expected_sha256 in SOURCE_HASHES.items():
        case = filename.removesuffix(".kicad_sch")
        source = FIXTURES / filename
        assert hashlib.sha256(source.read_bytes()).hexdigest() == expected_sha256
        exports = []
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
                    str(source),
                ),
                work,
                home_directory=f"serial-connector-named-rail-{version}-{case}-{repeat}",
                fixture_directory=FIXTURES,
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
        expected_cases = CASES[case]
        for pin, function, expected_net, _expected_subject in expected_cases:
            assert observed.pin_functions[pin] == function
            assigned_net = next(net for net, pins in observed.nets.items() if pin in pins)
            assert assigned_net == expected_net

        project_id = f"synthetic-serial-connector-named-rail-{case}-{version}"
        report: DesignLintReport = evaluate(
            project_id,
            ContractCoachReport(
                status="READY_FOR_REVIEW",
                project_id=project_id,
                observed=observed,
                netlist_sha256=netlist_sha256,
            ),
            DesignLintPolicy(),
        )
        findings = tuple(item for item in report.findings if item.rule_id == RULE_ID)
        expected_findings = {
            pin: (function, expected_net, subject)
            for pin, function, expected_net, subject in expected_cases
            if subject is not None
        }
        actual_findings = {item.evidence["pin"][0]: item for item in findings}
        assert actual_findings.keys() == expected_findings.keys()
        for pin, (function, expected_net, expected_subject) in expected_findings.items():
            finding = actual_findings[pin]
            assert finding.subject == expected_subject
            assert finding.evidence["pin_function"] == (function,)
            assert finding.evidence["assigned_net"] == (expected_net,)
            assert finding.evidence["component_pin_inventory"] == ("1", "2", "3", "4")
        if expected_findings:
            assert report.status == "REVIEW"
        else:
            assert not findings
