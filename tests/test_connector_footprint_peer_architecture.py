"""Keep footprint-alias grouping and metadata checks in focused modules."""

from __future__ import annotations

import ast

import pytest

from tests.lint_architecture_support import HWREPO, IMPLEMENTATION_MAX_LINES, line_count

pytestmark = [pytest.mark.design_lint, pytest.mark.connector_lint, pytest.mark.architecture]

PEER_MODULES = (
    "connector_footprint_peer_groups.py",
    "connector_footprint_peer_pins.py",
    "connector_footprint_peer_metadata.py",
    "connector_footprint_peer_missing_metadata.py",
    "connector_footprint_peer_missing_metadata_open.py",
)


def test_connector_footprint_peer_modules_stay_below_review_limit() -> None:
    sizes = {name: line_count(HWREPO / name) for name in PEER_MODULES}
    oversized = {name: size for name, size in sizes.items() if size >= IMPLEMENTATION_MAX_LINES}

    assert not oversized, f"Split connector footprint peer modules: {oversized}"


def test_connector_alias_scans_share_candidate_and_inventory_owners() -> None:
    expected_helpers = {
        "connector_footprint_peer_candidate_groups",
        "complete_connector_footprint_peer_pin_inventory",
    }
    for filename in PEER_MODULES[1:]:
        source = HWREPO / filename
        tree = ast.parse(source.read_text(encoding="utf-8"), filename=filename)
        imports = {
            alias.name
            for node in tree.body
            if isinstance(node, ast.ImportFrom) and node.module == "connector_footprint_peer_groups"
            for alias in node.names
        }
        assert expected_helpers <= imports, (
            f"{filename} duplicated alias grouping or inventory logic"
        )
