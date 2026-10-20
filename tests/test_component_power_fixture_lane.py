"""Portable fault and control checks for disconnected component power pins."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from tests.hosted_ci_component_power_support import assert_unconnected_component_power_input_cases

pytestmark = [pytest.mark.design_lint, pytest.mark.component_lint, pytest.mark.power_lint]


def test_unconnected_component_power_input_requires_a_board_connection(
    connector_return_fixture_results: SimpleNamespace,
) -> None:
    assert_unconnected_component_power_input_cases(
        connector_return_fixture_results.results,
        connector_return_fixture_results.version,
    )
