"""Focused review regressions for UART TX/RX pin and net-label mismatches."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.design_lint import candidates, evaluate
from kicad_tooling.hwrepo.design_lint_finding_models import (
    DesignLintFinding,
    DesignLintIgnore,
    DesignLintRuleOverride,
)
from kicad_tooling.hwrepo.design_lint_policy_models import DesignLintPolicy
from kicad_tooling.hwrepo.design_lint_report_models import DesignLintReport
from kicad_tooling.hwrepo.models import NetlistContract
from kicad_tooling.hwrepo.serial_tx_rx_label_mismatch import (
    serial_tx_rx_label_mismatch_candidates,
)
from tests.design_lint_fixtures import coach
from tests.design_lint_fixtures.serial_tx_rx_label_mismatch import serial_tx_rx_label_netlist

pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint]

RULE_ID = "bus.serial_tx_rx_label_mismatch"


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
                reason="Review synthetic serial direction labels",
            ),
        ),
        ignores=() if ignore is None else (ignore,),
    )
    return evaluate("synthetic-serial-tx-rx-labels", coach(netlist), policy)


def _findings(report: DesignLintReport) -> tuple[DesignLintFinding, ...]:
    return tuple(item for item in report.findings if item.rule_id == RULE_ID)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_opposite_uart_labels_are_reviewed_while_pins_remain_separate() -> None:
    source = serial_tx_rx_label_netlist()
    findings = serial_tx_rx_label_mismatch_candidates(source)

    assert tuple(item.subject for item in findings) == (
        "U1.1: USART1_TX on USART1_RX",
        "U1.2: USART1_RX on USART1_TX",
    )
    assert findings[0].evidence["pin_role"] == ("tx",)
    assert findings[0].evidence["net_role"] == ("rx",)
    assert findings[1].evidence["pin_role"] == ("rx",)
    assert findings[1].evidence["net_role"] == ("tx",)
    assert _report(source).status == "REVIEW"
    assert tuple(item.subject for item in _findings(_report(source))) == tuple(
        item.subject for item in candidates(source) if item.rule_id == RULE_ID
    )


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_matching_labels_generic_names_and_other_channels_remain_quiet() -> None:
    source = serial_tx_rx_label_netlist(crossed=False)
    generic_functions = source.model_copy(update={"pin_functions": {"U1.1": "TXD", "U1.2": "RXD"}})
    generic_labels = source.model_copy(update={"nets": {"RX": ("U1.1",), "TX": ("U1.2",)}})
    mismatched_channel = source.model_copy(
        update={"nets": {"USART2_RX": ("U1.1",), "USART2_TX": ("U1.2",)}}
    )
    other_protocol = source.model_copy(
        update={"nets": {"CAN1_RX": ("U1.1",), "CAN1_TX": ("U1.2",)}}
    )

    for control in (source, generic_functions, generic_labels, mismatched_channel, other_protocol):
        assert not serial_tx_rx_label_mismatch_candidates(control)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_aliases_dnp_open_multi_assignment_and_incomplete_inventory_are_bounded() -> None:
    source = serial_tx_rx_label_netlist()
    aliases = source.model_copy(
        update={"pin_functions": {"U1.1": "USART1_TXD", "U1.2": "USART1_RXD"}}
    )
    dnp = source.model_copy(update={"dnp_components": ("U1",)})
    open_pins = source.model_copy(update={"nets": {}})
    multi_assigned = source.model_copy(
        update={"nets": {"USART1_RX": ("U1.1", "U1.2"), "USART1_RX_AUX": ("U1.1",)}}
    )
    missing_inventory = source.model_copy(update={"component_pin_numbers": {}})
    inconsistent_inventory = source.model_copy(
        update={
            "nets": {"USART1_RX": ("U1.1", "U1.2")},
            "component_pin_numbers": {"U1": ("2",)},
        }
    )
    connector = source.model_copy(
        update={
            "components": {"J1": source.components["U1"]},
            "nets": {"USART1_RX": ("J1.1",), "USART1_TX": ("J1.2",)},
            "component_symbols": {"J1": "Synthetic:UartConnector"},
            "pin_functions": {"J1.1": "USART1_TX", "J1.2": "USART1_RX"},
            "component_pin_numbers": {"J1": ("1", "2")},
        }
    )

    assert len(serial_tx_rx_label_mismatch_candidates(aliases)) == 2
    for unsupported in (
        dnp,
        open_pins,
        multi_assigned,
        missing_inventory,
        inconsistent_inventory,
        connector,
    ):
        assert not serial_tx_rx_label_mismatch_candidates(unsupported)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_project_policy_can_block_disable_or_ignore_exact_assignments() -> None:
    source = serial_tx_rx_label_netlist()
    initial = _findings(_report(source))
    blocked = _findings(_report(source, "block"))
    disabled = _findings(_report(source, "off"))
    ignored = _findings(
        _report(
            source,
            ignore=DesignLintIgnore(
                rule_id=RULE_ID,
                fingerprint=initial[0].fingerprint,
                reason="Reviewed serial endpoint naming convention",
            ),
        )
    )

    assert _report(source, "block").status == "FAIL"
    assert all(item.mode == "block" for item in blocked)
    assert all(item.disposition == "RULE_OFF" for item in disabled)
    assert ignored[0].disposition == "IGNORED"


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_findings_are_order_stable_and_correction_clears_them() -> None:
    source = serial_tx_rx_label_netlist()
    reordered = source.model_copy(
        update={
            "components": dict(reversed(tuple(source.components.items()))),
            "nets": dict(reversed(tuple(source.nets.items()))),
            "pin_functions": dict(reversed(tuple(source.pin_functions.items()))),
            "component_pin_numbers": dict(reversed(tuple(source.component_pin_numbers.items()))),
        }
    )

    assert _findings(_report(reordered)) == _findings(_report(source))
    assert not serial_tx_rx_label_mismatch_candidates(serial_tx_rx_label_netlist(crossed=False))
