"""Fault/control tests for direct output-driven LED review candidates."""

from __future__ import annotations

import hashlib
import unittest

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.models import (
    ComponentContract,
    ComponentRoleBinding,
    ComponentRoleMap,
    ComponentRolePin,
    ContractCoachReport,
    DesignLintIgnore,
    DesignLintPolicy,
    DesignLintRuleOverride,
    NetlistContract,
)

RULE_ID = "component.led_directly_driven_from_output"


def output_led_netlist(
    topology: str = "direct",
    *,
    output_type: str | None = "output",
    dnp: tuple[str, ...] = (),
    led_symbol: str = "Device:LED",
    return_net: str = "GND",
    led_part_id: str | None = None,
    led_footprint: str = "Synthetic:LED",
) -> NetlistContract:
    components = {
        "U1": ComponentContract(value="Synthetic output", footprint="Synthetic:IC"),
        "D1": ComponentContract(value="LED", footprint=led_footprint, part_id=led_part_id),
    }
    symbols = {"U1": "Synthetic:OutputDevice", "D1": led_symbol}
    pin_numbers: dict[str, tuple[str, ...]] = {"U1": ("1",), "D1": ("1", "2")}
    pin_types = {} if output_type is None else {"U1.1": output_type}
    nets: dict[str, tuple[str, ...]]
    if topology == "direct":
        nets = {"GPIO_LED": ("U1.1", "D1.1"), return_net: ("D1.2",)}
    elif topology == "series-output-side":
        components["R1"] = ComponentContract(value="1k", footprint="Synthetic:R")
        symbols["R1"] = "Device:R"
        pin_numbers["R1"] = ("1", "2")
        nets = {
            "GPIO_SOURCE": ("U1.1", "R1.1"),
            "LED_SIGNAL": ("R1.2", "D1.1"),
            return_net: ("D1.2",),
        }
    elif topology == "series-return-side":
        components["R1"] = ComponentContract(value="1k", footprint="Synthetic:R")
        symbols["R1"] = "Device:R"
        pin_numbers["R1"] = ("1", "2")
        nets = {
            "GPIO_LED": ("U1.1", "D1.1"),
            "LED_RETURN": ("D1.2", "R1.1"),
            return_net: ("R1.2",),
        }
    elif topology == "parallel-resistor":
        components["R1"] = ComponentContract(value="1k", footprint="Synthetic:R")
        symbols["R1"] = "Device:R"
        pin_numbers["R1"] = ("1", "2")
        nets = {
            "GPIO_LED": ("U1.1", "D1.1", "R1.1"),
            return_net: ("D1.2", "R1.2"),
        }
    else:
        raise ValueError(f"Unsupported synthetic topology: {topology}")
    return NetlistContract(
        components=components,
        nets=nets,
        dnp_components=dnp,
        component_symbols=symbols,
        pin_functions={"D1.1": "A", "D1.2": "K"},
        pin_electrical_types={**pin_types, "D1.1": "passive", "D1.2": "passive"},
        component_pin_numbers=pin_numbers,
    )


def custom_led_role_map(
    basis: str = "Synthetic reviewed library symbol declaration",
) -> ComponentRoleMap:
    return ComponentRoleMap(
        entries=(
            ComponentRoleBinding(
                part_id="training-led",
                symbol="Training:LED_5mm",
                footprint="Training:LED_0603",
                role="led",
                pins=(
                    ComponentRolePin(number="1", function="A", electrical_type="passive"),
                    ComponentRolePin(number="2", function="K", electrical_type="passive"),
                ),
                basis=basis,
            ),
        )
    )


def observed_report(netlist: NetlistContract, policy: DesignLintPolicy | None = None):
    encoded = netlist.model_dump_json().encode("utf-8")
    netlist_sha256 = hashlib.sha256(encoded).hexdigest()
    coach = ContractCoachReport(
        status="READY_FOR_REVIEW",
        project_id="synthetic-led-output",
        netlist_sha256=netlist_sha256,
        observed=netlist,
    )
    return evaluate(coach.project_id, coach, policy or DesignLintPolicy())


