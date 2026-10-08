"""Synthetic source-bound I2C responder-address coverage and lint regressions."""

from __future__ import annotations

import hashlib
import unittest

from pydantic import ValidationError

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.i2c_addressing import scan_i2c_address_map
from kicad_tooling.hwrepo.models import (
    ComponentContract,
    ContractCoachReport,
    DesignLintIgnore,
    DesignLintPolicy,
    DesignLintRuleOverride,
    I2cAddressBitRequirement,
    I2cAddressMap,
    I2cAddressSegmentRequirement,
    I2cResponderAddressRequirement,
    NetlistContract,
)

_NETLIST_HASH = "b" * 64


def responder(
    reference: str,
    *,
    address: int | None = 0x50,
    strap: bool = True,
    segment: str = "MAIN",
) -> tuple[str, I2cResponderAddressRequirement]:
    address_bits = (
        (
            I2cAddressBitRequirement(
                bit=0,
                pin=f"{reference}.3",
                function="A0",
                low_net="GND",
                high_net="+3V3",
            ),
        )
        if strap
        else ()
    )
    mode = "strapped" if strap else "fixed" if address is not None else "dynamic"
    return (
        segment,
        I2cResponderAddressRequirement(
            reference=reference,
            expected_symbol="Synthetic:EEPROM",
            sda_pin=f"{reference}.1",
            scl_pin=f"{reference}.2",
            mode=mode,
            address=address,
            address_bits=address_bits,
            basis=f"Synthetic reviewed address basis for {reference}",
        ),
    )


def address_map(*responders: tuple[str, I2cResponderAddressRequirement]) -> I2cAddressMap:
    grouped: dict[str, list[I2cResponderAddressRequirement]] = {}
    for segment, requirement in responders:
        grouped.setdefault(segment, []).append(requirement)
    return I2cAddressMap(
        basis="Synthetic segment and responder map",
        segments=tuple(
            I2cAddressSegmentRequirement(
                id=segment,
                sda_net=f"{segment}_SDA",
                scl_net=f"{segment}_SCL",
                responders=tuple(items),
            )
            for segment, items in sorted(grouped.items())
        ),
    )


def address_netlist(
    specification: I2cAddressMap,
    *,
    strap_values: dict[str, int | None] | None = None,
    symbol_overrides: dict[str, str] | None = None,
    function_overrides: dict[str, str] | None = None,
    misplaced_pins: dict[str, str] | None = None,
    dnp: tuple[str, ...] = (),
) -> NetlistContract:
    strap_values = strap_values or {}
    symbol_overrides = symbol_overrides or {}
    function_overrides = function_overrides or {}
    misplaced_pins = misplaced_pins or {}
    components: dict[str, ComponentContract] = {}
    symbols: dict[str, str] = {}
    functions: dict[str, str] = {}
    pin_numbers: dict[str, tuple[str, ...]] = {}
    nets: dict[str, list[str]] = {}

    for segment in specification.segments:
        for requirement in segment.responders:
            reference = requirement.reference
            components[reference] = ComponentContract(value="EEPROM", footprint="Synthetic:SOIC8")
            symbols[reference] = symbol_overrides.get(reference, requirement.expected_symbol)
            all_pins = {requirement.sda_pin, requirement.scl_pin}
            all_pins.update(item.pin for item in requirement.address_bits)
            pin_numbers[reference] = tuple(
                sorted((pin.rsplit(".", 1)[1] for pin in all_pins), key=int)
            )
            functions[requirement.sda_pin] = function_overrides.get(requirement.sda_pin, "SDA")
            functions[requirement.scl_pin] = function_overrides.get(requirement.scl_pin, "SCL")
            nets.setdefault(misplaced_pins.get(requirement.sda_pin, segment.sda_net), []).append(
                requirement.sda_pin
            )
            nets.setdefault(misplaced_pins.get(requirement.scl_pin, segment.scl_net), []).append(
                requirement.scl_pin
            )
            for bit in requirement.address_bits:
                functions[bit.pin] = function_overrides.get(bit.pin, bit.function)
                value = strap_values.get(reference, 0)
                assigned_net = (
                    None if value is None else bit.low_net if value == 0 else bit.high_net
                )
                if assigned_net is not None:
                    nets.setdefault(misplaced_pins.get(bit.pin, assigned_net), []).append(bit.pin)

    resistor_number = 1
    for segment in specification.segments:
        for signal_net in (segment.sda_net, segment.scl_net):
            reference = f"R{resistor_number}"
            resistor_number += 1
            components[reference] = ComponentContract(value="4.7k", footprint="Synthetic:RES")
            pin_numbers[reference] = ("1", "2")
            nets.setdefault(signal_net, []).append(f"{reference}.1")
            nets.setdefault("+3V3", []).append(f"{reference}.2")

    return NetlistContract(
        components=components,
        nets={net: tuple(pins) for net, pins in nets.items()},
        dnp_components=dnp,
        component_symbols=symbols,
        pin_functions=functions,
        component_pin_numbers=pin_numbers,
    )


