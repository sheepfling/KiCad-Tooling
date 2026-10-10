"""Focused synthetic regressions for the serial peer voltage lint theme."""

from __future__ import annotations

import unittest

import pytest

from kicad_tooling.hwrepo.design_lint import (
    candidates,
    evaluate,
    fingerprint,
)
from kicad_tooling.hwrepo.design_lint_peer_candidates import DigitalPeerVoltageLintContext
from kicad_tooling.hwrepo.models import (
    DesignLintIgnore,
    DesignLintPolicy,
    DesignLintRuleOverride,
)
from tests.design_lint_fixtures import (
    coach,
    serial_peer_voltage_map,
    serial_peer_voltage_netlist,
    serial_peer_voltage_translator_netlist,
)

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.interface_lint,
]


class DesignLintSerialPeerVoltageTests(unittest.TestCase):
    def test_serial_peer_voltage_prompt_requires_matching_role_and_unambiguous_native_evidence(
        self,
    ) -> None:
        source = serial_peer_voltage_netlist()
        findings = [
            item for item in candidates(source) if item.rule_id == "bus.serial_peer_voltage_review"
        ]
        self.assertEqual(len(findings), 1)
        finding = findings[0]
        self.assertEqual(finding.subject, "U1 -> U2: serial voltage-domain review")
        self.assertEqual(finding.evidence["output_supply_net"], ("+5V",))
        self.assertEqual(finding.evidence["output_supply_label_value"], ("5 V",))
        self.assertEqual(finding.evidence["input_supply_net"], ("+3V3",))
        self.assertEqual(finding.evidence["input_supply_label_value"], ("3.3 V",))
        self.assertEqual(
            finding.evidence["shared_serial_pin_assignments"],
            ("UART_TX: U1.1 (UART1_TX, output) -> U2.1 (UART1_RX, input)",),
        )
        self.assertIn("does not establish incompatibility", finding.message)

        controls = {
            "same rail": serial_peer_voltage_netlist(output_rail="+3V3", input_rail="+3V3"),
            "level-translated TX path": serial_peer_voltage_translator_netlist(),
            "DNP receiver": serial_peer_voltage_netlist(dnp=("U2",)),
            "missing native pin types": serial_peer_voltage_netlist(missing_pin_types=True),
            "unconnected receiver supply": serial_peer_voltage_netlist(
                unconnected_input_supply=True
            ),
            "multiple receiver supplies": serial_peer_voltage_netlist(input_extra_supply=True),
            "TX function on receiver": serial_peer_voltage_netlist(input_function="UART1_TX"),
            "RX function on driver": serial_peer_voltage_netlist(output_function="UART1_RX"),
            "input-only TX": serial_peer_voltage_netlist(output_type="input"),
            "open-collector TX": serial_peer_voltage_netlist(output_type="open_collector"),
            "negative supply": serial_peer_voltage_netlist(output_rail="-5V"),
            "ambiguous supply": serial_peer_voltage_netlist(output_rail="SUPPLY_5V_1V8"),
        }
        for label, control in controls.items():
            with self.subTest(control=label):
                self.assertNotIn(
                    "bus.serial_peer_voltage_review",
                    {item.rule_id for item in candidates(control)},
                )

    def test_serial_peer_voltage_prompt_suppresses_only_exact_fully_mapped_links(self) -> None:
        source = serial_peer_voltage_netlist()
        incomplete = serial_peer_voltage_map(with_limits=False)
        still_open = [
            item
            for item in candidates(
                source,
                digital_peer_voltage_context=DigitalPeerVoltageLintContext(
                    state="required", analysis=incomplete
                ),
            )
            if item.rule_id == "bus.serial_peer_voltage_review"
        ]
        self.assertEqual(len(still_open), 1)

        mapped = serial_peer_voltage_map()
        self.assertNotIn(
            "bus.serial_peer_voltage_review",
            {
                item.rule_id
                for item in candidates(
                    source,
                    digital_peer_voltage_context=DigitalPeerVoltageLintContext(
                        state="required", analysis=mapped
                    ),
                )
            },
        )

        stale_link = mapped.links[0].model_copy(
            update={
                "receiver": mapped.links[0].receiver.model_copy(update={"footprint": "Other:Part"})
            }
        )
        stale_map = mapped.model_copy(update={"links": (stale_link,)})
        self.assertIn(
            "bus.serial_peer_voltage_review",
            {
                item.rule_id
                for item in candidates(
                    source,
                    digital_peer_voltage_context=DigitalPeerVoltageLintContext(
                        state="required", analysis=stale_map
                    ),
                )
            },
        )

    def test_serial_peer_voltage_prompt_is_stable_and_project_configurable(self) -> None:
        source = serial_peer_voltage_netlist()
        reordered = source.model_copy(
            update={
                "nets": dict(reversed(tuple(source.nets.items()))),
                "pin_functions": dict(reversed(tuple(source.pin_functions.items()))),
                "pin_electrical_types": dict(reversed(tuple(source.pin_electrical_types.items()))),
                "component_pin_numbers": {
                    reference: tuple(reversed(numbers))
                    for reference, numbers in source.component_pin_numbers.items()
                },
            }
        )
        initial = next(
            item for item in candidates(source) if item.rule_id == "bus.serial_peer_voltage_review"
        )
        reordered_finding = next(
            item
            for item in candidates(reordered)
            if item.rule_id == "bus.serial_peer_voltage_review"
        )
        self.assertEqual(fingerprint(initial), fingerprint(reordered_finding))

        default = evaluate("serial-voltage", coach(source), DesignLintPolicy())
        finding = next(
            item for item in default.findings if item.rule_id == "bus.serial_peer_voltage_review"
        )
        self.assertEqual(
            (default.status, finding.mode, finding.disposition), ("REVIEW", "review", "OPEN")
        )

        off = evaluate(
            "serial-voltage",
            coach(source),
            DesignLintPolicy(
                rules=(
                    DesignLintRuleOverride(
                        rule_id="bus.serial_peer_voltage_review",
                        mode="off",
                        reason="Synthetic owner decision disables this review prompt",
                    ),
                )
            ),
        )
        off_finding = next(
            item for item in off.findings if item.rule_id == "bus.serial_peer_voltage_review"
        )
        self.assertEqual(off_finding.disposition, "RULE_OFF")

        blocked = evaluate(
            "serial-voltage",
            coach(source),
            DesignLintPolicy(
                rules=(
                    DesignLintRuleOverride(
                        rule_id="bus.serial_peer_voltage_review",
                        mode="block",
                        reason="Synthetic owner decision explicitly escalates this prompt",
                    ),
                )
            ),
        )
        self.assertEqual(blocked.status, "FAIL")

        ignored = evaluate(
            "serial-voltage",
            coach(source),
            DesignLintPolicy(
                ignores=(
                    DesignLintIgnore(
                        rule_id=finding.rule_id,
                        fingerprint=finding.fingerprint,
                        reason="Synthetic exact reviewed rail pair",
                    ),
                )
            ),
        )
        ignored_finding = next(
            item for item in ignored.findings if item.rule_id == "bus.serial_peer_voltage_review"
        )
        self.assertEqual(ignored_finding.disposition, "IGNORED")
