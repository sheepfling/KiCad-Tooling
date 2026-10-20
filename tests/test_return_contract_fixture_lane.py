"""Portable common-versus-isolated grounding contract regressions."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from tests.hosted_ci_connector_return_support import assert_grounding_contract_cases

pytestmark = [pytest.mark.design_lint, pytest.mark.connector_lint, pytest.mark.return_path_lint]


def test_grounding_and_pin_connectivity_contracts_preserve_declared_domains(
    connector_return_fixture_results: SimpleNamespace,
) -> None:
    results = connector_return_fixture_results.results
    version = connector_return_fixture_results.version

    assert_grounding_contract_cases(results, version)
