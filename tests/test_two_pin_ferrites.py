"""Synthetic regressions for the same-net two-pin ferrite review rule."""

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
from kicad_tooling.hwrepo.two_pin_ferrites import two_pin_ferrites_on_same_net


def ferrite_netlist(
    *,
    same_net: bool = True,
    dnp: tuple[str, ...] = (),
    omit_inventory: tuple[str, ...] = (),
    ambiguous: tuple[str, ...] = (),
    multi_pin: tuple[str, ...] = (),
    unassigned: tuple[str, ...] = (),
    symbols: dict[str, str] | None = None,
) -> NetlistContract:
    symbols = symbols or {"FB1": "Device:FerriteBead", "FB2": "Device:FerriteBead_Small"}
    components = {
        reference: ComponentContract(value="600R@100MHz", footprint="Synthetic:Ferrite_0603")
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
        pins = (first, second, f"{reference}.3") if reference in multi_pin else (first, second)
        if same_net:
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
        project_id="synthetic-two-pin-ferrites",
        netlist_sha256=hashlib.sha256(serialized).hexdigest(),
        observed=observed,
    )
    return evaluate(coach.project_id, coach, policy or DesignLintPolicy())


class TwoPinFerriteLintTests(unittest.TestCase):
    def test_native_schematic_sources_match_reviewed_hashes(self) -> None:
        fixture_root = Path(__file__).parents[1] / "tests/fixtures/design_lint/two-pin-ferrites"
        expected = {
            "same-net-ferrite.kicad_sch": "8ede05ea1d9c8afb0cec2f1c8c9bddf527eab015ab779097f4ddc528866751f7",
            "distinct-nets-ferrite.kicad_sch": "199c802ca290b1281622c623f4966b159144f0e95fd99ed0e21a14a0875734a7",
        }
        self.assertEqual(
            {
                name: hashlib.sha256((fixture_root / name).read_bytes()).hexdigest()
                for name in expected
            },
            expected,
        )

    def test_detects_exact_device_ferrite_bead_families_on_one_net(self) -> None:
        observed = ferrite_netlist()
        candidates = two_pin_ferrites_on_same_net(observed)
        self.assertEqual(
            [(item.reference, item.kind, item.value) for item in candidates],
            [
                ("FB1", "ferrite_bead", "600R@100MHz"),
                ("FB2", "ferrite_bead", "600R@100MHz"),
            ],
        )
        report = lint_report(observed)
        findings = [
            item for item in report.findings if item.rule_id == "component.two_pin_ferrite_same_net"
        ]
        self.assertEqual(report.status, "REVIEW")
        self.assertEqual(len(findings), 2)
        finding = next(item for item in findings if item.subject.startswith("FB1 "))
        self.assertEqual(finding.mode, "review")
        self.assertEqual(finding.evidence["symbol"], ("Device:FerriteBead",))
        self.assertEqual(finding.evidence["net"], ("BYPASSED_FB1",))
        self.assertEqual(
            finding.evidence["pin_assignments"],
            ("FB1.1 -> BYPASSED_FB1", "FB1.2 -> BYPASSED_FB1"),
        )
        self.assertIn("does not establish that the topology is wrong", finding.message)

    def test_distinct_pin_nets_are_the_no_finding_control(self) -> None:
        report = lint_report(ferrite_netlist(same_net=False))
        self.assertNotIn(
            "component.two_pin_ferrite_same_net",
            {item.rule_id for item in report.findings},
        )
        self.assertEqual(report.status, "PASS")

    def test_skips_dnp_incomplete_ambiguous_and_unsupported_symbols(self) -> None:
        observed = ferrite_netlist(
            dnp=("FB1",),
            omit_inventory=("FB2",),
            ambiguous=("FB3",),
            multi_pin=("FB4",),
            unassigned=("FB5",),
            symbols={
                "FB1": "Device:FerriteBead",
                "FB2": "Device:FerriteBead_Small",
                "FB3": "Device:FerriteBead",
                "FB4": "Device:FerriteBead",
                "FB5": "Device:FerriteBead",
                "X1": "Synthetic:FerriteBead",
                "FB6": "Device:FerriteBead_Custom",
                "L1": "Device:L_Ferrite",
            },
        )
        self.assertFalse(two_pin_ferrites_on_same_net(observed))

    def test_rule_policy_and_exact_ignore_are_project_configurable(self) -> None:
        observed = ferrite_netlist()
        rule_id = "component.two_pin_ferrite_same_net"
        original = lint_report(observed)
        finding = next(item for item in original.findings if item.rule_id == rule_id)
        blocked = lint_report(
            observed,
            DesignLintPolicy(
                rules=(
                    DesignLintRuleOverride(
                        rule_id=rule_id,
                        mode="block",
                        reason="Synthetic policy requires review of a bypassed ferrite",
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
                        reason="Synthetic project accepts this documented ferrite bypass",
                    ),
                )
            ),
        )
        ignored_finding = next(
            item for item in ignored.findings if item.fingerprint == finding.fingerprint
        )
        self.assertEqual(ignored_finding.disposition, "IGNORED")

    def test_order_is_stable_and_splitting_one_component_clears_only_its_finding(self) -> None:
        source = ferrite_netlist()
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
        rule_id = "component.two_pin_ferrite_same_net"
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
        self.assertEqual(original_findings, reordered_findings)
        split = source.model_copy(
            update={"nets": {**source.nets, "FB1_INPUT": ("FB1.1",), "FB1_OUTPUT": ("FB1.2",)}}
        )
        remaining = lint_report(split)
        remaining_findings = {
            item.subject for item in remaining.findings if item.rule_id == rule_id
        }
        self.assertEqual(
            remaining_findings, {"FB2 (600R@100MHz ferrite_bead) has both pins on one net"}
        )


if __name__ == "__main__":
    unittest.main()
