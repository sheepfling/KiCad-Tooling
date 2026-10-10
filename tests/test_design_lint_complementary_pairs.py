"""Focused synthetic regressions for the complementary pairs lint theme."""

from __future__ import annotations

import hashlib
import unittest

import pytest
from pydantic import ValidationError

from kicad_tooling.hwrepo.design_lint import (
    candidates,
    evaluate,
    fingerprint,
)
from kicad_tooling.hwrepo.models import (
    ComplementaryPinFunctionAlias,
    ComplementaryPinFunctionAliasMap,
    ComponentContract,
    DesignLintIgnore,
    DesignLintPolicy,
    DesignLintReport,
    NetlistContract,
)
from tests.design_lint_fixtures import (
    can_netlist,
    coach,
    complementary_usb_netlist,
)

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.interface_lint,
]


class DesignLintComplementaryPairTests(unittest.TestCase):
    def test_complementary_pair_assignments_are_reviewed_without_inferred_requirements(
        self,
    ) -> None:
        missing_side = evaluate(
            "synthetic-usb", coach(complementary_usb_netlist(negative_net=None)), DesignLintPolicy()
        )
        pair_findings = [
            item
            for item in missing_side.findings
            if item.rule_id == "bus.complementary_pair_assignment"
        ]
        self.assertEqual(len(pair_findings), 1)
        self.assertEqual(pair_findings[0].evidence["positive_pins"], ("J1.1",))
        self.assertEqual(pair_findings[0].evidence["negative_pins"], ("J1.2",))
        self.assertEqual(pair_findings[0].evidence["negative_nets"], ())
        self.assertIn("lack a unique", pair_findings[0].message)

        shorted = complementary_usb_netlist(positive_net="USB_DATA", negative_net="USB_DATA")
        shorted_report = evaluate("synthetic-usb", coach(shorted), DesignLintPolicy())
        shorted_findings = [
            item
            for item in shorted_report.findings
            if item.rule_id == "bus.complementary_pair_assignment"
        ]
        self.assertEqual(len(shorted_findings), 1)
        self.assertIn("share one schematic net", shorted_findings[0].message)

        can_shorted = can_netlist().model_copy(update={"nets": {"CAN_BUS": ("U1.1", "U1.2")}})
        can_pair_findings = [
            item
            for item in evaluate("synthetic-can", coach(can_shorted), DesignLintPolicy()).findings
            if item.rule_id == "bus.complementary_pair_assignment"
        ]
        self.assertEqual(len(can_pair_findings), 1)

        for family, functions in (("TX", ("TXP", "TXN")), ("RX", ("RX+", "RX−"))):
            with self.subTest(family=family):
                paired = NetlistContract(
                    components={},
                    nets={"POS": ("U2.1",), "NEG": ("U2.2",)},
                    component_symbols={"U2": "Synthetic:DifferentialDevice"},
                    pin_functions={"U2.1": functions[0], "U2.2": functions[1]},
                )
                self.assertFalse(
                    any(
                        item.rule_id == "bus.complementary_pair_assignment"
                        for item in candidates(paired)
                    )
                )

        missing_counterpart = NetlistContract(
            components={},
            nets={"TX_POS": ("U3.1",)},
            component_symbols={"U3": "Synthetic:DifferentialDevice"},
            pin_functions={"U3.1": "TXP"},
        )
        missing_function = next(
            item
            for item in candidates(missing_counterpart)
            if item.rule_id == "bus.complementary_pair_assignment"
        )
        self.assertEqual(missing_function.evidence["negative_pins"], ())
        self.assertIn("absent from the symbol pin functions", missing_function.message)

        valid_pair = evaluate(
            "synthetic-usb", coach(complementary_usb_netlist()), DesignLintPolicy()
        )
        self.assertFalse(
            any(item.rule_id == "bus.complementary_pair_assignment" for item in valid_pair.findings)
        )

        intentionally_unused = complementary_usb_netlist(positive_net=None, negative_net=None)
        candidate = next(
            item
            for item in candidates(intentionally_unused)
            if item.rule_id == "bus.complementary_pair_assignment"
        )
        reviewed_unused = evaluate(
            "synthetic-usb",
            coach(intentionally_unused),
            DesignLintPolicy(
                ignores=(
                    DesignLintIgnore(
                        rule_id=candidate.rule_id,
                        fingerprint=fingerprint(candidate),
                        reason="This approved variant leaves its USB data pair unused",
                    ),
                )
            ),
        )
        self.assertEqual(reviewed_unused.status, "PASS")
        self.assertEqual(reviewed_unused.findings[0].disposition, "IGNORED")

    def test_usb_superspeed_connector_aliases_have_fault_and_control_coverage(self) -> None:
        rule_id = "bus.complementary_pair_assignment"
        for prefix in ("", "StdA_", "StdB_"):
            with self.subTest(prefix=prefix):
                functions = {
                    "J1.1": f"{prefix}SSTX+",
                    "J1.2": f"{prefix}SSTX−",
                    "J1.3": f"{prefix}SSRX+",
                    "J1.4": f"{prefix}SSRX−",
                }
                nets = {
                    "HOST_TO_PORT_POS": ("J1.1",),
                    "HOST_TO_PORT_NEG": ("J1.2",),
                    "PORT_TO_HOST_POS": ("J1.3",),
                    "PORT_TO_HOST_NEG": ("J1.4",),
                }
                control = NetlistContract(
                    components={},
                    nets=nets,
                    component_symbols={"J1": "Synthetic:UsbSuperSpeedPort"},
                    pin_functions=functions,
                )
                self.assertFalse(any(item.rule_id == rule_id for item in candidates(control)))

                fault = control.model_copy(
                    update={
                        "nets": {name: pins for name, pins in nets.items() if "J1.4" not in pins}
                    }
                )
                findings = [item for item in candidates(fault) if item.rule_id == rule_id]
                self.assertEqual(len(findings), 1)
                self.assertEqual(findings[0].subject, "J1: USB SuperSpeed RX pair")
                self.assertEqual(findings[0].evidence["positive_pins"], ("J1.3",))
                self.assertEqual(findings[0].evidence["negative_pins"], ("J1.4",))
                self.assertEqual(findings[0].evidence["negative_nets"], ())

        # USB-C has lane-indexed TX1/TX2 and RX1/RX2 pairs. Keep those outside
        # this single-pair-per-role heuristic until it can preserve lane identity.
        lane_indexed = NetlistContract(
            components={},
            nets={
                "TX1P": ("J2.1",),
                "TX1N": ("J2.2",),
                "TX2P": ("J2.3",),
                "TX2N": ("J2.4",),
                "RX1P": ("J2.5",),
                "RX1N": ("J2.6",),
                "RX2P": ("J2.7",),
                "RX2N": ("J2.8",),
            },
            component_symbols={"J2": "Synthetic:UsbTypeCPort"},
            pin_functions={
                "J2.1": "TX1+",
                "J2.2": "TX1−",
                "J2.3": "TX2+",
                "J2.4": "TX2−",
                "J2.5": "RX1+",
                "J2.6": "RX1−",
                "J2.7": "RX2+",
                "J2.8": "RX2−",
            },
        )
        self.assertFalse(any(item.rule_id == rule_id for item in candidates(lane_indexed)))

    def test_project_complementary_aliases_are_symbol_scoped_and_stale_maps_block(self) -> None:
        rule_id = "bus.complementary_pair_assignment"
        alias = ComplementaryPinFunctionAlias(
            symbol="Vendor:DualOutput",
            family="lane 0",
            positive_functions=("OUTP", "OUT_PLUS"),
            negative_functions=("OUTN", "OUT_MINUS"),
            basis="Synthetic project review maps these exact symbol functions as one pair",
        )
        policy = DesignLintPolicy(
            complementary_pin_function_alias_map=ComplementaryPinFunctionAliasMap(entries=(alias,))
        )

        def source(*, negative_net: str | None = None, dnp: bool = False) -> NetlistContract:
            nets = {"LANE0_P": ("U1.1",)}
            if negative_net is not None:
                nets[negative_net] = ("U1.2",)
            return NetlistContract(
                components={"U1": ComponentContract(value="Synthetic PHY", footprint="")},
                nets=nets,
                dnp_components=("U1",) if dnp else (),
                component_symbols={"U1": "Vendor:DualOutput"},
                pin_functions={"U1.1": "OUTP", "U1.2": "OUTN"},
                component_pin_numbers={"U1": ("1", "2")},
            )

        fault_source = source()
        fault = evaluate("synthetic-vendor-pair", coach(fault_source), policy)
        finding = next(item for item in fault.findings if item.rule_id == rule_id)
        self.assertEqual(fault.status, "REVIEW")
        self.assertEqual(finding.subject, "U1: lane 0 pair")
        self.assertEqual(finding.evidence["positive_pins"], ("U1.1",))
        self.assertEqual(finding.evidence["negative_pins"], ("U1.2",))
        self.assertEqual(finding.evidence["negative_nets"], ())
        self.assertEqual(finding.evidence["alias_symbol"], ("Vendor:DualOutput",))
        self.assertEqual(finding.evidence["alias_basis"], (alias.basis,))
        self.assertRegex(finding.evidence["alias_sha256"][0], r"^[a-f0-9]{64}$")

        baseline = evaluate("synthetic-vendor-pair", coach(fault_source), DesignLintPolicy())
        self.assertNotIn(rule_id, {item.rule_id for item in baseline.findings})

        valid = evaluate("synthetic-vendor-pair", coach(source(negative_net="LANE0_N")), policy)
        self.assertNotIn(rule_id, {item.rule_id for item in valid.findings})
        dnp = evaluate("synthetic-vendor-pair", coach(source(dnp=True)), policy)
        self.assertNotIn(rule_id, {item.rule_id for item in dnp.findings})

        reordered_alias = alias.model_copy(
            update={
                "positive_functions": tuple(reversed(alias.positive_functions)),
                "negative_functions": tuple(reversed(alias.negative_functions)),
            }
        )
        reordered_policy = DesignLintPolicy(
            complementary_pin_function_alias_map=ComplementaryPinFunctionAliasMap(
                entries=(reordered_alias,)
            )
        )
        reordered = evaluate("synthetic-vendor-pair", coach(fault_source), reordered_policy)
        reordered_finding = next(item for item in reordered.findings if item.rule_id == rule_id)
        self.assertEqual(
            (reordered_finding.fingerprint, reordered_finding.evidence),
            (finding.fingerprint, finding.evidence),
        )

        changed_basis = alias.model_copy(update={"basis": "Synthetic alternate review record"})
        changed_policy = DesignLintPolicy(
            complementary_pin_function_alias_map=ComplementaryPinFunctionAliasMap(
                entries=(changed_basis,)
            )
        )
        changed = evaluate("synthetic-vendor-pair", coach(fault_source), changed_policy)
        changed_finding = next(item for item in changed.findings if item.rule_id == rule_id)
        self.assertNotEqual(changed_finding.fingerprint, finding.fingerprint)

        stale_alias = alias.model_copy(
            update={
                "positive_functions": ("OLD_POSITIVE",),
                "negative_functions": ("OLD_NEGATIVE",),
            }
        )
        stale = evaluate(
            "synthetic-vendor-pair",
            coach(fault_source),
            DesignLintPolicy(
                complementary_pin_function_alias_map=ComplementaryPinFunctionAliasMap(
                    entries=(stale_alias,)
                )
            ),
        )
        self.assertEqual(stale.status, "BLOCKED")
        self.assertTrue(any("is stale" in item for item in stale.issues))
        self.assertTrue(
            any(
                "Refresh the project complementary pin-function alias map" in item
                for item in stale.next_actions
            )
        )

        wrong_symbol = alias.model_copy(update={"symbol": "Vendor:RenamedDevice"})
        exact_identity = evaluate(
            "synthetic-vendor-pair",
            coach(fault_source),
            DesignLintPolicy(
                complementary_pin_function_alias_map=ComplementaryPinFunctionAliasMap(
                    entries=(wrong_symbol,)
                )
            ),
        )
        self.assertEqual(exact_identity.status, "BLOCKED")
        self.assertTrue(
            any("no exact native symbol instance" in item for item in exact_identity.issues)
        )

        repeated_builtin = alias.model_copy(
            update={"positive_functions": ("TX+",), "negative_functions": ("TX-",)}
        )
        built_in_collision = evaluate(
            "synthetic-vendor-pair",
            coach(fault_source),
            DesignLintPolicy(
                complementary_pin_function_alias_map=ComplementaryPinFunctionAliasMap(
                    entries=(repeated_builtin,)
                )
            ),
        )
        self.assertEqual(built_in_collision.status, "BLOCKED")
        self.assertTrue(any("repeats built-in" in item for item in built_in_collision.issues))

        with self.assertRaises(ValidationError):
            ComplementaryPinFunctionAlias(
                symbol="Vendor:DualOutput",
                family="ambiguous",
                positive_functions=("OUTP",),
                negative_functions=(" out_p ",),
                basis="Invalid overlapping aliases",
            )

    def test_complementary_pair_finding_is_order_stable_and_assignment_clears_it(self) -> None:
        rule_id = "bus.complementary_pair_assignment"
        source = complementary_usb_netlist(negative_net=None)

        def lint(netlist: NetlistContract) -> tuple[str, DesignLintReport]:
            source_hash = hashlib.sha256(netlist.model_dump_json().encode("utf-8")).hexdigest()
            return source_hash, evaluate(
                "synthetic-usb", coach(netlist, source_hash), DesignLintPolicy()
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
                "nets": dict(reversed(tuple(source.nets.items()))),
                "component_symbols": dict(reversed(tuple(source.component_symbols.items()))),
                "pin_functions": dict(reversed(tuple(source.pin_functions.items()))),
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

        repaired_hash, repaired = lint(complementary_usb_netlist())
        self.assertNotEqual(source_hash, repaired_hash)
        self.assertNotIn(rule_id, {item.rule_id for item in repaired.findings})
