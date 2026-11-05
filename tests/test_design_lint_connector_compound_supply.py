"""Regressions for compound connector supply pin-function heuristics."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.design_lint_finding_models import DesignLintFinding
from kicad_tooling.hwrepo.models import DesignLintPolicy, DesignLintReport, NetlistContract
from tests.design_lint_fixtures import coach, cross_symbol_power

pytestmark = [pytest.mark.design_lint, pytest.mark.connector_lint, pytest.mark.power_lint]

RULE_ID = "connector.repeated_pin_function"


def _report(source: NetlistContract) -> DesignLintReport:
    return evaluate("synthetic-compound-connector-supply", coach(source), DesignLintPolicy())


def _rule_findings(report: DesignLintReport) -> tuple[DesignLintFinding, ...]:
    return tuple(item for item in report.findings if item.rule_id == RULE_ID)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
@pytest.mark.parametrize(
    (
        "usb_function",
        "serial_function",
        "serial_connected",
        "expected_serial_nets",
        "expected_subject",
    ),
    [
        ("USB_VBUS", "SERIAL_VBUS", True, ("SERIAL_SUPPLY",), "USB_VBUS"),
        ("USB_VBUS", "VBUS", True, ("SERIAL_SUPPLY",), "USB_VBUS"),
        ("USB_3V3", "SERIAL_3.3V", True, ("SERIAL_SUPPLY",), "USB_3V3"),
        ("USB_+5V", "SERIAL_5V", False, (), "USB_+5V"),
    ],
    ids=("compound-vbus", "compound-to-exact-vbus", "voltage-aliases", "open-voltage-peer"),
)
def test_matching_compound_supply_categories_prompt_review(
    usb_function: str,
    serial_function: str,
    serial_connected: bool,
    expected_serial_nets: tuple[str, ...],
    expected_subject: str,
) -> None:
    report = _report(
        cross_symbol_power(
            serial_connected=serial_connected,
            usb_function=usb_function,
            serial_function=serial_function,
        )
    )

    findings = _rule_findings(report)
    assert report.status == "REVIEW"
    assert len(findings) == 1
    assert findings[0].subject == f"multiple connector symbols: {expected_subject}"
    assert findings[0].evidence == {
        "J1.1": ("USB_SUPPLY",),
        "J2.1": expected_serial_nets,
    }
    assert "Matching connector supply pins" in findings[0].message


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_matching_compound_supply_categories_on_one_net_are_a_control() -> None:
    report = _report(
        cross_symbol_power(
            common=True,
            usb_function="USB_VBUS",
            serial_function="SERIAL_VBUS",
        )
    )

    assert report.status == "PASS"
    assert not _rule_findings(report)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
@pytest.mark.parametrize(
    ("usb_function", "serial_function"),
    [
        ("USB_VBUS", "SERIAL_VCC"),
        ("USB_N_VBUS", "SERIAL_N_VBUS"),
        ("USB_VBUS_3V3", "SERIAL_VBUS_3V3"),
        ("USB_GND_VBUS", "SERIAL_GND_VBUS"),
        ("USB_SHIELD_VBUS", "SERIAL_SHIELD_VBUS"),
        ("USB_VBUS_SENSE", "SERIAL_VBUS_SENSE"),
        ("USB_VBUS", "SERIAL_VBUS_DETECT"),
        ("USB_VBUS", "SERIAL_VBUS_MONITOR"),
        ("USB_VBUS", "SERIAL_VBUS_FEEDBACK"),
        ("USB_VBUS", "SERIAL_VBUS_SWITCHED"),
        ("USB_VBUS", "SERIAL_VBUS_ENABLE"),
        ("USB_VBUS", "SERIAL_VBUS_STATUS"),
        ("USB_BUS", "SERIAL_BUS"),
    ],
    ids=(
        "distinct-rail",
        "negative-role",
        "multiple-rails",
        "mixed-return",
        "shield",
        "sense",
        "detect",
        "monitor",
        "feedback",
        "switch",
        "enable",
        "status",
        "substring-lookalike",
    ),
)
def test_compound_supply_heuristic_keeps_ambiguous_roles_quiet(
    usb_function: str, serial_function: str
) -> None:
    report = _report(
        cross_symbol_power(
            usb_function=usb_function,
            serial_function=serial_function,
        )
    )

    assert report.status == "PASS"
    assert not _rule_findings(report)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_compound_supply_finding_is_stable_under_mapping_order() -> None:
    source = cross_symbol_power(
        usb_function="USB_VBUS",
        serial_function="SERIAL_VBUS",
    )
    reordered = source.model_copy(
        update={
            "nets": dict(reversed(tuple(source.nets.items()))),
            "component_symbols": dict(reversed(tuple(source.component_symbols.items()))),
            "pin_functions": dict(reversed(tuple(source.pin_functions.items()))),
        }
    )
    first, second = _report(source), _report(reordered)

    def signature(
        report: DesignLintReport,
    ) -> tuple[tuple[str, str, tuple[tuple[str, tuple[str, ...]], ...]], ...]:
        return tuple(
            sorted(
                (
                    item.rule_id,
                    item.subject,
                    tuple(sorted(item.evidence.items())),
                )
                for item in _rule_findings(report)
            )
        )

    assert signature(first) == signature(second)
