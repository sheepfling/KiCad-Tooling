"""Regression coverage for numbered returns on multiple USB and serial ports."""

from __future__ import annotations

import hashlib

import pytest

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.models import DesignLintPolicy, DesignLintReport, NetlistContract
from tests.design_lint_fixtures import coach

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.interface_lint,
    pytest.mark.return_path_lint,
]

RULE_ID = "net.numbered_returns"


def _report(netlist: NetlistContract) -> DesignLintReport:
    digest = hashlib.sha256(netlist.model_dump_json().encode("utf-8")).hexdigest()
    return evaluate(
        "synthetic-multi-port-return-review",
        coach(netlist, digest),
        DesignLintPolicy(),
    )


def test_usb_and_serial_port_returns_are_grouped_by_protocol_stem() -> None:
    netlist = NetlistContract(
        components={},
        nets={
            "USB1_GND": ("J1.5",),
            "USB2_GND": ("J2.5",),
            "USB3_GND": ("J3.5",),
            "UART1_GND": ("J4.1",),
            "UART2_GND": ("J5.1",),
        },
    )

    report = _report(netlist)
    findings = [item for item in report.findings if item.rule_id == RULE_ID]

    assert report.status == "REVIEW"
    assert {item.subject: item.evidence for item in findings} == {
        "USB_GND": {
            "USB1_GND": ("J1.5",),
            "USB2_GND": ("J2.5",),
            "USB3_GND": ("J3.5",),
        },
        "UART_GND": {
            "UART1_GND": ("J4.1",),
            "UART2_GND": ("J5.1",),
        },
    }
    assert all("intentionally isolated" in item.message for item in findings)


def test_common_return_net_across_usb_and_serial_ports_is_a_valid_control() -> None:
    pins = ("J1.5", "J2.5", "J3.5", "J4.1", "J5.1")
    netlist = NetlistContract(
        components={},
        nets={"GND": pins},
        pin_functions={pin: "GND" for pin in pins},
    )

    report = _report(netlist)

    assert report.status == "PASS"
    assert not report.findings
