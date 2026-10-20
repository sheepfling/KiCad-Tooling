"""The shipped lint catalog is tied to implementation and fault/control regressions."""

from __future__ import annotations

import ast
import importlib
from pathlib import Path

import pytest

from kicad_tooling.hwrepo.design_lint import rule_catalog

pytestmark = pytest.mark.design_lint


def _refs(owner: str, *tests: str) -> tuple[str, ...]:
    return tuple(f"{owner}.{name}" for name in tests)


_PARITY_FIXTURES_BY_RULE = {
    "bus.i2c_missing_pullup": {
        "fault_fixtures": _refs(
            "tests.test_design_lint_i2c_parity.DesignLintI2cParityTests",
            "test_mapped_array_control_and_missing_array_fault_match_cli_and_mcp",
        ),
        "valid_control_fixtures": _refs(
            "tests.test_design_lint_i2c_parity.DesignLintI2cParityTests",
            "test_mapped_array_control_and_missing_array_fault_match_cli_and_mcp",
        ),
    },
    "bus.serial_unmapped_peer": {
        "fault_fixtures": (
            *_refs(
                "tests.test_design_lint_i2c_parity.DesignLintI2cParityTests",
                "test_mapped_array_control_and_missing_array_fault_match_cli_and_mcp",
            ),
            *_refs(
                "tests.test_design_lint_serial_parity.DesignLintSerialParityTests",
                "test_alternate_function_uart_labels_match_cli_and_mcp",
            ),
        ),
    },
    "component.peer_power_output_unconnected": {
        "fault_fixtures": _refs(
            "tests.test_design_lint_mcp_parity_peer_pins",
            "test_peer_power_output_unconnected_lint_cli_mcp_parity",
        ),
        "valid_control_fixtures": _refs(
            "tests.test_design_lint_mcp_parity_peer_pins",
            "test_peer_power_output_unconnected_lint_cli_mcp_parity",
        ),
    },
    "component.peer_signal_input_unconnected": {
        "fault_fixtures": _refs(
            "tests.test_design_lint_mcp_parity_peer_pins",
            "test_peer_signal_input_unconnected_lint_cli_mcp_parity",
        ),
        "valid_control_fixtures": _refs(
            "tests.test_design_lint_mcp_parity_peer_pins",
            "test_peer_signal_input_unconnected_lint_cli_mcp_parity",
        ),
    },
    "component.peer_signal_output_unconnected": {
        "fault_fixtures": _refs(
            "tests.test_design_lint_mcp_parity_peer_pins",
            "test_peer_signal_output_unconnected_lint_cli_mcp_parity",
        ),
        "valid_control_fixtures": _refs(
            "tests.test_design_lint_mcp_parity_peer_pins",
            "test_peer_signal_output_unconnected_lint_cli_mcp_parity",
        ),
    },
    "component.peer_bidirectional_pin_unconnected": {
        "fault_fixtures": _refs(
            "tests.test_design_lint_mcp_parity_peer_pins",
            "test_peer_bidirectional_pin_unconnected_lint_cli_mcp_parity",
        ),
        "valid_control_fixtures": _refs(
            "tests.test_design_lint_mcp_parity_peer_pins",
            "test_peer_bidirectional_pin_unconnected_lint_cli_mcp_parity",
        ),
    },
    "component.two_pin_passive_same_net": {
        "fault_fixtures": _refs(
            "tests.test_design_lint_mcp_parity_mapped_custom_passive",
            "test_mapped_custom_capacitor_same_net_lint_cli_mcp_parity",
        )
        + _refs(
            "tests.test_design_lint_mcp_parity_two_pin_thermistors",
            "test_same_net_thermistor_lint_cli_mcp_parity",
        ),
        "valid_control_fixtures": _refs(
            "tests.test_design_lint_mcp_parity_mapped_custom_passive",
            "test_mapped_custom_capacitor_same_net_lint_cli_mcp_parity",
        )
        + _refs(
            "tests.test_design_lint_mcp_parity_two_pin_thermistors",
            "test_same_net_thermistor_lint_cli_mcp_parity",
        ),
    },
    "component.unconnected_power_output": {
        "fault_fixtures": _refs(
            "tests.test_design_lint_mcp_parity_unconnected_power_output",
            "test_generic_power_output_review_cli_mcp_parity",
        ),
        "valid_control_fixtures": _refs(
            "tests.test_design_lint_mcp_parity_unconnected_power_output",
            "test_generic_power_output_review_cli_mcp_parity",
        ),
    },
    "connector.generic_peer_pin_all_open": {
        "fault_fixtures": _refs(
            "tests.test_design_lint_mcp_parity_connector_all_open",
            "test_all_open_generic_peer_pin_lint_cli_mcp_parity",
        ),
        "valid_control_fixtures": _refs(
            "tests.test_design_lint_mcp_parity_connector_all_open",
            "test_all_open_generic_peer_pin_lint_cli_mcp_parity",
        ),
    },
    "connector.footprint_peer_pin_all_open": {
        "fault_fixtures": _refs(
            "tests.test_connector_footprint_peer_open",
            "test_all_generic_contacts_open_across_footprint_aliases_is_opt_in_review",
        )
        + _refs(
            "tests.test_connector_footprint_peer_parity",
            "test_footprint_alias_review_matches_cli_and_mcp",
        ),
        "valid_control_fixtures": _refs(
            "tests.test_connector_footprint_peer_open",
            "test_all_open_footprint_alias_requires_a_shared_anchor_and_eligible_generic_metadata",
        )
        + _refs(
            "tests.test_connector_footprint_peer_parity",
            "test_footprint_alias_review_matches_cli_and_mcp",
        ),
        "metamorphic_fixtures": _refs(
            "tests.test_connector_footprint_peer_open",
            "test_all_open_footprint_alias_is_stable_under_mapping_order",
        )
        + _refs(
            "tests.test_connector_footprint_peer_parity",
            "test_footprint_alias_review_matches_cli_and_mcp",
        ),
    },
    "connector.footprint_named_power_input_open_outlier": {
        "fault_fixtures": _refs(
            "tests.test_connector_footprint_peer_parity",
            "test_footprint_alias_review_matches_cli_and_mcp",
        ),
        "valid_control_fixtures": _refs(
            "tests.test_connector_footprint_peer_parity",
            "test_footprint_alias_review_matches_cli_and_mcp",
        ),
    },
    "connector.footprint_named_signal_input_open_outlier": {
        "fault_fixtures": _refs(
            "tests.test_connector_footprint_peer_parity",
            "test_footprint_alias_review_matches_cli_and_mcp",
        ),
        "valid_control_fixtures": _refs(
            "tests.test_connector_footprint_peer_parity",
            "test_footprint_alias_review_matches_cli_and_mcp",
        ),
    },
    "connector.footprint_named_power_output_open_outlier": {
        "fault_fixtures": _refs(
            "tests.test_connector_footprint_peer_parity",
            "test_footprint_alias_review_matches_cli_and_mcp",
        ),
        "valid_control_fixtures": _refs(
            "tests.test_connector_footprint_peer_parity",
            "test_footprint_alias_review_matches_cli_and_mcp",
        ),
    },
    "connector.footprint_named_signal_output_open_outlier": {
        "fault_fixtures": _refs(
            "tests.test_connector_footprint_peer_parity",
            "test_footprint_alias_review_matches_cli_and_mcp",
        ),
        "valid_control_fixtures": _refs(
            "tests.test_connector_footprint_peer_parity",
            "test_footprint_alias_review_matches_cli_and_mcp",
        ),
    },
    "connector.footprint_named_signal_assignment_divergence": {
        "fault_fixtures": _refs(
            "tests.test_connector_footprint_named_signal_divergence",
            "test_named_signal_pin_on_different_nets_is_reviewed_with_a_common_anchor",
        )
        + _refs(
            "tests.test_connector_footprint_peer_parity",
            "test_footprint_alias_review_matches_cli_and_mcp",
        ),
        "valid_control_fixtures": _refs(
            "tests.test_connector_footprint_named_signal_divergence",
            "test_common_unanchored_or_ineligible_contacts_are_not_signal_divergence_findings",
        )
        + _refs(
            "tests.test_connector_footprint_peer_parity",
            "test_footprint_alias_review_matches_cli_and_mcp",
        ),
    },
    "connector.footprint_named_power_input_assignment_divergence": {
        "fault_fixtures": _refs(
            "tests.test_connector_footprint_named_power_input_divergence",
            "test_named_power_input_on_different_nets_is_reviewed_with_a_common_anchor",
        )
        + _refs(
            "tests.test_connector_footprint_peer_parity",
            "test_footprint_alias_review_matches_cli_and_mcp",
        )
        + _refs(
            "tests.test_connector_footprint_named_power_input_native_fixture_lane",
            "test_native_named_power_input_divergence_fault_and_control_are_repeatable",
        ),
        "valid_control_fixtures": _refs(
            "tests.test_connector_footprint_named_power_input_divergence",
            "test_common_unanchored_or_ineligible_contacts_are_not_power_divergence_findings",
        )
        + _refs(
            "tests.test_connector_footprint_peer_parity",
            "test_footprint_alias_review_matches_cli_and_mcp",
        )
        + _refs(
            "tests.test_connector_footprint_named_power_input_native_fixture_lane",
            "test_native_named_power_input_divergence_fault_and_control_are_repeatable",
        ),
        "metamorphic_fixtures": _refs(
            "tests.test_connector_footprint_named_power_input_divergence",
            "test_named_power_input_divergence_is_stable_under_mapping_order",
        )
        + _refs(
            "tests.test_connector_footprint_peer_parity",
            "test_footprint_alias_review_matches_cli_and_mcp",
        ),
    },
    "connector.footprint_named_power_output_assignment_divergence": {
        "fault_fixtures": _refs(
            "tests.test_connector_footprint_named_power_output_divergence",
            "test_named_power_output_on_different_nets_is_reviewed_with_a_common_anchor",
        )
        + _refs(
            "tests.test_connector_footprint_peer_parity",
            "test_footprint_alias_review_matches_cli_and_mcp",
        )
        + _refs(
            "tests.test_connector_footprint_named_power_output_native_fixture_lane",
            "test_native_named_power_output_divergence_fault_and_control_are_repeatable",
        ),
        "valid_control_fixtures": _refs(
            "tests.test_connector_footprint_named_power_output_divergence",
            "test_common_unanchored_or_ineligible_contacts_are_not_power_output_findings",
        )
        + _refs(
            "tests.test_connector_footprint_peer_parity",
            "test_footprint_alias_review_matches_cli_and_mcp",
        )
        + _refs(
            "tests.test_connector_footprint_named_power_output_native_fixture_lane",
            "test_native_named_power_output_divergence_fault_and_control_are_repeatable",
        ),
        "metamorphic_fixtures": _refs(
            "tests.test_connector_footprint_named_power_output_divergence",
            "test_named_power_output_divergence_is_stable_under_mapping_order",
        ),
    },
    "connector.unconnected_power_output": {
        "fault_fixtures": _refs(
            "tests.test_design_lint_mcp_parity_connector_power_output",
            "test_generic_connector_power_output_review_cli_mcp_parity",
        ),
        "valid_control_fixtures": _refs(
            "tests.test_design_lint_mcp_parity_connector_power_output",
            "test_generic_connector_power_output_review_cli_mcp_parity",
        ),
    },
    "connector.unconnected_power_input": {
        "fault_fixtures": _refs(
            "tests.test_design_lint_mcp_parity_connector_coverage",
            "test_design_lint_connector_coverage_and_review_lifecycle",
        )
        + _refs(
            "tests.test_design_lint_power_pin_patterns.TestDesignLintPowerPinPatterns",
            "test_power_input_aliases_use_typed_rule_instead_of_generic_all_open_hint",
        ),
        "valid_control_fixtures": _refs(
            "tests.test_design_lint_power_pin_patterns.TestDesignLintPowerPinPatterns",
            "test_power_input_aliases_use_typed_rule_instead_of_generic_all_open_hint",
        ),
    },
    "power.named_supply_pin_on_negative_rail": {
        "fault_fixtures": _refs(
            "tests.test_design_lint_mcp_parity_power_pin_roles",
            "test_named_supply_pin_on_negative_rail_cli_mcp_parity",
        ),
        "valid_control_fixtures": _refs(
            "tests.test_design_lint_mcp_parity_power_pin_roles",
            "test_named_supply_pin_on_negative_rail_cli_mcp_parity",
        ),
    },
    "power.ic_decoupling_below_project_minimum": {
        "fault_fixtures": _refs(
            "tests.test_design_lint_mcp_parity_ic_decoupling",
            "test_ic_decoupling_review_matches_between_cli_and_mcp",
        ),
        "valid_control_fixtures": _refs(
            "tests.test_design_lint_mcp_parity_ic_decoupling",
            "test_ic_decoupling_review_matches_between_cli_and_mcp",
        ),
    },
    "pcb.keepout_intent_coverage": {
        "valid_control_fixtures": _refs(
            "tests.test_pcb_keepouts_mcp_parity",
            "test_disabled_keepout_coverage_matches_cli_and_mcp",
        ),
    },
    "pcb.rf_module_antenna_keepout_coverage": {
        "fault_fixtures": _refs(
            "tests.test_pcb_rf_antenna_mcp_parity",
            "test_enabled_rf_antenna_fault_and_control_match_cli_and_mcp",
        ),
        "valid_control_fixtures": (
            *_refs(
                "tests.test_pcb_rf_antenna_mcp_parity",
                "test_disabled_rf_antenna_coverage_matches_cli_and_mcp",
            ),
            *_refs(
                "tests.test_pcb_rf_antenna_mcp_parity",
                "test_enabled_rf_antenna_fault_and_control_match_cli_and_mcp",
            ),
        ),
    },
    "pcb.signal_path_rule_coverage": {
        "valid_control_fixtures": _refs(
            "tests.test_pcb_signal_path_mcp_parity",
            "test_disabled_signal_path_coverage_matches_cli_and_mcp",
        ),
    },
    "oscillator.output_load_path_mismatch": {
        "fault_fixtures": _refs(
            "tests.test_design_lint_mcp_parity_oscillator_output_paths",
            "test_oscillator_output_path_matches_cli_and_mcp",
        ),
        "valid_control_fixtures": _refs(
            "tests.test_design_lint_mcp_parity_oscillator_output_paths",
            "test_oscillator_output_path_matches_cli_and_mcp",
        ),
    },
}


