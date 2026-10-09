"""Project-authored component voltage rating comparisons use exact native identity."""

from __future__ import annotations

from pathlib import Path
from xml.etree import ElementTree as ET

import pytest
from pydantic import ValidationError

from kicad_tooling.hwrepo.component_voltage_ratings import component_voltage_rating_checks
from kicad_tooling.hwrepo.models import (
    ComponentContract,
    ComponentVoltageRatingAnalysis,
    ComponentVoltageRatingRequirement,
    NetlistContract,
)
from kicad_tooling.validate import read_netlist


def requirement(
    *,
    rated_voltage_v: float = 16.0,
    maximum_expected_voltage_v: float = 12.0,
    maximum_utilization_fraction: float = 0.8,
) -> ComponentVoltageRatingAnalysis:
    return ComponentVoltageRatingAnalysis(
        basis="Synthetic capacitor working-voltage review",
        requirements=(
            ComponentVoltageRatingRequirement(
                id="input-capacitor",
                reference="C1",
                expected_symbol="Device:C",
                expected_footprint="Capacitor_SMD:C_0603_1608Metric",
                expected_part_id="CAP-0603-16V",
                pins=("C1.1", "C1.2"),
                nets=("VINPUT", "GND"),
                rated_working_voltage_v=rated_voltage_v,
                maximum_expected_voltage_v=maximum_expected_voltage_v,
                maximum_utilization_fraction=maximum_utilization_fraction,
                rating_source="Synthetic capacitor datasheet Rev A, Table 2",
                rating_conditions="DC working voltage at the declared temperature range",
                stress_basis="Synthetic source-voltage envelope, worst-case steady state",
            ),
        ),
    )


def netlist(*, fault: str | None = None) -> NetlistContract:
    footprint = "Capacitor_SMD:C_0603_1608Metric"
    symbol = "Device:C"
    part_id = "CAP-0603-16V"
    pin_numbers = ("1", "2")
    first_net = "VINPUT"
    second_net = "GND"
    dnp_components: tuple[str, ...] = ()
    if fault == "wrong-footprint":
        footprint = "Capacitor_SMD:C_0805_2012Metric"
    elif fault == "wrong-symbol":
        symbol = "Device:R"
    elif fault == "wrong-part-id":
        part_id = "CAP-0603-6V3"
    elif fault == "wrong-pin-inventory":
        pin_numbers = ("1", "2", "3")
    elif fault == "wrong-net":
        second_net = "VLOGIC"
    elif fault == "unconnected":
        second_net = ""
    elif fault == "dnp":
        dnp_components = ("C1",)

    nets = {first_net: ("C1.1",)}
    if second_net:
        nets[second_net] = ("C1.2",)
    return NetlistContract(
        components={"C1": ComponentContract(value="10uF", footprint=footprint, part_id=part_id)},
        nets=nets,
        dnp_components=dnp_components,
        component_symbols={"C1": symbol},
        component_pin_numbers={"C1": pin_numbers},
    )


def native_netlist_xml() -> str:
    root = ET.Element("export")
    components = ET.SubElement(root, "components")
    component = ET.SubElement(components, "comp", ref="C1")
    ET.SubElement(component, "value").text = "10uF"
    ET.SubElement(component, "footprint").text = "Capacitor_SMD:C_0603_1608Metric"
    fields = ET.SubElement(component, "fields")
    ET.SubElement(fields, "field", name="PART_ID").text = "CAP-0603-16V"
    ET.SubElement(component, "libsource", lib="Device", part="C")
    units = ET.SubElement(component, "units")
    unit = ET.SubElement(units, "unit", name="A")
    pins = ET.SubElement(unit, "pins")
    for number in ("1", "2"):
        ET.SubElement(pins, "pin", num=number)
    libparts = ET.SubElement(root, "libparts")
    libpart = ET.SubElement(libparts, "libpart", lib="Device", part="C")
    pin_table = ET.SubElement(libpart, "pins")
    for number in ("1", "2"):
        ET.SubElement(pin_table, "pin", num=number, name=f"{number}", type="passive")
    nets = ET.SubElement(root, "nets")
    for name, number in (("VINPUT", "1"), ("GND", "2")):
        net = ET.SubElement(nets, "net", name=name)
        ET.SubElement(net, "node", ref="C1", pin=number)
    return ET.tostring(root, encoding="unicode")


