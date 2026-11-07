"""Cross-process stability for protocol connector-return review reports."""

from __future__ import annotations

import pytest

from tests.design_lint_fixtures.hashseed_reports import hashseed_probe_reports
from tests.json_types import JsonObject

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.slow,
    pytest.mark.connector_lint,
    pytest.mark.interface_lint,
    pytest.mark.return_path_lint,
]

_RULES = {
    "serial": "connector.serial_pair_without_return_review",
    "i2c": "connector.i2c_pair_without_return_review",
    "i3c": "connector.i3c_pair_without_return_review",
    "swd": "connector.swd_pair_without_return_review",
    "can": "connector.can_pair_without_return_review",
    "rs485": "connector.rs485_pair_without_return_review",
    "usb2": "connector.usb2_pair_without_return_review",
    "usb_superspeed": "connector.usb_superspeed_pair_without_return_review",
    "spi": "connector.spi_triad_without_return_review",
}


def _finding_rule_ids(report: JsonObject) -> set[str]:
    return {str(finding["rule_id"]) for finding in report["findings"]}


def _assert_protocol_reports(protocol: str) -> None:
    reports = hashseed_probe_reports(families=("connector_return_protocols",))
    fault = reports[f"{protocol}_connector_return_fault"]
    control = reports[f"{protocol}_connector_return_control"]
    rule_id = _RULES[protocol]

    assert fault != control
    assert rule_id in _finding_rule_ids(fault)
    assert rule_id not in _finding_rule_ids(control)


@pytest.mark.design_lint_rule(rule_id="connector.serial_pair_without_return_review")
def test_serial_connector_return_reports_are_stable_across_hash_seeds() -> None:
    _assert_protocol_reports("serial")


@pytest.mark.design_lint_rule(rule_id="connector.i2c_pair_without_return_review")
def test_i2c_connector_return_reports_are_stable_across_hash_seeds() -> None:
    _assert_protocol_reports("i2c")


@pytest.mark.design_lint_rule(rule_id="connector.i3c_pair_without_return_review")
def test_i3c_connector_return_reports_are_stable_across_hash_seeds() -> None:
    _assert_protocol_reports("i3c")


@pytest.mark.design_lint_rule(rule_id="connector.swd_pair_without_return_review")
def test_swd_connector_return_reports_are_stable_across_hash_seeds() -> None:
    _assert_protocol_reports("swd")


@pytest.mark.design_lint_rule(rule_id="connector.can_pair_without_return_review")
def test_can_connector_return_reports_are_stable_across_hash_seeds() -> None:
    _assert_protocol_reports("can")


@pytest.mark.design_lint_rule(rule_id="connector.rs485_pair_without_return_review")
def test_rs485_connector_return_reports_are_stable_across_hash_seeds() -> None:
    _assert_protocol_reports("rs485")


@pytest.mark.design_lint_rule(rule_id="connector.usb2_pair_without_return_review")
def test_usb2_connector_return_reports_are_stable_across_hash_seeds() -> None:
    _assert_protocol_reports("usb2")


@pytest.mark.design_lint_rule(rule_id="connector.usb_superspeed_pair_without_return_review")
def test_usb_superspeed_connector_return_reports_are_stable_across_hash_seeds() -> None:
    _assert_protocol_reports("usb_superspeed")


@pytest.mark.design_lint_rule(rule_id="connector.spi_triad_without_return_review")
def test_spi_connector_return_reports_are_stable_across_hash_seeds() -> None:
    _assert_protocol_reports("spi")
