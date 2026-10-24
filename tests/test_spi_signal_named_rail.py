"""Focused regressions for SPI signal pins assigned directly to named rails."""

from __future__ import annotations

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
from tests.design_lint_fixtures.spi_signal_named_rail import spi_signal_on_named_rail_netlist

RULE_ID = "bus.spi_signal_on_named_rail"

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.interface_lint,
    pytest.mark.design_lint_rule(rule_id=RULE_ID),
]


def _report(
    source: NetlistContract,
    policy: DesignLintPolicy | None = None,
) -> DesignLintReport:
    return evaluate(
        "synthetic-spi-signal-named-rail",
        coach(source),
        DesignLintPolicy() if policy is None else policy,
    )


@pytest.mark.parametrize(
    ("pin", "rail_name", "function", "pin_role", "channel", "rail_role"),
    (
        ("U1.1", "GND", "SPI1_SCK", "clock", "index1", "return-like"),
        ("U1.2", "+3V3", "SPI1_MOSI", "data_input", "index1", "supply-like"),
        ("U1.3", "0V PWM 2", "SPI1_MISO", "data_output", "index1", "return-like"),
        ("U1.4", "+5V", "SPI1_NSS", "chip_select", "index1", "supply-like"),
    ),
)
def test_spi_pin_assigned_to_named_rail_requests_review_with_exact_evidence(
    pin: str,
    rail_name: str,
    function: str,
    pin_role: str,
    channel: str,
    rail_role: str,
) -> None:
    report = _report(spi_signal_on_named_rail_netlist(rail_name=rail_name, pin=pin))
    finding = next(item for item in report.findings if item.rule_id == RULE_ID)

    assert report.status == "REVIEW"
    assert finding.subject == f"{pin}: {function} on {rail_role} net {rail_name}"
    assert finding.evidence == {
        "pin": (pin,),
        "pin_function": (function,),
        "pin_role": (pin_role,),
        "spi_channel": (channel,),
        "assigned_net": (rail_name,),
        "net_label_role_clue": (rail_role,),
        "component_pin_inventory": ("1", "2", "3", "4"),
    }
    assert "not proof of electrical potential" in finding.message
    assert "intentional rail strap" in finding.message


def test_neutral_labels_and_unsupported_spi_functions_are_quiet() -> None:
    source = spi_signal_on_named_rail_netlist(rail_name="CLOCK_A")
    unsupported_function = source.model_copy(
        update={"pin_functions": {**source.pin_functions, "U1.1": "SPI1_TX"}}
    )
    incomplete_inventory = source.model_copy(
        update={"component_pin_numbers": {"U1": ("2", "3", "4")}}
    )
    connector = source.model_copy(
        update={
            "components": {"J1": source.components["U1"]},
            "nets": {"GND": ("J1.1",), "SPI1_CS": ("J1.4",)},
            "component_symbols": {"J1": "Connector_Generic:Conn_01x04"},
            "pin_functions": {
                f"J1.{index}": function
                for index, function in enumerate(source.pin_functions.values(), 1)
            },
            "component_pin_numbers": {"J1": ("1", "2", "3", "4")},
        }
    )
    non_spi_signal = source.model_copy(
        update={"pin_functions": {**source.pin_functions, "U1.1": "GPIO1"}}
    )

    for control in (source, unsupported_function, incomplete_inventory, connector, non_spi_signal):
        assert not any(item.rule_id == RULE_ID for item in _report(control).findings)


def test_dnp_open_ambiguous_and_duplicate_pin_metadata_are_skipped() -> None:
    source = spi_signal_on_named_rail_netlist()
    dnp = source.model_copy(update={"dnp_components": ("U1",)})
    open_pin = source.model_copy(update={"nets": {"SPI1_MOSI": ("U1.2",)}})
    ambiguous = source.model_copy(update={"nets": {**source.nets, "0V": ("U1.1",)}})
    incomplete_functions = source.model_copy(
        update={"pin_functions": {"U1.1": "SPI1_SCK", "u1.1": "SPI1_MOSI"}}
    )

    for control in (dnp, open_pin, ambiguous, incomplete_functions):
        assert not any(item.rule_id == RULE_ID for item in _report(control).findings)


def test_chip_select_rail_strap_can_be_disabled_or_ignored_exactly() -> None:
    source = spi_signal_on_named_rail_netlist(rail_name="+3V3", pin="U1.4")
    review = _report(source)
    finding = next(item for item in review.findings if item.rule_id == RULE_ID)
    off = _report(
        source,
        DesignLintPolicy(
            rules=(DesignLintRuleOverride(rule_id=RULE_ID, mode="off", reason="test policy"),)
        ),
    )
    blocked = _report(
        source,
        DesignLintPolicy(
            rules=(DesignLintRuleOverride(rule_id=RULE_ID, mode="block", reason="test policy"),)
        ),
    )
    ignored = _report(
        source,
        DesignLintPolicy(
            ignores=(
                DesignLintIgnore(
                    rule_id=RULE_ID,
                    fingerprint=finding.fingerprint,
                    reason="This chip select is intentionally strapped inactive",
                ),
            )
        ),
    )

    assert finding.subject.startswith("U1.4: SPI1_NSS")
    assert "intentional rail strap" in finding.message
    assert blocked.status == "FAIL"
    assert next(item for item in off.findings if item.rule_id == RULE_ID).disposition == "RULE_OFF"
    assert (
        next(item for item in ignored.findings if item.rule_id == RULE_ID).disposition == "IGNORED"
    )


def test_mapping_order_is_stable_and_repaired_assignment_clears_review() -> None:
    fault = spi_signal_on_named_rail_netlist()
    reordered = fault.model_copy(
        update={
            "nets": dict(reversed(tuple(fault.nets.items()))),
            "pin_functions": dict(reversed(tuple(fault.pin_functions.items()))),
        }
    )
    repaired = fault.model_copy(
        update={
            "nets": {"SPI1_SCK": ("U1.1",), **{k: v for k, v in fault.nets.items() if k != "GND"}}
        }
    )
    findings = tuple(item for item in _report(fault).findings if item.rule_id == RULE_ID)
    reordered_findings = tuple(
        item for item in _report(reordered).findings if item.rule_id == RULE_ID
    )

    assert tuple(item.model_dump() for item in findings) == tuple(
        item.model_dump() for item in reordered_findings
    )
    assert not any(item.rule_id == RULE_ID for item in _report(repaired).findings)
