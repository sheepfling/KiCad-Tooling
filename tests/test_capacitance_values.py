"""Bounded capacitance spellings shared by electrical lint rules."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.capacitance_values import parse_capacitance_pf

pytestmark = [pytest.mark.design_lint, pytest.mark.component_lint, pytest.mark.power_lint]


@pytest.mark.parametrize(
    ("value", "expected_pf"),
    (("18 pF", 18), ("0.018 nF", 18), ("0.000018 uF", 18), ("18p", 18)),
)
def test_parser_accepts_explicit_units(value: str, expected_pf: int) -> None:
    assert parse_capacitance_pf(value) == expected_pf


@pytest.mark.parametrize("value", ("18", "Cload", "0nF", "-1uF", f"{'9' * 129}pF"))
def test_parser_rejects_ambiguous_nonpositive_or_unbounded_values(value: str) -> None:
    assert parse_capacitance_pf(value) is None
