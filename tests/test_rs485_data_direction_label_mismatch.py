"""Focused RS-485 D/R-to-UART direction-label review regressions."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.design_lint_finding_models import (
    DesignLintFinding,
    DesignLintIgnore,
    DesignLintRuleOverride,
)
from kicad_tooling.hwrepo.design_lint_policy_models import DesignLintPolicy
from kicad_tooling.hwrepo.design_lint_report_models import DesignLintReport
from kicad_tooling.hwrepo.models import NetlistContract
from kicad_tooling.hwrepo.rs485_data_label_mismatch import (
    rs485_data_direction_label_candidates,
)
from tests.design_lint_fixtures import coach
from tests.design_lint_fixtures.rs485_data_label_mismatch import rs485_data_label_netlist

pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint]

RULE_ID = "bus.rs485_data_direction_label_mismatch"


def _report(
    netlist: NetlistContract,
    mode: str = "review",
    *,
    ignore: DesignLintIgnore | None = None,
) -> DesignLintReport:
    policy = DesignLintPolicy(
        rules=(
            DesignLintRuleOverride(
                rule_id=RULE_ID,
                mode=mode,
                reason="Review synthetic RS-485 transceiver data directions",
            ),
        ),
        ignores=() if ignore is None else (ignore,),
    )
    return evaluate("synthetic-rs485-data-direction", coach(netlist), policy)


def _findings(report: DesignLintReport) -> tuple[DesignLintFinding, ...]:
    return tuple(item for item in report.findings if item.rule_id == RULE_ID)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_crossed_driver_and_receiver_labels_are_reviewed() -> None:
    source = rs485_data_label_netlist()
    findings = rs485_data_direction_label_candidates(source)

    assert tuple(item.subject for item in findings) == (
        "U1.1: D on UART1_RX",
        "U1.2: R on UART1_TX",
    )
    assert findings[0].evidence["pin_role"] == ("tx",)
    assert findings[0].evidence["net_role"] == ("rx",)
    assert findings[1].evidence["pin_role"] == ("rx",)
    assert findings[1].evidence["net_role"] == ("tx",)
    assert _report(source).status == "REVIEW"


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_correct_aliases_and_matching_labels_are_controls() -> None:
    controls = (
        rs485_data_label_netlist(crossed=False),
        rs485_data_label_netlist(crossed=False, functions=("DI", "RO")),
        rs485_data_label_netlist(crossed=False, functions=("driver input", "receiver output")),
    )
    for source in controls:
        assert not rs485_data_direction_label_candidates(source)
    assert (
        len(
            rs485_data_direction_label_candidates(
                rs485_data_label_netlist(crossed=True, functions=("DI", "RO"))
            )
        )
        == 2
    )


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_only_paired_same_channel_explicit_uart_labels_are_classified() -> None:
    source = rs485_data_label_netlist()
    generic_labels = source.model_copy(update={"nets": {"RX": ("U1.1",), "TX": ("U1.2",)}})
    mixed_protocol = source.model_copy(
        update={"nets": {"UART1_RX": ("U1.1",), "USART1_TX": ("U1.2",)}}
    )
    mismatched_channel = source.model_copy(
        update={"nets": {"UART1_RX": ("U1.1",), "UART2_TX": ("U1.2",)}}
    )
    one_unrecognized = source.model_copy(update={"nets": {"UART1_RX": ("U1.1",), "AUX": ("U1.2",)}})
    for control in (generic_labels, mixed_protocol, mismatched_channel, one_unrecognized):
        assert not rs485_data_direction_label_candidates(control)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_dnp_open_multiply_assigned_incomplete_and_ambiguous_roles_are_skipped() -> None:
    source = rs485_data_label_netlist()
    unsupported = (
        source.model_copy(update={"dnp_components": ("U1",)}),
        source.model_copy(update={"nets": {"UART1_RX": ("U1.1",)}}),
        source.model_copy(update={"nets": {**source.nets, "UART1_RX_AUX": ("U1.1",)}}),
        source.model_copy(update={"component_pin_numbers": {}}),
        source.model_copy(update={"component_pin_numbers": {"U1": ("3",)}}),
        source.model_copy(update={"pin_functions": {"U1.1": "D", "U1.2": "R", "U1.3": "DI"}}),
    )
    for case in unsupported:
        assert not rs485_data_direction_label_candidates(case)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_connector_and_non_ic_references_are_excluded() -> None:
    source = rs485_data_label_netlist()
    connector = source.model_copy(
        update={
            "components": {"J1": source.components["U1"]},
            "nets": {"UART1_RX": ("J1.1",), "UART1_TX": ("J1.2",)},
            "component_symbols": {"J1": "Synthetic:Rs485Transceiver"},
            "pin_functions": {"J1.1": "D", "J1.2": "R"},
            "component_pin_numbers": {"J1": ("1", "2")},
        }
    )
    non_ic = source.model_copy(
        update={
            "components": {"Q1": source.components["U1"]},
            "nets": {"UART1_RX": ("Q1.1",), "UART1_TX": ("Q1.2",)},
            "component_symbols": {"Q1": "Synthetic:Rs485Transceiver"},
            "pin_functions": {"Q1.1": "D", "Q1.2": "R"},
            "component_pin_numbers": {"Q1": ("1", "2")},
        }
    )

    assert not rs485_data_direction_label_candidates(connector)
    assert not rs485_data_direction_label_candidates(non_ic)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_project_policy_can_review_block_disable_or_ignore_exact_assignments() -> None:
    source = rs485_data_label_netlist()
    initial = _findings(_report(source))
    blocked = _findings(_report(source, "block"))
    disabled = _findings(_report(source, "off"))
    ignored = _findings(
        _report(
            source,
            ignore=DesignLintIgnore(
                rule_id=RULE_ID,
                fingerprint=initial[0].fingerprint,
                reason="Reviewed transceiver and label convention",
            ),
        )
    )

    assert _report(source, "block").status == "FAIL"
    assert all(item.mode == "block" for item in blocked)
    assert all(item.disposition == "RULE_OFF" for item in disabled)
    assert ignored[0].disposition == "IGNORED"


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_reordering_is_stable_and_correcting_assignments_clears_candidates() -> None:
    source = rs485_data_label_netlist()
    reordered = source.model_copy(
        update={
            "components": dict(reversed(tuple(source.components.items()))),
            "nets": dict(reversed(tuple(source.nets.items()))),
            "pin_functions": dict(reversed(tuple(source.pin_functions.items()))),
            "component_pin_numbers": dict(reversed(tuple(source.component_pin_numbers.items()))),
        }
    )

    assert _findings(_report(reordered)) == _findings(_report(source))
    assert not rs485_data_direction_label_candidates(rs485_data_label_netlist(crossed=False))
