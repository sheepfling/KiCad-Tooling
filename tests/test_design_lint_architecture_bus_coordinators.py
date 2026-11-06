"""Guard small bus and peer-candidate dispatch coordinators."""

from __future__ import annotations

import ast
import inspect
from typing import get_type_hints

import pytest

from kicad_tooling.hwrepo import (
    design_lint_candidate_aggregation,
    design_lint_evaluator,
    design_lint_peer_candidates,
    digital_peer_voltage_types,
)
from kicad_tooling.hwrepo.connector_pin_metadata import connector_pin_metadata_matches_inventory
from kicad_tooling.hwrepo.design_lint_bus_inputs import BusCandidateInputs
from kicad_tooling.hwrepo.design_lint_candidate_inputs import DesignLintCandidateInputs
from kicad_tooling.hwrepo.design_lint_component_candidates import (
    ComponentCandidateScanResult,
    ComponentTopologyCandidateInputs,
    scan_component_candidates,
)
from kicad_tooling.hwrepo.design_lint_mapped_coverage_candidates import (
    MappedCoverageCandidateInputs,
    MappedCoverageCandidateResult,
    scan_mapped_coverage_candidates,
)
from kicad_tooling.hwrepo.design_lint_mapped_topology_coverage import (
    mapped_topology_coverage_runs,
)
from kicad_tooling.hwrepo.design_lint_mapped_topology_results import (
    MappedTopologyFindingCounts,
)
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
        "design_lint_usb_peer_group_candidates.py",
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
        "spi_participant_candidates",
        "digital_peer_voltage_candidates",
        "usb_peer_group_candidates",
        "usb_c_peer_candidates",
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
        "design_lint_i2c_bus_candidates.py",
        "design_lint_i2c_pullup_candidates.py",
        "design_lint_spi_candidates.py",
        "design_lint_spi_bus_candidates.py",
        "design_lint_spi_generic_connector_candidates.py",
        "design_lint_serial_bus_candidates.py",
        "design_lint_serial_generic_connector_candidates.py",
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
        "i2c_protocol_bus_candidates",
        "two_wire_signal_candidates",
        "serial_protocol_bus_candidates",
        "spi_protocol_bus_candidates",
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


def test_generic_connector_protocols_share_pin_metadata_inventory_check() -> None:
    helper = HWREPO / "connector_pin_metadata.py"
    modules = (
        "can_generic_connector_candidates.py",
        "i2c_generic_connector_candidates.py",
        "spi_generic_connector_candidates.py",
        "serial_generic_connector_candidates.py",
    )
    assert line_count(helper) < IMPLEMENTATION_MAX_LINES
    for name in modules:
        source = HWREPO / name
        tree = ast.parse(source.read_text(encoding="utf-8"), filename=source.name)
        imports = {
            (node.module, alias.name)
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom)
            for alias in node.names
        }
        local_helpers = {node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)}
        assert ("connector_pin_metadata", "connector_pin_metadata_matches_inventory") in imports
        assert "_metadata_matches_inventory" not in local_helpers

    assert callable(connector_pin_metadata_matches_inventory)


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
        and node.func.id == "scan_bus_candidates"
    )
    (bus_call,) = bus_calls
    assert len(bus_call.args) == 1
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


