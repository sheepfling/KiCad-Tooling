"""Bounded capacitance spellings shared by electrical lint rules."""

from __future__ import annotations

from decimal import Decimal

import pytest

from kicad_tooling.hwrepo.capacitance_values import parse_capacitance_pf

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.component_lint,
    pytest.mark.interface_lint,
    pytest.mark.power_lint,
]


@pytest.mark.parametrize(
    ("value", "expected_pf"),
    (
        ("18 pF", 18),
        ("0.018 nF", 18),
        ("0.000018 uF", 18),
        ("18p", 18),
        ("1 mF", 1_000_000_000),
        ("1F", 1_000_000_000_000),
        ("0.25 F", 250_000_000_000),
    ),
)
def test_parser_accepts_explicit_units(value: str, expected_pf: int) -> None:
    assert parse_capacitance_pf(value) == expected_pf


@pytest.mark.design_lint_rule(rule_id="bus.i2c_pullup_input_limit_coverage")
@pytest.mark.parametrize(
    ("value", "expected_pf"),
    (
        ("0,1uF", Decimal(100000)),
        ("1fF", Decimal("0.001")),
        ("0,1uF, 50V", Decimal(100000)),
        ("78 182pF", Decimal(78182)),
        (",5uF", Decimal(500000)),
        ("1 234,567pF", Decimal("1234.567")),
    ),
)
def test_parser_accepts_unambiguous_kicad_value_fields(value: str, expected_pf: Decimal) -> None:
    assert parse_capacitance_pf(value) == expected_pf


@pytest.mark.design_lint_rule(rule_id="bus.i2c_pullup_input_limit_coverage")
@pytest.mark.parametrize(
    "value",
    (
        "18",
        "Cload",
        "0nF",
        "-1uF",
        "1,000uF",
        "1, 000pF",
        "78 18pF",
        f"{'9' * 129}pF",
    ),
)
def test_parser_rejects_ambiguous_nonpositive_or_unbounded_values(value: str) -> None:
    assert parse_capacitance_pf(value) is None
