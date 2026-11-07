"""Keep native JTAG connector return fixtures local and hash-pinned."""

from __future__ import annotations

from hashlib import sha256

import pytest

from kicad_tooling.ci_hosted_jtag_connector_return_cases import (
    JTAG_CONNECTOR_RETURN_SOURCE_HASHES,
    jtag_connector_return_fixture_sources,
)

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.connector_lint,
    pytest.mark.interface_lint,
    pytest.mark.return_path_lint,
]

RULE_ID = "connector.jtag_pair_without_return_review"


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_native_source_registry_is_hash_pinned_and_tooling_local() -> None:
    sources = jtag_connector_return_fixture_sources()
    assert set(sources) == {"fault", "control"}
    assert all(path.is_file() for path in sources.values())
    assert {case: sha256(path.read_bytes()).hexdigest() for case, path in sources.items()} == (
        JTAG_CONNECTOR_RETURN_SOURCE_HASHES
    )
    assert all(
        "jtag-connector-return-native" in str(path) or "jtag-generic-connector-native" in str(path)
        for path in sources.values()
    )