class LedOutputHeuristicTests(unittest.TestCase):
    def test_direct_output_to_led_and_return_is_reviewable_and_configurable(self) -> None:
        source = output_led_netlist()
        report = observed_report(source)
        finding = next(item for item in report.findings if item.rule_id == RULE_ID)
        self.assertEqual(report.status, "REVIEW")
        self.assertEqual(finding.subject, "D1: LED directly shares an output net and a rail")
        self.assertEqual(finding.evidence["led_pins"], ("D1.1", "D1.2"))
        self.assertEqual(finding.evidence["output_pins"], ("U1.1",))
        self.assertEqual(finding.evidence["output_pin_types"], ("U1.1=output",))
        self.assertEqual(finding.evidence["driven_net"], ("GPIO_LED",))
        self.assertEqual(finding.evidence["opposite_net_role"], ("return",))
        self.assertIn("does not infer LED polarity", finding.message)

        blocked = evaluate(
            "synthetic-led-output",
            ContractCoachReport(
                status="READY_FOR_REVIEW",
                project_id="synthetic-led-output",
                netlist_sha256=report.netlist_sha256,
                observed=source,
            ),
            DesignLintPolicy(
                rules=(
                    DesignLintRuleOverride(
                        rule_id=RULE_ID,
                        mode="block",
                        reason="Synthetic project requires output-driven indicator review",
                    ),
                )
            ),
        )
        self.assertEqual(blocked.status, "FAIL")

        ignored = evaluate(
            "synthetic-led-output",
            ContractCoachReport(
                status="READY_FOR_REVIEW",
                project_id="synthetic-led-output",
                netlist_sha256=report.netlist_sha256,
                observed=source,
            ),
            DesignLintPolicy(
                ignores=(
                    DesignLintIgnore(
                        rule_id=finding.rule_id,
                        fingerprint=finding.fingerprint,
                        reason="Synthetic output pin has an independently verified current limit",
                    ),
                )
            ),
        )
        self.assertEqual(ignored.status, "PASS")
        self.assertEqual(ignored.findings[0].disposition, "IGNORED")

        disabled = evaluate(
            "synthetic-led-output",
            ContractCoachReport(
                status="READY_FOR_REVIEW",
                project_id="synthetic-led-output",
                netlist_sha256=report.netlist_sha256,
                observed=source,
            ),
            DesignLintPolicy(
                rules=(
                    DesignLintRuleOverride(
                        rule_id=RULE_ID,
                        mode="off",
                        reason="Synthetic project reviews this indicator in a separate driver contract",
                    ),
                )
            ),
        )
        self.assertEqual(disabled.status, "PASS")
        self.assertEqual(disabled.findings[0].disposition, "RULE_OFF")

    def test_visible_series_resistor_and_unrecognized_output_are_controls(self) -> None:
        controls = (
            output_led_netlist("series-output-side"),
            output_led_netlist("series-return-side"),
            output_led_netlist(output_type=None),
            output_led_netlist(output_type="input"),
            output_led_netlist(dnp=("U1",)),
            output_led_netlist(dnp=("D1",)),
            output_led_netlist(led_symbol="Custom:LED"),
            output_led_netlist(return_net="LOCAL_REFERENCE"),
        )
        for source in controls:
            with self.subTest(nets=source.nets, dnp=source.dnp_components):
                self.assertNotIn(
                    RULE_ID, {item.rule_id for item in observed_report(source).findings}
                )

    def test_open_drain_output_is_reviewed_but_parallel_resistor_stays_a_fault(self) -> None:
        for pin_type in ("bidirectional", "tri_state", "open_collector", "open_emitter"):
            with self.subTest(pin_type=pin_type):
                report = observed_report(output_led_netlist(output_type=pin_type))
                self.assertIn(RULE_ID, {item.rule_id for item in report.findings})

        parallel = observed_report(output_led_netlist("parallel-resistor"))
        self.assertIn(RULE_ID, {item.rule_id for item in parallel.findings})

    def test_output_led_finding_is_order_stable_and_clears_on_series_path(self) -> None:
        source = output_led_netlist()
        original = observed_report(source)
        original_finding = next(item for item in original.findings if item.rule_id == RULE_ID)
        reordered = source.model_copy(
            update={
                "components": dict(reversed(tuple(source.components.items()))),
                "nets": dict(reversed(tuple(source.nets.items()))),
                "component_symbols": dict(reversed(tuple(source.component_symbols.items()))),
                "component_pin_numbers": dict(
                    reversed(tuple(source.component_pin_numbers.items()))
                ),
                "pin_electrical_types": dict(reversed(tuple(source.pin_electrical_types.items()))),
            }
        )
        reordered_finding = next(
            item for item in observed_report(reordered).findings if item.rule_id == RULE_ID
        )
        self.assertEqual(original_finding.fingerprint, reordered_finding.fingerprint)
        self.assertEqual(original_finding.evidence, reordered_finding.evidence)
        self.assertNotIn(
            RULE_ID,
            {
                item.rule_id
                for item in observed_report(output_led_netlist("series-return-side")).findings
            },
        )

    def test_custom_led_needs_exact_project_role_map_and_reports_review_basis(self) -> None:
        custom = output_led_netlist(
            led_symbol="Training:LED_5mm",
            led_part_id="training-led",
            led_footprint="Training:LED_0603",
        )
        self.assertNotIn(RULE_ID, {item.rule_id for item in observed_report(custom).findings})

        role_map = custom_led_role_map()
        mapped = observed_report(custom, DesignLintPolicy(component_role_map=role_map))
        finding = next(item for item in mapped.findings if item.rule_id == RULE_ID)
        self.assertEqual(mapped.status, "REVIEW")
        self.assertEqual(finding.evidence["classified_role"], ("led",))
        self.assertEqual(finding.evidence["role_part_id"], ("training-led",))
        self.assertEqual(finding.evidence["role_symbol"], ("Training:LED_5mm",))
        self.assertEqual(finding.evidence["role_footprint"], ("Training:LED_0603",))
        self.assertEqual(
            finding.evidence["role_pin_inventory"],
            ("1=A/passive", "2=K/passive"),
        )
        self.assertEqual(
            finding.evidence["role_basis"],
            ("Synthetic reviewed library symbol declaration",),
        )
        self.assertRegex(finding.evidence["role_binding_sha256"][0], r"^[a-f0-9]{64}$")

        series_control = output_led_netlist(
            "series-return-side",
            led_symbol="Training:LED_5mm",
            led_part_id="training-led",
            led_footprint="Training:LED_0603",
        )
        self.assertNotIn(
            RULE_ID,
            {
                item.rule_id
                for item in observed_report(
                    series_control, DesignLintPolicy(component_role_map=role_map)
                ).findings
            },
        )
        same_value_unlisted_symbol = output_led_netlist(
            led_symbol="Training:UnrelatedPart",
            led_part_id="training-unlisted",
            led_footprint="Training:LED_0603",
        )
        self.assertNotIn(
            RULE_ID,
            {item.rule_id for item in observed_report(same_value_unlisted_symbol).findings},
        )

    def test_custom_led_role_map_is_exact_and_stale_identity_blocks_lint(self) -> None:
        custom = output_led_netlist(
            led_symbol="Training:LED_5mm",
            led_part_id="training-led",
            led_footprint="Training:LED_0603",
        )
        wrong_symbol = custom.model_copy(
            update={"component_symbols": {**custom.component_symbols, "D1": "Training:OtherLED"}}
        )
        wrong_footprint = custom.model_copy(
            update={
                "components": {
                    **custom.components,
                    "D1": custom.components["D1"].model_copy(
                        update={"footprint": "Training:OtherFootprint"}
                    ),
                }
            }
        )
        wrong_pin_function = custom.model_copy(
            update={"pin_functions": {**custom.pin_functions, "D1.1": "CATHODE"}}
        )
        wrong_pin_inventory = custom.model_copy(
            update={"component_pin_numbers": {**custom.component_pin_numbers, "D1": ("1", "3")}}
        )
        wrong_part_id = custom.model_copy(
            update={
                "components": {
                    **custom.components,
                    "D1": custom.components["D1"].model_copy(update={"part_id": "different-led"}),
                }
            }
        )
        for source in (
            wrong_symbol,
            wrong_footprint,
            wrong_pin_function,
            wrong_pin_inventory,
            wrong_part_id,
        ):
            with self.subTest(source=source.model_dump(mode="json")):
                report = observed_report(
                    source,
                    DesignLintPolicy(component_role_map=custom_led_role_map()),
                )
                self.assertEqual(report.status, "BLOCKED")
                self.assertTrue(any("role map" in issue.casefold() for issue in report.issues))
                self.assertNotIn(RULE_ID, {item.rule_id for item in report.findings})

    def test_custom_capacitor_role_does_not_activate_led_rule(self) -> None:
        capacitor = output_led_netlist(
            led_symbol="Vendor:CAP123",
            led_part_id="synthetic-capacitor",
            led_footprint="Synthetic:CAP123_0603",
        )
        role_map = ComponentRoleMap(
            entries=(
                ComponentRoleBinding(
                    part_id="synthetic-capacitor",
                    symbol="Vendor:CAP123",
                    footprint="Synthetic:CAP123_0603",
                    role="capacitor",
                    pins=(
                        ComponentRolePin(number="1", function="A", electrical_type="passive"),
                        ComponentRolePin(number="2", function="K", electrical_type="passive"),
                    ),
                    basis="Synthetic fixture maps this opaque part only as a capacitor",
                ),
            )
        )
        report = observed_report(capacitor, DesignLintPolicy(component_role_map=role_map))
        self.assertNotIn(RULE_ID, {item.rule_id for item in report.findings})

    def test_custom_led_role_fingerprint_is_order_stable_and_basis_bound(self) -> None:
        custom = output_led_netlist(
            led_symbol="Training:LED_5mm",
            led_part_id="training-led",
            led_footprint="Training:LED_0603",
        )
        ordered_map = custom_led_role_map()
        reversed_pins = ordered_map.model_copy(
            update={
                "entries": (
                    ordered_map.entries[0].model_copy(
                        update={"pins": tuple(reversed(ordered_map.entries[0].pins))}
                    ),
                )
            }
        )
        first = next(
            item
            for item in observed_report(
                custom, DesignLintPolicy(component_role_map=ordered_map)
            ).findings
            if item.rule_id == RULE_ID
        )
        reordered = next(
            item
            for item in observed_report(
                custom, DesignLintPolicy(component_role_map=reversed_pins)
            ).findings
            if item.rule_id == RULE_ID
        )
        changed_basis = next(
            item
            for item in observed_report(
                custom,
                DesignLintPolicy(component_role_map=custom_led_role_map("Updated reviewed basis")),
            ).findings
            if item.rule_id == RULE_ID
        )
        self.assertEqual(first.fingerprint, reordered.fingerprint)
        self.assertEqual(first.evidence, reordered.evidence)
        self.assertNotEqual(first.fingerprint, changed_basis.fingerprint)
        self.assertNotEqual(
            first.evidence["role_binding_sha256"],
            changed_basis.evidence["role_binding_sha256"],
        )


if __name__ == "__main__":
    unittest.main()