def _pytest_collects_class(owner: type) -> bool:
    return (
        owner.__name__.startswith("Test")
        or owner.__name__.endswith("Tests")
        or any(
            base.__module__ == "unittest.case" and base.__name__ == "TestCase"
            for base in owner.__mro__
        )
    )


def test_active_rules_reference_existing_regression_fixtures() -> None:
    """Validate locators and exercise only class cases pytest cannot collect."""
    pytest_class_tests: set[str] = set()
    legacy_class_tests: set[tuple[type, str]] = set()
    pytest_fixtures: set[str] = set()
    metamorphic_rules: set[str] = set()
    for entry in rule_catalog().rules:
        assert entry.fault_fixtures
        assert entry.valid_control_fixtures
        if entry.metamorphic_fixtures:
            metamorphic_rules.add(entry.rule_id)
        for name in (
            *entry.fault_fixtures,
            *entry.valid_control_fixtures,
            *entry.metamorphic_fixtures,
        ):
            parts = name.split(".")
            module = None
            module_length = 0
            for length in range(len(parts) - 1, 0, -1):
                try:
                    module = importlib.import_module(".".join(parts[:length]))
                except ModuleNotFoundError:
                    continue
                module_length = length
                break
            assert module is not None, name
            attributes = parts[module_length:]
            owner = module
            for attribute in attributes[:-1]:
                owner = getattr(owner, attribute)
            target = getattr(owner, attributes[-1])
            assert callable(target), name
            if isinstance(owner, type):
                assert target.__name__.startswith("test_"), name
                if _pytest_collects_class(owner):
                    pytest_class_tests.add(name)
                else:
                    legacy_class_tests.add((owner, attributes[-1]))
            else:
                assert len(attributes) == 1, name
                assert target.__name__.startswith("test_"), name
                pytest_fixtures.add(name)

    assert len(metamorphic_rules) >= 2
    assert pytest_class_tests, "catalog should support pytest-collected class methods"
    assert pytest_fixtures, "catalog should support pytest function fixtures"
    for owner, method_name in sorted(
        legacy_class_tests,
        key=lambda item: (item[0].__module__, item[0].__qualname__, item[1]),
    ):
        getattr(owner(), method_name)()


