"""Project-authored component power rating comparisons use exact native identity."""

from __future__ import annotations

import unittest
from xml.etree import ElementTree as ET

from pydantic import ValidationError

from kicad_tooling.hwrepo.component_power_ratings import component_power_rating_checks
from kicad_tooling.hwrepo.models import (
    ComponentContract,
    ComponentPowerRatingAnalysis,
    ComponentPowerRatingRequirement,
    NetlistContract,
)
from kicad_tooling.validate import read_netlist


def requirement(
    *,
    rated_power_w: float = 0.5,
    derated_allowable_power_w: float = 0.25,
    maximum_expected_power_w: float = 0.1,
    maximum_utilization_fraction: float = 0.8,
) -> ComponentPowerRatingAnalysis:
    return ComponentPowerRatingAnalysis(
        basis="Synthetic resistor dissipation comparison",
        requirements=(
            ComponentPowerRatingRequirement(
                id="sense-resistor",
                reference="R1",
                expected_symbol="Device:R",
                expected_footprint="Synthetic:R_0603",
                expected_part_id="RES-10K-0P5W",
                pins=("R1.1", "R1.2"),
                nets=("SENSE", "GND"),
                rated_power_w=rated_power_w,
                derated_allowable_power_w=derated_allowable_power_w,
                maximum_expected_power_w=maximum_expected_power_w,
                maximum_utilization_fraction=maximum_utilization_fraction,
                rating_source="Synthetic resistor datasheet Rev A, power table",
                rating_conditions="Rated at the stated board and ambient conditions",
                derating_basis="Synthetic reviewed thermal derating curve at 70 C",
                stress_basis="Synthetic worst-case current and resistance tolerance calculation",
            ),
        ),
    )


def netlist(*, fault: str | None = None) -> NetlistContract:
    footprint = "Synthetic:R_0603"
    symbol = "Device:R"
    part_id = "RES-10K-0P5W"
    pin_numbers = ("1", "2")
    first_net = "SENSE"
    second_net = "GND"
    dnp_components: tuple[str, ...] = ()
    if fault == "wrong-footprint":
        footprint = "Synthetic:R_0805"
    elif fault == "wrong-symbol":
        symbol = "Device:C"
    elif fault == "wrong-part-id":
        part_id = "RES-10K-0P125W"
    elif fault == "wrong-pin-inventory":
        pin_numbers = ("1", "2", "3")
    elif fault == "wrong-net":
        second_net = "VLOGIC"
    elif fault == "unconnected":
        second_net = ""
    elif fault == "dnp":
        dnp_components = ("R1",)

    nets = {first_net: ("R1.1",)}
    if second_net:
        nets[second_net] = ("R1.2",)
    return NetlistContract(
        components={"R1": ComponentContract(value="10k", footprint=footprint, part_id=part_id)},
        nets=nets,
        dnp_components=dnp_components,
        component_symbols={"R1": symbol},
        component_pin_numbers={"R1": pin_numbers},
    )


def native_netlist_xml() -> str:
    root = ET.Element("export")
    components = ET.SubElement(root, "components")
    component = ET.SubElement(components, "comp", ref="R1")
    ET.SubElement(component, "value").text = "10k"
    ET.SubElement(component, "footprint").text = "Synthetic:R_0603"
    fields = ET.SubElement(component, "fields")
    ET.SubElement(fields, "field", name="PART_ID").text = "RES-10K-0P5W"
    ET.SubElement(component, "libsource", lib="Device", part="R")
    units = ET.SubElement(component, "units")
    unit = ET.SubElement(units, "unit", name="A")
    pins = ET.SubElement(unit, "pins")
    for number in ("1", "2"):
        ET.SubElement(pins, "pin", num=number)
    libparts = ET.SubElement(root, "libparts")
    libpart = ET.SubElement(libparts, "libpart", lib="Device", part="R")
    pin_table = ET.SubElement(libpart, "pins")
    for number in ("1", "2"):
        ET.SubElement(pin_table, "pin", num=number, name=f"{number}", type="passive")
    nets = ET.SubElement(root, "nets")
    for name, number in (("SENSE", "1"), ("GND", "2")):
        net = ET.SubElement(nets, "net", name=name)
        ET.SubElement(net, "node", ref="R1", pin=number)
    return ET.tostring(root, encoding="unicode")


