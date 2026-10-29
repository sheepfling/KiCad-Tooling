"""Exact resistor-array maps for the SPI chip-select bias review heuristic."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.models import (
    ComponentContract,
    DesignLintPolicy,
    NetlistContract,
)
from kicad_tooling.hwrepo.spi_contract import spi_checks
from kicad_tooling.hwrepo.spi_models import (
    SpiAnalysis,
    SpiBiasArrayChannelRequirement,
    SpiBiasResistorArrayRequirement,
    SpiBusRequirement,
    SpiControllerRequirement,
    SpiDeviceRequirement,
    SpiPinNetRequirement,
    SpiPinNotPresent,
)
from kicad_tooling.hwrepo.spi_participants import SpiRosterContext
from tests.design_lint_fixtures import coach, spi_active_low_select_netlist

pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint]

RULE_ID = "bus.spi_active_low_chip_select_without_pullup"


def _array_requirement(
    *,
    resistance_ohms: float = 10_000,
    rail_net: str = "+3V3",
) -> SpiBiasResistorArrayRequirement:
    return SpiBiasResistorArrayRequirement(
        reference="RN1",
        expected_symbol="Synthetic:ResistorArray",
        expected_footprint="Synthetic:RA4",
        expected_value="4x10k",
        expected_part_id="SYNTHETIC-ARRAY-10K",
        basis="Synthetic exact SPI chip-select array and channel map",
        channels=(
            SpiBiasArrayChannelRequirement(
                id="chip-select",
                signal_pin="RN1.1",
                rail_pin="RN1.2",
                signal_net="SPI_CS_N",
                rail_net=rail_net,
                resistance_ohms=resistance_ohms,
                basis="Synthetic reviewed channel nominal value",
            ),
        ),
        unmapped_pin_reasons={
            "RN1.3": "Unused array channel is not connected",
            "RN1.4": "Unused array channel is not connected",
        },
    )


def _analysis(
    array: SpiBiasResistorArrayRequirement | None = None,
) -> SpiAnalysis:
    controller = SpiControllerRequirement(
        reference="U1",
        symbol="Synthetic:SpiController",
        footprint="Synthetic:QFN",
        sck=SpiPinNetRequirement(pin="U1.2", net="SPI_CLOCK"),
        mosi=SpiPinNetRequirement(pin="U1.3", net="SPI_MOSI"),
        miso=SpiPinNotPresent(mode="not_present", reason="Synthetic controller has no MISO"),
        chip_selects=(SpiPinNetRequirement(pin="U1.4", net="SPI_CS_N"),),
    )
    device = SpiDeviceRequirement(
        id="flash",
        reference="U2",
        symbol="Synthetic:SpiPeripheral",
        footprint="Synthetic:SOIC",
        sck=SpiPinNetRequirement(pin="U2.2", net="SPI_CLOCK"),
        mosi=SpiPinNetRequirement(pin="U2.3", net="SPI_MOSI"),
        miso=SpiPinNotPresent(mode="not_present", reason="Synthetic peripheral has no MISO"),
        chip_select=SpiPinNetRequirement(pin="U2.1", net="SPI_CS_N"),
    )
    bus = SpiBusRequirement(
        id="main",
        basis="Synthetic SPI roster with one active-low peripheral select",
        controller=controller,
        devices=(device,),
    )
    return SpiAnalysis(
        basis="Synthetic reviewed SPI membership and bias-array requirements",
        buses=(bus,),
        chip_select_pullup_arrays=() if array is None else (array,),
    )


def _array_netlist(*, fault: str | None = None) -> NetlistContract:
    base = spi_active_low_select_netlist()
    components = dict(base.components)
    components["U1"] = ComponentContract(value="Synthetic controller", footprint="Synthetic:QFN")
    components["U2"] = ComponentContract(value="Synthetic peripheral", footprint="Synthetic:SOIC")
    components["RN1"] = ComponentContract(
        value="4x10k", footprint="Synthetic:RA4", part_id="SYNTHETIC-ARRAY-10K"
    )
    symbols = {
        "U1": "Synthetic:SpiController",
        "U2": "Synthetic:SpiPeripheral",
        "RN1": "Synthetic:ResistorArray",
    }
    functions = {
        "U1.1": "VDD",
        "U1.2": "SCK",
        "U1.3": "MOSI",
        "U1.4": "CS_OUT",
        "U1.5": "GND",
        "U2.1": "CS_N",
        "U2.2": "SCK",
        "U2.3": "MOSI",
        "RN1.1": "1",
        "RN1.2": "2",
    }
    pin_types = {"U1.4": "output", "U2.1": "input"}
    nets: dict[str, tuple[str, ...]] = {
        "+3V3": ("U1.1", "RN1.2"),
        "SPI_CS_N": ("U1.4", "U2.1", "RN1.1"),
        "SPI_CLOCK": ("U1.2", "U2.2"),
        "SPI_MOSI": ("U1.3", "U2.3"),
        "GND": ("U1.5",),
    }
    inventory = {
        "U1": ("1", "2", "3", "4", "5"),
        "U2": ("1", "2", "3"),
        "RN1": ("1", "2", "3", "4"),
    }
    dnp: tuple[str, ...] = ()
    if fault == "wrong-symbol":
        symbols["RN1"] = "Synthetic:OtherArray"
    elif fault == "wrong-footprint":
        components["RN1"] = components["RN1"].model_copy(update={"footprint": "Synthetic:RA8"})
    elif fault == "wrong-value":
        components["RN1"] = components["RN1"].model_copy(update={"value": "4x47k"})
    elif fault == "wrong-part-id":
        components["RN1"] = components["RN1"].model_copy(update={"part_id": "SYNTHETIC-ARRAY-47K"})
    elif fault == "dnp":
        dnp = ("RN1",)
    elif fault == "wrong-channel-net":
        nets["SPI_CS_N"] = ("U1.4", "U2.1")
        nets["SPI_CS_WRONG"] = ("RN1.1",)
    elif fault == "wrong-channel-rail":
        nets["+3V3"] = ("U1.1",)
        nets["+5V"] = ("RN1.2",)
    elif fault == "unconnected":
        nets["+3V3"] = ("U1.1",)
    elif fault == "extra-pin":
        inventory["RN1"] = ("1", "2", "3", "4", "5")
    elif fault == "missing-inventory":
        inventory.pop("RN1")
    return NetlistContract(
        components=components,
        nets=nets,
        dnp_components=dnp,
        component_symbols=symbols,
        pin_functions=functions,
        pin_electrical_types=pin_types,
        component_pin_numbers=inventory,
    )


def _report(
    observed: NetlistContract,
    analysis: SpiAnalysis | None,
) -> tuple[str, ...]:
    context = (
        SpiRosterContext(state="not_configured")
        if analysis is None
        else SpiRosterContext(
            state="required",
            analysis=analysis,
            source_path="tests/fixtures/synthetic-spi/electrical.json",
            source_sha256="b" * 64,
        )
    )
    report = evaluate(
        "synthetic-spi-bias-array", coach(observed), DesignLintPolicy(), spi_roster=context
    )
    return tuple(item.rule_id for item in report.findings)


def test_exact_array_contract_resolves_only_the_matching_chip_select_prompt() -> None:
    observed = _array_netlist()
    analysis = _analysis(_array_requirement())
    checks = {item.id: item for item in spi_checks(analysis, observed)}

    assert checks["spi/bias-array/RN1/chip-select"].status == "PASS"
    assert RULE_ID not in _report(observed, analysis)
    assert RULE_ID in _report(observed, None)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_open_peripheral_select_fails_endpoint_but_keeps_array_channel_valid() -> None:
    connected = _array_netlist()
    nets = {
        net: tuple(pin for pin in pins if pin != "U2.1") for net, pins in connected.nets.items()
    }
    observed = connected.model_copy(
        update={"nets": nets, "unconnected_nets": {"unconnected": ("U2.1",)}}
    )
    analysis = _analysis(_array_requirement())
    checks = {item.id: item for item in spi_checks(analysis, observed)}

    assert checks["spi/main/device/flash/pins"].status == "FAIL"
    assert checks["spi/bias-array/RN1/chip-select"].status == "PASS"


@pytest.mark.parametrize(
    ("fault", "expected_issue"),
    (
        ("wrong-symbol", "symbol is Synthetic:OtherArray"),
        ("wrong-footprint", "footprint is Synthetic:RA8"),
        ("wrong-value", "value is 4x47k"),
        ("wrong-part-id", "PART_ID is SYNTHETIC-ARRAY-47K"),
        ("dnp", "RN1 is DNP"),
        ("wrong-channel-net", "expected one pin on SPI_CS_N and one on +3V3"),
        ("wrong-channel-rail", "expected one pin on SPI_CS_N and one on +3V3"),
        ("unconnected", "is on unconnected"),
        ("extra-pin", "unreviewed symbol pins"),
        ("missing-inventory", "has no native symbol pin inventory"),
    ),
)
def test_stale_or_miswired_array_keeps_the_review_prompt_open(
    fault: str,
    expected_issue: str,
) -> None:
    observed = _array_netlist(fault=fault)
    analysis = _analysis(_array_requirement())
    checks = {item.id: item for item in spi_checks(analysis, observed)}

    assert checks["spi/bias-array/RN1/chip-select"].status == "FAIL"
    assert expected_issue in checks["spi/bias-array/RN1/chip-select"].detail
    assert _report(observed, analysis) == (RULE_ID,)


def test_array_outside_the_review_resistance_band_does_not_resolve_the_prompt() -> None:
    observed = _array_netlist()
    analysis = _analysis(_array_requirement(resistance_ohms=100_001))

    assert {item.id: item.status for item in spi_checks(analysis, observed)}[
        "spi/bias-array/RN1/chip-select"
    ] == "PASS"
    assert _report(observed, analysis) == (RULE_ID,)


def test_unrecognized_array_rail_does_not_resolve_the_prompt() -> None:
    observed = _array_netlist()
    nets = dict(observed.nets)
    nets["+3V3"] = ("U1.1",)
    nets["BIAS_FEED"] = ("RN1.2",)
    observed = observed.model_copy(update={"nets": nets})
    analysis = _analysis(_array_requirement(rail_net="BIAS_FEED"))

    assert {item.id: item.status for item in spi_checks(analysis, observed)}[
        "spi/bias-array/RN1/chip-select"
    ] == "PASS"
    assert _report(observed, analysis) == (RULE_ID,)


def test_mapped_array_channel_does_not_clear_an_unmapped_chip_select_gap() -> None:
    observed = _array_netlist()
    nets = dict(observed.nets)
    nets["SPI_CS_OTHER"] = ("U2.4",)
    functions = dict(observed.pin_functions)
    functions["U2.4"] = "CS_N"
    electrical_types = dict(observed.pin_electrical_types)
    electrical_types["U2.4"] = "input"
    inventory = dict(observed.component_pin_numbers)
    inventory["U2"] = (*inventory["U2"], "4")
    observed = observed.model_copy(
        update={
            "nets": nets,
            "pin_functions": functions,
            "pin_electrical_types": electrical_types,
            "component_pin_numbers": inventory,
        }
    )
    analysis = _analysis(_array_requirement())
    report = evaluate(
        "synthetic-spi-bias-array",
        coach(observed),
        DesignLintPolicy(),
        spi_roster=SpiRosterContext(
            state="required",
            analysis=analysis,
            source_path="tests/fixtures/synthetic-spi/electrical.json",
            source_sha256="b" * 64,
        ),
    )

    subjects = tuple(item.subject for item in report.findings if item.rule_id == RULE_ID)
    assert subjects == ("SPI_CS_OTHER: active-low SPI chip-select bias",)


def test_shared_rail_pin_requires_one_rail_net() -> None:
    array = _array_requirement()
    raw = array.model_dump()
    raw["unmapped_pin_reasons"].pop("RN1.3")
    second_channel = {
        "id": "chip-select-secondary",
        "signal_pin": "RN1.3",
        "rail_pin": "RN1.2",
        "signal_net": "SPI_CS_OTHER",
        "rail_net": "+3V3",
        "resistance_ohms": 10_000,
        "basis": "Synthetic reviewed shared rail assignment",
    }
    raw["channels"] = (*raw["channels"], second_channel)

    valid = SpiBiasResistorArrayRequirement.model_validate(raw)
    assert len(valid.channels) == 2

    raw["channels"] = (*raw["channels"][:-1], {**second_channel, "rail_net": "+5V"})

    with pytest.raises(ValueError, match="one exact rail net"):
        SpiBiasResistorArrayRequirement.model_validate(raw)


def test_array_channel_predicate_is_stable_under_netlist_mapping_order() -> None:
    source = _array_netlist(fault="wrong-channel-net")
    reordered = source.model_copy(
        update={
            "components": dict(reversed(tuple(source.components.items()))),
            "nets": dict(reversed(tuple(source.nets.items()))),
            "component_symbols": dict(reversed(tuple(source.component_symbols.items()))),
            "pin_functions": dict(reversed(tuple(source.pin_functions.items()))),
            "component_pin_numbers": dict(reversed(tuple(source.component_pin_numbers.items()))),
        }
    )
    analysis = _analysis(_array_requirement())
    first = evaluate(
        "synthetic-spi-bias-array",
        coach(source),
        DesignLintPolicy(),
        spi_roster=SpiRosterContext(state="required", analysis=analysis),
    )
    second = evaluate(
        "synthetic-spi-bias-array",
        coach(reordered),
        DesignLintPolicy(),
        spi_roster=SpiRosterContext(state="required", analysis=analysis),
    )

    assert first.findings == second.findings
