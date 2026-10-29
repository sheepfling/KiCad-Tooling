"""Mapped rule coverage cannot imply coverage outside an authored layer scope."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.pcb_drc_rule_coverage import compare_native_rules
from tests.design_lint_fixtures.pcb_signal_path import compare, native_rules
from tests.test_pcb_drc_coverage import pair_map, rules_text

pytestmark = [pytest.mark.design_lint, pytest.mark.pcb_lint]


@pytest.mark.parametrize("layer_clause", ("(layer F.Cu)", "(layer F.Cu) (layer B.Cu)", "(layer)"))
@pytest.mark.parametrize(
    ("rule_name", "constraint"),
    (
        ("synthetic-dp-width", "track_width"),
        ("synthetic-dp-gap", "diff_pair_gap"),
        ("synthetic-dp-skew", "skew"),
        ("synthetic-dp-uncoupled", "diff_pair_uncoupled"),
        ("synthetic-dp-edge-clearance", "edge_clearance"),
    ),
)
def test_pair_rule_layer_scope_is_incomplete(
    rule_name: str, constraint: str, layer_clause: str
) -> None:
    source = rules_text()
    marker = f'(rule "{rule_name}"'
    scoped = source.replace(marker, f"{marker}\n  {layer_clause}")
    (control,) = compare_native_rules(pair_map(), source, frozenset())
    (fault,) = compare_native_rules(pair_map(), scoped, frozenset())
    assert control.status == "COMPLETE"
    assert fault.status == "INCOMPLETE"
    result = next(item for item in fault.constraints if item.constraint == constraint)
    assert result.status == "UNSUPPORTED"
    assert "layer" in (result.issue or "").lower()


@pytest.mark.parametrize("layer_clause", ("(layer F.Cu)", "(layer F.Cu) (layer B.Cu)", "(layer)"))
@pytest.mark.parametrize(
    ("rule_name", "entry_id", "constraint"),
    (
        ("synthetic-clock-length", "clock", "length"),
        ("synthetic-clock-edge-clearance", "clock", "edge_clearance"),
        ("synthetic-serial-skew", "serial-bundle", "skew"),
    ),
)
def test_signal_rule_layer_scope_is_incomplete(
    rule_name: str, entry_id: str, constraint: str, layer_clause: str
) -> None:
    source = native_rules()
    marker = f'(rule "{rule_name}"'
    scoped = source.replace(marker, f"{marker}\n  {layer_clause}")
    control = next(item for item in compare(rules=source) if item.id == entry_id)
    fault = next(item for item in compare(rules=scoped) if item.id == entry_id)
    assert control.status == "COMPLETE"
    assert fault.status == "INCOMPLETE"
    result = next(item for item in fault.constraints if item.constraint == constraint)
    assert result.status == "UNSUPPORTED"
    assert "layer" in (result.issue or "").lower()
