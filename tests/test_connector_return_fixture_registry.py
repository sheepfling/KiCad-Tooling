"""Keep the hosted connector native-source and typed-netlist registries aligned."""

from __future__ import annotations

from pathlib import Path

import pytest

from kicad_tooling.ci_hosted_connector_return_fixture_sources import (
    connector_return_fixture_sources,
)
from tests.connector_return_fixture_support import connector_return_fixture_contracts

pytestmark = [pytest.mark.design_lint, pytest.mark.connector_lint]


def test_every_hosted_connector_source_has_one_typed_contract() -> None:
    """Require all synthetic native exports to have a typed counterpart."""
    source_cases = connector_return_fixture_sources(Path("synthetic-fixtures"))
    typed_cases = connector_return_fixture_contracts()

    assert set(source_cases) == set(typed_cases)
