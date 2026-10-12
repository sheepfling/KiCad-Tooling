"""Power source/load connectivity contract regressions."""

from __future__ import annotations

import json
from typing import Literal

import pytest

from kicad_tooling.hwrepo.models import (
    AnalysisNotApplicable,
    ElectricalAnalysisContract,
    ElectricalCheck,
    PowerAnalysis,
    PowerConnectivityAnalysis,
    PowerConnectivityRailRequirement,
    PowerLoad,
    PowerLoadConnectivityRequirement,
    PowerRail,
    SimulationMeasure,
    TransientAnalysis,
)
from kicad_tooling.hwrepo.power_connectivity import power_connectivity_checks
from tests.electrical_power_connectivity_support import (
    power_connectivity_netlist,
    power_connectivity_requirement,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.power_lint]

PowerConnectivityFault = Literal[
    "source-wrong-net",
    "load-wrong-net",
    "source-dnp",
    "all-sources-dnp",
    "source-identity-wrong",
]


def _checks(
    requirement: PowerConnectivityAnalysis,
    fault: PowerConnectivityFault | None = None,
) -> dict[str, ElectricalCheck]:
    return {
        item.id: item
        for item in power_connectivity_checks(
            requirement,
            power_connectivity_netlist(fault=fault),
        )
    }


def _contract_with_power_map(
    power_connectivity: PowerConnectivityAnalysis,
) -> ElectricalAnalysisContract:
    """Build a minimal in-memory budget for the map-identity contract test."""
    digest = "0" * 64

    def transient_case(case_id: str, measures: tuple[SimulationMeasure, ...]) -> TransientAnalysis:
        return TransientAnalysis(
            id=case_id,
            basis="Synthetic model-bound power case",
            deck="synthetic/power.cir",
            model_sha256={"synthetic/power.cir": digest},
            source_sha256={"synthetic/design.kicad_sch": digest},
            step_s=0.001,
            stop_s=0.01,
            measures=measures,
        )

    return ElectricalAnalysisContract(
        project_id="synthetic-power-map",
        ngspice_version="47",
        grounding=AnalysisNotApplicable(mode="not_applicable", reason="Synthetic contract scope"),
        power=PowerAnalysis(
            rails=(
                PowerRail(
                    id="supply",
                    basis="Synthetic budget rail",
                    voltage_v=5.0,
                    continuous_limit_a=1.0,
                    peak_limit_a=1.5,
                    peak_duration_limit_s=0.1,
                    loads=(
                        PowerLoad(
                            id="load",
                            basis="Synthetic budget load",
                            steady_a=0.1,
                            startup_a=0.2,
                            startup_s=0.001,
                        ),
                    ),
                ),
            ),
            startup=(
                transient_case(
                    "startup",
                    (
                        SimulationMeasure(
                            id="peak-current",
                            expression="i(vrail)",
                            statistic="max",
                            unit="A",
                            start=0.0,
                            stop=0.01,
                            maximum=1.5,
                        ),
                    ),
                ),
            ),
            steady_state=(
                transient_case(
                    "steady-state",
                    (
                        SimulationMeasure(
                            id="average-current",
                            expression="i(vrail)",
                            statistic="avg",
                            unit="A",
                            start=0.001,
                            stop=0.01,
                            maximum=1.0,
                        ),
                        SimulationMeasure(
                            id="average-power",
                            expression="v(supply)*i(vrail)",
                            statistic="avg",
                            unit="W",
                            start=0.001,
                            stop=0.01,
                            maximum=5.0,
                        ),
                    ),
                ),
            ),
        ),
        power_connectivity=power_connectivity,
        high_frequency=AnalysisNotApplicable(
            mode="not_applicable", reason="Synthetic contract scope"
        ),
    )


def test_authored_power_sources_and_loads_match_the_synthetic_netlist() -> None:
    checks = _checks(power_connectivity_requirement())

    assert all(item.status == "PASS" for item in checks.values())
    assert checks["power-connectivity/supply/source/approved-inputs"].status == "PASS"
    assert checks["power-connectivity/supply/load/load"].status == "PASS"


@pytest.mark.parametrize(
    ("fault", "check_id"),
    (
        ("source-wrong-net", "power-connectivity/supply/source/approved-inputs"),
        ("load-wrong-net", "power-connectivity/supply/load/load"),
        ("source-dnp", "power-connectivity/supply/source/approved-inputs"),
        ("source-identity-wrong", "power-connectivity/supply/source/approved-inputs"),
    ),
)
def test_power_connectivity_faults_fail_the_mapped_check(
    fault: PowerConnectivityFault, check_id: str
) -> None:
    checks = _checks(power_connectivity_requirement(), fault)

    assert checks[check_id].status == "FAIL"


def test_any_approved_source_allows_one_populated_alternative() -> None:
    requirement = power_connectivity_requirement(source_selection="any")

    one_available = _checks(requirement, "source-dnp")
    none_available = _checks(requirement, "all-sources-dnp")

    check_id = "power-connectivity/supply/source/approved-inputs"
    assert one_available[check_id].status == "PASS"
    assert none_available[check_id].status == "FAIL"


def test_power_connectivity_map_matches_budget_rail_and_load_ids() -> None:
    source_rail = power_connectivity_requirement().rails[0]
    mapped = PowerConnectivityAnalysis(
        basis="Synthetic connectivity map matched to its budget",
        rails=(
            PowerConnectivityRailRequirement(
                id="supply",
                basis="Existing budget rail with exact schematic membership",
                net="VIN_IN",
                source_groups=source_rail.source_groups,
                loads=(
                    PowerLoadConnectivityRequirement(
                        id="load",
                        basis="Existing budget load covers both selected components",
                        endpoints=tuple(
                            endpoint for load in source_rail.loads for endpoint in load.endpoints
                        ),
                    ),
                ),
            ),
        ),
    )
    contract = _contract_with_power_map(mapped)
    validated = ElectricalAnalysisContract.model_validate_json(contract.model_dump_json())
    assert validated.power_connectivity is not None

    raw = json.loads(contract.model_dump_json())
    raw["power_connectivity"]["rails"][0]["loads"][0]["id"] = "unbudgeted-load"
    with pytest.raises(ValueError, match="load IDs must match"):
        ElectricalAnalysisContract.model_validate_json(json.dumps(raw))
