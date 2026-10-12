"""Synthetic electrical contract and simulator requirement builders."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from kicad_tooling.hwrepo.analysis_state_models import AnalysisNotApplicable
from kicad_tooling.hwrepo.contracts import write_model
from kicad_tooling.hwrepo.electrical import selected_config
from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.models import (
    ElectricalAnalysisContract,
    FrequencyAnalysis,
    GroundDomain,
    GroundingAnalysis,
    HighFrequencyAnalysis,
    PowerAnalysis,
    PowerLoad,
    PowerRail,
    SimulationMeasure,
    TransientAnalysis,
)
from kicad_tooling.validate import hashes

PROJECT = "controller"
ISLAND = "examples/projects/controller"
NA = AnalysisNotApplicable(mode="not_applicable", reason="Synthetic test scope")


def install_fixture(root: Path, version: str = "47") -> ElectricalAnalysisContract:
    """Author synthetic requirements only in a disposable copy of the training island."""
    from tests.support import template_root

    template = template_root()
    directory = root / ISLAND / "tests/electrical"
    directory.mkdir(parents=True)
    for name in ("startup.cir", "signal.cir"):
        shutil.copy2(template / "templates/electrical" / name, directory / name)
    config = selected_config(root, PROJECT)
    source = hashes(root, config.source_roots)

    def model(name: str) -> dict[str, str]:
        path = directory / name
        return {path.relative_to(root).as_posix(): digest(path)}

    startup_model = model("startup.cir")
    signal_model = model("signal.cir")
    startup = TransientAnalysis(
        id="startup",
        basis="Synthetic 5 V source ramp into 100 uF through 1 ohm",
        deck=next(iter(startup_model)),
        source_sha256=source,
        model_sha256=startup_model,
        step_s=1e-6,
        stop_s=0.005,
        measures=(
            SimulationMeasure(
                id="peak-current",
                expression="-i(vrail)",
                statistic="max",
                unit="A",
                start=0.0,
                stop=0.001,
                maximum=5.1,
            ),
        ),
    )
    steady = startup.model_copy(
        update={
            "id": "steady-state",
            "measures": (
                SimulationMeasure(
                    id="average-current",
                    expression="-i(vrail)",
                    statistic="avg",
                    unit="A",
                    start=0.004,
                    stop=0.005,
                    minimum=0.049,
                    maximum=0.051,
                ),
                SimulationMeasure(
                    id="average-power",
                    expression="-v(supply)*i(vrail)",
                    statistic="avg",
                    unit="W",
                    start=0.004,
                    stop=0.005,
                    minimum=0.24,
                    maximum=0.26,
                ),
                SimulationMeasure(
                    id="rail-minimum",
                    expression="v(out)",
                    statistic="min",
                    unit="V",
                    start=0.004,
                    stop=0.005,
                    minimum=4.9,
                ),
            ),
        }
    )
    sweep = FrequencyAnalysis(
        id="passband",
        basis="Synthetic 50 ohm/10 pF first-order low-pass",
        deck=next(iter(signal_model)),
        source_sha256=source,
        model_sha256=signal_model,
        start_hz=1000.0,
        stop_hz=1e9,
        measures=(
            SimulationMeasure(
                id="gain",
                expression="db(v(out)/v(in))",
                statistic="min",
                unit="dB",
                start=1000.0,
                stop=1e6,
                minimum=-0.1,
                maximum=0.0,
            ),
        ),
    )
    waveform = TransientAnalysis(
        id="edges",
        basis="Synthetic 1 MHz source with 1 ns rise and fall times",
        deck=sweep.deck,
        source_sha256=source,
        model_sha256=signal_model,
        step_s=1e-10,
        stop_s=3e-6,
        measures=(
            SimulationMeasure(
                id="overshoot",
                expression="v(out)",
                statistic="max",
                unit="V",
                start=0.0,
                stop=3e-6,
                minimum=0.99,
                maximum=1.01,
            ),
        ),
    )
    contract = ElectricalAnalysisContract(
        project_id=PROJECT,
        ngspice_version=version,
        grounding=GroundingAnalysis(
            basis="Synthetic reference net, not protective earth",
            domains=(GroundDomain(net="PILOT_B", pins=("R1.2", "R2.2")),),
        ),
        pcb_return_paths=NA,
        power=PowerAnalysis(
            rails=(
                PowerRail(
                    id="supply",
                    basis="Synthetic derated supply and path limits",
                    voltage_v=5.0,
                    continuous_limit_a=0.1,
                    peak_limit_a=6.0,
                    peak_duration_limit_s=0.002,
                    loads=(
                        PowerLoad(
                            id="load",
                            basis="Synthetic worst case",
                            steady_a=0.05,
                            startup_a=5.0,
                            startup_s=0.001,
                        ),
                    ),
                ),
            ),
            startup=(startup,),
            steady_state=(steady,),
        ),
        high_frequency=HighFrequencyAnalysis(
            basis="Synthetic model only",
            frequency_hz=1e6,
            rise_time_s=1e-9,
            sweeps=(sweep,),
            waveforms=(waveform,),
        ),
        test_access=NA,
    )
    path = root / ISLAND / "tests/electrical.json"
    write_model(path, contract)
    test_path = root / ISLAND / "tests/contract.json"
    raw = json.loads(test_path.read_text())
    raw["electrical"] = "tests/electrical.json"
    test_path.write_text(json.dumps(raw))
    return contract
