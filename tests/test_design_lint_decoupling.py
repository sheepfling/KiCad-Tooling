"""Focused synthetic regressions for the decoupling lint theme."""

from __future__ import annotations

import hashlib
import unittest

import pytest
from pydantic import ValidationError

from kicad_tooling.hwrepo.design_lint import (
    evaluate,
)
from kicad_tooling.hwrepo.models import (
    ComponentContract,
    ComponentRoleBinding,
    ComponentRoleMap,
    DesignLintIgnore,
    DesignLintPolicy,
    DesignLintReport,
    DesignLintRuleOverride,
    NetlistContract,
)
from tests.design_lint_fixtures import (
    coach,
    custom_decoupling_capacitor_role_map,
    custom_ic_decoupling_capacitor_fixture,
    ic_power_decoupling_fixture,
)

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.component_lint,
    pytest.mark.power_lint,
]


class DesignLintDecouplingTests(unittest.TestCase):
    def test_ic_power_rail_without_fitted_capacitor_needs_review(self) -> None:
        report = evaluate(
            "synthetic-decoupling-presence",
            coach(ic_power_decoupling_fixture()),
            DesignLintPolicy(),
        )
        findings = [
            item
            for item in report.findings
            if item.rule_id == "power.ic_rail_without_fitted_capacitor"
        ]
        self.assertEqual(report.status, "REVIEW")
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].subject, "+3V3: IC supply decoupling review")
        self.assertEqual(
            findings[0].evidence,
            {
                "net": ("+3V3",),
                "power_input_pins": ("U1.1",),
                "component_references": ("U1",),
            },
        )
        self.assertIn("does not establish local", findings[0].message)

    def test_fitted_capacitor_to_return_controls_review(self) -> None:
        report = evaluate(
            "synthetic-decoupling-presence-control",
            coach(ic_power_decoupling_fixture(capacitor_net="+3V3")),
            DesignLintPolicy(),
        )
        self.assertNotIn(
            "power.ic_rail_without_fitted_capacitor",
            {item.rule_id for item in report.findings},
        )

    def test_custom_decoupling_capacitor_requires_exact_project_role(self) -> None:
        rule_id = "power.ic_rail_without_fitted_capacitor"
        source = custom_ic_decoupling_capacitor_fixture()
        unclassified = evaluate(
            "synthetic-custom-decoupling-capacitor",
            coach(source),
            DesignLintPolicy(),
        )
        self.assertEqual(unclassified.status, "REVIEW")
        self.assertEqual(
            {item.rule_id for item in unclassified.findings if item.rule_id == rule_id},
            {rule_id},
        )

        role_map = custom_decoupling_capacitor_role_map()
        mapped = evaluate(
            "synthetic-custom-decoupling-capacitor",
            coach(source),
            DesignLintPolicy(component_role_map=role_map),
        )
        self.assertEqual(mapped.status, "PASS")
        self.assertNotIn(rule_id, {item.rule_id for item in mapped.findings})
        self.assertNotIn(
            "component.led_directly_driven_from_output",
            {item.rule_id for item in mapped.findings},
        )

        wrong_return = evaluate(
            "synthetic-custom-decoupling-capacitor",
            coach(custom_ic_decoupling_capacitor_fixture(capacitor_reference_net="CAP_REF")),
            DesignLintPolicy(component_role_map=role_map),
        )
        self.assertEqual(wrong_return.status, "REVIEW")
        self.assertIn(rule_id, {item.rule_id for item in wrong_return.findings})

        dnp = evaluate(
            "synthetic-custom-decoupling-capacitor",
            coach(custom_ic_decoupling_capacitor_fixture(dnp_capacitor=True)),
            DesignLintPolicy(component_role_map=role_map),
        )
        self.assertEqual(dnp.status, "REVIEW")
        self.assertIn(rule_id, {item.rule_id for item in dnp.findings})

        stale_map = role_map.model_copy(
            update={
                "entries": (
                    role_map.entries[0].model_copy(update={"footprint": "Synthetic:Other"}),
                )
            }
        )
        stale = evaluate(
            "synthetic-custom-decoupling-capacitor",
            coach(source),
            DesignLintPolicy(component_role_map=stale_map),
        )
        self.assertEqual(stale.status, "BLOCKED")
        self.assertTrue(any("stale at C1" in issue for issue in stale.issues))

        with self.assertRaises(ValidationError):
            ComponentRoleBinding.model_validate(
                {
                    **role_map.entries[0].model_dump(),
                    "pins": (role_map.entries[0].pins[0].model_dump(),),
                }
            )
        with self.assertRaises(ValidationError):
            ComponentRoleBinding.model_validate(
                {
                    **role_map.entries[0].model_dump(),
                    "pins": (
                        role_map.entries[0].pins[0].model_dump(),
                        {
                            **role_map.entries[0].pins[1].model_dump(),
                            "electrical_type": "input",
                        },
                    ),
                }
            )

    def test_custom_decoupling_capacitor_suppression_is_input_order_stable(self) -> None:
        source = custom_ic_decoupling_capacitor_fixture()
        policy = DesignLintPolicy(component_role_map=custom_decoupling_capacitor_role_map())
        original = evaluate("synthetic-custom-decoupling-capacitor", coach(source), policy)
        reordered_source = source.model_copy(
            update={
                "components": dict(reversed(tuple(source.components.items()))),
                "nets": dict(reversed(tuple(source.nets.items()))),
                "component_symbols": dict(reversed(tuple(source.component_symbols.items()))),
                "component_pin_numbers": dict(
                    reversed(tuple(source.component_pin_numbers.items()))
                ),
                "pin_functions": dict(reversed(tuple(source.pin_functions.items()))),
                "pin_electrical_types": dict(reversed(tuple(source.pin_electrical_types.items()))),
            }
        )
        role_binding = custom_decoupling_capacitor_role_map().entries[0]
        reordered_policy = DesignLintPolicy(
            component_role_map=ComponentRoleMap(
                entries=(
                    role_binding.model_copy(update={"pins": tuple(reversed(role_binding.pins))}),
                )
            )
        )
        repeated = evaluate(
            "synthetic-custom-decoupling-capacitor",
            coach(reordered_source),
            reordered_policy,
        )
        self.assertEqual(original.status, "PASS")
        self.assertEqual(repeated.status, "PASS")
        self.assertEqual(original.findings, repeated.findings)
        self.assertEqual(original.issues, repeated.issues)

    def test_ic_decoupling_prompt_is_order_stable_and_fitted_capacitor_clears_it(
        self,
    ) -> None:
        rule_id = "power.ic_rail_without_fitted_capacitor"
        source = ic_power_decoupling_fixture()

        def lint(netlist: NetlistContract) -> tuple[str, DesignLintReport]:
            source_hash = hashlib.sha256(netlist.model_dump_json().encode("utf-8")).hexdigest()
            return source_hash, evaluate(
                "synthetic-decoupling-presence",
                coach(netlist, source_hash),
                DesignLintPolicy(),
            )

        source_hash, original = lint(source)
        self.assertEqual(original.netlist_sha256, source_hash)
        original_findings = {
            item.subject: (item.fingerprint, item.evidence)
            for item in original.findings
            if item.rule_id == rule_id
        }
        self.assertEqual(len(original_findings), 1)

        reordered_source = source.model_copy(
            update={
                "components": dict(reversed(tuple(source.components.items()))),
                "nets": dict(reversed(tuple(source.nets.items()))),
                "component_symbols": dict(reversed(tuple(source.component_symbols.items()))),
                "pin_functions": dict(reversed(tuple(source.pin_functions.items()))),
                "pin_electrical_types": dict(reversed(tuple(source.pin_electrical_types.items()))),
            }
        )
        reordered_hash, reordered = lint(reordered_source)
        self.assertNotEqual(source_hash, reordered_hash)
        self.assertEqual(reordered.netlist_sha256, reordered_hash)
        reordered_findings = {
            item.subject: (item.fingerprint, item.evidence)
            for item in reordered.findings
            if item.rule_id == rule_id
        }
        self.assertEqual(reordered_findings, original_findings)

        repaired_hash, repaired = lint(ic_power_decoupling_fixture(capacitor_net="+3V3"))
        self.assertNotEqual(source_hash, repaired_hash)
        self.assertNotIn(rule_id, {item.rule_id for item in repaired.findings})

    def test_ic_power_decoupling_enforces_capacitor_and_scope_boundaries(
        self,
    ) -> None:
        custom_return = ic_power_decoupling_fixture(
            capacitor_net="+3V3", capacitor_reference_net="CAP_REF"
        )
        custom_return = custom_return.model_copy(
            update={
                "components": {
                    **custom_return.components,
                    "U2": ComponentContract(value="Synthetic return pin", footprint=""),
                },
                "component_symbols": {
                    **custom_return.component_symbols,
                    "U2": "Synthetic:ReturnPin",
                },
                "nets": {**custom_return.nets, "CAP_REF": ("C1.2", "U2.2")},
                "pin_functions": {**custom_return.pin_functions, "U2.2": "GND"},
            }
        )
        cases = (
            # A DNP capacitor does not count as fitted.
            (ic_power_decoupling_fixture(capacitor_net="+3V3", dnp_capacitor=True), True),
            # A capacitor on another rail does not cover this rail.
            (ic_power_decoupling_fixture(capacitor_net="+5V"), True),
            # A capacitor without a recognized return connection does not count.
            (
                ic_power_decoupling_fixture(capacitor_net="+3V3", capacitor_reference_net="+5V"),
                True,
            ),
            (
                ic_power_decoupling_fixture(
                    capacitor_net="+3V3", capacitor_reference_net="CAP_REF"
                ),
                True,
            ),
            (custom_return, False),
            # An open or same-net terminal assignment does not count.
            (
                ic_power_decoupling_fixture(capacitor_net="+3V3", capacitor_reference_net=None),
                True,
            ),
            (
                ic_power_decoupling_fixture(capacitor_net="+3V3", capacitor_reference_net="+3V3"),
                True,
            ),
            # A CP-prefixed IC library name is not a capacitor symbol.
            (
                ic_power_decoupling_fixture().model_copy(
                    update={"component_symbols": {"U1": "Synthetic:CP2102"}}
                ),
                True,
            ),
            # DNP ICs and connector power pins are outside the rule.
            (ic_power_decoupling_fixture(dnp_ic=True), False),
            (ic_power_decoupling_fixture(reference="J1"), False),
            # Only native power-input pins on narrowly recognized positive rails qualify.
            (ic_power_decoupling_fixture(electrical_type="passive"), False),
            (
                ic_power_decoupling_fixture(rail="LOCAL_A", power_function="LOCAL_SUPPLY"),
                False,
            ),
        )
        for source, expected in cases:
            with self.subTest(
                dnp=source.dnp_components,
                rails=tuple(source.nets),
                power_type=source.pin_electrical_types,
            ):
                report = evaluate(
                    "synthetic-decoupling-presence-boundary",
                    coach(source),
                    DesignLintPolicy(),
                )
                present = "power.ic_rail_without_fitted_capacitor" in {
                    item.rule_id for item in report.findings
                }
                self.assertEqual(present, expected)

    def test_ic_power_decoupling_review_supports_rule_policy_and_exact_ignore(self) -> None:
        source = ic_power_decoupling_fixture()
        initial = evaluate(
            "synthetic-decoupling-presence-policy", coach(source), DesignLintPolicy()
        )
        finding = next(
            item
            for item in initial.findings
            if item.rule_id == "power.ic_rail_without_fitted_capacitor"
        )
        blocked = evaluate(
            "synthetic-decoupling-presence-policy",
            coach(source),
            DesignLintPolicy(
                rules=(
                    DesignLintRuleOverride(
                        rule_id="power.ic_rail_without_fitted_capacitor",
                        mode="block",
                        reason="Synthetic project requires owner review of uncapped IC rails",
                    ),
                )
            ),
        )
        self.assertEqual(blocked.status, "FAIL")

        disabled = evaluate(
            "synthetic-decoupling-presence-policy",
            coach(source),
            DesignLintPolicy(
                rules=(
                    DesignLintRuleOverride(
                        rule_id="power.ic_rail_without_fitted_capacitor",
                        mode="off",
                        reason="Synthetic project documents internal or off-board decoupling",
                    ),
                )
            ),
        )
        self.assertEqual(disabled.status, "PASS")
        self.assertEqual(
            next(
                item
                for item in disabled.findings
                if item.rule_id == "power.ic_rail_without_fitted_capacitor"
            ).disposition,
            "RULE_OFF",
        )

        ignored = evaluate(
            "synthetic-decoupling-presence-policy",
            coach(source),
            DesignLintPolicy(
                ignores=(
                    DesignLintIgnore(
                        rule_id="power.ic_rail_without_fitted_capacitor",
                        fingerprint=finding.fingerprint,
                        reason="Synthetic control records an intentional remote decoupling plan",
                    ),
                )
            ),
        )
        self.assertEqual(ignored.status, "PASS")
        self.assertEqual(
            next(
                item
                for item in ignored.findings
                if item.rule_id == "power.ic_rail_without_fitted_capacitor"
            ).disposition,
            "IGNORED",
        )
