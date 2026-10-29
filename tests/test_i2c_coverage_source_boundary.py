"""I2C coverage resolving a prompt must identify its authored contract."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.i2c_pullup_heuristics import i2c_pullup_heuristic_coverage
from kicad_tooling.hwrepo.i2c_pullup_models import I2cPullupHeuristicCoverage
from kicad_tooling.hwrepo.models import DesignLintPolicy
from tests.design_lint_fixtures import coach
from tests.design_lint_fixtures.i2c_arrays import array_netlist, array_requirement
from tests.electrical_i2c_support import i2c_pullup_voltage_requirement, i2c_series_pullup_netlist

pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint]


def test_covered_pullup_without_contract_identity_blocks_evaluation() -> None:
    observed = array_netlist()
    coverage = i2c_pullup_heuristic_coverage(
        observed,
        netlist_sha256="a" * 64,
        source_path=None,
        source_sha256=None,
        state="required",
        spec=array_requirement(),
    )
    assert coverage.entries[0].status == "COVERED"
    report = evaluate(
        "i2c-evidence",
        coach(observed),
        DesignLintPolicy(),
        i2c_pullup_heuristic_coverage=coverage,
    )
    assert report.status == "BLOCKED"
    assert "identified electrical contract" in report.issues[0]


def test_covered_voltage_without_contract_identity_blocks_evaluation() -> None:
    observed = i2c_series_pullup_netlist()
    coverage = i2c_pullup_heuristic_coverage(
        observed,
        netlist_sha256="a" * 64,
        source_path=None,
        source_sha256=None,
        state="required",
        spec=i2c_pullup_voltage_requirement(),
    )
    assert any(entry.status == "COVERED" for entry in coverage.voltage_entries)
    assert not coverage.entries
    report = evaluate(
        "i2c-evidence",
        coach(observed),
        DesignLintPolicy(),
        i2c_pullup_heuristic_coverage=coverage,
    )
    assert report.status == "BLOCKED"
    assert "identified electrical contract" in report.issues[0]


@pytest.mark.parametrize("state", ("NOT_CONFIGURED", "PENDING", "NOT_APPLICABLE"))
@pytest.mark.parametrize("voltage", (False, True), ids=("pullup", "voltage"))
def test_unresolved_state_cannot_contain_covered_evidence(state: str, voltage: bool) -> None:
    observed = i2c_series_pullup_netlist() if voltage else array_netlist()
    spec = i2c_pullup_voltage_requirement() if voltage else array_requirement()
    coverage = i2c_pullup_heuristic_coverage(
        observed,
        netlist_sha256="a" * 64,
        source_path="projects/synthetic/electrical.json",
        source_sha256="b" * 64,
        state="required",
        spec=spec,
    )
    assert any(item.status == "COVERED" for item in (*coverage.entries, *coverage.voltage_entries))
    contradictory = I2cPullupHeuristicCoverage.model_validate(
        {**coverage.model_dump(), "status": state}
    )
    report = evaluate(
        "i2c-evidence",
        coach(observed),
        DesignLintPolicy(),
        i2c_pullup_heuristic_coverage=contradictory,
    )
    assert report.status == "BLOCKED"
    assert "requires complete or open coverage" in report.issues[0]
