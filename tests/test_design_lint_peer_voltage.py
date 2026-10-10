"""Focused synthetic regressions for the peer voltage lint theme."""

from __future__ import annotations

import unittest

import pytest

from kicad_tooling.hwrepo.design_lint import (
    candidates,
    evaluate,
    fingerprint,
    text_report,
)
from kicad_tooling.hwrepo.design_lint_peer_candidates import DigitalPeerVoltageLintContext
from kicad_tooling.hwrepo.models import (
    DesignLintIgnore,
    DesignLintPolicy,
    DesignLintRuleOverride,
)
from tests.design_lint_fixtures import (
    coach,
    header_only_spi_uart_netlist,
    serial_peer_voltage_map,
    serial_peer_voltage_netlist,
    spi_peer_voltage_map,
    spi_peer_voltage_netlist,
)

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.interface_lint,
]


class DesignLintPeerVoltageTests(unittest.TestCase):
    def test_spi_peer_voltage_prompt_requires_unambiguous_native_evidence(self) -> None:
        source = spi_peer_voltage_netlist()
        findings = [
            item for item in candidates(source) if item.rule_id == "bus.spi_peer_voltage_review"
        ]
        self.assertEqual(len(findings), 1)
        finding = findings[0]
        self.assertEqual(
            finding.subject,
            "U1 -> U2: SPI voltage-domain review",
        )
        self.assertEqual(finding.evidence["output_supply_net"], ("+5V",))
        self.assertEqual(finding.evidence["output_supply_label_value"], ("5 V",))
        self.assertEqual(finding.evidence["input_supply_net"], ("+3V3",))
        self.assertEqual(finding.evidence["input_supply_label_value"], ("3.3 V",))
        self.assertEqual(len(finding.evidence["shared_SPI_pin_assignments"]), 2)
        self.assertIn("does not establish incompatibility", finding.message)

        controls = {
            "same named rail": spi_peer_voltage_netlist(output_rail="+3V3", input_rail="+3V3"),
            "DNP receiver": spi_peer_voltage_netlist(dnp=("U2",)),
            "missing native pin types": spi_peer_voltage_netlist(missing_pin_types=True),
            "unconnected receiver supply": spi_peer_voltage_netlist(unconnected_input_supply=True),
            "multiple receiver supplies": spi_peer_voltage_netlist(input_extra_supply=True),
            "level-shifted peer path": spi_peer_voltage_netlist(level_shifted=True),
            "unrecognized signal functions": spi_peer_voltage_netlist(
                all_signal_function="ANALOG_IN"
            ),
            "open-collector signal": spi_peer_voltage_netlist(output_type="open_collector"),
            "input-only peers": spi_peer_voltage_netlist(output_type="input"),
            "negative supply label": spi_peer_voltage_netlist(output_rail="-5V"),
            "ambiguous supply label": spi_peer_voltage_netlist(output_rail="SUPPLY_5V_1V8"),
        }
        for label, control in controls.items():
            with self.subTest(control=label):
                self.assertNotIn(
                    "bus.spi_peer_voltage_review",
                    {item.rule_id for item in candidates(control)},
                )

    def test_peer_voltage_coverage_distinguishes_evaluated_and_incomplete_scope(self) -> None:
        fault = evaluate("peer-voltage", coach(spi_peer_voltage_netlist()), DesignLintPolicy())
        spi = next(
            item
            for item in fault.digital_peer_voltage_coverage
            if item.rule_id == "bus.spi_peer_voltage_review"
        )
        self.assertEqual(
            (
                spi.status,
                spi.recognized_endpoint_count,
                spi.assigned_endpoint_count,
                spi.direct_peer_link_count,
                spi.voltage_comparison_count,
                spi.same_voltage_link_count,
                spi.different_voltage_link_count,
                spi.candidate_group_count,
            ),
            ("EVALUATED", 4, 4, 2, 2, 0, 2, 1),
        )

        same_rail = evaluate(
            "peer-voltage",
            coach(spi_peer_voltage_netlist(output_rail="+3V3", input_rail="+3V3")),
            DesignLintPolicy(),
        )
        same_rail_spi = next(
            item
            for item in same_rail.digital_peer_voltage_coverage
            if item.rule_id == "bus.spi_peer_voltage_review"
        )
        self.assertEqual(
            (
                same_rail_spi.status,
                same_rail_spi.voltage_comparison_count,
                same_rail_spi.same_voltage_link_count,
                same_rail_spi.different_voltage_link_count,
                same_rail_spi.candidate_group_count,
            ),
            ("EVALUATED", 2, 2, 0, 0),
        )

        incomplete = evaluate(
            "peer-voltage",
            coach(spi_peer_voltage_netlist(missing_pin_types=True)),
            DesignLintPolicy(),
        )
        incomplete_spi = next(
            item
            for item in incomplete.digital_peer_voltage_coverage
            if item.rule_id == "bus.spi_peer_voltage_review"
        )
        self.assertEqual(
            (
                incomplete_spi.status,
                incomplete_spi.recognized_endpoint_count,
                incomplete_spi.assigned_endpoint_count,
                incomplete_spi.direct_peer_link_count,
            ),
            ("INCOMPLETE", 4, 0, 0),
        )

        unsupported = evaluate(
            "peer-voltage",
            coach(spi_peer_voltage_netlist(all_signal_function="ANALOG_IN")),
            DesignLintPolicy(),
        )
        unsupported_spi = next(
            item
            for item in unsupported.digital_peer_voltage_coverage
            if item.rule_id == "bus.spi_peer_voltage_review"
        )
        self.assertEqual(unsupported_spi.status, "NO_SUPPORTED_ENDPOINTS")

        mapped = evaluate(
            "peer-voltage",
            coach(serial_peer_voltage_netlist()),
            DesignLintPolicy(),
            digital_peer_voltage_context=DigitalPeerVoltageLintContext(
                state="required",
                analysis=serial_peer_voltage_map(),
            ),
        )
        mapped_serial = next(
            item
            for item in mapped.digital_peer_voltage_coverage
            if item.rule_id == "bus.serial_peer_voltage_review"
        )
        self.assertEqual(
            (
                mapped_serial.status,
                mapped_serial.authored_map_state,
                mapped_serial.direct_peer_link_count,
                mapped_serial.voltage_comparison_count,
                mapped_serial.different_voltage_link_count,
                mapped_serial.mapped_mismatch_link_count,
                mapped_serial.candidate_group_count,
            ),
            ("EVALUATED", "required", 1, 1, 1, 1, 0),
        )

        report_text = text_report(fault)
        self.assertIn("Direct SPI/UART peer-voltage heuristic coverage:", report_text)
        self.assertIn("2 voltage comparison(s)", report_text)

    def test_spi_peer_voltage_prompt_suppresses_translator_separated_paths(self) -> None:
        source = spi_peer_voltage_netlist(level_shifted=True)

        self.assertEqual(source.nets["SPI_SCK_CONTROLLER"], ("U1.1", "U3.1"))
        self.assertEqual(source.nets["SPI_SCK_PERIPHERAL"], ("U3.2", "U2.1"))
        self.assertEqual(source.nets["+5V"], ("U1.8", "U3.5"))
        self.assertEqual(source.nets["+3V3"], ("U2.8", "U3.6"))
        self.assertNotIn(
            "bus.spi_peer_voltage_review",
            {item.rule_id for item in candidates(source)},
        )

    def test_peer_voltage_coverage_excludes_header_only_spi_and_uart_endpoints(self) -> None:
        external_interfaces = header_only_spi_uart_netlist()

        report = evaluate(
            "synthetic-external-buses", coach(external_interfaces), DesignLintPolicy()
        )
        peer_coverage = {item.rule_id: item for item in report.digital_peer_voltage_coverage}
        self.assertEqual(
            {
                rule_id: (
                    item.status,
                    item.recognized_endpoint_count,
                    item.direct_peer_link_count,
                    item.voltage_comparison_count,
                    item.candidate_group_count,
                )
                for rule_id, item in peer_coverage.items()
            },
            {
                "bus.spi_peer_voltage_review": ("NO_SUPPORTED_ENDPOINTS", 0, 0, 0, 0),
                "bus.serial_peer_voltage_review": ("NO_SUPPORTED_ENDPOINTS", 0, 0, 0, 0),
            },
        )
        self.assertEqual(
            {
                item.rule_id
                for item in report.findings
                if item.rule_id in {"bus.spi_peer_voltage_review", "bus.serial_peer_voltage_review"}
            },
            set(),
        )

    def test_spi_peer_voltage_prompt_suppresses_only_exact_fully_mapped_links(self) -> None:
        source = spi_peer_voltage_netlist()
        incomplete = spi_peer_voltage_map(with_limits=False)
        still_open = [
            item
            for item in candidates(
                source,
                digital_peer_voltage_context=DigitalPeerVoltageLintContext(
                    state="required", analysis=incomplete
                ),
            )
            if item.rule_id == "bus.spi_peer_voltage_review"
        ]
        self.assertEqual(len(still_open), 1)
        self.assertEqual(len(still_open[0].evidence["shared_SPI_pin_assignments"]), 2)

        one_mapped = spi_peer_voltage_map()
        remaining = [
            item
            for item in candidates(
                source,
                digital_peer_voltage_context=DigitalPeerVoltageLintContext(
                    state="required", analysis=one_mapped
                ),
            )
            if item.rule_id == "bus.spi_peer_voltage_review"
        ]
        self.assertEqual(len(remaining), 1)
        self.assertEqual(
            remaining[0].evidence["shared_SPI_pin_assignments"],
            ("SPI_MOSI: U1.2 (MOSI, output) -> U2.2 (MOSI, input)",),
        )

        all_mapped = spi_peer_voltage_map(
            (("U1.1", "U2.1"), ("U1.2", "U2.2")),
            receiver_absolute_maximum_v=5.5,
        )
        self.assertNotIn(
            "bus.spi_peer_voltage_review",
            {
                item.rule_id
                for item in candidates(
                    source,
                    digital_peer_voltage_context=DigitalPeerVoltageLintContext(
                        state="required", analysis=all_mapped
                    ),
                )
            },
        )

        stale_link = one_mapped.links[0].model_copy(
            update={
                "receiver": one_mapped.links[0].receiver.model_copy(
                    update={"footprint": "Other:Part"}
                )
            }
        )
        stale_map = one_mapped.model_copy(update={"links": (stale_link,)})
        self.assertIn(
            "bus.spi_peer_voltage_review",
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

    def test_spi_peer_voltage_prompt_is_stable_and_project_configurable(self) -> None:
        source = spi_peer_voltage_netlist()
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
            item for item in candidates(source) if item.rule_id == "bus.spi_peer_voltage_review"
        )
        reordered_finding = next(
            item for item in candidates(reordered) if item.rule_id == "bus.spi_peer_voltage_review"
        )
        self.assertEqual(fingerprint(initial), fingerprint(reordered_finding))

        default = evaluate("spi-voltage", coach(source), DesignLintPolicy())
        open_finding = next(
            item for item in default.findings if item.rule_id == "bus.spi_peer_voltage_review"
        )
        self.assertEqual(
            (default.status, open_finding.mode, open_finding.disposition),
            ("REVIEW", "review", "OPEN"),
        )

        off_policy = DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id="bus.spi_peer_voltage_review",
                    mode="off",
                    reason="This synthetic project explicitly accepts rail-name prompts as inapplicable",
                ),
            )
        )
        off = evaluate("spi-voltage", coach(source), off_policy)
        off_finding = next(
            item for item in off.findings if item.rule_id == "bus.spi_peer_voltage_review"
        )
        self.assertEqual(off_finding.disposition, "RULE_OFF")

        block_policy = DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id="bus.spi_peer_voltage_review",
                    mode="block",
                    reason="Synthetic project illustrates explicit owner escalation",
                ),
            )
        )
        blocked = evaluate("spi-voltage", coach(source), block_policy)
        self.assertEqual(blocked.status, "FAIL")

        ignored_policy = DesignLintPolicy(
            ignores=(
                DesignLintIgnore(
                    rule_id=open_finding.rule_id,
                    fingerprint=open_finding.fingerprint,
                    reason="Synthetic control records this exact reviewed rail pair",
                ),
            )
        )
        ignored = evaluate("spi-voltage", coach(source), ignored_policy)
        ignored_finding = next(
            item for item in ignored.findings if item.rule_id == "bus.spi_peer_voltage_review"
        )
        self.assertEqual(ignored_finding.disposition, "IGNORED")
