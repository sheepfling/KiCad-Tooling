"""Review partial I2C pin pairs without treating all-open pairs as used buses."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from typing import Literal

import pytest

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.design_lint_report_models import DesignLintReport
from kicad_tooling.hwrepo.models import (
    DesignLintIgnore,
    DesignLintPolicy,
    DesignLintRuleOverride,
    NetlistContract,
)
from tests.design_lint_fixtures import coach
from tests.design_lint_fixtures.i2c_unconnected_pins import i2c_unconnected_netlist

RULE_ID = "bus.i2c_unconnected_pin"

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.interface_lint,
    pytest.mark.design_lint_rule(rule_id=RULE_ID),
]


def _report(
    source: NetlistContract | None = None,
    mode: Literal["review", "block", "off"] | None = None,
    ignores: tuple[DesignLintIgnore, ...] = (),
) -> DesignLintReport:
    selected = i2c_unconnected_netlist() if source is None else source
    overrides = (
        ()
        if mode is None
        else (DesignLintRuleOverride(rule_id=RULE_ID, mode=mode, reason="test policy"),)
    )
    return evaluate(
        "synthetic-i2c-unconnected-pin",
        coach(selected),
        DesignLintPolicy(rules=overrides, ignores=ignores),
    )


def test_native_fault_fixture_source_is_pinned() -> None:
    fixture = (
        Path(__file__).parent / "fixtures/design_lint/i2c-unconnected-pin-native/fault.kicad_sch"
    )
    assert sha256(fixture.read_bytes()).hexdigest() == (
        "6e98c35fae5fd7484979811006c3d24a7bf100abf7ac59680a679b9b5d1ee133"
    )


def test_open_i2c_pin_emits_pair_and_net_evidence_when_enabled() -> None:
    report = _report(mode="review")
    finding = next(item for item in report.findings if item.rule_id == RULE_ID)

    assert finding.subject == "U1.1: SDA"
    assert finding.evidence == {
        "U1.1": (),
        "function": ("SDA",),
        "i2c_role": ("SDA",),
        "paired_pin": ("U1.2",),
        "paired_net": ("I2C_CLOCK",),
    }
    assert "function names do not establish bus intent or PCB routing" in finding.message


def test_rule_defaults_off_and_supports_review_block_off_and_exact_ignore() -> None:
    default = next(item for item in _report().findings if item.rule_id == RULE_ID)
    assert (default.mode, default.disposition) == ("off", "RULE_OFF")
    assert _report(mode="review").status == "REVIEW"
    assert _report(mode="block").status == "FAIL"
    assert _report(mode="off").status == _report().status
    ignored = _report(
        mode="review",
        ignores=(
            DesignLintIgnore(
                rule_id=RULE_ID,
                fingerprint=default.fingerprint,
                reason="Reviewed partial I2C endpoint",
            ),
        ),
    )
    assert [item.disposition for item in ignored.findings if item.rule_id == RULE_ID] == ["IGNORED"]


@pytest.mark.parametrize(
    ("functions", "open_pin", "role", "paired_pin"),
    (
        ({"U1.1": "SDA", "U1.2": "SCL"}, "U1.1", "SDA", "U1.2"),
        ({"U1.1": "I2C_SDA", "U1.2": "I2C_SCL"}, "U1.1", "SDA", "U1.2"),
        ({"U1.1": "I2C_SDA", "U1.2": "SCL"}, "U1.2", "SCL", "U1.1"),
    ),
)
def test_bounded_i2c_aliases_keep_pair_direction(
    functions: dict[str, str], open_pin: str, role: str, paired_pin: str
) -> None:
    source = i2c_unconnected_netlist(open_pins=(open_pin,), functions=functions)
    finding = next(
        item for item in _report(source, mode="review").findings if item.rule_id == RULE_ID
    )
    assert finding.subject == f"{open_pin}: {functions[open_pin]}"
    assert finding.evidence["i2c_role"] == (role,)
    assert finding.evidence["paired_pin"] == (paired_pin,)


@pytest.mark.parametrize(
    "source",
    (
        pytest.param(i2c_unconnected_netlist(open_pins=()), id="complete-pair"),
        pytest.param(i2c_unconnected_netlist(open_pins=("U1.1", "U1.2")), id="entire-pair-open"),
        pytest.param(i2c_unconnected_netlist(dnp_components=("U1",)), id="dnp-component"),
        pytest.param(
            i2c_unconnected_netlist(
                open_pins=("U1.1",),
                functions={"U1.1": "SDA", "U1.2": "SCL", "U1.3": "I2C_SCL"},
            ).model_copy(update={"component_pin_numbers": {"U1": ("1", "2", "3")}}),
            id="ambiguous-repeated-role",
        ),
        pytest.param(
            i2c_unconnected_netlist(functions={"U1.1": "DATA", "U1.2": "CLOCK"}),
            id="unsupported-aliases",
        ),
        pytest.param(
            i2c_unconnected_netlist(functions={"U1.1": "SDA0", "U1.2": "SCL0"}),
            id="unsupported-indexed-aliases",
        ),
        pytest.param(
            i2c_unconnected_netlist().model_copy(update={"component_pin_numbers": {}}),
            id="incomplete-pin-inventory",
        ),
    ),
)
def test_complete_unused_dnp_ambiguous_or_unsupported_shapes_are_quiet(
    source: NetlistContract,
) -> None:
    assert not any(item.rule_id == RULE_ID for item in _report(source, mode="review").findings)


def test_multi_net_pair_evidence_is_ambiguous_and_quiet() -> None:
    source = i2c_unconnected_netlist().model_copy(
        update={"nets": {"I2C_CLOCK": ("U1.2",), "OTHER": ("U1.2",)}}
    )
    assert not any(item.rule_id == RULE_ID for item in _report(source, mode="review").findings)


def test_ordering_is_stable_and_assigning_open_pin_clears_candidate() -> None:
    source = i2c_unconnected_netlist()
    reordered = source.model_copy(
        update={
            "nets": dict(reversed(tuple(source.nets.items()))),
            "pin_functions": dict(reversed(tuple(source.pin_functions.items()))),
            "components": dict(reversed(tuple(source.components.items()))),
        }
    )
    original = next(
        item for item in _report(source, mode="review").findings if item.rule_id == RULE_ID
    )
    repeated = next(
        item for item in _report(reordered, mode="review").findings if item.rule_id == RULE_ID
    )
    repaired = source.model_copy(update={"nets": {**source.nets, "I2C_DATA": ("U1.1",)}})

    assert (repeated.fingerprint, repeated.evidence) == (original.fingerprint, original.evidence)
    assert not any(item.rule_id == RULE_ID for item in _report(repaired, mode="review").findings)
