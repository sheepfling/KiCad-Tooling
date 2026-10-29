"""Keep the I2C pull-up theme behind one explicit, required input record."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from kicad_tooling.hwrepo.design_lint_i2c_candidates import i2c_pullup_candidates
from kicad_tooling.hwrepo.design_lint_i2c_pullup_candidates import (
    i2c_pullup_theme_candidates,
)
from kicad_tooling.hwrepo.i2c_pullup_inputs import I2cPullupSnifferInput
from kicad_tooling.hwrepo.i2c_pullup_models import I2cPullupHeuristicCoverage
from tests.design_lint_fixtures import i2c_netlist

pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint]


@pytest.mark.parametrize(
    "coverage",
    (
        None,
        I2cPullupHeuristicCoverage(status="NOT_CONFIGURED"),
        I2cPullupHeuristicCoverage(status="PENDING"),
        I2cPullupHeuristicCoverage(status="NOT_APPLICABLE"),
        I2cPullupHeuristicCoverage(status="BLOCKED", issue="stale native netlist hash"),
    ),
)
def test_typed_theme_path_preserves_legacy_candidate_records(
    coverage: I2cPullupHeuristicCoverage | None,
) -> None:
    observed = i2c_netlist()
    typed = I2cPullupSnifferInput.from_legacy_arguments(observed, coverage)

    assert i2c_pullup_theme_candidates(typed) == i2c_pullup_candidates(observed, coverage)


def test_legacy_missing_coverage_becomes_explicit_not_configured_state() -> None:
    inputs = I2cPullupSnifferInput.from_legacy_arguments(i2c_netlist(), None)

    assert inputs.coverage.status == "NOT_CONFIGURED"
    assert inputs.coverage.entries == ()


def test_theme_input_record_is_immutable() -> None:
    inputs = I2cPullupSnifferInput.from_legacy_arguments(i2c_netlist(), None)

    with pytest.raises(FrozenInstanceError):
        inputs.coverage = I2cPullupHeuristicCoverage(status="PENDING")  # type: ignore[misc]
