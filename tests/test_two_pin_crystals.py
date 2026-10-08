"""Synthetic regressions for the same-net two-pin crystal review rule."""

from __future__ import annotations

import hashlib
import unittest
from pathlib import Path

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.models import (
    ComponentContract,
    ContractCoachReport,
    DesignLintIgnore,
    DesignLintPolicy,
    DesignLintRuleOverride,
    NetlistContract,
)
from kicad_tooling.hwrepo.two_pin_crystals import two_pin_crystals_on_same_net

RULE_ID = "component.two_pin_crystal_same_net"


def crystal_netlist(
    *,
    same_net: bool = True,
    split_references: tuple[str, ...] = (),
    dnp: tuple[str, ...] = (),
    omit_inventory: tuple[str, ...] = (),
    ambiguous: tuple[str, ...] = (),
    multi_pin: tuple[str, ...] = (),
    unassigned: tuple[str, ...] = (),
    symbols: dict[str, str] | None = None,
) -> NetlistContract:
    symbols = symbols or {
        "Y1": "Device:Crystal",
        "Y2": "Device:Crystal_Small",
    }
    components = {
        reference: ComponentContract(value="16 MHz", footprint="Synthetic:Crystal")
        for reference in symbols
    }
    pin_numbers = {
        reference: ("1", "2", "3") if reference in multi_pin else ("1", "2")
        for reference in symbols
        if reference not in omit_inventory
    }
    nets: dict[str, tuple[str, ...]] = {}
    for reference in symbols:
        if reference in dnp or reference in omit_inventory:
            continue
        first, second = f"{reference}.1", f"{reference}.2"
        if reference in unassigned:
            nets[f"PARTIAL_{reference}"] = (first,)
            continue
        if same_net and reference not in split_references:
            pins = (first, second, f"{reference}.3") if reference in multi_pin else (first, second)
            nets[f"SHORT_{reference}"] = pins
        else:
            nets[f"{reference}_A"] = (first,)
            nets[f"{reference}_B"] = (second,)
        if reference in ambiguous:
            nets[f"ALSO_{reference}"] = (second,)
    return NetlistContract(
        components=components,
        nets=nets,
        dnp_components=dnp,
        component_symbols=symbols,
        component_pin_numbers=pin_numbers,
    )


def lint_report(
    observed: NetlistContract,
    policy: DesignLintPolicy | None = None,
) -> object:
    serialized = observed.model_dump_json().encode("utf-8")
    coach = ContractCoachReport(
        status="READY_FOR_REVIEW",
        project_id="synthetic-two-pin-crystals",
        netlist_sha256=hashlib.sha256(serialized).hexdigest(),
        observed=observed,
    )
    return evaluate(coach.project_id, coach, policy or DesignLintPolicy())


