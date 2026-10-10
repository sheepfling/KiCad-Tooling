"""Focused synthetic regressions for the i2c lint theme."""

from __future__ import annotations

import unittest

import pytest

from kicad_tooling.hwrepo.design_lint import (
    candidates,
    evaluate,
    fingerprint,
)
from kicad_tooling.hwrepo.models import (
    DesignLintFinding,
    DesignLintIgnore,
    DesignLintPolicy,
    DesignLintReport,
    DesignLintRuleOverride,
)
from tests.design_lint_fixtures import (
    coach,
    i2c_netlist,
    i2c_netlist_with_parallel_sda,
    i2c_netlist_with_pullup_rails,
    i2c_netlist_with_series_sda,
    policy_without_i2c_map_prompt,
)

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.interface_lint,
]


class DesignLintI2cTests(unittest.TestCase):
    def test_i2c_pullup_hint_detects_missing_or_invalid_local_resistors(self) -> None:
        policy = policy_without_i2c_map_prompt()
        report = evaluate("synthetic-i2c", coach(i2c_netlist()), policy)
        self.assertEqual(report.status, "REVIEW")
        open_findings = [item for item in report.findings if item.disposition == "OPEN"]
        self.assertEqual(len(open_findings), 1)
        finding = open_findings[0]
        self.assertEqual(finding.rule_id, "bus.i2c_missing_pullup")
        self.assertEqual(finding.evidence["missing_pullups"], ("SDA", "SCL"))
        self.assertIn("internal or off-board pull-ups", finding.message)

        one_line = evaluate("synthetic-i2c", coach(i2c_netlist(pullups=("SDA",))), policy)
        one_line_finding = next(item for item in one_line.findings if item.disposition == "OPEN")
        self.assertEqual(one_line_finding.evidence["missing_pullups"], ("SCL",))

        connected = evaluate(
            "synthetic-i2c",
            coach(i2c_netlist(pullups=("SDA", "SCL"), resistance="4k7")),
            policy,
        )
        self.assertEqual(connected.status, "PASS")
        self.assertFalse([item for item in connected.findings if item.disposition == "OPEN"])

        for boundary in ("1k", "100k"):
            with self.subTest(resistance_boundary=boundary):
                boundary_report = evaluate(
                    "synthetic-i2c",
                    coach(i2c_netlist(pullups=("SDA", "SCL"), resistance=boundary)),
                    policy,
                )
                self.assertEqual(boundary_report.status, "PASS")
                self.assertFalse(
                    [item for item in boundary_report.findings if item.disposition == "OPEN"]
                )

        unpopulated_pullups = i2c_netlist(pullups=("SDA", "SCL")).model_copy(
            update={"dnp_components": ("R1", "R2")}
        )
        dnp_report = evaluate("synthetic-i2c", coach(unpopulated_pullups), policy)
        self.assertEqual(dnp_report.status, "REVIEW")
        dnp_finding = next(item for item in dnp_report.findings if item.disposition == "OPEN")
        self.assertEqual(dnp_finding.rule_id, "bus.i2c_missing_pullup")
        self.assertEqual(dnp_finding.evidence["missing_pullups"], ("SDA", "SCL"))

        invalid_value = evaluate(
            "synthetic-i2c",
            coach(i2c_netlist(pullups=("SDA", "SCL"), resistance="0R")),
            policy,
        )
        self.assertEqual(invalid_value.status, "REVIEW")
        invalid_finding = next(
            item for item in invalid_value.findings if item.disposition == "OPEN"
        )
        self.assertEqual(invalid_finding.evidence["missing_pullups"], ("SDA", "SCL"))

        negative_rail = evaluate(
            "synthetic-i2c",
            coach(i2c_netlist(pullups=("SDA", "SCL"), rail="-5V")),
            policy,
        )
        self.assertEqual(negative_rail.status, "REVIEW")

    def test_i2c_missing_pullup_is_order_stable_and_tracks_each_line_path(self) -> None:
        policy = policy_without_i2c_map_prompt()
        source = i2c_netlist()
        original = evaluate("synthetic-i2c", coach(source), policy)
        reordered_source = source.model_copy(
            update={
                "nets": dict(reversed(tuple(source.nets.items()))),
                "pin_functions": dict(reversed(tuple(source.pin_functions.items()))),
            }
        )
        reordered = evaluate("synthetic-i2c", coach(reordered_source), policy)

        def finding_for(report: DesignLintReport) -> DesignLintFinding:
            return next(
                item for item in report.findings if item.rule_id == "bus.i2c_missing_pullup"
            )

        original_finding = finding_for(original)
        reordered_finding = finding_for(reordered)
        self.assertEqual(
            (reordered_finding.fingerprint, reordered_finding.evidence),
            (original_finding.fingerprint, original_finding.evidence),
        )
        self.assertEqual(original_finding.evidence["missing_pullups"], ("SDA", "SCL"))

        for connected_line, remaining_line in (("SDA", "SCL"), ("SCL", "SDA")):
            with self.subTest(connected_line=connected_line):
                partial = evaluate(
                    "synthetic-i2c",
                    coach(i2c_netlist(pullups=(connected_line,))),
                    policy,
                )
                finding = finding_for(partial)
                self.assertEqual(finding.evidence["missing_pullups"], (remaining_line,))

        complete = evaluate(
            "synthetic-i2c",
            coach(i2c_netlist(pullups=("SDA", "SCL"), resistance="4k7")),
            policy,
        )
        self.assertNotIn("bus.i2c_missing_pullup", {item.rule_id for item in complete.findings})

    def test_i2c_series_pullup_paths_are_bounded_and_unbranched(self) -> None:
        policy = policy_without_i2c_map_prompt()
        series_control = evaluate(
            "synthetic-i2c",
            coach(i2c_netlist_with_series_sda()),
            policy,
        )
        self.assertEqual(series_control.status, "PASS")
        self.assertFalse([item for item in series_control.findings if item.disposition == "OPEN"])

        too_weak = evaluate(
            "synthetic-i2c",
            coach(i2c_netlist_with_series_sda("56k", "56k")),
            policy,
        )
        too_weak_findings = [item for item in too_weak.findings if item.disposition == "OPEN"]
        self.assertEqual(len(too_weak_findings), 1)
        self.assertEqual(too_weak_findings[0].rule_id, "bus.i2c_missing_pullup")
        self.assertEqual(too_weak_findings[0].evidence["missing_pullups"], ("SDA",))

        branched = evaluate(
            "synthetic-i2c",
            coach(i2c_netlist_with_series_sda(branched_junction=True)),
            policy,
        )
        branched_findings = [item for item in branched.findings if item.disposition == "OPEN"]
        self.assertEqual(len(branched_findings), 1)
        self.assertEqual(branched_findings[0].rule_id, "bus.i2c_missing_pullup")
        self.assertEqual(branched_findings[0].evidence["missing_pullups"], ("SDA",))

        dnp = i2c_netlist_with_series_sda().model_copy(update={"dnp_components": ("R4",)})
        unpopulated = evaluate("synthetic-i2c", coach(dnp), policy)
        unpopulated_findings = [item for item in unpopulated.findings if item.disposition == "OPEN"]
        self.assertEqual(len(unpopulated_findings), 1)
        self.assertEqual(unpopulated_findings[0].evidence["missing_pullups"], ("SDA",))

    def test_i2c_pullup_hint_can_be_configured_per_project(self) -> None:
        report = evaluate(
            "synthetic-i2c",
            coach(i2c_netlist()),
            DesignLintPolicy(
                rules=(
                    DesignLintRuleOverride(
                        rule_id="bus.i2c_missing_pullup",
                        mode="block",
                        reason="Every local I2C bus requires reviewed pull-up evidence",
                    ),
                ),
            ),
        )
        self.assertEqual(report.status, "FAIL")

    def test_i2c_parallel_pullups_are_reviewed_by_nominal_equivalent_resistance(self) -> None:
        low_resistance = evaluate(
            "synthetic-i2c",
            coach(i2c_netlist_with_parallel_sda()),
            DesignLintPolicy(),
        )
        findings = [
            item
            for item in low_resistance.findings
            if item.rule_id == "bus.i2c_low_equivalent_resistance"
        ]
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].evidence["lines"], ("SDA",))
        self.assertEqual(findings[0].evidence["equivalent_ohms"], ("SDA=500Ω",))
        self.assertEqual(
            findings[0].evidence["pullup_resistors"],
            ("R1=1000Ω to +3V3", "R3=1000Ω to +3V3"),
        )

        ordered = i2c_netlist_with_parallel_sda(parallel_resistance="1k5")
        reordered = ordered.model_copy(
            update={"components": dict(reversed(tuple(ordered.components.items())))}
        )
        first_candidate = next(
            item
            for item in candidates(ordered)
            if item.rule_id == "bus.i2c_low_equivalent_resistance"
        )
        reordered_candidate = next(
            item
            for item in candidates(reordered)
            if item.rule_id == "bus.i2c_low_equivalent_resistance"
        )
        self.assertEqual(fingerprint(first_candidate), fingerprint(reordered_candidate))

        accepted = evaluate(
            "synthetic-i2c",
            coach(i2c_netlist_with_parallel_sda("4k7")),
            DesignLintPolicy(),
        )
        self.assertFalse(
            any(item.rule_id == "bus.i2c_low_equivalent_resistance" for item in accepted.findings)
        )

        dnp_control = i2c_netlist_with_parallel_sda().model_copy(update={"dnp_components": ("R3",)})
        dnp_report = evaluate("synthetic-i2c", coach(dnp_control), DesignLintPolicy())
        self.assertFalse(
            any(item.rule_id == "bus.i2c_low_equivalent_resistance" for item in dnp_report.findings)
        )

        blocked = evaluate(
            "synthetic-i2c",
            coach(i2c_netlist_with_parallel_sda()),
            DesignLintPolicy(
                rules=(
                    DesignLintRuleOverride(
                        rule_id="bus.i2c_low_equivalent_resistance",
                        mode="block",
                        reason="The reviewed I2C bus requires at least 1 kΩ nominal pull-up resistance",
                    ),
                )
            ),
        )
        self.assertEqual(blocked.status, "FAIL")

    def test_i2c_low_equivalent_includes_series_pullup_paths(self) -> None:
        low_resistance = evaluate(
            "synthetic-i2c",
            coach(
                i2c_netlist_with_series_sda(
                    "1k",
                    "1k",
                    base_pullups=("SDA", "SCL"),
                    base_resistance="1k",
                )
            ),
            DesignLintPolicy(),
        )
        findings = [
            item
            for item in low_resistance.findings
            if item.rule_id == "bus.i2c_low_equivalent_resistance"
        ]
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].evidence["lines"], ("SDA",))
        self.assertEqual(findings[0].evidence["equivalent_ohms"], ("SDA=666.667Ω",))
        self.assertEqual(
            findings[0].evidence["pullup_resistors"],
            ("R1=1000Ω to +3V3", "R3 + R4=2000Ω to +3V3"),
        )

        valid = evaluate(
            "synthetic-i2c",
            coach(
                i2c_netlist_with_series_sda(
                    "4.7k",
                    "4.7k",
                    base_pullups=("SDA", "SCL"),
                    base_resistance="4.7k",
                )
            ),
            DesignLintPolicy(),
        )
        self.assertFalse(
            any(item.rule_id == "bus.i2c_low_equivalent_resistance" for item in valid.findings)
        )

    def test_i2c_pullups_to_distinct_rail_families_request_review(self) -> None:
        policy = policy_without_i2c_map_prompt()
        fault = i2c_netlist_with_pullup_rails(("+3V3", "+5V"), ("+3V3",))
        report = evaluate("synthetic-i2c-rail-review", coach(fault), policy)
        findings = [
            item
            for item in report.findings
            if item.rule_id == "bus.i2c_multiple_pullup_rail_families"
        ]
        self.assertEqual(len(findings), 1)
        finding = findings[0]
        self.assertEqual(finding.disposition, "OPEN")
        self.assertEqual(finding.evidence["rail_families"], ("3v3", "5v"))
        self.assertEqual(
            finding.evidence["pullup_paths"],
            (
                "SCL: R3=4700Ω to +3V3 (3v3)",
                "SDA: R1=4700Ω to +3V3 (3v3)",
                "SDA: R2=4700Ω to +5V (5v)",
            ),
        )
        self.assertIn("do not establish voltage compatibility", finding.message)

        separate_line_fault = evaluate(
            "synthetic-i2c-rail-review",
            coach(i2c_netlist_with_pullup_rails(("+3V3",), ("+5V",))),
            policy,
        )
        self.assertEqual(
            sum(
                item.rule_id == "bus.i2c_multiple_pullup_rail_families"
                for item in separate_line_fault.findings
            ),
            1,
        )

        for sda_rails, scl_rails in (
            (("+3V3",), ("+3V3",)),
            (("+3V3", "+3.3V"), ("3V3",)),
            (("+3V3", "+9V_CUSTOM"), ("+3V3",)),
        ):
            with self.subTest(sda_rails=sda_rails, scl_rails=scl_rails):
                control = evaluate(
                    "synthetic-i2c-rail-review",
                    coach(i2c_netlist_with_pullup_rails(sda_rails, scl_rails)),
                    policy,
                )
                self.assertNotIn(
                    "bus.i2c_multiple_pullup_rail_families",
                    {item.rule_id for item in control.findings},
                )

        dnp_resistor = i2c_netlist_with_pullup_rails(("+3V3", "+5V"), ("+3V3",)).model_copy(
            update={"dnp_components": ("R2",)}
        )
        dnp_report = evaluate("synthetic-i2c-rail-review", coach(dnp_resistor), policy)
        self.assertNotIn(
            "bus.i2c_multiple_pullup_rail_families",
            {item.rule_id for item in dnp_report.findings},
        )

        dnp_bus = i2c_netlist_with_pullup_rails(("+3V3", "+5V"), ("+3V3",)).model_copy(
            update={"dnp_components": ("U1",)}
        )
        dnp_bus_report = evaluate("synthetic-i2c-rail-review", coach(dnp_bus), policy)
        self.assertNotIn(
            "bus.i2c_multiple_pullup_rail_families",
            {item.rule_id for item in dnp_bus_report.findings},
        )

        blocked = evaluate(
            "synthetic-i2c-rail-review",
            coach(fault),
            DesignLintPolicy(
                rules=(
                    *policy.rules,
                    DesignLintRuleOverride(
                        rule_id="bus.i2c_multiple_pullup_rail_families",
                        mode="block",
                        reason="Synthetic project explicitly reviews I2C voltage domains",
                    ),
                )
            ),
        )
        self.assertEqual(blocked.status, "FAIL")

        disabled = evaluate(
            "synthetic-i2c-rail-review",
            coach(fault),
            DesignLintPolicy(
                rules=(
                    *policy.rules,
                    DesignLintRuleOverride(
                        rule_id="bus.i2c_multiple_pullup_rail_families",
                        mode="off",
                        reason="Synthetic fixture disables this review prompt",
                    ),
                )
            ),
        )
        self.assertEqual(disabled.status, "PASS")
        ignored = evaluate(
            "synthetic-i2c-rail-review",
            coach(fault),
            DesignLintPolicy(
                rules=policy.rules,
                ignores=(
                    DesignLintIgnore(
                        rule_id="bus.i2c_multiple_pullup_rail_families",
                        fingerprint=finding.fingerprint,
                        reason="Synthetic fixture records an intentional level-domain exception",
                    ),
                ),
            ),
        )
        self.assertEqual(ignored.status, "PASS")
        ignored_finding = next(
            item
            for item in ignored.findings
            if item.rule_id == "bus.i2c_multiple_pullup_rail_families"
        )
        self.assertEqual(ignored_finding.disposition, "IGNORED")

    def test_i2c_pullup_rail_finding_is_order_stable(self) -> None:
        source = i2c_netlist_with_pullup_rails(("+3V3", "+5V"), ("+3V3",))
        policy = policy_without_i2c_map_prompt()
        reordered = source.model_copy(
            update={
                "components": dict(reversed(tuple(source.components.items()))),
                "nets": dict(reversed(tuple(source.nets.items()))),
                "pin_functions": dict(reversed(tuple(source.pin_functions.items()))),
            }
        )
        original_finding = next(
            item
            for item in evaluate("synthetic-i2c-rail-review", coach(source), policy).findings
            if item.rule_id == "bus.i2c_multiple_pullup_rail_families"
        )
        reordered_finding = next(
            item
            for item in evaluate("synthetic-i2c-rail-review", coach(reordered), policy).findings
            if item.rule_id == "bus.i2c_multiple_pullup_rail_families"
        )
        self.assertEqual(
            (original_finding.fingerprint, original_finding.evidence),
            (reordered_finding.fingerprint, reordered_finding.evidence),
        )
