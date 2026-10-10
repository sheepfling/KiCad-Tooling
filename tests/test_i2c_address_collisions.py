"""Focused source-bound I2C address collision regressions."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.i2c_addressing import scan_i2c_address_map
from kicad_tooling.hwrepo.models import DesignLintIgnore, DesignLintPolicy, DesignLintRuleOverride
from tests.design_lint_fixtures.i2c_addresses import (
    _NETLIST_HASH,
    address_map,
    address_netlist,
    coach,
    responder,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint]


def test_same_segment_static_address_collision_is_reported() -> None:
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

    assert coverage.status == "COMPLETE"
    assert coverage.netlist_sha256 == _NETLIST_HASH
    assert report.status == "REVIEW"
    collisions = [item for item in report.findings if item.rule_id == "bus.i2c_address_collision"]
    assert len(collisions) == 1
    assert collisions[0].subject == "MAIN: U1, U2 at 0x50"
    assert collisions[0].evidence["U1.address"] == ("expected 0x50; observed 0x50",)


def test_collision_order_is_stable_and_separate_segments_clear_it() -> None:
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
            "component_pin_numbers": dict(reversed(tuple(observed.component_pin_numbers.items()))),
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
        item for item in reordered_report.findings if item.rule_id == "bus.i2c_address_collision"
    )
    assert (reordered_finding.fingerprint, reordered_finding.evidence) == (
        original_finding.fingerprint,
        original_finding.evidence,
    )
    assert tuple(
        (entry.reference, entry.status, entry.observed_address)
        for entry in sorted(
            reordered_report.i2c_address_coverage.entries, key=lambda item: item.reference
        )
    ) == tuple(
        (entry.reference, entry.status, entry.observed_address)
        for entry in sorted(
            original_report.i2c_address_coverage.entries, key=lambda item: item.reference
        )
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
    assert "bus.i2c_address_collision" not in {item.rule_id for item in isolated_report.findings}


def test_not_fitted_responder_does_not_create_a_collision() -> None:
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

    assert report.i2c_address_coverage.status == "COMPLETE"
    statuses = {entry.reference: entry.status for entry in report.i2c_address_coverage.entries}
    assert statuses["U2"] == "NOT_FITTED"
    assert not report.findings
    assert report.status == "PASS"


def test_rule_can_block_or_accept_one_exact_collision() -> None:
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
    assert blocked.status == "FAIL"

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
    assert accepted.status == "PASS"
    assert accepted.findings[0].disposition == "IGNORED"
