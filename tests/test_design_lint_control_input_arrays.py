"""Exact resistor-array maps for connected reset, enable, and boot inputs."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.control_input_bias import control_input_bias_heuristic_coverage
from kicad_tooling.hwrepo.control_input_checks import control_input_checks
from kicad_tooling.hwrepo.control_input_models import (
    ControlBiasArrayChannelRequirement,
    ControlBiasResistorArrayRequirement,
    ControlInputsAnalysis,
    ControlLocalBiasRequirement,
    ControlPinRequirement,
    ControlSignalRequirement,
)
from kicad_tooling.hwrepo.models import ComponentContract, NetlistContract

pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint, pytest.mark.power_lint]

RULE_ID = "control.connected_control_input_without_visible_bias"


def control_array_spec(*, extra_channel: bool = False) -> ControlInputsAnalysis:
    channels = [
        ControlBiasArrayChannelRequirement(
            id="reset",
            signal_pin="RN1.1",
            bias_pin="RN1.2",
            bias_net="+3V3",
            direction="pull_up",
            nominal_ohms=10_000,
            minimum_ohms=9_000,
            maximum_ohms=11_000,
            basis="Synthetic datasheet resistance and reviewed reset window",
        )
    ]
    if extra_channel:
        channels.append(
            ControlBiasArrayChannelRequirement(
                id="reset-secondary",
                signal_pin="RN1.3",
                bias_pin="RN1.2",
                bias_net="+3V3",
                direction="pull_up",
                nominal_ohms=10_000,
                minimum_ohms=9_000,
                maximum_ohms=11_000,
                basis="Synthetic second channel shares the reviewed rail pin",
            )
        )
    array = ControlBiasResistorArrayRequirement(
        reference="RN1",
        expected_symbol="Synthetic:ResistorArray",
        expected_footprint="Synthetic:RA4",
        expected_value="4x10k",
        expected_part_id="SYNTHETIC-ARRAY-10K",
        basis="Synthetic resistor-array datasheet and pin map",
        channels=tuple(channels),
        unmapped_pin_reasons={
            "RN1.3": "Unused channel pin" if not extra_channel else "",
            "RN1.4": "Unused channel pin",
        }
        if not extra_channel
        else {"RN1.4": "Unused channel pin"},
    )
    return ControlInputsAnalysis(
        basis="Synthetic exact reset-input requirement",
        signals=(
            ControlSignalRequirement(
                id="main-reset",
                basis="Synthetic reset input and reviewed resistor-array bias",
                signal_net="RESET_N",
                driver_policy="none",
                endpoints=(
                    ControlPinRequirement(
                        role="controlled_input",
                        reference="U1",
                        symbol="Synthetic:Controller",
                        footprint="Synthetic:SOIC",
                        pin="U1.1",
                        electrical_type="input",
                    ),
                ),
                bias=ControlLocalBiasRequirement(
                    mode="local",
                    basis="Reviewed synthetic reset bias network",
                    arrays=(array,),
                ),
            ),
        ),
    )


def control_array_netlist(
    *, fault: str | None = None, extra_channel: bool = False
) -> NetlistContract:
    components = {
        "U1": ComponentContract(value="Synthetic controller", footprint="Synthetic:SOIC"),
        "RN1": ComponentContract(
            value="4x10k", footprint="Synthetic:RA4", part_id="SYNTHETIC-ARRAY-10K"
        ),
    }
    symbols = {"U1": "Synthetic:Controller", "RN1": "Synthetic:ResistorArray"}
    nets: dict[str, tuple[str, ...]] = {
        "RESET_N": ("U1.1", "RN1.1") + (("RN1.3",) if extra_channel else ()),
        "+3V3": ("RN1.2",),
    }
    dnp: tuple[str, ...] = ()
    inventory = {"U1": ("1",), "RN1": ("1", "2", "3", "4")}
    if fault == "wrong-symbol":
        symbols["RN1"] = "Synthetic:OtherArray"
    elif fault == "wrong-footprint":
        components["RN1"] = components["RN1"].model_copy(update={"footprint": "Synthetic:RA8"})
    elif fault == "wrong-value":
        components["RN1"] = components["RN1"].model_copy(update={"value": "4x47k"})
    elif fault == "wrong-part-id":
        components["RN1"] = components["RN1"].model_copy(update={"part_id": "SYNTHETIC-ARRAY-47K"})
    elif fault == "missing-part-id":
        components["RN1"] = components["RN1"].model_copy(update={"part_id": None})
    elif fault == "dnp":
        dnp = ("RN1",)
    elif fault == "wrong-net":
        nets.pop("+3V3")
        nets["+5V"] = ("RN1.2",)
    elif fault == "unconnected":
        nets.pop("+3V3")
    elif fault == "wrong-endpoint":
        nets["RESET_N"] = ("U1.1",)
        nets["OTHER"] = ("RN1.1",)
    elif fault == "extra-pin":
        inventory["RN1"] = ("1", "2", "3", "4", "5")
    elif fault == "missing-inventory":
        inventory.pop("RN1")

    return NetlistContract(
        components=components,
        nets=nets,
        dnp_components=dnp,
        component_symbols=symbols,
        pin_functions={"U1.1": "RESET_N", "RN1.1": "1", "RN1.2": "2"},
        pin_electrical_types={"U1.1": "input", "RN1.1": "passive", "RN1.2": "passive"},
        component_pin_numbers=inventory,
    )


def _coverage(
    observed: NetlistContract,
    spec: ControlInputsAnalysis | None = None,
    *,
    configured: bool = True,
) -> tuple[str, tuple[str, ...]]:
    report = control_input_bias_heuristic_coverage(
        observed,
        netlist_sha256="a" * 64,
        source_path="design_lint/control_inputs.json",
        source_sha256="b" * 64,
        state="ready",
        spec=(control_array_spec() if spec is None else spec) if configured else None,
    )
    assert len(report.entries) == 1
    return report.entries[0].status, report.entries[0].issues


def test_exact_array_mapping_resolves_connected_reset_bias_prompt() -> None:
    observed = control_array_netlist()
    rows = {item.id: item for item in control_input_checks(control_array_spec(), observed)}

    assert rows["control-inputs/main-reset/bias"].status == "PASS"
    assert rows["control-inputs/main-reset/bias"].detail.startswith("1 declared local bias path")
    assert _coverage(observed)[0] == "COVERED"


@pytest.mark.parametrize(
    ("fault", "expected_issue"),
    (
        ("wrong-symbol", "symbol is Synthetic:OtherArray"),
        ("wrong-footprint", "footprint is Synthetic:RA8"),
        ("wrong-value", "value is 4x47k"),
        ("wrong-part-id", "PART_ID is SYNTHETIC-ARRAY-47K"),
        ("missing-part-id", "PART_ID is missing"),
        ("dnp", "RN1 is DNP"),
        ("wrong-net", "expected one pin on RESET_N and one on +3V3"),
        ("unconnected", "is on unconnected"),
        ("wrong-endpoint", "RN1.1 is on OTHER"),
        ("extra-pin", "unreviewed symbol pins"),
        ("missing-inventory", "has no native symbol pin inventory"),
    ),
)
def test_stale_or_miswired_array_maps_keep_bias_prompt_open(
    fault: str, expected_issue: str
) -> None:
    observed = control_array_netlist(fault=fault)
    rows = {item.id: item for item in control_input_checks(control_array_spec(), observed)}
    status, issues = _coverage(observed)

    assert rows["control-inputs/main-reset/bias"].status == "FAIL"
    assert expected_issue in rows["control-inputs/main-reset/bias"].detail
    assert status == "OPEN"
    assert any(expected_issue in issue for issue in issues)


def test_shared_bias_pin_is_supported_only_for_one_declared_domain() -> None:
    shared = control_array_spec(extra_channel=True)
    assert {
        item.id: item.status
        for item in control_input_checks(shared, control_array_netlist(extra_channel=True))
    }["control-inputs/main-reset/bias"] == "PASS"

    raw = shared.model_dump()
    raw["signals"][0]["bias"]["arrays"][0]["channels"][1]["bias_net"] = "+5V"
    with pytest.raises(ValueError, match="one net and direction"):
        ControlInputsAnalysis.model_validate(raw)


def test_array_nominal_resistance_must_fit_the_reviewed_window() -> None:
    raw = control_array_spec().model_dump()
    raw["signals"][0]["bias"]["arrays"][0]["channels"][0]["nominal_ohms"] = 47_000

    with pytest.raises(ValueError, match="outside its reviewed range"):
        ControlInputsAnalysis.model_validate(raw)


def test_missing_array_contract_keeps_heuristic_prompt_open() -> None:
    status, issues = _coverage(control_array_netlist(), configured=False)
    assert status == "OPEN"
    assert any("No project-authored control-input requirement" in issue for issue in issues)


def test_array_control_coverage_is_stable_under_mapping_order() -> None:
    observed = control_array_netlist()
    reordered = observed.model_copy(
        update={
            "components": dict(reversed(tuple(observed.components.items()))),
            "nets": dict(reversed(tuple(observed.nets.items()))),
            "component_symbols": dict(reversed(tuple(observed.component_symbols.items()))),
        }
    )
    spec = control_array_spec()

    assert control_input_checks(spec, observed) == control_input_checks(spec, reordered)
    assert _coverage(observed, spec) == _coverage(reordered, spec)
