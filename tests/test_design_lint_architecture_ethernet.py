"""Keep Ethernet protocol predicates in focused theme-owned modules."""

from __future__ import annotations

import pytest

from tests.lint_architecture_support import HWREPO, IMPLEMENTATION_MAX_LINES, line_count

pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint, pytest.mark.architecture]


def test_ethernet_data_label_rule_uses_a_focused_predicate_owner() -> None:
    from kicad_tooling.hwrepo.design_lint import rule_catalog

    rule = next(
        item for item in rule_catalog().rules if item.rule_id == "bus.ethernet_data_label_mismatch"
    )
    assert rule.theme == "interfaces"
    assert rule.implementation_owner == (
        "kicad_tooling/hwrepo/bus_ethernet_pair_labels.py#ethernet_data_label_mismatch_candidates"
    )
    assert rule.implementation_owner in rule.implementation_refs
    assert (
        "kicad_tooling/hwrepo/bus_signal_pairs.py#ethernet_data_pair_function_role"
        in rule.implementation_refs
    )


def test_ethernet_management_label_rule_uses_a_focused_predicate_owner() -> None:
    from kicad_tooling.hwrepo.design_lint import rule_catalog

    rule = next(
        item
        for item in rule_catalog().rules
        if item.rule_id == "bus.ethernet_management_label_mismatch"
    )
    assert rule.theme == "interfaces"
    assert rule.implementation_owner == (
        "kicad_tooling/hwrepo/bus_ethernet_pair_labels.py#"
        "ethernet_management_label_mismatch_candidates"
    )
    assert rule.implementation_owner in rule.implementation_refs


def test_ethernet_management_unconnected_rule_has_a_bounded_theme_owner() -> None:
    from kicad_tooling.hwrepo.design_lint import rule_catalog

    rule = next(
        item
        for item in rule_catalog().rules
        if item.rule_id == "bus.ethernet_management_unconnected_pin"
    )
    assert rule.theme == "interfaces"
    assert rule.implementation_owner == (
        "kicad_tooling/hwrepo/bus_ethernet_unconnected_management.py#"
        "ethernet_management_unconnected_pin_candidates"
    )
    assert rule.implementation_owner in rule.implementation_refs
    assert (
        "kicad_tooling/hwrepo/bus_signal_pairs.py#ethernet_management_function_role"
        in rule.implementation_refs
    )
    assert (
        "kicad_tooling/hwrepo/casefold_mapping_lookup.py#lookup_unique_casefold"
        in rule.implementation_refs
    )
    assert line_count(HWREPO / "bus_ethernet_unconnected_management.py") < IMPLEMENTATION_MAX_LINES
