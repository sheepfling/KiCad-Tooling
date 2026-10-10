"""Focused source-bound I2C address strap regressions."""

from __future__ import annotations

import hashlib

import pytest

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.models import DesignLintPolicy, NetlistContract
from tests.design_lint_fixtures.i2c_addresses import address_map, address_netlist, coach, responder

pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint]


def test_address_strap_mismatch_is_reported() -> None:
    device = responder("U1", address=0x50)
    spec = address_map(device)
    observed = address_netlist(spec, strap_values={"U1": 1})
    report = evaluate(
        "synthetic-i2c-addresses",
        coach(observed),
        DesignLintPolicy(i2c_address_map=spec),
    )

    assert report.i2c_address_coverage.status == "COMPLETE"
    assert report.status == "REVIEW"
    mismatch = next(item for item in report.findings if item.rule_id == "bus.i2c_address_mismatch")
    assert mismatch.subject == "U1 on MAIN: 0x51"
    assert mismatch.evidence["U1.bit0"] == ("U1.3 function A0; nets +3V3; resolved 1",)


def test_strap_mismatch_is_order_stable_and_corrected_strap_clears_it() -> None:
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
    assert original.netlist_sha256 == source_hash
    assert original.i2c_address_coverage.netlist_sha256 == source_hash
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
    reordered_hash, reordered = lint(reordered_source)
    assert source_hash != reordered_hash
    assert reordered.netlist_sha256 == reordered_hash
    assert reordered.i2c_address_coverage.netlist_sha256 == reordered_hash
    reordered_findings = {
        item.subject: (item.fingerprint, item.evidence)
        for item in reordered.findings
        if item.rule_id == rule_id
    }
    assert reordered_findings == original_findings

    repaired_hash, repaired = lint(address_netlist(specification, strap_values={"U1": 0}))
    assert source_hash != repaired_hash
    assert repaired.i2c_address_coverage.status == "COMPLETE"
    assert repaired.i2c_address_coverage.netlist_sha256 == repaired_hash
    assert repaired.i2c_address_coverage.entries[0].observed_address == 0x50
    assert rule_id not in {item.rule_id for item in repaired.findings}


def test_distinct_straps_and_same_addresses_on_isolated_segments_are_valid() -> None:
    distinct = address_map(responder("U1", address=0x50), responder("U2", address=0x51))
    distinct_observed = address_netlist(distinct, strap_values={"U1": 0, "U2": 1})
    distinct_report = evaluate(
        "synthetic-i2c-addresses",
        coach(distinct_observed),
        DesignLintPolicy(i2c_address_map=distinct),
    )
    assert distinct_report.i2c_address_coverage.status == "COMPLETE"
    assert distinct_report.status == "PASS"
    assert not distinct_report.findings

    isolated = address_map(
        responder("U3", address=0x50, strap=False, segment="MUX_A"),
        responder("U4", address=0x50, strap=False, segment="MUX_B"),
    )
    isolated_report = evaluate(
        "synthetic-i2c-addresses",
        coach(address_netlist(isolated)),
        DesignLintPolicy(i2c_address_map=isolated),
    )
    assert isolated_report.i2c_address_coverage.status == "COMPLETE"
    assert isolated_report.status == "PASS"
    assert not isolated_report.findings