def test_cli_mcp_fault_and_control_parity_is_reachable_by_rule_selector() -> None:
    """Keep cross-surface fault/control cases visible to focused lint gates."""
    rules = {entry.rule_id: entry for entry in rule_catalog().rules}
    for rule_id, expected_fields in _PARITY_FIXTURES_BY_RULE.items():
        entry = rules[rule_id]
        for field, references in expected_fields.items():
            catalogued = set(getattr(entry, field))
            assert set(references) <= catalogued, (
                f"{rule_id}: {field} omits CLI/MCP fixture references "
                f"{sorted(set(references) - catalogued)}"
            )


def test_catalog_implementation_references_resolve_to_sources_or_fixtures() -> None:
    repository = Path(__file__).resolve().parents[1]
    for rule in rule_catalog().rules:
        for reference in rule.implementation_refs:
            target, separator, symbol = reference.partition("#")
            target_path = (
                repository / target
                if "/" in target
                else repository.joinpath(*target.split(".")).with_suffix(".py")
            )
            assert target_path.is_file(), f"{rule.rule_id}: missing implementation {target}"
            if not separator or target_path.suffix != ".py":
                continue
            module = ast.parse(target_path.read_text(encoding="utf-8"))
            names = {
                node.name
                for node in module.body
                if isinstance(node, (ast.AsyncFunctionDef, ast.ClassDef, ast.FunctionDef))
            }
            names.update(
                alias.asname or alias.name
                for node in module.body
                if isinstance(node, ast.ImportFrom)
                for alias in node.names
            )
            assert symbol in names, (
                f"{rule.rule_id}: {reference} does not resolve to a top-level source symbol"
            )