def coach(observed: NetlistContract, netlist_sha256: str = _NETLIST_HASH) -> ContractCoachReport:
    return ContractCoachReport(
        status="READY_FOR_REVIEW",
        project_id="synthetic-i2c-addresses",
        observed=observed,
        netlist_sha256=netlist_sha256,
    )


def unmapped_responder_netlist(reference: str = "U1") -> NetlistContract:
    return NetlistContract(
        components={
            reference: ComponentContract(value="Synthetic target", footprint="Synthetic:SOIC8"),
            "R1": ComponentContract(value="4.7k", footprint="Synthetic:RES"),
            "R2": ComponentContract(value="4.7k", footprint="Synthetic:RES"),
        },
        nets={
            "SDA_BUS": (f"{reference}.1", "R1.1"),
            "SCL_BUS": (f"{reference}.2", "R2.1"),
            "+3V3": ("R1.2", "R2.2"),
        },
        component_symbols={reference: "Synthetic:Target"},
        pin_functions={f"{reference}.1": "SDA", f"{reference}.2": "I2C_SCL"},
        component_pin_numbers={reference: ("1", "2")},
    )


class I2cAddressingTests(unittest.TestCase):
    def test_unmapped_responder_prompt_is_order_stable_and_map_entry_clears_it(self) -> None:
        segment, mapped_responder = responder("U1", strap=False)
        mapped_responder = mapped_responder.model_copy(
            update={"expected_symbol": "Synthetic:Target"}
        )
        specification = address_map((segment, mapped_responder))
        source = address_netlist(specification)
        rule_id = "bus.i2c_unmapped_responder"

        def lint(netlist: NetlistContract, address_map_specification: I2cAddressMap | None):
            source_hash = hashlib.sha256(netlist.model_dump_json().encode("utf-8")).hexdigest()
            policy = DesignLintPolicy(i2c_address_map=address_map_specification)
            return source_hash, evaluate(
                "synthetic-i2c-addresses", coach(netlist, source_hash), policy
            )

        source_hash, original = lint(source, None)
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
                "component_pin_numbers": dict(
                    reversed(tuple(source.component_pin_numbers.items()))
                ),
            }
        )
        reordered_hash, reordered = lint(reordered_source, None)
        self.assertNotEqual(source_hash, reordered_hash)
        self.assertEqual(reordered.netlist_sha256, reordered_hash)
        reordered_findings = {
            item.subject: (item.fingerprint, item.evidence)
            for item in reordered.findings
            if item.rule_id == rule_id
        }
        self.assertEqual(reordered_findings, original_findings)

        mapped_hash, mapped = lint(source, specification)
        self.assertEqual(mapped_hash, source_hash)
        self.assertEqual(mapped.i2c_address_coverage.status, "COMPLETE")
        self.assertEqual(mapped.i2c_address_coverage.netlist_sha256, source_hash)
        self.assertNotIn(rule_id, {item.rule_id for item in mapped.findings})

    def test_unmapped_addressable_ic_without_map_is_review_candidate(self) -> None:
        observed = unmapped_responder_netlist()
        report = evaluate(
            "synthetic-i2c-addresses",
            coach(observed),
            DesignLintPolicy(),
        )

        self.assertEqual(report.i2c_address_coverage.status, "NOT_REQUESTED")
        self.assertEqual(report.status, "REVIEW")
        candidates = [
            item for item in report.findings if item.rule_id == "bus.i2c_unmapped_responder"
        ]
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].subject, "U1: I2C address-map coverage")
        self.assertIn("no project I2C address map is configured", candidates[0].message)
        self.assertEqual(candidates[0].evidence["SDA_pins"], ("U1.1",))
        self.assertEqual(candidates[0].evidence["SCL_pins"], ("U1.2",))
        self.assertEqual(
            candidates[0].evidence["assigned_net_pairs"],
            ("SDA_BUS / SCL_BUS",),
        )
        self.assertEqual(candidates[0].mode, "review")

    def test_address_map_suppresses_listed_responder_and_finds_unlisted_peer(self) -> None:
        specification = address_map(responder("U1", strap=False))
        observed = address_netlist(specification)
        components = dict(observed.components)
        components["U2"] = ComponentContract(
            value="Synthetic second target", footprint="Synthetic:SOIC8"
        )
        nets = dict(observed.nets)
        nets["MAIN_SDA"] = (*nets["MAIN_SDA"], "U2.1")
        nets["MAIN_SCL"] = (*nets["MAIN_SCL"], "U2.2")
        symbols = dict(observed.component_symbols)
        symbols["U2"] = "Synthetic:Target"
        functions = dict(observed.pin_functions)
        functions.update({"U2.1": "SDA", "U2.2": "SCL"})
        pin_numbers = dict(observed.component_pin_numbers)
        pin_numbers["U2"] = ("1", "2")
        observed = observed.model_copy(
            update={
                "components": components,
                "nets": nets,
                "component_symbols": symbols,
                "pin_functions": functions,
                "component_pin_numbers": pin_numbers,
            }
        )

        report = evaluate(
            "synthetic-i2c-addresses",
            coach(observed),
            DesignLintPolicy(i2c_address_map=specification),
        )
        candidates = [
            item for item in report.findings if item.rule_id == "bus.i2c_unmapped_responder"
        ]
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].subject, "U2: I2C address-map coverage")
        self.assertIn("not listed as a responder", candidates[0].message)
        self.assertEqual(candidates[0].evidence["assigned_net_pairs"], ("MAIN_SDA / MAIN_SCL",))

    def test_address_map_candidate_skips_declared_dnp_and_non_ic_controls(self) -> None:
        specification = address_map(responder("U1", strap=False))
        mapped = evaluate(
            "synthetic-i2c-addresses",
            coach(address_netlist(specification)),
            DesignLintPolicy(i2c_address_map=specification),
        )
        self.assertFalse(
            any(item.rule_id == "bus.i2c_unmapped_responder" for item in mapped.findings)
        )

        dnp = unmapped_responder_netlist().model_copy(update={"dnp_components": ("U1",)})
        dnp_report = evaluate(
            "synthetic-i2c-addresses",
            coach(dnp),
            DesignLintPolicy(),
        )
        self.assertFalse(
            any(item.rule_id == "bus.i2c_unmapped_responder" for item in dnp_report.findings)
        )

        non_ic = unmapped_responder_netlist().model_copy(
            update={
                "components": {
                    "J1": ComponentContract(value="External connector", footprint="Synthetic:DB9"),
                    "R1": ComponentContract(value="4.7k", footprint="Synthetic:RES"),
                    "R2": ComponentContract(value="4.7k", footprint="Synthetic:RES"),
                },
                "nets": {
                    "SDA_BUS": ("J1.1", "R1.1"),
                    "SCL_BUS": ("J1.2", "R2.1"),
                    "+3V3": ("R1.2", "R2.2"),
                },
                "component_symbols": {"J1": "Synthetic:Connector"},
                "pin_functions": {"J1.1": "SDA", "J1.2": "SCL"},
                "component_pin_numbers": {"J1": ("1", "2")},
            }
        )
        non_ic_report = evaluate(
            "synthetic-i2c-addresses",
            coach(non_ic),
            DesignLintPolicy(),
        )
        self.assertFalse(
            any(item.rule_id == "bus.i2c_unmapped_responder" for item in non_ic_report.findings)
        )

    def test_unmapped_address_candidate_obeys_project_rule_mode(self) -> None:
        observed = unmapped_responder_netlist()
        review = evaluate(
            "synthetic-i2c-addresses",
            coach(observed),
            DesignLintPolicy(),
        )
        finding = next(
            item for item in review.findings if item.rule_id == "bus.i2c_unmapped_responder"
        )
        self.assertEqual(finding.mode, "review")
        self.assertEqual(finding.disposition, "OPEN")

        block_policy = DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id="bus.i2c_unmapped_responder",
                    mode="block",
                    reason="All fitted I2C ICs need an authored address disposition",
                ),
            )
        )
        blocked = evaluate("synthetic-i2c-addresses", coach(observed), block_policy)
        self.assertEqual(blocked.status, "FAIL")
        self.assertEqual(
            next(
                item for item in blocked.findings if item.rule_id == "bus.i2c_unmapped_responder"
            ).mode,
            "block",
        )

        off_policy = DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id="bus.i2c_unmapped_responder",
                    mode="off",
                    reason="This project uses no static I2C responders",
                ),
            )
        )
        off = evaluate("synthetic-i2c-addresses", coach(observed), off_policy)
        self.assertEqual(off.status, "PASS")
        self.assertEqual(
            next(
                item for item in off.findings if item.rule_id == "bus.i2c_unmapped_responder"
            ).disposition,
            "RULE_OFF",
        )

        ignored_policy = DesignLintPolicy(
            ignores=(
                DesignLintIgnore(
                    rule_id=finding.rule_id,
                    fingerprint=finding.fingerprint,
                    reason="Synthetic control records an intentionally unaddressed interface IC",
                ),
            )
        )
        ignored = evaluate("synthetic-i2c-addresses", coach(observed), ignored_policy)
        self.assertEqual(ignored.status, "PASS")
        self.assertEqual(
            next(item for item in ignored.findings if item.rule_id == finding.rule_id).disposition,
            "IGNORED",
        )

    def test_same_segment_static_address_collision_is_reported(self) -> None:
        first = responder("U1", strap=False)
        second = responder("U2", strap=False)
        spec = address_map(first, second)
        observed = address_netlist(spec)
        coverage = scan_i2c_address_map(spec, observed, _NETLIST_HASH)
        report = evaluate(
            "synthetic-i2c-addresses",
            coach(observed),
            DesignLintPolicy(i2c_address_map=spec),
        )

        self.assertEqual(coverage.status, "COMPLETE")
        self.assertEqual(coverage.netlist_sha256, _NETLIST_HASH)
        self.assertEqual(report.status, "REVIEW")
        collisions = [
            item for item in report.findings if item.rule_id == "bus.i2c_address_collision"
        ]
        self.assertEqual(len(collisions), 1)
        self.assertEqual(collisions[0].subject, "MAIN: U1, U2 at 0x50")
        self.assertEqual(collisions[0].evidence["U1.address"], ("expected 0x50; observed 0x50",))

    def test_collision_order_is_stable_and_separate_segments_clear_it(self) -> None:
        spec = address_map(responder("U1", strap=False), responder("U2", strap=False))
        reordered_spec = spec.model_copy(
            update={
                "segments": tuple(
                    segment.model_copy(update={"responders": tuple(reversed(segment.responders))})
                    for segment in reversed(spec.segments)
                )
            }
        )
        observed = address_netlist(spec)
        reordered_observed = observed.model_copy(
            update={
                "components": dict(reversed(tuple(observed.components.items()))),
                "nets": dict(reversed(tuple(observed.nets.items()))),
                "component_symbols": dict(reversed(tuple(observed.component_symbols.items()))),
                "pin_functions": dict(reversed(tuple(observed.pin_functions.items()))),
                "component_pin_numbers": dict(
                    reversed(tuple(observed.component_pin_numbers.items()))
                ),
            }
        )
        original_report = evaluate(
            "synthetic-i2c-addresses",
            coach(observed),
            DesignLintPolicy(i2c_address_map=spec),
        )
        reordered_report = evaluate(
            "synthetic-i2c-addresses",
            coach(reordered_observed),
            DesignLintPolicy(i2c_address_map=reordered_spec),
        )
        original_finding = next(
            item for item in original_report.findings if item.rule_id == "bus.i2c_address_collision"
        )
        reordered_finding = next(
            item
            for item in reordered_report.findings
            if item.rule_id == "bus.i2c_address_collision"
        )
        self.assertEqual(
            (reordered_finding.fingerprint, reordered_finding.evidence),
            (original_finding.fingerprint, original_finding.evidence),
        )
        self.assertEqual(
            tuple(
                (entry.reference, entry.status, entry.observed_address)
                for entry in sorted(
                    reordered_report.i2c_address_coverage.entries, key=lambda item: item.reference
                )
            ),
            tuple(
                (entry.reference, entry.status, entry.observed_address)
                for entry in sorted(
                    original_report.i2c_address_coverage.entries, key=lambda item: item.reference
                )
            ),
        )

        isolated_spec = address_map(
            responder("U1", strap=False, segment="MUX_A"),
            responder("U2", strap=False, segment="MUX_B"),
        )
        isolated_report = evaluate(
            "synthetic-i2c-addresses-isolated",
            coach(address_netlist(isolated_spec)),
            DesignLintPolicy(i2c_address_map=isolated_spec),
        )
        self.assertNotIn(
            "bus.i2c_address_collision",
            {item.rule_id for item in isolated_report.findings},
        )

    def test_address_strap_mismatch_is_reported(self) -> None:
        device = responder("U1", address=0x50)
        spec = address_map(device)
        observed = address_netlist(spec, strap_values={"U1": 1})
        report = evaluate(
            "synthetic-i2c-addresses",
            coach(observed),
            DesignLintPolicy(i2c_address_map=spec),
        )

        self.assertEqual(report.i2c_address_coverage.status, "COMPLETE")
        self.assertEqual(report.status, "REVIEW")
        mismatch = next(
            item for item in report.findings if item.rule_id == "bus.i2c_address_mismatch"
        )
        self.assertEqual(mismatch.subject, "U1 on MAIN: 0x51")
        self.assertEqual(mismatch.evidence["U1.bit0"], ("U1.3 function A0; nets +3V3; resolved 1",))

    def test_strap_mismatch_is_order_stable_and_corrected_strap_clears_it(self) -> None:
        specification = address_map(responder("U1", address=0x50))
        source = address_netlist(specification, strap_values={"U1": 1})
        rule_id = "bus.i2c_address_mismatch"

        def lint(netlist: NetlistContract):
            source_hash = hashlib.sha256(netlist.model_dump_json().encode("utf-8")).hexdigest()
            return source_hash, evaluate(
                "synthetic-i2c-addresses",
                coach(netlist, source_hash),
                DesignLintPolicy(i2c_address_map=specification),
            )

        source_hash, original = lint(source)
        self.assertEqual(original.netlist_sha256, source_hash)
        self.assertEqual(original.i2c_address_coverage.netlist_sha256, source_hash)
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
                "component_pin_numbers": dict(
                    reversed(tuple(source.component_pin_numbers.items()))
                ),
            }
        )
        reordered_hash, reordered = lint(reordered_source)
        self.assertNotEqual(source_hash, reordered_hash)
        self.assertEqual(reordered.netlist_sha256, reordered_hash)
        self.assertEqual(reordered.i2c_address_coverage.netlist_sha256, reordered_hash)
        reordered_findings = {
            item.subject: (item.fingerprint, item.evidence)
            for item in reordered.findings
            if item.rule_id == rule_id
        }
        self.assertEqual(reordered_findings, original_findings)

        repaired_hash, repaired = lint(address_netlist(specification, strap_values={"U1": 0}))
        self.assertNotEqual(source_hash, repaired_hash)
        self.assertEqual(repaired.i2c_address_coverage.status, "COMPLETE")
        self.assertEqual(repaired.i2c_address_coverage.netlist_sha256, repaired_hash)
        self.assertEqual(repaired.i2c_address_coverage.entries[0].observed_address, 0x50)
        self.assertNotIn(rule_id, {item.rule_id for item in repaired.findings})

    def test_distinct_straps_and_same_addresses_on_isolated_segments_are_valid(self) -> None:
        distinct = address_map(responder("U1", address=0x50), responder("U2", address=0x51))
        distinct_observed = address_netlist(distinct, strap_values={"U1": 0, "U2": 1})
        distinct_report = evaluate(
            "synthetic-i2c-addresses",
            coach(distinct_observed),
            DesignLintPolicy(i2c_address_map=distinct),
        )
        self.assertEqual(distinct_report.i2c_address_coverage.status, "COMPLETE")
        self.assertEqual(distinct_report.status, "PASS")
        self.assertFalse(distinct_report.findings)

        isolated = address_map(
            responder("U3", address=0x50, strap=False, segment="MUX_A"),
            responder("U4", address=0x50, strap=False, segment="MUX_B"),
        )
        isolated_report = evaluate(
            "synthetic-i2c-addresses",
            coach(address_netlist(isolated)),
            DesignLintPolicy(i2c_address_map=isolated),
        )
        self.assertEqual(isolated_report.i2c_address_coverage.status, "COMPLETE")
        self.assertEqual(isolated_report.status, "PASS")
        self.assertFalse(isolated_report.findings)

    def test_unresolved_and_dynamic_addresses_are_visible_coverage_gaps(self) -> None:
        spec = address_map(
            responder("U1", strap=False),
            responder("U2", address=0x50),
            responder("U3", address=None, strap=False),
        )
        observed = address_netlist(spec, strap_values={"U2": None})
        report = evaluate(
            "synthetic-i2c-addresses",
            coach(observed),
            DesignLintPolicy(i2c_address_map=spec),
        )

        self.assertEqual(report.status, "REVIEW")
        self.assertEqual(report.i2c_address_coverage.status, "INCOMPLETE")
        statuses = {entry.reference: entry.status for entry in report.i2c_address_coverage.entries}
        self.assertEqual(statuses["U2"], "INCOMPLETE")
        self.assertEqual(statuses["U3"], "DYNAMIC")
        self.assertFalse(
            any(item.rule_id == "bus.i2c_address_collision" for item in report.findings)
        )
        self.assertTrue(any("dynamic" in issue for issue in report.issues))

    def test_native_identity_pin_function_and_bus_mismatches_leave_coverage_incomplete(
        self,
    ) -> None:
        spec = address_map(responder("U1", address=0x50))
        valid = address_netlist(spec)
        variants = (
            (
                valid.model_copy(update={"components": {}}),
                "U1 is absent from the native netlist",
            ),
            (
                valid.model_copy(update={"component_symbols": {"U1": "Synthetic:Other"}}),
                "symbol is Synthetic:Other",
            ),
            (
                address_netlist(spec, function_overrides={"U1.3": "A1"}),
                "function is A1",
            ),
            (
                address_netlist(spec, misplaced_pins={"U1.1": "OTHER_SDA"}),
                "SDA pin U1.1 is on OTHER_SDA",
            ),
            (
                valid.model_copy(update={"component_pin_numbers": {"U1": ("1", "2")}}),
                "address pin U1.3 is absent",
            ),
        )
        for observed, expected in variants:
            with self.subTest(expected=expected):
                coverage = scan_i2c_address_map(spec, observed, _NETLIST_HASH)
                self.assertEqual(coverage.status, "INCOMPLETE")
                self.assertIn(expected, " ".join(coverage.issues))

    def test_not_fitted_responder_does_not_create_a_collision(self) -> None:
        spec = address_map(
            responder("U1", strap=False),
            responder("U2", strap=False),
        )
        observed = address_netlist(spec, dnp=("U2",))
        report = evaluate(
            "synthetic-i2c-addresses",
            coach(observed),
            DesignLintPolicy(i2c_address_map=spec),
        )

        self.assertEqual(report.i2c_address_coverage.status, "COMPLETE")
        statuses = {entry.reference: entry.status for entry in report.i2c_address_coverage.entries}
        self.assertEqual(statuses["U2"], "NOT_FITTED")
        self.assertFalse(report.findings)
        self.assertEqual(report.status, "PASS")

    def test_rule_can_block_or_accept_one_exact_collision(self) -> None:
        spec = address_map(
            responder("U1", strap=False),
            responder("U2", strap=False),
        )
        observed = address_netlist(spec)
        open_report = evaluate(
            "synthetic-i2c-addresses",
            coach(observed),
            DesignLintPolicy(i2c_address_map=spec),
        )
        collision = next(
            item for item in open_report.findings if item.rule_id == "bus.i2c_address_collision"
        )
        block_policy = DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id="bus.i2c_address_collision",
                    mode="block",
                    reason="Reviewed I2C segments cannot contain duplicate static addresses",
                ),
            ),
            i2c_address_map=spec,
        )
        blocked = evaluate("synthetic-i2c-addresses", coach(observed), block_policy)
        self.assertEqual(blocked.status, "FAIL")

        ignored_policy = block_policy.model_copy(
            update={
                "ignores": (
                    DesignLintIgnore(
                        rule_id=collision.rule_id,
                        fingerprint=collision.fingerprint,
                        reason="Synthetic test records the same address behind an approved mux",
                    ),
                )
            }
        )
        accepted = evaluate("synthetic-i2c-addresses", coach(observed), ignored_policy)
        self.assertEqual(accepted.status, "PASS")
        self.assertEqual(accepted.findings[0].disposition, "IGNORED")

    def test_address_map_rejects_ambiguous_pin_and_segment_declarations(self) -> None:
        first = responder("U1", address=0x50)
        with self.assertRaises(ValidationError):
            I2cAddressBitRequirement(
                bit=7,
                pin="U1.3",
                function="A0",
                low_net="GND",
                high_net="+3V3",
            )
        with self.assertRaisesRegex(ValidationError, "unique SDA/SCL net pairs"):
            I2cAddressMap(
                basis="Synthetic duplicate segments use one signal pair",
                segments=(
                    I2cAddressSegmentRequirement(
                        id="A",
                        sda_net="I2C_SDA",
                        scl_net="I2C_SCL",
                        responders=(first[1],),
                    ),
                    I2cAddressSegmentRequirement(
                        id="B",
                        sda_net="I2C_SDA",
                        scl_net="I2C_SCL",
                        responders=(responder("U2", address=0x50, segment="B")[1],),
                    ),
                ),
            )

        with self.assertRaisesRegex(ValidationError, "cannot share signal nets"):
            I2cAddressMap(
                basis="Synthetic shared endpoint must not declare isolated address domains",
                segments=(
                    I2cAddressSegmentRequirement(
                        id="A",
                        sda_net="SDA_A",
                        scl_net="SCL_SHARED",
                        responders=(first[1],),
                    ),
                    I2cAddressSegmentRequirement(
                        id="B",
                        sda_net="SDA_B",
                        scl_net="SCL_SHARED",
                        responders=(responder("U2", address=0x50, segment="B")[1],),
                    ),
                ),
            )


if __name__ == "__main__":
    unittest.main()
