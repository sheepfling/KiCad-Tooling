"""Focused tests for the shared operation-to-runner selection boundary."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.contract_coach import (
    AutoNetlistRunner,
    ContainerNetlistRunner,
    LocalNetlistRunner,
)
from kicad_tooling.hwrepo.netlist_runner_selection import select_netlist_runner

pytestmark = pytest.mark.architecture


@pytest.mark.parametrize(
    ("runner_mode", "expected_type"),
    (
        ("auto", AutoNetlistRunner),
        ("local", LocalNetlistRunner),
        ("container", ContainerNetlistRunner),
    ),
)
def test_runner_selection_returns_the_requested_runner(runner_mode, expected_type) -> None:
    assert isinstance(select_netlist_runner(runner_mode, "custom-kicad-cli"), expected_type)
