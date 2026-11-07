"""Keep synthetic RS-485 return fixture sources hash-pinned and tooling-local."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from kicad_tooling.ci_hosted_rs485_connector_return_cases import (
    RS485_CONNECTOR_RETURN_SOURCE_HASHES,
    rs485_connector_return_fixture_sources,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.connector_lint, pytest.mark.return_path_lint]

RULE_ID = "connector.rs485_pair_without_return_review"


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_native_source_registry_is_hash_pinned_and_tooling_local() -> None:
    fixture_root = Path(__file__).parent / "fixtures/design_lint"
    sources = rs485_connector_return_fixture_sources()

    assert set(sources) == {"fault", "control"}
    assert all(path.resolve().is_relative_to(fixture_root.resolve()) for path in sources.values())
    assert {path.parent for path in sources.values()} == {
        fixture_root / "rs485-connector-return-native"
    }
    assert {
        case: hashlib.sha256(path.read_bytes()).hexdigest() for case, path in sources.items()
    } == RS485_CONNECTOR_RETURN_SOURCE_HASHES