def test_exact_part_below_utilization_limit_passes() -> None:
    checks = {
        item.id.rsplit("/", maxsplit=1)[-1]: item
        for item in component_voltage_rating_checks(requirement(), netlist())
    }
    assert checks["identity"].status == "PASS"
    assert checks["pin-1"].status == "PASS"
    assert checks["pin-2"].status == "PASS"
    assert checks["utilization"].status == "PASS"
    assert checks["utilization"].observed == pytest.approx(0.75)
    assert checks["utilization"].unit == "fraction"


def test_inclusive_limit_passes_and_excess_utilization_fails() -> None:
    at_limit = {
        item.id: item
        for item in component_voltage_rating_checks(
            requirement(maximum_expected_voltage_v=12.8), netlist()
        )
    }
    assert at_limit["component-voltage-rating/input-capacitor/utilization"].status == "PASS"

    over_limit = {
        item.id: item
        for item in component_voltage_rating_checks(
            requirement(maximum_expected_voltage_v=13.0), netlist()
        )
    }
    utilization = over_limit["component-voltage-rating/input-capacitor/utilization"]
    assert utilization.status == "FAIL"
    assert "Synthetic source-voltage envelope" in utilization.detail


@pytest.mark.parametrize(
    "fault",
    (
        "wrong-footprint",
        "wrong-symbol",
        "wrong-part-id",
        "wrong-pin-inventory",
        "wrong-net",
        "unconnected",
        "dnp",
    ),
)
def test_exact_identity_pin_and_population_faults_keep_margin_unresolved(fault: str) -> None:
    checks = {
        item.id.rsplit("/", maxsplit=1)[-1]: item
        for item in component_voltage_rating_checks(requirement(), netlist(fault=fault))
    }
    assert any(check.status == "FAIL" for check in checks.values()), checks
    assert checks["utilization"].status == "NOT_APPLICABLE"


def test_missing_component_is_a_fail_closed_identity_mismatch() -> None:
    observed = netlist().model_copy(
        update={
            "components": {},
            "component_symbols": {},
            "component_pin_numbers": {},
            "nets": {},
        }
    )
    checks = {item.id: item for item in component_voltage_rating_checks(requirement(), observed)}
    identity = checks["component-voltage-rating/input-capacitor/identity"]
    assert identity.status == "FAIL"
    assert "absent from the native netlist" in identity.detail


def test_requirement_rejects_invalid_component_and_margin_maps() -> None:
    raw = requirement().model_dump()
    raw["requirements"][0]["pins"] = ["C1.1", "R1.2"]
    with pytest.raises(ValidationError):
        ComponentVoltageRatingAnalysis.model_validate(raw)

    raw = requirement().model_dump()
    raw["requirements"][0]["maximum_utilization_fraction"] = 1.01
    with pytest.raises(ValidationError):
        ComponentVoltageRatingAnalysis.model_validate(raw)


def test_reordered_native_maps_keep_check_ids_and_results_stable() -> None:
    source = netlist()
    reordered = source.model_copy(
        update={
            "nets": dict(reversed(tuple(source.nets.items()))),
            "components": dict(reversed(tuple(source.components.items()))),
        }
    )
    assert component_voltage_rating_checks(
        requirement(), source
    ) == component_voltage_rating_checks(requirement(), reordered)


def test_native_kicad_netlist_fields_supply_exact_rating_identity(tmp_path: Path) -> None:
    path = tmp_path / "netlist.xml"
    path.write_text(native_netlist_xml(), encoding="utf-8")
    observed = read_netlist(path)

    component = observed.components["C1"]
    assert component.part_id == "CAP-0603-16V"
    assert observed.component_symbols["C1"] == "Device:C"
    assert observed.component_pin_numbers["C1"] == ("1", "2")
    checks = {item.id: item for item in component_voltage_rating_checks(requirement(), observed)}
    assert all(item.status == "PASS" for item in checks.values()), checks
