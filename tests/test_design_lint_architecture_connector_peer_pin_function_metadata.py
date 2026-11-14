"""Architecture boundaries for generic peer function metadata review."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.connector_footprint_peer_pin_function_metadata import (
    connector_footprint_peer_pin_function_metadata_gaps,
)
from kicad_tooling.hwrepo.design_lint import rule_catalog
from tests.lint_architecture_support import HWREPO, IMPLEMENTATION_MAX_LINES, line_count

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.connector_lint,
    pytest.mark.interface_lint,
    pytest.mark.architecture,
]


def test_connector_peer_function_metadata_rule_has_a_focused_owner() -> None:
    modules = (
        "connector_footprint_peer_pin_function_metadata.py",
        "connector_footprint_peer_pin_function_support.py",
        "connector_footprint_peer_pin_function_consistency.py",
    )
    module_sizes = {name: line_count(HWREPO / name) for name in modules}
    oversized = {
        name: lines for name, lines in module_sizes.items() if lines >= IMPLEMENTATION_MAX_LINES
    }
    owner = (
        "kicad_tooling/hwrepo/connector_footprint_peer_pin_function_metadata.py#"
        "connector_footprint_peer_pin_function_metadata_gaps"
    )
    rule = next(
        item
        for item in rule_catalog().rules
        if item.rule_id == "connector.footprint_peer_pin_function_metadata_incomplete"
    )

    assert not oversized, f"Connector peer-function modules reached the review limit: {oversized}"
    assert rule.theme == "connectors"
    assert rule.implementation_owner == owner
    assert owner in rule.implementation_refs
    assert connector_footprint_peer_pin_function_metadata_gaps.__module__.endswith(
        "connector_footprint_peer_pin_function_metadata"
    )
