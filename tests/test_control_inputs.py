"""Synthetic reset/enable/boot control requirements and deterministic faults."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.control_inputs import control_input_checks
from kicad_tooling.hwrepo.models import (
    ComponentContract,
    ControlBiasResistorRequirement,
    ControlInputsAnalysis,
    ControlLocalBiasRequirement,
    ControlPinRequirement,
    ControlSignalRequirement,
    NetlistContract,
)


def control_requirement(*, bias_mode: str = "local") -> ControlInputsAnalysis:
    bias = (
        ControlLocalBiasRequirement(
            mode="local",
            basis="Synthetic device reset requirement calls for an external pull-up",
            resistors=(
                ControlBiasResistorRequirement(
                    reference="R1",
                    symbol="Device:R",
                    footprint="Resistor_SMD:R_0603_1608Metric",
                    signal_net="RESET_N",
                    bias_net="+3V3",
                    direction="pull_up",
                    minimum_ohms=9_000,
                    maximum_ohms=11_000,
                ),
            ),
        )
        if bias_mode == "local"
        else {
            "mode": bias_mode,
            "basis": "Synthetic reviewed control-pin requirement",
            "reason": "The synthetic device or remote host provides the bias",
        }
    )
    return ControlInputsAnalysis(
        basis="Synthetic exact control-signal requirements",
        signals=(
            ControlSignalRequirement(
                id="main-reset",
                basis="Synthetic device reset and supervisory reset requirements",
                signal_net="RESET_N",
                driver_policy="shared_open_drain",
                driver_basis="Both reset sources are approved wired open-drain contributors",
                endpoints=(
                    ControlPinRequirement(
                        role="controlled_input",
                        reference="U1",
                        symbol="Synthetic:Controller",
                        footprint="Package_QFN:QFN-16",
                        pin="U1.1",
                        electrical_type="input",
                    ),
                    ControlPinRequirement(
                        role="approved_driver",
                        reference="U2",
                        symbol="Synthetic:Supervisor",
                        footprint="Package_SO:SOIC-8",
                        pin="U2.1",
                        electrical_type="open_collector",
                    ),
                    ControlPinRequirement(
                        role="approved_driver",
                        reference="U3",
                        symbol="Synthetic:Supervisor",
                        footprint="Package_SO:SOIC-8",
                        pin="U3.1",
                        electrical_type="open_collector",
                    ),
                    ControlPinRequirement(
                        role="external_interface",
                        reference="J1",
                        symbol="Synthetic:DB9",
                        footprint="Connector:Dsub-9_Male",
                        pin="J1.9",
                        electrical_type="passive",
                    ),
                ),
                bias=bias,
            ),
        ),
    )


def control_netlist(*, fault: str | None = None) -> NetlistContract:
    components = {
        "U1": ComponentContract(value="Synthetic controller", footprint="Package_QFN:QFN-16"),
        "U2": ComponentContract(value="Synthetic supervisor A", footprint="Package_SO:SOIC-8"),
        "U3": ComponentContract(value="Synthetic supervisor B", footprint="Package_SO:SOIC-8"),
        "J1": ComponentContract(value="Synthetic DB9", footprint="Connector:Dsub-9_Male"),
        "TP1": ComponentContract(
            value="Synthetic test point",
            footprint="TestPoint:TestPoint_Pad_D1.0mm",
        ),
        "R1": ComponentContract(value="10k", footprint="Resistor_SMD:R_0603_1608Metric"),
        "U5": ComponentContract(value="Synthetic hazardous output", footprint="Package_SO:SOIC-8"),
    }
    symbols = {
        "U1": "Synthetic:Controller",
        "U2": "Synthetic:Supervisor",
        "U3": "Synthetic:Supervisor",
        "J1": "Synthetic:DB9",
        "TP1": "TestPoint:TestPoint",
        "R1": "Device:R",
        "U5": "Synthetic:HazardousOutput",
    }
    nets: dict[str, tuple[str, ...]] = {
        "RESET_N": ("U1.1", "U2.1", "U3.1", "J1.9", "R1.1"),
        "+3V3": ("R1.2", "TP1.1"),
        "HV_OUT": ("U5.1",),
    }
    pin_types = {
        "U1.1": "input",
        "U2.1": "open_collector",
        "U3.1": "open_collector",
        "J1.9": "passive",
        "TP1.1": "passive",
        "R1.1": "passive",
        "R1.2": "passive",
        "U5.1": "output",
    }
    dnp: tuple[str, ...] = ()
    if fault == "missing-component":
        components.pop("J1")
        symbols.pop("J1")
        pin_types.pop("J1.9")
        nets["RESET_N"] = tuple(pin for pin in nets["RESET_N"] if pin != "J1.9")
    elif fault == "missing-excluded-net":
        nets.pop("HV_OUT")
    elif fault == "wrong-footprint":
        components["J1"] = components["J1"].model_copy(update={"footprint": "Connector:Other"})
    elif fault == "endpoint-dnp":
        dnp = ("J1",)
    elif fault == "missing-resistor":
        components.pop("R1")
        symbols.pop("R1")
        pin_types.pop("R1.1")
        pin_types.pop("R1.2")
        nets["RESET_N"] = tuple(pin for pin in nets["RESET_N"] if not pin.startswith("R1."))
        nets.pop("+3V3")
    elif fault == "wrong-rail":
        nets["+5V"] = nets.pop("+3V3")
    elif fault == "wrong-value":
        components["R1"] = components["R1"].model_copy(update={"value": "47k"})
    elif fault == "resistor-dnp":
        dnp = ("R1",)
    elif fault == "driver-type":
        pin_types["U2.1"] = "output"
    elif fault == "missing-pin-type":
        pin_types.pop("U3.1")
    elif fault == "extra-output":
        components["U4"] = ComponentContract(
            value="Synthetic unreviewed driver", footprint="Package_SO:SOIC-8"
        )
        symbols["U4"] = "Synthetic:PushPullOutput"
        pin_types["U4.1"] = "output"
        nets["RESET_N"] = (*nets["RESET_N"], "U4.1")

    return NetlistContract(
        components=components,
        nets=nets,
        dnp_components=dnp,
        component_symbols=symbols,
        pin_functions={
            "U1.1": "RESET_N",
            "U2.1": "RESET_N",
            "U3.1": "RESET_N",
            "J1.9": "RESET",
            "TP1.1": "TestPoint",
            "R1.1": "1",
            "R1.2": "2",
            "U5.1": "HV_OUT",
            **({"U4.1": "RESET_N"} if fault == "extra-output" else {}),
        },
        pin_electrical_types=pin_types,
        component_pin_numbers={
            "U1": ("1",),
            "U2": ("1",),
            "U3": ("1",),
            "J1": ("9",),
            "TP1": ("1",),
            "U5": ("1",),
            **({"R1": ("1", "2")} if "R1" in components else {}),
            **({"U4": ("1",)} if fault == "extra-output" else {}),
        },
    )


def control_rows(*, fault: str | None = None, bias_mode: str = "local"):
    return {
        row.id: row
        for row in control_input_checks(
            control_requirement(bias_mode=bias_mode), control_netlist(fault=fault)
        )
    }


def test_synthetic_shared_open_drain_reset_and_pullup_pass() -> None:
    rows = control_rows()
    assert rows["control-inputs/main-reset/endpoints"].status == "PASS"
    assert rows["control-inputs/main-reset/drivers"].status == "PASS"
    assert rows["control-inputs/main-reset/bias"].status == "PASS"


@pytest.mark.parametrize("fault", ("missing-resistor", "wrong-rail", "wrong-value", "resistor-dnp"))
def test_required_bias_resistor_faults_fail(fault: str) -> None:
    assert control_rows(fault=fault)["control-inputs/main-reset/bias"].status == "FAIL"


@pytest.mark.parametrize(
    ("fault", "check_id"),
    (
        ("driver-type", "drivers"),
        ("extra-output", "drivers"),
        ("missing-pin-type", "endpoints"),
    ),
)
def test_driver_type_and_inventory_faults_fail(fault: str, check_id: str) -> None:
    assert control_rows(fault=fault)[f"control-inputs/main-reset/{check_id}"].status == "FAIL"


@pytest.mark.parametrize("mode", ("internal", "external", "not_required"))
def test_nonlocal_bias_is_explicitly_unverified(mode: str) -> None:
    assert control_rows(bias_mode=mode)["control-inputs/main-reset/bias"].status == "NOT_APPLICABLE"


def test_shared_open_drain_contract_rejects_push_pull_type() -> None:
    raw = control_requirement().model_dump()
    raw["signals"][0]["endpoints"][1]["electrical_type"] = "output"
    with pytest.raises(ValueError, match="open-collector/emitter"):
        ControlInputsAnalysis.model_validate(raw)
