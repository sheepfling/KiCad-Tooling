"""Source-bound constant-current hold-up checks for mapped storage capacitors."""

from __future__ import annotations

import xml.etree.ElementTree as ET

import pytest
from pydantic import ValidationError

from kicad_tooling.hwrepo.electrical_report_models import ElectricalCheck
from kicad_tooling.hwrepo.energy_storage_hold_up import energy_storage_hold_up_checks
from kicad_tooling.hwrepo.energy_storage_models import (
    EnergyStorageAnalysis,
    EnergyStorageHoldUpRequirement,
)
from kicad_tooling.hwrepo.netlist_contract_models import ComponentContract, NetlistContract

pytestmark = pytest.mark.power_lint


def requirement(*, minimum_hold_up_time_s: float = 0.5) -> EnergyStorageAnalysis:
    return EnergyStorageAnalysis(
        basis="Synthetic exact-part supercapacitor hold-up contract",
        requirements=(
            EnergyStorageHoldUpRequirement(
                id="controller-rail-hold-up",
                reference="C1",
                expected_symbol="Device:C",
                expected_footprint="Synthetic:Radial_Supercap",
                expected_part_id="SUPER-CAP-0P1F",
                pins=("C1.1", "C1.2"),
                nets=("VLOAD", "GND"),
                minimum_start_voltage_v=1.8,
                minimum_operating_voltage_v=1.2,
                maximum_constant_load_current_a=0.05,
                minimum_hold_up_time_s=minimum_hold_up_time_s,
                minimum_effective_capacitance_fraction=0.6,
                maximum_utilization_fraction=0.8,
                capacitance_source="Synthetic supercapacitor data table, Rev A",
                effective_capacitance_basis=(
                    "Synthetic lower-bound factor including stated tolerance and temperature range"
                ),
                load_current_basis="Synthetic maximum constant-current load calculation",
                voltage_window_basis="Synthetic minimum start and regulated-load voltage corners",
                hold_up_basis="Synthetic minimum backup duration requirement",
            ),
        ),
    )


def netlist(*, fault: str | None = None) -> NetlistContract:
    value = "0.1F"
    footprint = "Synthetic:Radial_Supercap"
    symbol = "Device:C"
    part_id = "SUPER-CAP-0P1F"
    pins = ("1", "2")
    positive_net = "VLOAD"
    negative_net = "GND"
    dnp: tuple[str, ...] = ()
    if fault == "wrong-value":
        value = "0.05F"
    elif fault == "unsupported-value":
        value = "CAP-SUPER"
    elif fault == "wrong-footprint":
        footprint = "Synthetic:Radial_Capacitor"
    elif fault == "wrong-symbol":
        symbol = "Device:R"
    elif fault == "wrong-part-id":
        part_id = "SUPER-CAP-0P2F"
    elif fault == "wrong-pin-inventory":
        pins = ("1", "2", "3")
    elif fault == "wrong-net":
        negative_net = "CHASSIS"
    elif fault == "open-pin":
        negative_net = ""
    elif fault == "dnp":
        dnp = ("C1",)

    nets = {positive_net: ("C1.1",)}
    if negative_net:
        nets[negative_net] = ("C1.2",)
    return NetlistContract(
        components={
            "C1": ComponentContract(
                value=value,
                footprint=footprint,
                part_id=part_id,
            )
        },
        nets=nets,
        component_symbols={"C1": symbol},
        component_pin_numbers={"C1": pins},
        dnp_components=dnp,
    )


def native_netlist_xml() -> str:
    """Build the minimal native-format exact-part netlist used by evidence replay."""
    root = ET.Element("export")
    components = ET.SubElement(root, "components")
    component = ET.SubElement(components, "comp", ref="C1")
    ET.SubElement(component, "value").text = "0.1F"
    ET.SubElement(component, "footprint").text = "Synthetic:Radial_Supercap"
    fields = ET.SubElement(component, "fields")
    ET.SubElement(fields, "field", name="PART_ID").text = "SUPER-CAP-0P1F"
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
        ET.SubElement(pin_table, "pin", num=number, name=number, type="passive")
    nets = ET.SubElement(root, "nets")
    for name, number in (("VLOAD", "1"), ("GND", "2")):
        net = ET.SubElement(nets, "net", name=name)
        ET.SubElement(net, "node", ref="C1", pin=number)
    return ET.tostring(root, encoding="unicode")


