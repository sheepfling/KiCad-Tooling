"""Keep synthetic I3C return native fixtures local and hash-pinned."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from kicad_tooling.ci_hosted_i3c_connector_return_cases import (
    I3C_CONNECTOR_RETURN_SOURCE_HASHES,
    i3c_connector_return_fixture_sources,
)

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.connector_lint,
    pytest.mark.interface_lint,
    pytest.mark.return_path_lint,
]

RULE_ID = "connector.i3c_pair_without_return_review"


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_native_source_registry_is_hash_pinned_and_local() -> None:
    fixture_root = Path(__file__).parent / "fixtures/design_lint/i3c-connector-return-native"
    sources = i3c_connector_return_fixture_sources()

    assert set(sources) == {"fault", "control"}
    assert all(path.resolve().is_relative_to(fixture_root.resolve()) for path in sources.values())
    assert {
        case: hashlib.sha256(path.read_bytes()).hexdigest() for case, path in sources.items()
    } == I3C_CONNECTOR_RETURN_SOURCE_HASHES
