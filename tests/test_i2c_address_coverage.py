"""Focused source-bound I2C address coverage regressions."""

from __future__ import annotations

import hashlib

import pytest

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.i2c_addressing import scan_i2c_address_map
from kicad_tooling.hwrepo.models import (
    ComponentContract,
    DesignLintIgnore,
    DesignLintPolicy,
    DesignLintRuleOverride,
    I2cAddressMap,
    NetlistContract,
)
from tests.design_lint_fixtures.i2c_addresses import (
    _NETLIST_HASH,
    address_map,
    address_netlist,
    coach,
    responder,
    unmapped_responder_netlist,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint]


def test_unmapped_responder_prompt_is_order_stable_and_map_entry_clears_it() -> None:
    segment, mapped_responder = responder("U1", strap=False)
    mapped_responder = mapped_responder.model_copy(update={"expected_symbol": "Synthetic:Target"})
    specification = address_map((segment, mapped_responder))
    source = address_netlist(specification)
    rule_id = "bus.i2c_unmapped_responder"

    def lint(netlist: NetlistContract, address_map_specification: I2cAddressMap | None):
        source_hash = hashlib.sha256(netlist.model_dump_json().encode("utf-8")).hexdigest()
        policy = DesignLintPolicy(i2c_address_map=address_map_specification)
        return source_hash, evaluate("synthetic-i2c-addresses", coach(netlist, source_hash), policy)

    source_hash, original = lint(source, None)
    assert original.netlist_sha256 == source_hash
    original_findings = {
        item.subject: (item.fingerprint, item.evidence)
        for item in original.findings
        if item.rule_id == rule_id
    }
    assert len(original_findings) == 1

    reordered_source = source.model_copy(
        update={
            "components": dict(reversed(tuple(source.components.items()))),
            "nets": dict(reversed(tuple(source.nets.items()))),
            "component_symbols": dict(reversed(tuple(source.component_symbols.items()))),
            "pin_functions": dict(reversed(tuple(source.pin_functions.items()))),
            "component_pin_numbers": dict(reversed(tuple(source.component_pin_numbers.items()))),
        }
    )
    reordered_hash, reordered = lint(reordered_source, None)
    assert source_hash != reordered_hash
    assert reordered.netlist_sha256 == reordered_hash
    reordered_findings = {
        item.subject: (item.fingerprint, item.evidence)
        for item in reordered.findings
        if item.rule_id == rule_id
    }
    assert reordered_findings == original_findings

    mapped_hash, mapped = lint(source, specification)
    assert mapped_hash == source_hash
    assert mapped.i2c_address_coverage.status == "COMPLETE"
    assert mapped.i2c_address_coverage.netlist_sha256 == source_hash
    assert rule_id not in {item.rule_id for item in mapped.findings}


def test_unmapped_addressable_ic_without_map_is_review_candidate() -> None:
    observed = unmapped_responder_netlist()
    report = evaluate(
        "synthetic-i2c-addresses",
        coach(observed),
        DesignLintPolicy(),
    )

    assert report.i2c_address_coverage.status == "NOT_REQUESTED"
    assert report.status == "REVIEW"
    candidates = [item for item in report.findings if item.rule_id == "bus.i2c_unmapped_responder"]
    assert len(candidates) == 1
    assert candidates[0].subject == "U1: I2C address-map coverage"
    assert "no project I2C address map is configured" in candidates[0].message
    assert candidates[0].evidence["SDA_pins"] == ("U1.1",)
    assert candidates[0].evidence["SCL_pins"] == ("U1.2",)
    assert candidates[0].evidence["assigned_net_pairs"] == ("SDA_BUS / SCL_BUS",)
    assert candidates[0].mode == "review"


def test_address_map_suppresses_listed_responder_and_finds_unlisted_peer() -> None:
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
    candidates = [item for item in report.findings if item.rule_id == "bus.i2c_unmapped_responder"]
    assert len(candidates) == 1
    assert candidates[0].subject == "U2: I2C address-map coverage"
    assert "not listed as a responder" in candidates[0].message
    assert candidates[0].evidence["assigned_net_pairs"] == ("MAIN_SDA / MAIN_SCL",)


def test_address_map_candidate_skips_declared_dnp_and_non_ic_controls() -> None:
    specification = address_map(responder("U1", strap=False))
    mapped = evaluate(
        "synthetic-i2c-addresses",
        coach(address_netlist(specification)),
        DesignLintPolicy(i2c_address_map=specification),
    )
    assert not any(item.rule_id == "bus.i2c_unmapped_responder" for item in mapped.findings)

    dnp = unmapped_responder_netlist().model_copy(update={"dnp_components": ("U1",)})
    dnp_report = evaluate(
        "synthetic-i2c-addresses",
        coach(dnp),
        DesignLintPolicy(),
    )
    assert not any(item.rule_id == "bus.i2c_unmapped_responder" for item in dnp_report.findings)

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
    assert not any(item.rule_id == "bus.i2c_unmapped_responder" for item in non_ic_report.findings)


def test_unmapped_address_candidate_obeys_project_rule_mode() -> None:
    observed = unmapped_responder_netlist()
    review = evaluate(
        "synthetic-i2c-addresses",
        coach(observed),
        DesignLintPolicy(),
    )
    finding = next(item for item in review.findings if item.rule_id == "bus.i2c_unmapped_responder")
    assert finding.mode == "review"
    assert finding.disposition == "OPEN"

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
    assert blocked.status == "FAIL"
    assert (
        next(item for item in blocked.findings if item.rule_id == "bus.i2c_unmapped_responder").mode
        == "block"
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
    assert off.status == "PASS"
    assert (
        next(
            item for item in off.findings if item.rule_id == "bus.i2c_unmapped_responder"
        ).disposition
        == "RULE_OFF"
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
    assert ignored.status == "PASS"
    assert (
        next(item for item in ignored.findings if item.rule_id == finding.rule_id).disposition
        == "IGNORED"
    )


def test_unresolved_and_dynamic_addresses_are_visible_coverage_gaps() -> None:
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

    assert report.status == "REVIEW"
    assert report.i2c_address_coverage.status == "INCOMPLETE"
    statuses = {entry.reference: entry.status for entry in report.i2c_address_coverage.entries}
    assert statuses["U2"] == "INCOMPLETE"
    assert statuses["U3"] == "DYNAMIC"
    assert not any(item.rule_id == "bus.i2c_address_collision" for item in report.findings)
    assert any("dynamic" in issue for issue in report.issues)


def test_native_identity_pin_function_and_bus_mismatches_leave_coverage_incomplete() -> None:
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
        coverage = scan_i2c_address_map(spec, observed, _NETLIST_HASH)
        assert coverage.status == "INCOMPLETE"
        assert expected in " ".join(coverage.issues)
