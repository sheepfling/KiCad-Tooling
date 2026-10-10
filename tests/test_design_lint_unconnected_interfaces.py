"""Focused synthetic regressions for the unconnected interfaces lint theme."""

from __future__ import annotations

import unittest

import pytest

from kicad_tooling.hwrepo.design_lint import (
    evaluate,
)
from kicad_tooling.hwrepo.models import (
    DesignLintPolicy,
    DesignLintReport,
)
from tests.design_lint_fixtures import (
    can_netlist,
    coach,
    unconnected_protocol_pins,
)

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.interface_lint,
]


class DesignLintUnconnectedInterfaceTests(unittest.TestCase):
    def test_unconnected_i2c_spi_and_usb_c_control_pins_are_distinct_review_rules(self) -> None:
        report = evaluate(
            "synthetic-interfaces", coach(unconnected_protocol_pins()), DesignLintPolicy()
        )
        self.assertEqual(report.status, "REVIEW")
        self.assertEqual(
            {item.rule_id for item in report.findings},
            {
                "bus.i2c_unconnected_pin",
                "bus.spi_unconnected_chip_select",
                "bus.usb_c_unconnected_cc_pin",
            },
        )
        self.assertEqual(
            {item.subject for item in report.findings},
            {
                "U1.1: SDA",
                "U1.2: I2C_SCL",
                "U2.1: CS_N",
                "J1.1: CC1",
                "J1.2: CC2",
            },
        )

        assigned = unconnected_protocol_pins().model_copy(
            update={
                "nets": {
                    "I2C_SDA": ("U1.1",),
                    "I2C_SCL": ("U1.2",),
                    "SPI_CS": ("U2.1",),
                    "USB_CC1": ("J1.1",),
                    "USB_CC2": ("J1.2",),
                }
            }
        )
        connected = evaluate("synthetic-interfaces", coach(assigned), DesignLintPolicy())
        self.assertEqual(
            {item.rule_id for item in connected.findings},
            {"bus.i2c_missing_pullup", "bus.i2c_unmapped_responder"},
        )

    def test_unconnected_protocol_pin_candidates_are_order_stable_and_clear_individually(
        self,
    ) -> None:
        base = unconnected_protocol_pins()
        source = base.model_copy(
            update={
                "nets": {
                    "CONTROL_GPIO": ("U1.3",),
                    "SPI_DATA": ("U2.2",),
                },
                "pin_functions": {
                    **base.pin_functions,
                    "U1.3": "GPIO",
                    "U2.2": "MISO",
                },
            }
        )
        target_rules = {
            "bus.i2c_unconnected_pin",
            "bus.spi_unconnected_chip_select",
            "bus.usb_c_unconnected_cc_pin",
        }
        original = evaluate("synthetic-interfaces", coach(source), DesignLintPolicy())
        reordered_source = source.model_copy(
            update={
                "nets": dict(reversed(tuple(source.nets.items()))),
                "component_symbols": dict(reversed(tuple(source.component_symbols.items()))),
                "pin_functions": dict(reversed(tuple(source.pin_functions.items()))),
            }
        )
        reordered = evaluate("synthetic-interfaces", coach(reordered_source), DesignLintPolicy())

        def selected_findings(
            report: DesignLintReport,
        ) -> dict[str, tuple[str, str, dict[str, tuple[str, ...]]]]:
            return {
                item.subject: (item.rule_id, item.fingerprint, item.evidence)
                for item in report.findings
                if item.rule_id in target_rules
            }

        original_findings = selected_findings(original)
        self.assertEqual(len(original_findings), 5)
        self.assertEqual(selected_findings(reordered), original_findings)

        for subject, original_finding in original_findings.items():
            pin = subject.split(":", maxsplit=1)[0]
            assigned = source.model_copy(
                update={
                    "nets": {
                        **source.nets,
                        f"ASSIGNED_{pin.replace('.', '_')}": (pin,),
                    }
                }
            )
            assigned_report = evaluate("synthetic-interfaces", coach(assigned), DesignLintPolicy())
            expected = dict(original_findings)
            del expected[subject]
            self.assertEqual(selected_findings(assigned_report), expected, original_finding)

    def test_unconnected_can_lines_are_order_stable_and_each_assignment_clears_one(self) -> None:
        base = can_netlist()
        source = base.model_copy(
            update={
                "nets": {
                    "CAN_DIAGNOSTIC": ("U1.3",),
                    "CAN_ENABLE": ("U1.4",),
                },
                "pin_functions": {
                    **base.pin_functions,
                    "U1.3": "TXD",
                    "U1.4": "STATUS",
                },
            }
        )
        original = evaluate("synthetic-can", coach(source), DesignLintPolicy())
        rule_id = "bus.can_unconnected_line"
        original_findings = {
            item.subject: (item.fingerprint, item.evidence)
            for item in original.findings
            if item.rule_id == rule_id
        }
        reordered_source = source.model_copy(
            update={
                "components": dict(reversed(tuple(source.components.items()))),
                "nets": dict(reversed(tuple(source.nets.items()))),
                "component_symbols": dict(reversed(tuple(source.component_symbols.items()))),
                "pin_functions": dict(reversed(tuple(source.pin_functions.items()))),
            }
        )
        reordered = evaluate("synthetic-can", coach(reordered_source), DesignLintPolicy())
        reordered_findings = {
            item.subject: (item.fingerprint, item.evidence)
            for item in reordered.findings
            if item.rule_id == rule_id
        }
        self.assertEqual(len(original_findings), 2)
        self.assertEqual(reordered_findings, original_findings)

        for subject, original_finding in original_findings.items():
            pin = subject.split(":", maxsplit=1)[0]
            assigned = source.model_copy(
                update={
                    "nets": {
                        **source.nets,
                        f"ASSIGNED_{pin.replace('.', '_')}": (pin,),
                    }
                }
            )
            assigned_report = evaluate("synthetic-can", coach(assigned), DesignLintPolicy())
            remaining_findings = {
                item.subject: (item.fingerprint, item.evidence)
                for item in assigned_report.findings
                if item.rule_id == rule_id
            }
            expected = dict(original_findings)
            del expected[subject]
            self.assertEqual(remaining_findings, expected, original_finding)
