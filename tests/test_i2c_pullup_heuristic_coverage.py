"""Synthetic regressions for source-bound I2C pull-up hint resolution."""

from __future__ import annotations

import unittest

from kicad_tooling.hwrepo.bus_heuristics import i2c_pullup_heuristic_coverage
from kicad_tooling.hwrepo.design_lint import candidates, evaluate, text_report
from kicad_tooling.hwrepo.models import (
    ComponentContract,
    ContractCoachReport,
    DesignLintPolicy,
    I2cPullupAnalysis,
    I2cPullupArrayChannelRequirement,
    I2cPullupArrayRequirement,
    I2cPullupBusRequirement,
    I2cPullupLineRequirement,
    NetlistContract,
)


def array_netlist(
    *,
    symbol: str = "Synthetic:ResistorArray",
    dnp: tuple[str, ...] = (),
    swapped_sda_channel: bool = False,
    wrong_sda_net: bool = False,
) -> NetlistContract:
    sda_assignments = ("RN1.2", "RN1.1") if swapped_sda_channel else ("RN1.1", "RN1.2")
    return NetlistContract(
        components={"RN1": ComponentContract(value="4x4.7k", footprint="Synthetic:RA4")},
        nets={
            "I2C_SDA": ("U1.1",) if wrong_sda_net else ("U1.1", sda_assignments[0]),
            "I2C_SCL": ("U1.2", "RN1.3", sda_assignments[0])
            if wrong_sda_net
            else ("U1.2", "RN1.3"),
            "+3V3": (sda_assignments[1], "RN1.4"),
        },
        dnp_components=dnp,
        component_symbols={
            "U1": "Synthetic:I2cTarget",
            "RN1": symbol,
        },
        pin_functions={"U1.1": "SDA", "U1.2": "SCL"},
        component_pin_numbers={"U1": ("1", "2"), "RN1": ("1", "2", "3", "4")},
    )


def array_requirement() -> I2cPullupAnalysis:
    return I2cPullupAnalysis(
        basis="Synthetic datasheet pin map and bus resistance requirement",
        buses=(
            I2cPullupBusRequirement(
                id="main",
                basis="Synthetic two-wire interface requirement",
                sda=I2cPullupLineRequirement(
                    net="I2C_SDA", rail="+3V3", minimum_ohms=1_000, maximum_ohms=100_000
                ),
                scl=I2cPullupLineRequirement(
                    net="I2C_SCL", rail="+3V3", minimum_ohms=1_000, maximum_ohms=100_000
                ),
            ),
        ),
        arrays=(
            I2cPullupArrayRequirement(
                reference="RN1",
                expected_symbol="Synthetic:ResistorArray",
                expected_footprint="Synthetic:RA4",
                expected_value="4x4.7k",
                basis="Synthetic array datasheet and pin map",
                channels=(
                    I2cPullupArrayChannelRequirement(
                        id="sda",
                        signal_pin="RN1.1",
                        rail_pin="RN1.2",
                        signal_net="I2C_SDA",
                        rail_net="+3V3",
                        resistance_ohms=4_700,
                        basis="Synthetic array channel 1 map",
                    ),
                    I2cPullupArrayChannelRequirement(
                        id="scl",
                        signal_pin="RN1.3",
                        rail_pin="RN1.4",
                        signal_net="I2C_SCL",
                        rail_net="+3V3",
                        resistance_ohms=4_700,
                        basis="Synthetic array channel 2 map",
                    ),
                ),
            ),
        ),
    )


