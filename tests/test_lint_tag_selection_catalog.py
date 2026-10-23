"""Keep rule-scoped prerelease tags tied to native fixture declarations."""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.lint_gate_scope import (
    active_design_lint_rule_ids,
    configured_native_fixtures,
    parse_tag_message,
    required_native_fixtures_by_rule,
)


@pytest.mark.parametrize(
    ("rule_id", "native_fixture"),
    (
        ("power.mapped_sequence_dependency_mismatch", "KICAD_RUN_NATIVE_POWER_SEQUENCE_FIXTURES"),
        ("component.generic_peer_pin_mixed_open", "KICAD_RUN_NATIVE_COMPONENT_PEER_PIN_FIXTURES"),
        ("component.peer_signal_input_unconnected", "KICAD_RUN_NATIVE_COMPONENT_PEER_PIN_FIXTURES"),
        (
            "component.peer_signal_output_unconnected",
            "KICAD_RUN_NATIVE_COMPONENT_PEER_PIN_FIXTURES",
        ),
        ("connector.repeated_pin_function", "KICAD_RUN_NATIVE_DB9_RETURN_CONTRACT_FIXTURES"),
        ("component.peer_power_output_unconnected", "KICAD_RUN_NATIVE_COMPONENT_PEER_PIN_FIXTURES"),
        (
            "component.peer_bidirectional_pin_unconnected",
            "KICAD_RUN_NATIVE_COMPONENT_PEER_PIN_FIXTURES",
        ),
        ("bus.i2c_missing_pullup", "KICAD_RUN_NATIVE_I2C_PULLUP_FIXTURES"),
        (
            "bus.usb_data_polarity_label_mismatch",
            "KICAD_RUN_NATIVE_USB_DATA_POLARITY_FIXTURES",
        ),
        (
            "power.ic_decoupling_below_project_minimum",
            "KICAD_RUN_NATIVE_IC_RAIL_CAPACITOR_FIXTURES",
        ),
        (
            "component.diode_anode_below_cathode_on_named_rails",
            "KICAD_RUN_NATIVE_COMPONENT_RATING_FIXTURES",
        ),
        (
            "component.mosfet_terminal_order_on_named_rails",
            "KICAD_RUN_NATIVE_COMPONENT_RATING_FIXTURES",
        ),
        ("component.mosfet_gate_direct_drive", "KICAD_RUN_NATIVE_COMPONENT_RATING_FIXTURES"),
        (
            "component.mosfet_drain_source_same_net",
            "KICAD_RUN_NATIVE_COMPONENT_RATING_FIXTURES",
        ),
        (
            "component.mosfet_gate_source_same_net",
            "KICAD_RUN_NATIVE_COMPONENT_RATING_FIXTURES",
        ),
        (
            "component.mosfet_gate_drain_same_net",
            "KICAD_RUN_NATIVE_COMPONENT_RATING_FIXTURES",
        ),
        (
            "component.bjt_terminal_order_on_named_rails",
            "KICAD_RUN_NATIVE_COMPONENT_TERMINAL_ORDER_FIXTURES",
        ),
        (
            "component.bjt_collector_emitter_same_net",
            "KICAD_RUN_NATIVE_COMPONENT_TERMINAL_ORDER_FIXTURES",
        ),
        (
            "component.bjt_base_emitter_same_net",
            "KICAD_RUN_NATIVE_COMPONENT_TERMINAL_ORDER_FIXTURES",
        ),
        (
            "component.bjt_base_collector_same_net",
            "KICAD_RUN_NATIVE_COMPONENT_TERMINAL_ORDER_FIXTURES",
        ),
        ("component.bjt_base_direct_drive", "KICAD_RUN_NATIVE_COMPONENT_BASE_DRIVE_FIXTURES"),
        (
            "component.bjt_base_without_visible_emitter_bias",
            "KICAD_RUN_NATIVE_COMPONENT_BASE_DRIVE_FIXTURES",
        ),
        ("power.regulator_feedback_mismatch", "KICAD_RUN_NATIVE_REGULATOR_FEEDBACK_FIXTURES"),
    ),
)
def test_lint_tag_selects_one_active_rule_and_its_configured_native_fixture(
    rule_id: str,
    native_fixture: str,
) -> None:
    repository = Path(__file__).resolve().parents[1]
    fixtures = configured_native_fixtures(repository)
    rule_ids = active_design_lint_rule_ids()
    assert rule_id in rule_ids
    assert native_fixture in fixtures

    scope = parse_tag_message(
        "Focused deterministic lint gate\n\n"
        f"Lint-Rule: {rule_id}\n"
        f"Native-Fixture: {native_fixture}\n",
        fixtures,
        rule_ids,
        required_native_fixtures_by_rule(),
    )

    assert scope.area is None
    assert scope.rule_id == rule_id
    assert scope.pytest_markexpr == f'design_lint and design_lint_rule(rule_id="{rule_id}")'
    assert scope.native_fixtures == (native_fixture,)
