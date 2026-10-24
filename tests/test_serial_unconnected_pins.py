"""Focused regressions for partially assigned UART/USART function channels."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path

import pytest

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.design_lint_report_models import DesignLintReport
from kicad_tooling.hwrepo.models import (
    DesignLintIgnore,
    DesignLintPolicy,
    DesignLintRuleOverride,
    NetlistContract,
)
from tests.design_lint_fixtures import coach
from tests.design_lint_fixtures.serial_unconnected_pins import serial_unconnected_netlist

RULE_ID = "bus.serial_unconnected_pin"

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.interface_lint,
    pytest.mark.design_lint_rule(rule_id=RULE_ID),
]


def _report(
    source: NetlistContract | None = None,
    mode: str | None = None,
    ignores: tuple[DesignLintIgnore, ...] = (),
) -> DesignLintReport:
    selected = serial_unconnected_netlist() if source is None else source
    overrides = (
        ()
        if mode is None
        else (DesignLintRuleOverride(rule_id=RULE_ID, mode=mode, reason="test policy"),)
    )
    return evaluate(
        "synthetic-serial-unconnected-pin",
        coach(selected),
        DesignLintPolicy(rules=overrides, ignores=ignores),
    )


def test_native_fault_fixture_source_is_pinned() -> None:
    fixture = (
        Path(__file__).parent / "fixtures/design_lint/serial-peer-native/unconnected-tx.kicad_sch"
    )

    assert sha256(fixture.read_bytes()).hexdigest() == (
        "c9b769a5fd0bd2c315d76e4b66c25c9de3311146c797a727e25c7ed2cf3f7130"
    )


def test_open_serial_pin_emits_exact_review_evidence_when_enabled() -> None:
    report = _report(mode="review")
    finding = next(item for item in report.findings if item.rule_id == RULE_ID)

    assert finding.subject == "J1.1: TX"
    assert finding.evidence == {
        "J1.1": (),
        "function": ("TX",),
        "serial_channel": ("default",),
        "serial_role": ("TX",),
    }
    assert "does not establish UART use or PCB routing" in finding.message


def test_rule_defaults_off_and_supports_review_block_off_and_exact_ignore() -> None:
    default = next(item for item in _report().findings if item.rule_id == RULE_ID)
    assert (default.mode, default.disposition) == ("off", "RULE_OFF")
    assert _report(mode="review").status == "REVIEW"
    assert _report(mode="block").status == "FAIL"
    assert _report(mode="off").status == _report().status
    ignored = _report(
        mode="review",
        ignores=(
            DesignLintIgnore(
                rule_id=RULE_ID,
                fingerprint=default.fingerprint,
                reason="reviewed one-way or unused UART channel",
            ),
        ),
    )
    ignored_findings = [item for item in ignored.findings if item.rule_id == RULE_ID]
    assert len(ignored_findings) == 1
    assert ignored_findings[0].disposition == "IGNORED"


@pytest.mark.parametrize(
    ("function", "role", "channel", "peer_function"),
    (
        ("TXD", "TX", "default", "RX"),
        ("UART_1_RXD", "RX", "uart1", "UART1_TX"),
        ("RX0", "RX", "index0", "TX0"),
    ),
)
def test_supported_serial_aliases_keep_role_and_channel_evidence(
    function: str, role: str, channel: str, peer_function: str
) -> None:
    source = serial_unconnected_netlist(
        open_pins=("J1.1",),
        functions={
            "J1.1": function,
            "J1.2": peer_function,
            "U1.1": "UART0_RX",
            "U1.2": "UART0_TX",
        },
    )
    finding = next(
        item for item in _report(source, mode="review").findings if item.rule_id == RULE_ID
    )
    assert finding.evidence["serial_role"] == (role,)
    assert finding.evidence["serial_channel"] == (channel,)


@pytest.mark.parametrize(
    "source",
    (
        pytest.param(serial_unconnected_netlist(open_pins=()), id="connected-control"),
        pytest.param(
            serial_unconnected_netlist(open_pins=("J1.1", "J1.2")),
            id="entire-channel-open",
        ),
        pytest.param(
            serial_unconnected_netlist(
                open_pins=("J1.1",),
                functions={
                    "J1.1": "TX0",
                    "J1.2": "RX1",
                    "U1.1": "UART0_RX",
                    "U1.2": "UART0_TX",
                },
            ),
            id="different-channel-control",
        ),
        pytest.param(
            serial_unconnected_netlist(dnp_components=("J1",)),
            id="dnp-endpoint",
        ),
        pytest.param(
            serial_unconnected_netlist(
                functions={
                    "J1.1": "DATA_TX",
                    "J1.2": "DATA_RX",
                    "U1.1": "UART0_RX",
                    "U1.2": "UART0_TX",
                }
            ),
            id="unsupported-aliases",
        ),
    ),
)
def test_connected_unused_or_unsupported_shapes_do_not_emit(source: NetlistContract) -> None:
    assert not any(item.rule_id == RULE_ID for item in _report(source, mode="review").findings)


def test_ordering_is_stable_and_assigning_open_pin_clears_candidate() -> None:
    source = serial_unconnected_netlist()
    reordered = source.model_copy(
        update={
            "nets": dict(reversed(tuple(source.nets.items()))),
            "pin_functions": dict(reversed(tuple(source.pin_functions.items()))),
            "component_symbols": dict(reversed(tuple(source.component_symbols.items()))),
        }
    )
    original = next(
        item for item in _report(source, mode="review").findings if item.rule_id == RULE_ID
    )
    repeated = next(
        item for item in _report(reordered, mode="review").findings if item.rule_id == RULE_ID
    )
    repaired = source.model_copy(update={"nets": {**source.nets, "UART_TX": ("J1.1", "U1.1")}})

    assert (repeated.fingerprint, repeated.evidence) == (original.fingerprint, original.evidence)
    assert not any(item.rule_id == RULE_ID for item in _report(repaired, mode="review").findings)
