"""Keep native I3C connector fixtures local and digest-pinned."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from tests.i3c_generic_connector_fixture_support import (
    I3C_GENERIC_CONNECTOR_SOURCE_HASHES,
    i3c_generic_connector_fixture_sources,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint]


@pytest.mark.design_lint_rule(rule_id="bus.i3c_generic_connector_pair_review")
def test_native_source_registry_is_hash_pinned_and_local() -> None:
    fixture_root = Path(__file__).parent / "fixtures/design_lint/i3c-generic-connector-native"
    sources = i3c_generic_connector_fixture_sources()

    assert set(sources) == {"fault", "control"}
    assert all(path.resolve().is_relative_to(fixture_root.resolve()) for path in sources.values())
    assert {
        f"{case}.kicad_sch": hashlib.sha256(path.read_bytes()).hexdigest()
        for case, path in sources.items()
    } == I3C_GENERIC_CONNECTOR_SOURCE_HASHES
