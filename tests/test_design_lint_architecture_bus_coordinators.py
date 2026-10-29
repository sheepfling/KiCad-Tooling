"""Guard small bus and peer-candidate dispatch coordinators."""

from __future__ import annotations

import ast
import inspect

import pytest

from kicad_tooling.hwrepo import (
    design_lint_candidate_aggregation,
    design_lint_evaluator,
    design_lint_peer_candidates,
    digital_peer_voltage_types,
)
from kicad_tooling.hwrepo.design_lint_bus_inputs import BusCandidateInputs
from tests.lint_architecture_support import (
    FACADE_MAX_LINES,
    HWREPO,
    IMPLEMENTATION_MAX_LINES,
    line_count,
)

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
        "design_lint_i2c_pullup_candidates.py",
        "design_lint_spi_candidates.py",
        "design_lint_unconnected_interface_candidates.py",
        "design_lint_can_candidates.py",
        "design_lint_rs485_candidates.py",
        "design_lint_signal_pair_candidates.py",
        "design_lint_interfaces_usb_data_polarity.py",
        "design_lint_two_wire_signal_candidates.py",
        "design_lint_bus_named_rail_candidates.py",
        "design_lint_serial_signal_candidates.py",
        "design_lint_spi_signal_candidates.py",
        "design_lint_bus_named_rail_candidates.py",
    )

    assert line_count(facade) < FACADE_MAX_LINES
    assert all((HWREPO / name).is_file() for name in modules)
    grouped_candidates = tuple(
        HWREPO / name
        for name in (
            "design_lint_two_wire_signal_candidates.py",
            "design_lint_serial_signal_candidates.py",
            "design_lint_spi_signal_candidates.py",
        )
    )
    assert all(line_count(path) < FACADE_MAX_LINES for path in grouped_candidates)

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
        "i2c_pullup_theme_candidates",
        "i2c_peer_reference_candidates",
        "two_wire_signal_candidates",
        "serial_signal_candidates",
        "spi_peer_reference_candidates",
        "spi_bias_candidates",
        "spi_signal_candidates",
        "unconnected_interface_candidates",
        "can_candidates",
        "rs485_candidates",
        "ethernet_data_label_mismatch_candidates",
        "ethernet_management_label_mismatch_candidates",
        "ethernet_unconnected_pin_candidates",
        "bus_named_rail_candidates",
        "complementary_signal_candidates",
        "usb_data_polarity_label_candidates",
        "usb_c_superspeed_lane_label_mismatch_candidates",
        "usb_data_same_net_candidates",
        "usb_c_same_net_candidates",
        "crossed_usb_c_cc_endpoint_candidates",
        "usb_c_sbu_same_net_candidates",
        "named_differential_pair_candidates",
        "i2c_address_theme_candidates",
    ]
    assert not candidate_constructions, "Bus dispatch should not construct lint findings."

    named_rail_tree = ast.parse(
        (HWREPO / "design_lint_bus_named_rail_candidates.py").read_text(encoding="utf-8")
    )
    named_rail_function = next(
        node
        for node in named_rail_tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "bus_named_rail_candidates"
    )
    named_rail_calls = sorted(
        (node.lineno, node.func.id)
        for node in ast.walk(named_rail_function)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    )
    assert [name for _, name in named_rail_calls] == [
        "ethernet_management_signal_on_named_rail_candidates",
        "ethernet_signal_on_named_rail_candidates",
        "usb_signal_on_named_rail_candidates",
        "usb_c_cc_signal_on_named_rail_candidates",
        "usb_c_sbu_signal_on_named_rail_candidates",
    ]


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


def test_i2c_pullup_typed_boundary_has_one_theme_owner() -> None:
    typed_inputs = HWREPO / "i2c_pullup_inputs.py"
    typed_service = HWREPO / "design_lint_i2c_pullup_candidates.py"
    legacy_adapter = HWREPO / "design_lint_i2c_candidates.py"

    assert line_count(typed_inputs) < IMPLEMENTATION_MAX_LINES
    assert line_count(typed_service) < IMPLEMENTATION_MAX_LINES
    input_tree = ast.parse(typed_inputs.read_text(encoding="utf-8"))
    assert any(
        isinstance(node, ast.ClassDef) and node.name == "I2cPullupSnifferInput"
        for node in input_tree.body
    )
    adapter_tree = ast.parse(legacy_adapter.read_text(encoding="utf-8"))
    adapter_imports = {
        node.module: {alias.name for alias in node.names}
        for node in adapter_tree.body
        if isinstance(node, ast.ImportFrom)
    }
    assert "I2cPullupSnifferInput" in adapter_imports["i2c_pullup_inputs"]


def test_i2c_address_input_replaces_separate_bus_arguments() -> None:
    typed_inputs = HWREPO / "i2c_address_inputs.py"
    bus_inputs = HWREPO / "design_lint_bus_inputs.py"
    aggregator = HWREPO / "design_lint_candidate_aggregation.py"
    facade = HWREPO / "design_lint_bus_candidates.py"

    assert line_count(typed_inputs) < IMPLEMENTATION_MAX_LINES
    assert line_count(bus_inputs) < IMPLEMENTATION_MAX_LINES
    input_tree = ast.parse(typed_inputs.read_text(encoding="utf-8"))
    assert any(
        isinstance(node, ast.ClassDef) and node.name == "I2cAddressCandidateInput"
        for node in input_tree.body
    )
    aggregator_tree = ast.parse(aggregator.read_text(encoding="utf-8"))
    bus_calls = (
        node
        for node in ast.walk(aggregator_tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "bus_candidates"
    )
    (bus_call,) = bus_calls
    assert len(bus_call.args) == 1
    route = bus_call.args[0]
    assert isinstance(route, ast.Call)
    assert isinstance(route.func, ast.Name) and route.func.id == "BusCandidateInputs"
    route_keywords = {keyword.arg for keyword in route.keywords}
    assert {"observed", "i2c_address", "i2c_pullup"} <= route_keywords
    assert "i2c_address_map" not in route_keywords
    assert "i2c_address_coverage" not in route_keywords
    assert "i2c_pullup_heuristic_coverage" not in route_keywords
    facade_tree = ast.parse(facade.read_text(encoding="utf-8"))
    bus_function = next(
        node
        for node in facade_tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "bus_candidates"
    )
    assert [argument.arg for argument in bus_function.args.args] == ["inputs"]
    assert not bus_function.args.kwonlyargs
    route_parameters = inspect.signature(BusCandidateInputs).parameters
    assert all(
        route_parameters[name].default is inspect.Parameter.empty
        for name in ("observed", "i2c_address", "i2c_pullup")
    )


def test_public_lint_compatibility_signatures_do_not_grow() -> None:
    candidate_parameters = inspect.signature(
        design_lint_candidate_aggregation.candidates
    ).parameters
    evaluator_parameters = inspect.signature(design_lint_evaluator.evaluate).parameters

    assert len(candidate_parameters) <= 49, (
        "Route new lint evidence through a typed theme input instead of widening "
        "the candidate compatibility API."
    )
    assert len(evaluator_parameters) <= 33, (
        "Route new lint evidence through prepared typed inputs instead of widening "
        "the evaluator compatibility API."
    )
