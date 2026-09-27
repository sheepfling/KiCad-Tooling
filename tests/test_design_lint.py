"""Synthetic connector regressions and exact project-owned lint decisions."""

from __future__ import annotations

import unittest

from pydantic import ValidationError

from kicad_tooling.hwrepo.design_lint import candidates, evaluate, fingerprint
from kicad_tooling.hwrepo.models import (
    ContractCoachReport,
    DesignLintIgnore,
    DesignLintPolicy,
    DesignLintRuleOverride,
    NetlistContract,
)


def observed(power_j3_connected: bool = False) -> NetlistContract:
    nets: dict[str, tuple[str, ...]] = {
        "+5V": ("J1.1", "J2.1"),
        "GND1": ("J1.7",),
        "GND2": ("J2.7",),
    }
    if power_j3_connected:
        nets["+12V"] = ("J3.1",)
    return NetlistContract(
        components={},
        nets=nets,
        component_symbols={"J1": "Synthetic:Port", "J2": "Synthetic:Port", "J3": "Synthetic:Port"},
        pin_functions={
            "J1.1": "PWR",
            "J2.1": "PWR",
            "J3.1": "PWR",
            "J1.7": "GND",
            "J2.7": "GND",
        },
    )


def coach(netlist: NetlistContract) -> ContractCoachReport:
    return ContractCoachReport(
        status="READY_FOR_REVIEW",
        project_id="synthetic-ports",
        observed=netlist,
        netlist_sha256="a" * 64,
    )


class DesignLintTests(unittest.TestCase):
    def test_open_findings_include_missing_power_and_separate_returns(self) -> None:
        report = evaluate("synthetic-ports", coach(observed()), DesignLintPolicy())
        self.assertEqual(report.status, "REVIEW")
        self.assertEqual(len(report.findings), 3)
        power = next(item for item in report.findings if item.subject.endswith("PWR"))
        self.assertEqual(power.evidence["J3.1"], ())
        self.assertEqual(power.disposition, "OPEN")
        self.assertEqual(
            {item.rule_id for item in report.findings},
            {"connector.repeated_pin_function", "net.numbered_returns"},
        )
        self.assertTrue(all(len(item.fingerprint) == 64 for item in report.findings))
        self.assertFalse(report.build_authorized)

    def test_exact_ignore_resurfaces_after_connection_changes(self) -> None:
        initial = evaluate("synthetic-ports", coach(observed()), DesignLintPolicy())
        power = next(item for item in initial.findings if item.subject.endswith("PWR"))
        policy = DesignLintPolicy(
            ignores=(
                DesignLintIgnore(
                    rule_id="connector.repeated_pin_function",
                    fingerprint=power.fingerprint,
                    reason="Independent review permits the currently unconnected third port",
                ),
            ),
        )
        ignored = evaluate("synthetic-ports", coach(observed()), policy)
        self.assertEqual(
            next(item for item in ignored.findings if item.subject.endswith("PWR")).disposition,
            "IGNORED",
        )
        changed = evaluate("synthetic-ports", coach(observed(True)), policy)
        self.assertEqual(changed.status, "REVIEW")
        self.assertEqual(changed.stale_ignores, policy.ignores)
        self.assertNotEqual(
            fingerprint(
                next(item for item in candidates(observed()) if item.subject.endswith("PWR"))
            ),
            fingerprint(
                next(item for item in candidates(observed(True)) if item.subject.endswith("PWR"))
            ),
        )

    def test_rule_overrides_block_or_turn_off_with_reason(self) -> None:
        blocked = evaluate(
            "synthetic-ports",
            coach(observed()),
            DesignLintPolicy(
                rules=(
                    DesignLintRuleOverride(
                        rule_id="connector.repeated_pin_function",
                        mode="block",
                        reason="Port pin discrepancies require release review",
                    ),
                ),
            ),
        )
        self.assertEqual(blocked.status, "FAIL")
        off = evaluate(
            "synthetic-ports",
            coach(observed()),
            DesignLintPolicy(
                rules=(
                    DesignLintRuleOverride(
                        rule_id="connector.repeated_pin_function",
                        mode="off",
                        reason="This synthetic board uses independent port rails",
                    ),
                    DesignLintRuleOverride(
                        rule_id="net.numbered_returns",
                        mode="off",
                        reason="This synthetic board uses isolated returns",
                    ),
                ),
            ),
        )
        self.assertEqual(off.status, "PASS")
        self.assertTrue(all(item.disposition == "RULE_OFF" for item in off.findings))
        self.assertTrue(all(item.reason for item in off.findings))

    def test_invalid_or_duplicate_decisions_fail_schema(self) -> None:
        with self.assertRaises(ValidationError):
            DesignLintPolicy(
                rules=(
                    DesignLintRuleOverride(
                        rule_id="net.numbered_returns", mode="off", reason="first"
                    ),
                    DesignLintRuleOverride(
                        rule_id="net.numbered_returns", mode="block", reason="second"
                    ),
                )
            )
        with self.assertRaises(ValidationError):
            DesignLintRuleOverride.model_validate(
                {"rule_id": "net.numbered_returns", "mode": "off", "reason": ""}
            )


if __name__ == "__main__":
    unittest.main()