class I2cPullupHeuristicCoverageTests(unittest.TestCase):
    def coverage(
        self,
        netlist: NetlistContract,
        spec: I2cPullupAnalysis | None = None,
        *,
        state: str = "required",
    ):
        return i2c_pullup_heuristic_coverage(
            netlist,
            netlist_sha256="a" * 64,
            source_path="projects/synthetic/electrical.json",
            source_sha256="b" * 64,
            state=state,
            spec=spec,
        )

    def test_valid_mapped_array_resolves_only_its_exact_missing_path_hint(self) -> None:
        netlist = array_netlist()
        baseline = candidates(netlist)
        self.assertIn("bus.i2c_missing_pullup", {item.rule_id for item in baseline})

        coverage = self.coverage(netlist, array_requirement())
        self.assertEqual(coverage.status, "COMPLETE")
        self.assertEqual(len(coverage.entries), 1)
        entry = coverage.entries[0]
        self.assertEqual(entry.status, "COVERED")
        self.assertEqual(entry.missing_lines, ("SDA", "SCL"))
        self.assertEqual(entry.bus_id, "main")
        self.assertEqual(
            entry.check_ids,
            ("i2c-pullup/main/sda", "i2c-pullup/main/scl"),
        )
        resolved = candidates(netlist, i2c_pullup_heuristic_coverage=coverage)
        self.assertNotIn("bus.i2c_missing_pullup", {item.rule_id for item in resolved})

        report = evaluate(
            "synthetic-i2c-array",
            ContractCoachReport(
                status="READY_FOR_REVIEW",
                project_id="synthetic-i2c-array",
                observed=netlist,
                netlist_sha256="a" * 64,
            ),
            DesignLintPolicy(),
            i2c_pullup_heuristic_coverage=coverage,
        )
        self.assertEqual(report.i2c_pullup_heuristic_coverage, coverage)
        self.assertNotIn("bus.i2c_missing_pullup", {item.rule_id for item in report.findings})
        rendered = text_report(report)
        self.assertIn(
            "I2C pull-up heuristic coverage: COMPLETE (1/1 candidate pairs covered)", rendered
        )
        self.assertIn("projects/synthetic/electrical.json", rendered)
        self.assertIn("b" * 64, rendered)
        self.assertIn("Native netlist SHA-256: " + "a" * 64, rendered)

    def test_missing_or_failing_exact_requirement_keeps_the_review_prompt_open(self) -> None:
        netlist = array_netlist()
        cases = (
            (None, "not_configured", netlist),
            (array_requirement(), "required", array_netlist(symbol="Synthetic:Unknown")),
            (array_requirement(), "required", array_netlist(dnp=("RN1",))),
            (array_requirement(), "required", array_netlist(wrong_sda_net=True)),
        )
        for spec, state, observed in cases:
            with self.subTest(state=state, spec_present=spec is not None):
                coverage = self.coverage(observed, spec, state=state)
                self.assertEqual(coverage.entries[0].status, "OPEN")
                self.assertTrue(coverage.entries[0].issues)
                found = candidates(observed, i2c_pullup_heuristic_coverage=coverage)
                self.assertIn("bus.i2c_missing_pullup", {item.rule_id for item in found})

    def test_symmetric_array_pin_orientation_is_a_valid_control(self) -> None:
        coverage = self.coverage(array_netlist(swapped_sda_channel=True), array_requirement())
        self.assertEqual(coverage.entries[0].status, "COVERED")

    def test_stale_native_netlist_hash_blocks_coverage_instead_of_suppressing(self) -> None:
        netlist = array_netlist()
        stale = self.coverage(netlist, array_requirement()).model_copy(
            update={"netlist_sha256": "c" * 64}
        )
        report = evaluate(
            "synthetic-i2c-array",
            ContractCoachReport(
                status="READY_FOR_REVIEW",
                project_id="synthetic-i2c-array",
                observed=netlist,
                netlist_sha256="a" * 64,
            ),
            DesignLintPolicy(),
            i2c_pullup_heuristic_coverage=stale,
        )
        self.assertEqual(report.status, "BLOCKED")
        self.assertEqual(report.i2c_pullup_heuristic_coverage.status, "BLOCKED")
        self.assertEqual(report.i2c_pullup_heuristic_coverage.entries, ())
        self.assertIn("different or unavailable native netlist hash", report.issues[0])

    def test_requirement_for_a_different_ordered_bus_does_not_resolve_hint(self) -> None:
        wrong_bus = array_requirement().model_copy(
            update={
                "buses": (
                    array_requirement()
                    .buses[0]
                    .model_copy(
                        update={
                            "sda": array_requirement()
                            .buses[0]
                            .sda.model_copy(update={"net": "OTHER_SDA"})
                        }
                    ),
                )
            }
        )
        netlist = array_netlist()
        coverage = self.coverage(netlist, wrong_bus)
        self.assertEqual(coverage.entries[0].status, "OPEN")
        self.assertIn("exact ordered SDA/SCL", coverage.entries[0].issues[0])
        self.assertIn(
            "bus.i2c_missing_pullup",
            {item.rule_id for item in candidates(netlist, i2c_pullup_heuristic_coverage=coverage)},
        )

    def test_pending_and_not_applicable_contracts_do_not_assume_external_pullups(self) -> None:
        netlist = array_netlist()
        for state, expected_status in (
            ("pending", "PENDING"),
            ("not_applicable", "NOT_APPLICABLE"),
        ):
            with self.subTest(state=state):
                coverage = self.coverage(netlist, state=state)
                self.assertEqual(coverage.status, expected_status)
                self.assertEqual(coverage.entries[0].status, "OPEN")
                self.assertIn(
                    "bus.i2c_missing_pullup",
                    {
                        item.rule_id
                        for item in candidates(netlist, i2c_pullup_heuristic_coverage=coverage)
                    },
                )


if __name__ == "__main__":
    unittest.main()
