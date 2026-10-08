"""Synthetic regressions for the same-net two-pin fuse review rule."""

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
from kicad_tooling.hwrepo.two_pin_fuses import two_pin_fuses_on_same_net


def fuse_netlist(
    *,
    same_net: bool = True,
    dnp: tuple[str, ...] = (),
    omit_inventory: tuple[str, ...] = (),
    ambiguous: tuple[str, ...] = (),
    multi_pin: tuple[str, ...] = (),
    symbols: dict[str, str] | None = None,
) -> NetlistContract:
    symbols = symbols or {"F1": "Device:Fuse", "F2": "Device:Polyfuse"}
    components = {
        reference: ComponentContract(value="1A", footprint="Synthetic:Fuse_1206")
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
        first = f"{reference}.1"
        second = f"{reference}.2"
        if reference in multi_pin:
            third = f"{reference}.3"
        if same_net:
            pins = (first, second, third) if reference in multi_pin else (first, second)
            nets[f"BYPASSED_{reference}"] = pins
        else:
            nets[f"{reference}_INPUT"] = (first,)
            nets[f"{reference}_OUTPUT"] = (second,)
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
        project_id="synthetic-two-pin-fuses",
        netlist_sha256=hashlib.sha256(serialized).hexdigest(),
        observed=observed,
    )
    return evaluate(coach.project_id, coach, policy or DesignLintPolicy())


class TwoPinFuseLintTests(unittest.TestCase):
    def test_native_schematic_sources_match_reviewed_hashes(self) -> None:
        fixture_root = Path(__file__).parents[1] / "tests/fixtures/design_lint/two-pin-fuses"
        expected = {
            "same-net-fuse.kicad_sch": "0aef6e17919aabf2b640183e91d992df28a7cb8db92ea76514afddd31c2f0f93",
            "distinct-nets-fuse.kicad_sch": "34e303f1ff54b324555cba0b7fa015881edebf3a91b32391fc010d0f5f92cc89",
            "same-net-polyfuse.kicad_sch": "3f024223a079ab029edcb6dc9314a6beb82eb75fa5d31ca2140425ae210ad6a7",
            "distinct-nets-polyfuse.kicad_sch": "e243a29359c911e2d04787a8d71dc2566c1c09e287251c94bae22ac9a7cfe4e7",
        }
        self.assertEqual(
            {
                name: hashlib.sha256((fixture_root / name).read_bytes()).hexdigest()
                for name in expected
            },
            expected,
        )

    def test_detects_exact_fuse_and_polyfuse_families_on_one_net(self) -> None:
        observed = fuse_netlist()
        candidates = two_pin_fuses_on_same_net(observed)
        self.assertEqual(
            [(item.reference, item.kind, item.value) for item in candidates],
            [("F1", "fuse", "1A"), ("F2", "polyfuse", "1A")],
        )

        report = lint_report(observed)
        findings = [
            item for item in report.findings if item.rule_id == "component.two_pin_fuse_same_net"
        ]
        self.assertEqual(report.status, "REVIEW")
        self.assertEqual(len(findings), 2)
        fuse_finding = next(item for item in findings if item.subject.startswith("F1 "))
        self.assertEqual(fuse_finding.mode, "review")
        self.assertEqual(fuse_finding.evidence["symbol"], ("Device:Fuse",))
        self.assertEqual(fuse_finding.evidence["component_kind"], ("fuse",))
        self.assertEqual(fuse_finding.evidence["net"], ("BYPASSED_F1",))
        self.assertEqual(
            fuse_finding.evidence["pin_assignments"],
            ("F1.1 -> BYPASSED_F1", "F1.2 -> BYPASSED_F1"),
        )
        self.assertIn("does not establish that the topology is wrong", fuse_finding.message)

    def test_distinct_pin_nets_are_the_no_finding_control(self) -> None:
        report = lint_report(fuse_netlist(same_net=False))
        self.assertNotIn(
            "component.two_pin_fuse_same_net",
            {item.rule_id for item in report.findings},
        )
        self.assertEqual(report.status, "PASS")

    def test_skips_dnp_incomplete_ambiguous_and_unsupported_symbols(self) -> None:
        observed = fuse_netlist(
            dnp=("F1",),
            omit_inventory=("F2",),
            ambiguous=("F3",),
            multi_pin=("F4",),
            symbols={
                "F1": "Device:Fuse",
                "F2": "Device:Polyfuse_Small",
                "F3": "Device:Fuse",
                "F4": "Device:Polyfuse",
                "F5": "Synthetic:Fuse",
                "R1": "Device:R",
                "D1": "Device:D",
            },
        )
        self.assertFalse(two_pin_fuses_on_same_net(observed))
        self.assertNotIn(
            "component.two_pin_fuse_same_net",
            {item.rule_id for item in lint_report(observed).findings},
        )

    def test_rule_policy_and_exact_ignore_are_project_configurable(self) -> None:
        observed = fuse_netlist()
        rule_id = "component.two_pin_fuse_same_net"
        original = lint_report(observed)
        finding = next(item for item in original.findings if item.rule_id == rule_id)

        blocked = lint_report(
            observed,
            DesignLintPolicy(
                rules=(
                    DesignLintRuleOverride(
                        rule_id=rule_id,
                        mode="block",
                        reason="Synthetic policy requires disposition of bypassed protection parts",
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
                        rule_id=rule_id,
                        mode="off",
                        reason="Synthetic configuration fixture disables this prompt",
                    ),
                )
            ),
        )
        self.assertEqual(disabled.status, "PASS")
        self.assertEqual(
            next(item for item in disabled.findings if item.rule_id == rule_id).disposition,
            "RULE_OFF",
        )

        ignored = lint_report(
            observed,
            DesignLintPolicy(
                ignores=(
                    DesignLintIgnore(
                        rule_id=rule_id,
                        fingerprint=finding.fingerprint,
                        reason="Synthetic project review accepts this explicit bypass",
                    ),
                )
            ),
        )
        ignored_finding = next(
            item for item in ignored.findings if item.fingerprint == finding.fingerprint
        )
        self.assertEqual(ignored_finding.disposition, "IGNORED")

    def test_order_is_stable_and_splitting_one_component_clears_only_its_finding(self) -> None:
        source = fuse_netlist()
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
        rule_id = "component.two_pin_fuse_same_net"
        original_findings = {
            item.subject: (item.fingerprint, item.evidence)
            for item in original.findings
            if item.rule_id == rule_id
        }
        reordered_findings = {
            item.subject: (item.fingerprint, item.evidence)
            for item in reordered.findings
            if item.rule_id == rule_id
        }
        self.assertEqual(len(original_findings), 2)
        self.assertEqual(reordered_findings, original_findings)

        split_nets = dict(source.nets)
        del split_nets["BYPASSED_F1"]
        split_nets["F1_INPUT"] = ("F1.1",)
        split_nets["F1_OUTPUT"] = ("F1.2",)
        split_report = lint_report(source.model_copy(update={"nets": split_nets}))
        remaining = {
            item.subject: (item.fingerprint, item.evidence)
            for item in split_report.findings
            if item.rule_id == rule_id
        }
        expected_f2 = {
            subject: details
            for subject, details in original_findings.items()
            if subject.startswith("F2 ")
        }
        self.assertEqual(remaining, expected_f2)
