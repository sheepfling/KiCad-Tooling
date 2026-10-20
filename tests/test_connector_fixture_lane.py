"""Portable connector heuristic fault and control checks through the hosted lane."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from tests.hosted_ci_connector_peer_support import assert_connector_peer_pin_cases
from tests.hosted_ci_connector_power_support import assert_connector_power_and_role_cases
from tests.hosted_ci_connector_return_support import (
    assert_base_connector_return_cases,
    assert_positive_rail_return_cases,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.connector_lint]


def test_connector_fixture_faults_and_controls_are_classified(
    connector_return_fixture_results: SimpleNamespace,
) -> None:
    results = connector_return_fixture_results.results
    version = connector_return_fixture_results.version

    assert_base_connector_return_cases(results, version)
    assert_positive_rail_return_cases(results, version)
    assert_connector_peer_pin_cases(
        results,
        version,
        all_open_pin_functions="J1.1=Pin_1;J1.2=Pin_2;J2.1=Pin_1;J2.2=Pin_2",
    )
    assert_connector_power_and_role_cases(results, version)
