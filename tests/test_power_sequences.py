"""Synthetic regressions for project-mapped power-sequence dependencies."""

from __future__ import annotations

import unittest

import pytest
from pydantic import ValidationError

from kicad_tooling.hwrepo.models import (
    ComponentContract,
    DesignLintIgnore,
    DesignLintRuleOverride,
    PowerSequenceMap,
)
from kicad_tooling.hwrepo.power_sequences import (
    power_sequence_graph_has_cycle,
    power_sequence_mismatches,
)
from tests.power_sequence_support import (
    RULE_ID,
    lint_report,
    power_sequence_map,
    power_sequence_netlist,
)

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.power_lint,
]


class PowerSequenceTests(unittest.TestCase):
    def test_explicit_power_good_to_enable_map_passes_including_firmware_control(self) -> None:
        sequence_map = power_sequence_map(firmware_enable=True)
        report = lint_report(power_sequence_netlist(), sequence_map)
        self.assertEqual(report.status, "PASS", report.issues)
        self.assertNotIn(RULE_ID, {item.rule_id for item in report.findings})
        run = next(item for item in report.mapped_check_runs if item.rule_id == RULE_ID)
        self.assertEqual(run.status, "EVALUATED")
        self.assertEqual(
            run.requirement_count, len(sequence_map.stages) + len(sequence_map.dependencies)
        )
        self.assertEqual(run.finding_count, 0)
        self.assertEqual(run.netlist_sha256, report.netlist_sha256)
        self.assertEqual(power_sequence_mismatches(sequence_map, power_sequence_netlist()), ())
        self.assertFalse(power_sequence_graph_has_cycle(sequence_map))

    def test_missing_net_identity_inventory_part_and_dnp_faults_are_reported(self) -> None:
        cases = (
            ("open-enable", "U2.1 is assigned to FLOATING", "rail-b"),
            ("wrong-output", "U1.2 is assigned to OTHER_RAIL", "rail-a"),
            ("wrong-symbol", "U1 symbol is Synthetic:Switch", "rail-a"),
            ("wrong-part-id", "U1 PART_ID is WRONG-PART", "rail-a"),
            ("missing-pin", "U2.1 is absent from the native pin inventory", "rail-b"),
            ("dnp", "U2 is marked DNP", "rail-b"),
        )
        for fault, expected_issue, expected_stage in cases:
            with self.subTest(fault=fault):
                report = lint_report(power_sequence_netlist(fault=fault), power_sequence_map())
                self.assertEqual(report.status, "REVIEW")
                run = next(item for item in report.mapped_check_runs if item.rule_id == RULE_ID)
                self.assertEqual(run.status, "EVALUATED")
                self.assertEqual(run.finding_count, 1)
                finding = next(item for item in report.findings if item.rule_id == RULE_ID)
                self.assertTrue(
                    any(expected_issue in issue for issue in finding.evidence["issues"]),
                    finding.evidence["issues"],
                )
                self.assertEqual(
                    finding.evidence["sequence_map_basis"],
                    ("Synthetic source page 4, startup dependency table",),
                )
                if expected_stage == "rail-b":
                    self.assertIn("enable: U2.1 on GOOD_A", finding.evidence["expected_endpoints"])
                self.assertEqual(
                    finding.evidence["dependencies"],
                    ("rail-a-before-rail-b: rail-a → rail-b on GOOD_A",),
                )
                self.assertTrue(finding.evidence["map_sha256"])

    def test_unconfigured_map_does_not_infer_requirements_from_pin_names(self) -> None:
        named_pins = power_sequence_netlist().model_copy(
            update={
                "pin_functions": {"U1.3": "PG", "U2.1": "EN"},
                "pin_electrical_types": {"U1.3": "output", "U2.1": "input"},
            }
        )
        report = lint_report(named_pins)
        self.assertNotIn(RULE_ID, {item.rule_id for item in report.findings})
        run = next(item for item in report.mapped_check_runs if item.rule_id == RULE_ID)
        self.assertEqual(run.status, "NOT_CONFIGURED")
        self.assertEqual(run.finding_count, 0)

    def test_rule_supports_review_block_off_and_exact_ignore(self) -> None:
        faulty = power_sequence_netlist(fault="open-enable")
        sequence_map = power_sequence_map()
        blocked = lint_report(
            faulty,
            sequence_map,
            override=DesignLintRuleOverride(
                rule_id=RULE_ID,
                mode="block",
                reason="Synthetic release policy requires the mapped sequence topology",
            ),
        )
        self.assertEqual(blocked.status, "FAIL")
        finding = next(
            item for item in lint_report(faulty, sequence_map).findings if item.rule_id == RULE_ID
        )
        ignored = lint_report(
            faulty,
            sequence_map,
            ignore=DesignLintIgnore(
                rule_id=RULE_ID,
                fingerprint=finding.fingerprint,
                reason="Synthetic approved alternate sequence is covered elsewhere",
            ),
        )
        self.assertEqual(
            next(item for item in ignored.findings if item.rule_id == RULE_ID).disposition,
            "IGNORED",
        )
        disabled = lint_report(
            faulty,
            sequence_map,
            override=DesignLintRuleOverride(
                rule_id=RULE_ID,
                mode="off",
                reason="Synthetic alternate variant has a separate sequence contract",
            ),
        )
        self.assertEqual(
            next(item for item in disabled.findings if item.rule_id == RULE_ID).disposition,
            "RULE_OFF",
        )
        disabled_run = next(item for item in disabled.mapped_check_runs if item.rule_id == RULE_ID)
        self.assertEqual((disabled_run.status, disabled_run.mode), ("EVALUATED", "off"))
        self.assertEqual(disabled_run.finding_count, 1)

    def test_netlist_order_is_stable_and_repair_clears_finding(self) -> None:
        sequence_map = power_sequence_map()
        faulty = power_sequence_netlist(fault="open-enable")
        report = lint_report(faulty, sequence_map)
        original = next(item for item in report.findings if item.rule_id == RULE_ID)
        reordered = faulty.model_copy(
            update={
                "nets": dict(reversed(tuple(faulty.nets.items()))),
                "components": dict(reversed(tuple(faulty.components.items()))),
                "component_symbols": dict(reversed(tuple(faulty.component_symbols.items()))),
                "component_pin_numbers": dict(
                    reversed(tuple(faulty.component_pin_numbers.items()))
                ),
            }
        )
        reordered_finding = next(
            item
            for item in lint_report(reordered, sequence_map).findings
            if item.rule_id == RULE_ID
        )
        self.assertEqual(
            (reordered_finding.fingerprint, reordered_finding.evidence),
            (original.fingerprint, original.evidence),
        )

        unrelated = faulty.model_copy(
            update={
                "components": {
                    **faulty.components,
                    "R9": ComponentContract(value="10k", footprint="Synthetic:R_0603"),
                },
                "nets": {
                    **faulty.nets,
                    "UNRELATED_A": ("R9.1",),
                    "UNRELATED_B": ("R9.2",),
                },
                "component_symbols": {**faulty.component_symbols, "R9": "Device:R"},
                "component_pin_numbers": {
                    **faulty.component_pin_numbers,
                    "R9": ("1", "2"),
                },
            }
        )
        unrelated_report = lint_report(unrelated, sequence_map)
        unrelated_finding = next(
            item for item in unrelated_report.findings if item.rule_id == RULE_ID
        )
        self.assertNotEqual(unrelated_report.netlist_sha256, report.netlist_sha256)
        self.assertEqual(
            (unrelated_finding.fingerprint, unrelated_finding.evidence),
            (original.fingerprint, original.evidence),
        )
        original_run = next(item for item in report.mapped_check_runs if item.rule_id == RULE_ID)
        unrelated_run = next(
            item for item in unrelated_report.mapped_check_runs if item.rule_id == RULE_ID
        )
        self.assertEqual(unrelated_run.netlist_sha256, unrelated_report.netlist_sha256)
        self.assertNotEqual(unrelated_run.netlist_sha256, original_run.netlist_sha256)
        self.assertEqual(unrelated_run.map_sha256, original_run.map_sha256)

        exact_ignore = DesignLintIgnore(
            rule_id=RULE_ID,
            fingerprint=original.fingerprint,
            reason="Synthetic review accepts this explicit rail-sequence exception",
        )
        for candidate in (faulty, unrelated):
            ignored_report = lint_report(candidate, sequence_map, ignore=exact_ignore)
            ignored_finding = next(
                item for item in ignored_report.findings if item.rule_id == RULE_ID
            )
            self.assertEqual(ignored_finding.fingerprint, original.fingerprint)
            self.assertEqual(ignored_finding.disposition, "IGNORED")

        self.assertNotIn(
            RULE_ID,
            {item.rule_id for item in lint_report(power_sequence_netlist(), sequence_map).findings},
        )

    def test_map_rejects_unresolved_or_inconsistent_dependencies(self) -> None:
        raw = power_sequence_map().model_dump(mode="python")
        raw["dependencies"][0]["successor_stage"] = "unknown-stage"
        with self.assertRaisesRegex(ValidationError, "name declared stages"):
            PowerSequenceMap.model_validate(raw)

        raw = power_sequence_map().model_dump(mode="python")
        raw["dependencies"][0]["signal_net"] = "WRONG_NET"
        with self.assertRaisesRegex(ValidationError, "match its power-good endpoint"):
            PowerSequenceMap.model_validate(raw)

        raw = power_sequence_map().model_dump(mode="python")
        raw["stages"][1]["enable_control"] = "external"
        raw["stages"][1]["enable"] = None
        with self.assertRaisesRegex(ValidationError, "requires a mapped enable endpoint"):
            PowerSequenceMap.model_validate(raw)


if __name__ == "__main__":
    unittest.main()