class ComponentPowerRatingTests(unittest.TestCase):
    def test_exact_part_with_power_below_project_limit_passes(self) -> None:
        checks = {
            item.id.rsplit("/", maxsplit=1)[-1]: item
            for item in component_power_rating_checks(requirement(), netlist())
        }
        self.assertEqual(checks["identity"].status, "PASS")
        self.assertEqual(checks["pin-1"].status, "PASS")
        self.assertEqual(checks["pin-2"].status, "PASS")
        self.assertEqual(checks["utilization"].status, "PASS")
        self.assertAlmostEqual(checks["utilization"].observed or 0.0, 0.4)
        self.assertEqual(checks["utilization"].unit, "fraction")

    def test_inclusive_limit_passes_and_excess_dissipation_fails(self) -> None:
        at_limit = {
            item.id: item
            for item in component_power_rating_checks(
                requirement(maximum_expected_power_w=0.2), netlist()
            )
        }
        self.assertEqual(
            at_limit["component-power-rating/sense-resistor/utilization"].status, "PASS"
        )

        over_limit = {
            item.id: item
            for item in component_power_rating_checks(
                requirement(maximum_expected_power_w=0.21), netlist()
            )
        }
        utilization = over_limit["component-power-rating/sense-resistor/utilization"]
        self.assertEqual(utilization.status, "FAIL")
        self.assertIn("thermal derating curve", utilization.detail)
        self.assertAlmostEqual(utilization.observed or 0.0, 0.84)

    def test_exact_identity_pin_and_population_faults_leave_margin_not_applicable(self) -> None:
        for fault in (
            "wrong-footprint",
            "wrong-symbol",
            "wrong-part-id",
            "wrong-pin-inventory",
            "wrong-net",
            "unconnected",
            "dnp",
        ):
            with self.subTest(fault=fault):
                checks = {
                    item.id.rsplit("/", maxsplit=1)[-1]: item
                    for item in component_power_rating_checks(requirement(), netlist(fault=fault))
                }
                self.assertTrue(any(check.status == "FAIL" for check in checks.values()), checks)
                self.assertEqual(checks["utilization"].status, "NOT_APPLICABLE")

    def test_missing_component_fails_identity_without_comparing_power(self) -> None:
        observed = netlist().model_copy(
            update={
                "components": {},
                "component_symbols": {},
                "component_pin_numbers": {},
                "nets": {},
            }
        )
        checks = {item.id: item for item in component_power_rating_checks(requirement(), observed)}
        self.assertEqual(checks["component-power-rating/sense-resistor/identity"].status, "FAIL")
        self.assertEqual(
            checks["component-power-rating/sense-resistor/utilization"].status,
            "NOT_APPLICABLE",
        )

    def test_requirement_rejects_invalid_margin_and_derating_inputs(self) -> None:
        raw = requirement().model_dump()
        raw["requirements"][0]["pins"] = ["R1.1", "C1.2"]
        with self.assertRaises(ValidationError):
            ComponentPowerRatingAnalysis.model_validate(raw)

        raw = requirement().model_dump()
        raw["requirements"][0]["derated_allowable_power_w"] = 0.6
        with self.assertRaisesRegex(ValidationError, "cannot exceed"):
            ComponentPowerRatingAnalysis.model_validate(raw)

        raw = requirement().model_dump()
        raw["requirements"][0]["maximum_utilization_fraction"] = 1.01
        with self.assertRaises(ValidationError):
            ComponentPowerRatingAnalysis.model_validate(raw)

    def test_reordered_native_maps_keep_check_results_stable(self) -> None:
        source = netlist()
        reordered = source.model_copy(
            update={
                "nets": dict(reversed(tuple(source.nets.items()))),
                "components": dict(reversed(tuple(source.components.items()))),
            }
        )
        self.assertEqual(
            component_power_rating_checks(requirement(), source),
            component_power_rating_checks(requirement(), reordered),
        )

    def test_native_netlist_fields_supply_exact_rating_identity(self) -> None:
        from pathlib import Path
        from tempfile import TemporaryDirectory

        with TemporaryDirectory() as temporary:
            path = Path(temporary) / "netlist.xml"
            path.write_text(native_netlist_xml(), encoding="utf-8")
            observed = read_netlist(path)

        component = observed.components["R1"]
        self.assertEqual(component.part_id, "RES-10K-0P5W")
        self.assertEqual(observed.component_symbols["R1"], "Device:R")
        self.assertEqual(observed.component_pin_numbers["R1"], ("1", "2"))
        checks = {item.id: item for item in component_power_rating_checks(requirement(), observed)}
        self.assertTrue(all(item.status == "PASS" for item in checks.values()), checks)


if __name__ == "__main__":
    unittest.main()