def test_legacy_and_prepared_candidate_paths_share_required_scanner_inputs() -> None:
    aggregation = HWREPO / "design_lint_candidate_aggregation.py"
    evaluation = HWREPO / "design_lint_evaluation_candidates.py"
    inputs = HWREPO / "design_lint_candidate_inputs.py"

    assert line_count(inputs) < IMPLEMENTATION_MAX_LINES
    scanner_parameters = inspect.signature(
        design_lint_candidate_aggregation.scan_candidates
    ).parameters
    assert tuple(scanner_parameters) == ("inputs",)

    input_parameters = inspect.signature(DesignLintCandidateInputs).parameters
    for group_name in (
        "connector",
        "component",
        "control",
        "power",
        "bus",
        "peer",
        "mapped",
        "pcb",
    ):
        assert input_parameters[group_name].default is inspect.Parameter.empty

    aggregation_tree = ast.parse(aggregation.read_text(encoding="utf-8"))
    legacy_function = next(
        node
        for node in aggregation_tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "candidates"
    )
    legacy_calls = [
        node
        for node in ast.walk(legacy_function)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "scan_candidates"
    ]
    assert len(legacy_calls) == 1
    assert isinstance(legacy_calls[0].args[0], ast.Call)
    assert isinstance(legacy_calls[0].args[0].func, ast.Name)
    assert legacy_calls[0].args[0].func.id == "DesignLintCandidateInputs"

    evaluation_tree = ast.parse(evaluation.read_text(encoding="utf-8"))
    prepared_calls = [
        node
        for node in ast.walk(evaluation_tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "scan_candidate_result"
    ]
    assert len(prepared_calls) == 1
    assert isinstance(prepared_calls[0].args[0], ast.Name)
    assert prepared_calls[0].args[0].id == "candidate_inputs"
    candidate_input_assignments = [
        node
        for node in ast.walk(evaluation_tree)
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "candidate_inputs"
            for target in node.targets
        )
    ]
    assert len(candidate_input_assignments) == 1
    assignment_value = candidate_input_assignments[0].value
    assert isinstance(assignment_value, ast.Attribute)
    assert assignment_value.attr == "candidate_inputs"
    assert isinstance(assignment_value.value, ast.Name)
    assert assignment_value.value.id == "prepared"

    preparation = HWREPO / "design_lint_evaluation_preparation.py"
    preparation_tree = ast.parse(preparation.read_text(encoding="utf-8"))
    prepared_input_constructions = [
        node
        for node in ast.walk(preparation_tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "DesignLintCandidateInputs"
    ]
    assert len(prepared_input_constructions) == 1

    candidate_results = HWREPO / "design_lint_candidate_results.py"
    assert line_count(candidate_results) < IMPLEMENTATION_MAX_LINES
    result_tree = ast.parse(candidate_results.read_text(encoding="utf-8"))
    result_type = next(
        node
        for node in result_tree.body
        if isinstance(node, ast.ClassDef) and node.name == "DesignLintCandidateScanResult"
    )
    result_fields = {
        node.target.id
        for node in result_type.body
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name)
    }
    assert result_fields == {
        "candidates",
        "peer_reference_keys",
        "connector_peer_pin_finding_counts",
        "component_peer_pin_finding_counts",
        "mapped_topology_finding_counts",
    }

    connector_result_owner = HWREPO / "connector_peer_pin_candidate_results.py"
    connector_coordinator = HWREPO / "design_lint_connector_candidates.py"
    evaluation_source = evaluation.read_text(encoding="utf-8")
    assert line_count(connector_result_owner) < IMPLEMENTATION_MAX_LINES
    connector_tree = ast.parse(connector_result_owner.read_text(encoding="utf-8"))
    connector_counts = next(
        node
        for node in connector_tree.body
        if isinstance(node, ast.ClassDef) and node.name == "ConnectorPeerPinFindingCounts"
    )
    assert {
        node.target.id
        for node in connector_counts.body
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name)
    } >= {
        "repeated_function_finding_count",
        "peer_pin_outlier_finding_count",
        "peer_pin_divergence_finding_count",
        "footprint_peer_pin_open_outlier_finding_count",
    }
    assert "def scan_connector_candidates(" in connector_coordinator.read_text(encoding="utf-8")
    assert "finding_counts=scan_result.connector_peer_pin_finding_counts" in evaluation_source
    assert "finding_counts=scan_result.component_peer_pin_finding_counts" in evaluation_source
    assert "scan_result.mapped_topology_finding_counts" in evaluation_source
    assert "connector.footprint_named_power_input_all_open" not in evaluation_source


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


@pytest.mark.rule_gate_integrity
def test_mapped_topology_coverage_consumes_owner_result_counts() -> None:
    coverage_parameters = inspect.signature(mapped_topology_coverage_runs).parameters
    coverage_types = get_type_hints(mapped_topology_coverage_runs)
    owners = (
        "design_lint_component_candidates.py",
        "design_lint_mapped_coverage_candidates.py",
        "design_lint_mapped_topology_coverage.py",
        "design_lint_mapped_topology_results.py",
    )

    assert "finding_counts" in coverage_parameters
    assert "candidates" not in coverage_parameters
    assert coverage_types["finding_counts"] is MappedTopologyFindingCounts
    assert all(line_count(HWREPO / name) < IMPLEMENTATION_MAX_LINES for name in owners)
    assert "def scan_component_candidates(" in (HWREPO / owners[0]).read_text(encoding="utf-8")
    mapped_source = (HWREPO / owners[1]).read_text(encoding="utf-8")
    assert "def scan_mapped_coverage_candidates(" in mapped_source
    assert "def mapped_coverage_candidates(" in mapped_source
    assert get_type_hints(scan_component_candidates) == {
        "inputs": ComponentTopologyCandidateInputs,
        "return": ComponentCandidateScanResult,
    }
    assert get_type_hints(scan_mapped_coverage_candidates) == {
        "inputs": MappedCoverageCandidateInputs,
        "return": MappedCoverageCandidateResult,
    }
    for filename in (
        "design_lint_candidate_aggregation.py",
        "design_lint_candidate_results.py",
        "design_lint_mapped_topology_coverage.py",
    ):
        tree = ast.parse((HWREPO / filename).read_text(encoding="utf-8"))
        assert any(
            isinstance(node, ast.ImportFrom)
            and node.level == 1
            and node.module == "design_lint_mapped_topology_results"
            and any(alias.name == "MappedTopologyFindingCounts" for alias in node.names)
            for node in ast.walk(tree)
        )
