"""Keep protocol lint tags connected to their exact-native fault/control cases."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.design_lint_catalog import rule_catalog

pytestmark = [pytest.mark.design_lint, pytest.mark.catalog_lint, pytest.mark.architecture]

_PROTOCOL_NATIVE_CASES = (
    pytest.param(
        "bus.i2c_peer_reference_review",
        "KICAD_RUN_NATIVE_I2C_PEER_REFERENCE_FIXTURES",
        "tests.test_i2c_peer_reference_native_fixture_lane."
        "test_native_i2c_peer_reference_fault_and_control_on_supported_images",
        id="i2c-peer-reference",
    ),
    pytest.param(
        "bus.spi_peer_reference_review",
        "KICAD_RUN_NATIVE_SPI_PEER_REFERENCE_FIXTURES",
        "tests.test_spi_peer_reference_native_fixture_lane."
        "test_native_spi_peer_reference_fault_and_control_on_supported_images",
        id="spi-peer-reference",
    ),
    pytest.param(
        "bus.can_peer_reference_review",
        "KICAD_RUN_NATIVE_CAN_PEER_REFERENCE_FIXTURES",
        "tests.test_can_native_fixture_lanes.test_native_can_peer_reference_fault_and_control",
        id="can-peer-reference",
    ),
    pytest.param(
        "bus.can_peer_assignment_divergence",
        "KICAD_RUN_NATIVE_CAN_PEER_FIXTURES",
        "tests.test_can_native_fixture_lanes.test_native_can_peer_assignment_fault_and_control",
        id="can-peer-assignment",
    ),
)


@pytest.mark.parametrize(("rule_id", "native_fixture", "native_test"), _PROTOCOL_NATIVE_CASES)
def test_protocol_rule_tags_select_native_fault_control_cases(
    rule_id: str, native_fixture: str, native_test: str
) -> None:
    rule = next(entry for entry in rule_catalog().rules if entry.rule_id == rule_id)

    assert native_fixture in rule.required_native_fixtures
    assert native_test in rule.fault_fixtures
    assert native_test in rule.valid_control_fixtures