class TwoPinCrystalLintTests(unittest.TestCase):
    def test_native_schematic_sources_match_reviewed_hashes(self) -> None:
        fixture_root = Path(__file__).parents[1] / "tests/fixtures/design_lint/two-pin-crystals"
        expected = {
            "same-net-crystal.kicad_sch": "0a55a739bcce60cacafaadf2c9995c0ff3ef07caf4284745b420a8e0f2de2b1a",
            "distinct-nets-crystal.kicad_sch": "0c000075d25bc1da32b777367079d084f96fe8be88e258146b5796db99bbe39e",
        }
        self.assertEqual(
            {
                name: hashlib.sha256((fixture_root / name).read_bytes()).hexdigest()
                for name in expected
            },
            expected,
        )

    def test_detects_exact_device_crystal_families_on_one_net(self) -> None:
        observed = crystal_netlist()
        candidates = two_pin_crystals_on_same_net(observed)
        self.assertEqual(
            [(item.reference, item.kind, item.value) for item in candidates],
            [("Y1", "crystal", "16 MHz"), ("Y2", "crystal", "16 MHz")],
        )

        report = lint_report(observed)
        findings = [item for item in report.findings if item.rule_id == RULE_ID]
        self.assertEqual(report.status, "REVIEW")
        self.assertEqual(len(findings), 2)
        finding = next(item for item in findings if item.subject.startswith("Y1 "))
        self.assertEqual(finding.mode, "review")
        self.assertEqual(finding.evidence["symbol"], ("Device:Crystal",))
        self.assertEqual(finding.evidence["net"], ("SHORT_Y1",))
        self.assertEqual(
            finding.evidence["pin_assignments"],
            ("Y1.1 -> SHORT_Y1", "Y1.2 -> SHORT_Y1"),
        )
        self.assertIn("does not establish that the topology is wrong", finding.message)

    def test_distinct_pin_nets_are_the_no_finding_control(self) -> None:
        report = lint_report(crystal_netlist(same_net=False))
        self.assertNotIn(RULE_ID, {item.rule_id for item in report.findings})
        self.assertEqual(report.status, "PASS")

    def test_skips_dnp_incomplete_ambiguous_multi_pin_open_and_custom_symbols(self) -> None:
        observed = crystal_netlist(
            dnp=("Y1",),
            omit_inventory=("Y2",),
            ambiguous=("Y3",),
            multi_pin=("Y4",),
            unassigned=("Y5",),
            symbols={
                "Y1": "Device:Crystal",
                "Y2": "Device:Crystal_Small",
                "Y3": "Device:Crystal",
                "Y4": "Device:Crystal_GND24",
                "Y5": "Device:Crystal",
                "Y6": "Synthetic:Crystal",
                "X1": "Oscillator:XO",
            },
        )
        self.assertFalse(two_pin_crystals_on_same_net(observed))

    def test_rule_policy_and_exact_ignore_are_project_configurable(self) -> None:
        observed = crystal_netlist()
        original = lint_report(observed)
        finding = next(item for item in original.findings if item.rule_id == RULE_ID)
        blocked = lint_report(
            observed,
            DesignLintPolicy(
                rules=(
                    DesignLintRuleOverride(
                        rule_id=RULE_ID,
                        mode="block",
                        reason="Synthetic policy requires review of a shorted crystal",
                    ),
                )
            ),
        )
        self.assertEqual(blocked.status, "FAIL")
        disabled = lint_report(
            observed,
            DesignLintPolicy(
                rules=(
                    DesignLintRuleOverride(
                        rule_id=RULE_ID,
                        mode="off",
                        reason="Synthetic configuration fixture disables this prompt",
                    ),
                )
            ),
        )
        self.assertEqual(disabled.status, "PASS")
        self.assertEqual(
            next(item for item in disabled.findings if item.rule_id == RULE_ID).disposition,
            "RULE_OFF",
        )
        ignored = lint_report(
            observed,
            DesignLintPolicy(
                ignores=(
                    DesignLintIgnore(
                        rule_id=RULE_ID,
                        fingerprint=finding.fingerprint,
                        reason="Synthetic project documents this crystal bypass",
                    ),
                )
            ),
        )
        ignored_finding = next(
            item for item in ignored.findings if item.fingerprint == finding.fingerprint
        )
        self.assertEqual(ignored_finding.disposition, "IGNORED")

    def test_order_is_stable_and_splitting_one_crystal_clears_only_its_finding(self) -> None:
        source = crystal_netlist()
        original = lint_report(source)
        reordered_source = source.model_copy(
            update={
                "components": dict(reversed(tuple(source.components.items()))),
                "nets": dict(reversed(tuple(source.nets.items()))),
                "component_symbols": dict(reversed(tuple(source.component_symbols.items()))),
                "component_pin_numbers": dict(
                    reversed(tuple(source.component_pin_numbers.items()))
                ),
            }
        )
        reordered = lint_report(reordered_source)
        original_findings = {
            item.subject: (item.fingerprint, item.evidence)
            for item in original.findings
            if item.rule_id == RULE_ID
        }
        reordered_findings = {
            item.subject: (item.fingerprint, item.evidence)
            for item in reordered.findings
            if item.rule_id == RULE_ID
        }
        self.assertEqual(original_findings, reordered_findings)

        repaired = lint_report(crystal_netlist(split_references=("Y1",)))
        repaired_findings = {
            item.subject: item.fingerprint for item in repaired.findings if item.rule_id == RULE_ID
        }
        self.assertEqual(len(repaired_findings), 1)
        self.assertTrue(next(iter(repaired_findings)).startswith("Y2 "))
        y2_subject = next(subject for subject in original_findings if subject.startswith("Y2 "))
        self.assertEqual(repaired_findings, {y2_subject: original_findings[y2_subject][0]})
