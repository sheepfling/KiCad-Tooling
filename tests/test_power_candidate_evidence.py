"""Power candidate projections preserve their typed scan source and wire fields."""

from __future__ import annotations

from operator import setitem

import pytest

from kicad_tooling.hwrepo.component_pin_patterns import RepeatedComponentSupplyPins
from kicad_tooling.hwrepo.component_power_input_domains import SplitPowerInputDomains
from kicad_tooling.hwrepo.design_lint_power_candidate_evidence import (
    PowerCandidate,
    PowerCandidateSource,
    project_power_candidate_evidence,
)
from kicad_tooling.hwrepo.net_dc_reference import ConnectorCapacitorOnlyNet
from kicad_tooling.hwrepo.power_decoupling import PowerRailCapacitorGap
from kicad_tooling.hwrepo.power_pin_paths import PowerInputSourcePathGap
from kicad_tooling.hwrepo.power_rail_models import NumberedPowerRailGroup


@pytest.mark.parametrize(
    ("source", "rule_id", "evidence"),
    [
        pytest.param(
            SplitPowerInputDomains(
                reference="U1",
                symbol="MCU:Example",
                nominal_voltage="3.3",
                pins={"U1.1": ("3V3_A",), "U1.2": ("3V3_B",)},
            ),
            "component.same_voltage_power_inputs_split",
            {"U1.1": ("3V3_A",), "U1.2": ("3V3_B",)},
            id="same-voltage-inputs",
        ),
        pytest.param(
            PowerRailCapacitorGap(
                net="3V3",
                input_pins=("U1.1",),
                component_references=("U1",),
            ),
            "power.ic_rail_without_fitted_capacitor",
            {
                "net": ("3V3",),
                "power_input_pins": ("U1.1",),
                "component_references": ("U1",),
            },
            id="rail-capacitor-gap",
        ),
        pytest.param(
            PowerInputSourcePathGap(
                net="VLOAD",
                input_pins=("U1.1",),
                capacitor_references=("C1",),
                source_nets=("VIN",),
            ),
            "power.input_without_supported_source_path",
            {
                "net": ("VLOAD",),
                "power_input_pins": ("U1.1",),
                "fitted_capacitors_to_return": ("C1",),
                "recognized_source_nets": ("VIN",),
                "source_anchor_state": ("recognized",),
            },
            id="recognized-source-anchor",
        ),
        pytest.param(
            PowerInputSourcePathGap(
                net="VLOAD",
                input_pins=("U1.1",),
                capacitor_references=("C1",),
                source_nets=(),
            ),
            "power.input_without_supported_source_path",
            {
                "net": ("VLOAD",),
                "power_input_pins": ("U1.1",),
                "fitted_capacitors_to_return": ("C1",),
                "recognized_source_nets": (),
                "source_anchor_state": ("not_recognized",),
            },
            id="missing-source-anchor",
        ),
        pytest.param(
            ConnectorCapacitorOnlyNet(
                net="VUSB",
                connector_pins=("J1.1",),
                capacitor_pins=("C1.1",),
                component_symbols=("C1=Device:C", "J1=Connector:USB"),
            ),
            "net.connector_capacitor_only_no_dc_anchor",
            {
                "net": ("VUSB",),
                "connector_pins": ("J1.1",),
                "capacitor_pins": ("C1.1",),
                "component_symbols": ("C1=Device:C", "J1=Connector:USB"),
            },
            id="connector-capacitor-only-net",
        ),
        pytest.param(
            RepeatedComponentSupplyPins(
                reference="U1",
                symbol="MCU:Example",
                function="VDD",
                pins={"U1.1": ("3V3_A",), "U1.2": ("3V3_B",)},
            ),
            "component.repeated_supply_pin_function",
            {"U1.1": ("3V3_A",), "U1.2": ("3V3_B",)},
            id="repeated-supply-function",
        ),
        pytest.param(
            NumberedPowerRailGroup(
                stem="5V",
                nets={"5V_1": ("J1.1",), "5V_2": ("J2.1",)},
            ),
            "net.numbered_power_rails",
            {"5V_1": ("J1.1",), "5V_2": ("J2.1",)},
            id="numbered-rails",
        ),
    ],
)
def test_power_projection_keeps_report_fields_bound_to_typed_source(
    source: PowerCandidateSource,
    rule_id: str,
    evidence: dict[str, tuple[str, ...]],
) -> None:
    projection = project_power_candidate_evidence(source)
    candidate = PowerCandidate.from_source_evidence(source, subject="review", message="inspect")

    assert projection.rule_id == rule_id
    assert dict(projection.evidence) == evidence
    assert candidate.source_evidence is source
    assert candidate.rule_id == rule_id
    assert dict(candidate.evidence) == evidence


def test_power_candidate_rejects_fields_that_do_not_match_its_source() -> None:
    source = PowerRailCapacitorGap("3V3", ("U1.1",), ("U1",))

    with pytest.raises(ValueError, match="typed source projection"):
        PowerCandidate(
            rule_id="power.ic_rail_without_fitted_capacitor",
            subject="review",
            message="inspect",
            evidence={"net": ("OTHER",)},
            source_evidence=source,
        )


def test_same_voltage_source_copies_and_freezes_its_pin_mapping() -> None:
    input_map = {"U1.1": ("3V3",)}
    source = SplitPowerInputDomains(
        reference="U1",
        symbol="MCU:Example",
        nominal_voltage="3.3",
        pins=input_map,
    )
    input_map["U1.1"] = ("5V",)

    assert source.pins == {"U1.1": ("3V3",)}
    with pytest.raises(TypeError):
        setitem(source.pins, "U1.2", ("5V",))


def test_repeated_supply_source_copies_and_freezes_its_pin_mapping() -> None:
    input_map = {"U1.1": ("3V3",)}
    source = RepeatedComponentSupplyPins(
        reference="U1",
        symbol="MCU:Example",
        function="VDD",
        pins=input_map,
    )
    input_map["U1.1"] = ("5V",)

    assert source.pins == {"U1.1": ("3V3",)}
    with pytest.raises(TypeError):
        setitem(source.pins, "U1.2", ("5V",))


def test_numbered_rail_source_copies_and_freezes_its_net_mapping() -> None:
    input_map = {"5V_1": ("J1.1",)}
    source = NumberedPowerRailGroup(stem="5V", nets=input_map)
    input_map["5V_1"] = ("J2.1",)

    assert source.nets == {"5V_1": ("J1.1",)}
    with pytest.raises(TypeError):
        setitem(source.nets, "5V_2", ("J2.1",))
