"""Keep the hosted connector native-source and typed-netlist registries aligned."""

from __future__ import annotations

from pathlib import Path

import pytest

from kicad_tooling.ci_hosted_connector_return_fixture_sources import (
    CONNECTOR_RETURN_FIXTURE_SOURCE_HASHES,
    connector_return_fixture_sources,
)
from kicad_tooling.hwrepo.evidence import digest
from tests.connector_return_fixture_support import connector_return_fixture_contracts

pytestmark = [pytest.mark.design_lint, pytest.mark.connector_lint]


def test_every_hosted_connector_source_has_one_typed_contract() -> None:
    """Require all synthetic native exports to have a typed counterpart."""
    fixture_root = Path(__file__).parent / "fixtures/design_lint"
    source_cases = connector_return_fixture_sources(fixture_root)
    typed_cases = connector_return_fixture_contracts()

    assert set(source_cases) == set(typed_cases)
    assert set(source_cases) == set(CONNECTOR_RETURN_FIXTURE_SOURCE_HASHES)
    assert {case: digest(source) for case, source in source_cases.items()} == dict(
        CONNECTOR_RETURN_FIXTURE_SOURCE_HASHES
    )
