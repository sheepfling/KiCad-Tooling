"""Guard the canonical owner for USB case-folded netlist lookup indexes."""

from __future__ import annotations

import ast

import pytest

from tests.lint_architecture_support import HWREPO, IMPLEMENTATION_MAX_LINES, line_count

pytestmark = [
    pytest.mark.architecture,
    pytest.mark.design_lint,
    pytest.mark.interface_lint,
]

_CONSUMERS = (
    "usb_peer_endpoint_analysis.py",
    "usb_peer_data_crossing.py",
    "usb_peer_path_analysis.py",
    "usb_peer_reference_evidence.py",
)


def test_usb_peer_casefold_indexes_use_the_canonical_owner() -> None:
    owner = HWREPO / "casefold_mapping_lookup.py"
    tree = ast.parse(owner.read_text(encoding="utf-8"), filename=owner.name)
    assert line_count(owner) < IMPLEMENTATION_MAX_LINES
    assert any(
        isinstance(node, ast.FunctionDef) and node.name == "casefolded_unique_index"
        for node in tree.body
    )

    for name in _CONSUMERS:
        path = HWREPO / name
        consumer = ast.parse(path.read_text(encoding="utf-8"), filename=path.name)
        assert line_count(path) < IMPLEMENTATION_MAX_LINES
        assert any(
            isinstance(node, ast.ImportFrom)
            and node.level == 1
            and node.module == "casefold_mapping_lookup"
            and any(alias.name == "casefolded_unique_index" for alias in node.names)
            for node in consumer.body
        )
        assert any(
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "casefolded_unique_index"
            for node in ast.walk(consumer)
        )
        assert not any(
            isinstance(node, ast.FunctionDef) and node.name == "casefold_mapping"
            for node in consumer.body
        )
