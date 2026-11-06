"""Keep native CAN connector fixtures local and hash-pinned."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from kicad_tooling.ci_hosted_can_generic_connector_cases import (
    CAN_GENERIC_CONNECTOR_SOURCE_HASHES,
    can_generic_connector_fixture_sources,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint]


@pytest.mark.design_lint_rule(rule_id="bus.can_generic_connector_pair_review")
def test_native_source_registry_is_hash_pinned_and_local() -> None:
    fixture_root = Path(__file__).parent / "fixtures/design_lint/can-generic-connector-native"
    sources = can_generic_connector_fixture_sources()

    assert set(sources) == {"fault", "control"}
    assert all(path.resolve().is_relative_to(fixture_root.resolve()) for path in sources.values())
    assert {
        case: hashlib.sha256(path.read_bytes()).hexdigest() for case, path in sources.items()
    } == CAN_GENERIC_CONNECTOR_SOURCE_HASHES
