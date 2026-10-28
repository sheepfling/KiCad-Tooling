"""Typed project contract for electrical-analysis checks."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, model_validator

from kicad_tooling.hwrepo.analysis_state_models import AnalysisNotApplicable, AnalysisPending
from kicad_tooling.hwrepo.electrical_simulation_models import (
    HighFrequencyAnalysis,
    PowerAnalysis,
    SimulationModel,
)
from kicad_tooling.hwrepo.power_connectivity_models import PowerConnectivityAnalysis

from .can_termination_models import CanTerminationAnalysis
from .component_rating_models import (
    ComponentPowerRatingAnalysis,
    ComponentVoltageRatingAnalysis,
)
from .connector_contact_rating_models import ConnectorContactRatingAnalysis
from .control_input_models import ControlInputsAnalysis
from .digital_peer_voltage_models import DigitalPeerVoltageAnalysis
from .grounding_models import GroundingAnalysis
from .i2c_pullup_models import I2cPullupAnalysis
from .model_primitives import Digest, Identifier, NonEmptyText, StrictModel
from .mosfet_stress_models import MosfetStressAnalysis
from .pcb_return_path_models import PcbReturnPathsAnalysis
from .pcb_test_access_models import TestAccessAnalysis
from .pin_connectivity_models import PinConnectivityAnalysis
from .rs485_models import Rs485Analysis
from .serial_peer_models import SerialPeerAnalysis
from .spi_models import SpiAnalysis
from .usb_c_models import UsbCAnalysis


class ElectricalAnalysisContract(StrictModel):
    schema_version: Literal["1"] = "1"
    project_id: Identifier
    ngspice_version: NonEmptyText
    ngspice_source_sha256: Digest | None = None
    grounding: Annotated[
        GroundingAnalysis | AnalysisNotApplicable | AnalysisPending, Field(discriminator="mode")
    ]
    pcb_return_paths: Annotated[
        PcbReturnPathsAnalysis | AnalysisNotApplicable | AnalysisPending,
        Field(discriminator="mode"),
    ] = Field(
        default_factory=lambda: AnalysisPending(
            reason="Review exact PCB return pads, their copper connectivity, and any intentional isolation."
        )
    )
    pin_connectivity: (
        Annotated[
            PinConnectivityAnalysis | AnalysisNotApplicable | AnalysisPending,
            Field(discriminator="mode"),
        ]
        | None
    ) = None
    i2c_pullups: (
        Annotated[
            I2cPullupAnalysis | AnalysisNotApplicable | AnalysisPending,
            Field(discriminator="mode"),
        ]
        | None
    ) = None
    can_termination: (
        Annotated[
            CanTerminationAnalysis | AnalysisNotApplicable | AnalysisPending,
            Field(discriminator="mode"),
        ]
        | None
    ) = None
    usb_c: (
        Annotated[
            UsbCAnalysis | AnalysisNotApplicable | AnalysisPending,
            Field(discriminator="mode"),
        ]
        | None
    ) = None
    spi: (
        Annotated[
            SpiAnalysis | AnalysisNotApplicable | AnalysisPending,
            Field(discriminator="mode"),
        ]
        | None
    ) = None
    serial_peers: (
        Annotated[
            SerialPeerAnalysis | AnalysisNotApplicable | AnalysisPending,
            Field(discriminator="mode"),
        ]
        | None
    ) = None
    digital_peer_voltages: (
        Annotated[
            DigitalPeerVoltageAnalysis | AnalysisNotApplicable | AnalysisPending,
            Field(discriminator="mode"),
        ]
        | None
    ) = None
    component_voltage_ratings: (
        Annotated[
            ComponentVoltageRatingAnalysis | AnalysisNotApplicable | AnalysisPending,
            Field(discriminator="mode"),
        ]
        | None
    ) = None
    component_power_ratings: (
        Annotated[
            ComponentPowerRatingAnalysis | AnalysisNotApplicable | AnalysisPending,
            Field(discriminator="mode"),
        ]
        | None
    ) = None
    connector_contact_ratings: (
        Annotated[
            ConnectorContactRatingAnalysis | AnalysisNotApplicable | AnalysisPending,
            Field(discriminator="mode"),
        ]
        | None
    ) = None
    mosfet_stress: (
        Annotated[
            MosfetStressAnalysis | AnalysisNotApplicable | AnalysisPending,
            Field(discriminator="mode"),
        ]
        | None
    ) = None
    rs485: (
        Annotated[
            Rs485Analysis | AnalysisNotApplicable | AnalysisPending,
            Field(discriminator="mode"),
        ]
        | None
    ) = None
    control_inputs: (
        Annotated[
            ControlInputsAnalysis | AnalysisNotApplicable | AnalysisPending,
            Field(discriminator="mode"),
        ]
        | None
    ) = None
    test_access: (
        Annotated[
            TestAccessAnalysis | AnalysisNotApplicable | AnalysisPending,
            Field(discriminator="mode"),
        ]
        | None
    ) = None
    power: Annotated[
        PowerAnalysis | AnalysisNotApplicable | AnalysisPending, Field(discriminator="mode")
    ]
    power_connectivity: (
        Annotated[
            PowerConnectivityAnalysis | AnalysisNotApplicable | AnalysisPending,
            Field(discriminator="mode"),
        ]
        | None
    ) = None
    high_frequency: Annotated[
        HighFrequencyAnalysis | AnalysisNotApplicable | AnalysisPending, Field(discriminator="mode")
    ]

    @model_validator(mode="after")
    def unique_cases(self) -> ElectricalAnalysisContract:
        cases: list[SimulationModel] = []
        power: PowerAnalysis | AnalysisNotApplicable | AnalysisPending = self.power
        high_frequency: HighFrequencyAnalysis | AnalysisNotApplicable | AnalysisPending = (
            self.high_frequency
        )
        power_connectivity: (
            PowerConnectivityAnalysis | AnalysisNotApplicable | AnalysisPending | None
        ) = self.power_connectivity
        if isinstance(power, PowerAnalysis):
            cases.extend((*power.startup, *power.steady_state))
        if isinstance(high_frequency, HighFrequencyAnalysis):
            cases.extend((*high_frequency.sweeps, *high_frequency.waveforms))
        if len({case.id.casefold() for case in cases}) != len(cases):
            raise ValueError("Simulation IDs must be unique across all lanes")
        if isinstance(power_connectivity, PowerConnectivityAnalysis) and isinstance(
            power, PowerAnalysis
        ):
            budget_rails = {rail.id: {load.id for load in rail.loads} for rail in power.rails}
            mapped_rails = {
                rail.id: {load.id for load in rail.loads} for rail in power_connectivity.rails
            }
            if set(mapped_rails) != set(budget_rails):
                raise ValueError(
                    "Power connectivity rail IDs must cover the authored power budget rails"
                )
            if mapped_rails != budget_rails:
                raise ValueError(
                    "Power connectivity load IDs must match the authored rail budget loads"
                )
        return self