def test_every_rule_fixture_module_has_design_lint_selection_marker() -> None:
    repository = Path(__file__).resolve().parents[1]
    for rule in rule_catalog().rules:
        for field in ("fault_fixtures", "valid_control_fixtures", "metamorphic_fixtures"):
            for fixture in getattr(rule, field):
                module_name = ".".join(fixture.split(".")[:2])
                module_path = repository.joinpath(*module_name.split(".")).with_suffix(".py")
                module = ast.parse(module_path.read_text(encoding="utf-8"))
                assignment = next(
                    (
                        node
                        for node in module.body
                        if isinstance(node, ast.Assign)
                        and any(
                            isinstance(target, ast.Name) and target.id == "pytestmark"
                            for target in node.targets
                        )
                    ),
                    None,
                )
                assert assignment is not None, f"{rule.rule_id}: {module_path} is not tagged"
                markers = {
                    node.attr
                    for node in ast.walk(assignment.value)
                    if isinstance(node, ast.Attribute)
                    and node.attr == "design_lint"
                    and isinstance(node.value, ast.Attribute)
                    and node.value.attr == "mark"
                    and isinstance(node.value.value, ast.Name)
                    and node.value.value.id == "pytest"
                }
                assert "design_lint" in markers, (
                    f"{rule.rule_id}: {module_path} lacks the design_lint marker"
                )
