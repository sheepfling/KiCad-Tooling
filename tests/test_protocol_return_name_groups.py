"""Bound compact protocol-prefix matching in the numbered-return review."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping

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


def _report(nets: Mapping[str, tuple[str, ...]]) -> DesignLintReport:
    pin_functions = {pin: "GND" for pins in nets.values() for pin in pins}
    observed = NetlistContract(components={}, nets=nets, pin_functions=pin_functions)
    digest = hashlib.sha256(observed.model_dump_json().encode("utf-8")).hexdigest()
    return evaluate(
        "synthetic-compact-protocol-returns",
        coach(observed, digest),
        DesignLintPolicy(),
    )


def test_compact_can_i2c_and_spi_return_families_are_reviewed_separately() -> None:
    report = _report(
        {
            "CAN1_GND": ("J1.1",),
            "CAN2_GND": ("J2.1",),
            "I2C1_0V": ("J3.1",),
            "I2C2_0V": ("J4.1",),
            "SPI1_RET": ("J5.1",),
            "SPI2_RET": ("J6.1",),
        }
    )
    findings = [item for item in report.findings if item.rule_id == RULE_ID]

    assert report.status == "REVIEW"
    assert {item.subject: item.evidence for item in findings} == {
        "CAN_GND": {"CAN1_GND": ("J1.1",), "CAN2_GND": ("J2.1",)},
        "I2C_0V": {"I2C1_0V": ("J3.1",), "I2C2_0V": ("J4.1",)},
        "SPI_RET": {"SPI1_RET": ("J5.1",), "SPI2_RET": ("J6.1",)},
    }


def test_common_protocol_return_nets_are_a_valid_control() -> None:
    report = _report(
        {
            "CAN_GND": ("J1.1", "J2.1"),
            "I2C_0V": ("J3.1", "J4.1"),
            "SPI_RET": ("J5.1", "J6.1"),
        }
    )

    assert report.status == "PASS"
    assert not report.findings


def test_unrecognized_compact_prefix_is_not_grouped_as_a_protocol_return() -> None:
    report = _report({"CPU1_GND": ("J1.1",), "CPU2_GND": ("J2.1",)})

    assert report.status == "PASS"
    assert not report.findings
