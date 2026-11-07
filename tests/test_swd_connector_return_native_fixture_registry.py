"""Pin the SWD connector-return native fixtures to tooling-owned sources."""

from __future__ import annotations

from pathlib import Path

import pytest

from kicad_tooling.ci_hosted_swd_connector_return_cases import (
    SWD_CONNECTOR_RETURN_SOURCE_HASHES,
    swd_connector_return_fixture_sources,
)
from kicad_tooling.hwrepo.evidence import digest

RULE_ID = "connector.swd_pair_without_return_review"

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.connector_lint,
    pytest.mark.interface_lint,
    pytest.mark.return_path_lint,
]


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_native_source_registry_is_hash_pinned_and_local() -> None:
    sources = swd_connector_return_fixture_sources()
    repository = Path(__file__).resolve().parents[1]

    assert set(sources) == {"fault", "control"}
    assert all(path.is_file() for path in sources.values())
    assert all(path.resolve().is_relative_to(repository) for path in sources.values())
    assert {case: digest(path) for case, path in sources.items()} == (
        SWD_CONNECTOR_RETURN_SOURCE_HASHES
    )