def checks_by_suffix(
    spec: EnergyStorageAnalysis | None = None, observed: NetlistContract | None = None
) -> dict[str, ElectricalCheck]:
    return {
        item.id.rsplit("/", maxsplit=1)[-1]: item
        for item in energy_storage_hold_up_checks(spec or requirement(), observed or netlist())
    }


def test_exact_storage_capacitor_passes_with_authored_effective_capacity() -> None:
    checks = checks_by_suffix()
    assert checks["identity"].status == "PASS"
    assert checks["pin-1"].status == "PASS"
    assert checks["pin-2"].status == "PASS"
    assert checks["hold-up"].status == "PASS"
    assert checks["hold-up"].observed == pytest.approx(0.6944444444)
    assert checks["hold-up"].unit == "fraction"
    assert "constant-current model" in checks["hold-up"].detail
    assert "ESR" not in checks["hold-up"].detail


def test_inclusive_utilization_limit_passes_and_longer_hold_up_fails() -> None:
    at_limit = checks_by_suffix(requirement(minimum_hold_up_time_s=0.576))
    assert at_limit["hold-up"].status == "PASS"
    assert at_limit["hold-up"].observed == pytest.approx(0.8)

    over_limit = checks_by_suffix(requirement(minimum_hold_up_time_s=0.6))
    assert over_limit["hold-up"].status == "FAIL"
    assert over_limit["hold-up"].observed == pytest.approx(0.8333333333)


def test_changed_capacitor_value_changes_hold_up_margin() -> None:
    checks = checks_by_suffix(observed=netlist(fault="wrong-value"))
    assert checks["identity"].status == "PASS"
    assert checks["pin-1"].status == "PASS"
    assert checks["pin-2"].status == "PASS"
    assert checks["hold-up"].status == "FAIL"


@pytest.mark.parametrize(
    "fault",
    (
        "wrong-footprint",
        "wrong-symbol",
        "wrong-part-id",
        "wrong-pin-inventory",
        "wrong-net",
        "open-pin",
        "dnp",
    ),
)
def test_stale_or_mismatched_native_component_evidence_blocks_comparison(fault: str) -> None:
    checks = checks_by_suffix(observed=netlist(fault=fault))
    assert any(item.status == "FAIL" for item in checks.values())
    assert checks["hold-up"].status == "NOT_APPLICABLE"


def test_unsupported_value_fails_instead_of_claiming_hold_up() -> None:
    checks = checks_by_suffix(observed=netlist(fault="unsupported-value"))
    assert checks["hold-up"].status == "FAIL"
    assert "not a supported explicit capacitance" in checks["hold-up"].detail


def test_contract_rejects_bad_voltage_window_pin_map_and_fraction() -> None:
    raw = requirement().model_dump()
    raw["requirements"][0]["pins"] = ("C1.1", "R1.2")
    with pytest.raises(ValidationError, match="belong to"):
        EnergyStorageAnalysis.model_validate(raw)

    raw = requirement().model_dump()
    raw["requirements"][0]["nets"] = ("GND", "gnd")
    with pytest.raises(ValidationError, match="distinct"):
        EnergyStorageAnalysis.model_validate(raw)

    raw = requirement().model_dump()
    raw["requirements"][0]["minimum_effective_capacitance_fraction"] = 1.1
    with pytest.raises(ValidationError):
        EnergyStorageAnalysis.model_validate(raw)

    raw = requirement().model_dump()
    raw["requirements"][0]["minimum_start_voltage_v"] = 1.2
    with pytest.raises(ValidationError, match="must exceed"):
        EnergyStorageAnalysis.model_validate(raw)


def test_check_results_are_stable_under_net_and_component_ordering() -> None:
    observed = netlist()
    reordered = observed.model_copy(
        update={
            "nets": dict(reversed(tuple(observed.nets.items()))),
            "components": dict(reversed(tuple(observed.components.items()))),
        }
    )
    assert energy_storage_hold_up_checks(requirement(), observed) == energy_storage_hold_up_checks(
        requirement(), reordered
    )
