"""Guard small bus and peer-candidate dispatch coordinators."""

from __future__ import annotations

import ast

import pytest

from kicad_tooling.hwrepo import design_lint_peer_candidates, digital_peer_voltage_types
from tests.lint_architecture_support import FACADE_MAX_LINES, HWREPO, line_count

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.interface_lint,
    pytest.mark.architecture,
]


def test_peer_candidate_coordinator_delegates_by_protocol() -> None:
    facade = HWREPO / "design_lint_peer_candidates.py"
    modules = (
        "design_lint_serial_peer_candidates.py",
        "design_lint_usb_peer_candidates.py",
        "design_lint_spi_peer_candidates.py",
        "design_lint_digital_peer_voltage_candidates.py",
        "design_lint_usb_c_candidates.py",
    )

    assert line_count(facade) < FACADE_MAX_LINES
    assert all((HWREPO / name).is_file() for name in modules)

    tree = ast.parse(facade.read_text(encoding="utf-8"), filename=facade.name)
    calls = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    candidate_constructions = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "Candidate"
    ]

    assert {
        "serial_unmapped_peer_candidates",
        "serial_reference_candidates",
        "usb_peer_reference_candidates",
        "spi_participant_candidates",
        "digital_peer_voltage_candidates",
        "usb_c_port_candidates",
    } <= calls
    assert not candidate_constructions, "Peer dispatch should not construct lint findings."
    assert (
        design_lint_peer_candidates.DigitalPeerVoltageLintContext
        is digital_peer_voltage_types.DigitalPeerVoltageLintContext
    )


def test_bus_candidate_coordinator_delegates_by_theme_in_stable_order() -> None:
    facade = HWREPO / "design_lint_bus_candidates.py"
    modules = (
        "design_lint_i2c_candidates.py",
        "design_lint_spi_candidates.py",
        "design_lint_unconnected_interface_candidates.py",
        "design_lint_can_candidates.py",
        "design_lint_rs485_candidates.py",
        "design_lint_signal_pair_candidates.py",
        "design_lint_interfaces_usb_data_polarity.py",
    )

    assert line_count(facade) < FACADE_MAX_LINES
    assert all((HWREPO / name).is_file() for name in modules)

    tree = ast.parse(facade.read_text(encoding="utf-8"), filename=facade.name)
    function = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "bus_candidates"
    )
    calls = sorted(
        (node.lineno, node.func.id)
        for node in ast.walk(function)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    )
    candidate_constructions = [
        node
        for node in ast.walk(function)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "Candidate"
    ]

    assert [name for _, name in calls] == [
        "i2c_pullup_candidates",
        "i2c_peer_reference_candidates",
        "i2c_signal_label_role_candidates",
        "i2c_sda_scl_same_net_candidates",
        "serial_tx_rx_same_net_candidates",
        "serial_tx_output_sharing_candidates",
        "spi_peer_reference_candidates",
        "spi_bias_candidates",
        "spi_data_polarity_label_candidates",
        "spi_clock_select_label_mismatch_candidates",
        "spi_data_input_output_same_net_candidates",
        "spi_clock_control_data_same_net_candidates",
        "spi_clock_chip_select_same_net_candidates",
        "spi_chip_select_inputs_share_net_candidates",
        "spi_data_outputs_share_net_candidates",
        "unconnected_interface_candidates",
        "can_candidates",
        "rs485_peer_reference_candidates",
        "complementary_signal_candidates",
        "usb_data_polarity_label_candidates",
        "named_differential_pair_candidates",
        "i2c_address_candidates",
        "i2c_responder_coverage_candidates",
    ]
    assert not candidate_constructions, "Bus dispatch should not construct lint findings."


def test_control_and_digital_peer_rule_refs_point_to_their_owners() -> None:
    catalog = HWREPO / "design-lint-rules.json"
    text = catalog.read_text(encoding="utf-8")

    assert "kicad_tooling/hwrepo/control_inputs.py#" not in text
    assert "kicad_tooling/hwrepo/control_input_inventory.py#unconnected_control_inputs" in text
    assert (
        "kicad_tooling/hwrepo/control_input_bias.py#control_input_bias_heuristic_coverage" in text
    )
    assert "kicad_tooling/hwrepo/digital_peer_voltage_review.py#" not in text
    assert (
        "kicad_tooling/hwrepo/digital_peer_voltage_scan.py#unmapped_spi_peer_voltage_reviews"
        in text
    )
    assert (
        "kicad_tooling/hwrepo/digital_peer_voltage_scan.py#unmapped_serial_peer_voltage_reviews"
        in text
    )
