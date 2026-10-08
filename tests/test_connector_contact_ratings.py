"""Source-bound per-contact current checks use only reviewed project inputs."""

from __future__ import annotations

import unittest
from xml.etree import ElementTree as ET

from pydantic import ValidationError

from kicad_tooling.hwrepo.connector_contact_ratings import connector_contact_rating_checks
from kicad_tooling.hwrepo.models import (
    ComponentContract,
    ConnectorContactCurrentRequirement,
    ConnectorContactRatingAnalysis,
    ConnectorContactRatingRequirement,
    NetlistContract,
)
from kicad_tooling.validate import read_netlist


def contact(
    *,
    id: str = "vbus-contact",
    pin_number: str = "1",
    expected_function: str = "VBUS",
    expected_net: str = "VBUS",
    maximum_expected_current_a: float = 1.0,
) -> ConnectorContactCurrentRequirement:
    return ConnectorContactCurrentRequirement(
        id=id,
        pin_number=pin_number,
        expected_function=expected_function,
        expected_net=expected_net,
        rated_current_a=3.0,
        derated_allowable_current_a=2.0,
        maximum_expected_current_a=maximum_expected_current_a,
        maximum_utilization_fraction=0.8,
        rating_source="Synthetic connector datasheet Rev A, contact table",
        rating_conditions="Synthetic 20 C ambient, two loaded contacts, specified wire gauge",
        derating_basis="Synthetic project derating review for the stated conditions",
        load_basis="Synthetic maximum DC load allocation for this individual contact",
    )


def requirement(
    *, contacts: tuple[ConnectorContactCurrentRequirement, ...] | None = None
) -> ConnectorContactRatingAnalysis:
    return ConnectorContactRatingAnalysis(
        basis="Synthetic per-contact connector current comparison",
        requirements=(
            ConnectorContactRatingRequirement(
                id="host-connector",
                reference="J1",
                expected_symbol="Connector_Generic:Conn_01x02",
                expected_footprint="Synthetic:Header_1x02",
                expected_part_id="HDR-2P-3A",
                native_pin_numbers=("1", "2"),
                contacts=(contact(),) if contacts is None else contacts,
            ),
        ),
    )


def multi_connector_requirement(
    *, reverse_order: bool = False, peer_current_a: float = 1.0
) -> ConnectorContactRatingAnalysis:
    host = requirement(
        contacts=(
            contact(id="host-vbus", maximum_expected_current_a=1.0),
            contact(
                id="host-return",
                pin_number="2",
                expected_function="GND",
                expected_net="GND",
                maximum_expected_current_a=0.0,
            ),
        )
    ).requirements[0]
    peer = host.model_copy(
        update={
            "id": "peer-connector",
            "reference": "J2",
            "contacts": (
                contact(
                    id="peer-vbus",
                    expected_net="PEER_VBUS",
                    maximum_expected_current_a=peer_current_a,
                ),
                contact(
                    id="peer-return",
                    pin_number="2",
                    expected_function="GND",
                    expected_net="PEER_GND",
                    maximum_expected_current_a=0.0,
                ),
            ),
        }
    )
    if reverse_order:
        host = host.model_copy(update={"contacts": tuple(reversed(host.contacts))})
        peer = peer.model_copy(update={"contacts": tuple(reversed(peer.contacts))})
    connectors = (peer, host) if reverse_order else (host, peer)
    return ConnectorContactRatingAnalysis(
        basis="Synthetic multi-connector contact-current order and locality control",
        requirements=connectors,
    )


def netlist(*, fault: str | None = None) -> NetlistContract:
    footprint = "Synthetic:Header_1x02"
    part_id = "HDR-2P-3A"
    symbol = "Connector_Generic:Conn_01x02"
    numbers = ("1", "2")
    functions = {"J1.1": "VBUS", "J1.2": "GND"}
    first_net = "VBUS"
    dnp_components: tuple[str, ...] = ()
    if fault == "wrong-footprint":
        footprint = "Synthetic:Header_1x03"
    elif fault == "wrong-symbol":
        symbol = "Connector_Generic:Conn_01x03"
    elif fault == "wrong-part-id":
        part_id = "HDR-2P-2A"
    elif fault == "wrong-pin-inventory":
        numbers = ("1", "2", "3")
    elif fault == "wrong-function":
        functions["J1.1"] = "SIGNAL"
    elif fault == "wrong-net":
        first_net = "SIGNAL"
    elif fault == "unconnected":
        first_net = ""
    elif fault == "dnp":
        dnp_components = ("J1",)

    nets = {"GND": ("J1.2",)}
    if first_net:
        nets[first_net] = ("J1.1",)
    return NetlistContract(
        components={
            "J1": ComponentContract(value="HOST_HEADER_1x02", footprint=footprint, part_id=part_id)
        },
        nets=nets,
        dnp_components=dnp_components,
        component_symbols={"J1": symbol},
        pin_functions=functions,
        component_pin_numbers={"J1": numbers},
    )


def multi_connector_netlist() -> NetlistContract:
    first = netlist()
    return first.model_copy(
        update={
            "components": {
                **first.components,
                "J2": first.components["J1"].model_copy(),
            },
            "nets": {
                "VBUS": ("J1.1",),
                "GND": ("J1.2",),
                "PEER_VBUS": ("J2.1",),
                "PEER_GND": ("J2.2",),
            },
            "component_symbols": {
                **first.component_symbols,
                "J2": first.component_symbols["J1"],
            },
            "pin_functions": {
                **first.pin_functions,
                "J2.1": "VBUS",
                "J2.2": "GND",
            },
            "component_pin_numbers": {
                **first.component_pin_numbers,
                "J2": first.component_pin_numbers["J1"],
            },
        }
    )


def native_netlist_xml() -> str:
    root = ET.Element("export")
    components = ET.SubElement(root, "components")
    component = ET.SubElement(components, "comp", ref="J1")
    ET.SubElement(component, "value").text = "HOST_HEADER_1x02"
    ET.SubElement(component, "footprint").text = "Synthetic:Header_1x02"
    fields = ET.SubElement(component, "fields")
    ET.SubElement(fields, "field", name="PART_ID").text = "HDR-2P-3A"
    ET.SubElement(component, "libsource", lib="Connector_Generic", part="Conn_01x02")
    units = ET.SubElement(component, "units")
    unit = ET.SubElement(units, "unit", name="A")
    pins = ET.SubElement(unit, "pins")
    for number in ("1", "2"):
        ET.SubElement(pins, "pin", num=number)
    libparts = ET.SubElement(root, "libparts")
    libpart = ET.SubElement(libparts, "libpart", lib="Connector_Generic", part="Conn_01x02")
    pin_table = ET.SubElement(libpart, "pins")
    ET.SubElement(pin_table, "pin", num="1", name="VBUS", type="passive")
    ET.SubElement(pin_table, "pin", num="2", name="GND", type="passive")
    nets = ET.SubElement(root, "nets")
    for name, number in (("VBUS", "1"), ("GND", "2")):
        net = ET.SubElement(nets, "net", name=name)
        ET.SubElement(net, "node", ref="J1", pin=number)
    return ET.tostring(root, encoding="unicode")


class ConnectorContactRatingTests(unittest.TestCase):
    def test_exact_contact_at_inclusive_utilization_limit_passes(self) -> None:
        checks = {
            item.id.rsplit("/", maxsplit=1)[-1]: item
            for item in connector_contact_rating_checks(
                requirement(contacts=(contact(maximum_expected_current_a=1.6),)), netlist()
            )
        }
        self.assertEqual(checks["identity"].status, "PASS")
        self.assertEqual(checks["assignment"].status, "PASS")
        self.assertEqual(checks["utilization"].status, "PASS")
        self.assertAlmostEqual(checks["utilization"].observed or 0.0, 0.8)
        self.assertEqual(checks["utilization"].unit, "fraction")

    def test_over_limit_contact_fails_with_reviewed_current_basis(self) -> None:
        checks = {
            item.id: item
            for item in connector_contact_rating_checks(
                requirement(contacts=(contact(maximum_expected_current_a=1.61),)), netlist()
            )
        }
        utilization = checks[
            "connector-contact-rating/host-connector/contact-vbus-contact/utilization"
        ]
        self.assertEqual(utilization.status, "FAIL")
        self.assertAlmostEqual(utilization.observed or 0.0, 0.805)
        self.assertIn("two loaded contacts", utilization.detail)
        self.assertIn("individual contact", utilization.detail)

    def test_contacts_sharing_a_net_keep_independent_authored_loads(self) -> None:
        shared_requirement = requirement(
            contacts=(
                contact(id="vbus-a", pin_number="1", maximum_expected_current_a=1.0),
                contact(
                    id="vbus-b",
                    pin_number="2",
                    expected_function="VBUS",
                    maximum_expected_current_a=1.0,
                ),
            )
        )
        shared_netlist = netlist().model_copy(
            update={
                "nets": {"VBUS": ("J1.1", "J1.2")},
                "pin_functions": {"J1.1": "VBUS", "J1.2": "VBUS"},
            }
        )
        checks = {
            item.id: item
            for item in connector_contact_rating_checks(shared_requirement, shared_netlist)
        }
        self.assertEqual(
            checks["connector-contact-rating/host-connector/contact-vbus-a/utilization"].status,
            "PASS",
        )
        self.assertEqual(
            checks["connector-contact-rating/host-connector/contact-vbus-b/utilization"].status,
            "PASS",
        )

    def test_identity_assignment_and_population_faults_block_current_comparison(self) -> None:
        for fault in (
            "wrong-footprint",
            "wrong-symbol",
            "wrong-part-id",
            "wrong-pin-inventory",
            "wrong-function",
            "wrong-net",
            "unconnected",
            "dnp",
        ):
            with self.subTest(fault=fault):
                checks = {
                    item.id.rsplit("/", maxsplit=1)[-1]: item
                    for item in connector_contact_rating_checks(requirement(), netlist(fault=fault))
                }
                self.assertTrue(any(item.status == "FAIL" for item in checks.values()), checks)
                self.assertEqual(checks["utilization"].status, "NOT_APPLICABLE")

    def test_absent_connector_fails_identity_without_current_comparison(self) -> None:
        absent = netlist().model_copy(
            update={
                "components": {},
                "component_symbols": {},
                "component_pin_numbers": {},
                "nets": {},
            }
        )
        checks = {item.id: item for item in connector_contact_rating_checks(requirement(), absent)}
        self.assertEqual(checks["connector-contact-rating/host-connector/identity"].status, "FAIL")
        self.assertEqual(
            checks[
                "connector-contact-rating/host-connector/contact-vbus-contact/utilization"
            ].status,
            "NOT_APPLICABLE",
        )

    def test_requirement_rejects_invalid_contact_values_and_pin_maps(self) -> None:
        raw = requirement().model_dump()
        raw["requirements"][0]["contacts"][0]["derated_allowable_current_a"] = 3.1
        with self.assertRaisesRegex(ValidationError, "cannot exceed"):
            ConnectorContactRatingAnalysis.model_validate(raw)

        raw = requirement().model_dump()
        raw["requirements"][0]["contacts"][0]["pin_number"] = "3"
        with self.assertRaisesRegex(ValidationError, "must be in the exact native pin inventory"):
            ConnectorContactRatingAnalysis.model_validate(raw)

        raw = requirement().model_dump()
        raw["requirements"][0]["contacts"][0]["maximum_utilization_fraction"] = 1.01
        with self.assertRaises(ValidationError):
            ConnectorContactRatingAnalysis.model_validate(raw)

    def test_native_netlist_supplies_exact_identity_function_and_pin_evidence(self) -> None:
        from pathlib import Path
        from tempfile import TemporaryDirectory

        with TemporaryDirectory() as temporary:
            path = Path(temporary) / "netlist.xml"
            path.write_text(native_netlist_xml(), encoding="utf-8")
            observed = read_netlist(path)

        self.assertEqual(observed.components["J1"].part_id, "HDR-2P-3A")
        self.assertEqual(observed.component_symbols["J1"], "Connector_Generic:Conn_01x02")
        self.assertEqual(observed.component_pin_numbers["J1"], ("1", "2"))
        self.assertEqual(observed.pin_functions["J1.1"], "VBUS")
        checks = connector_contact_rating_checks(requirement(), observed)
        self.assertTrue(all(item.status == "PASS" for item in checks), checks)

    def test_reordered_native_maps_keep_check_results_stable(self) -> None:
        source = netlist()
        reordered = source.model_copy(
            update={
                "nets": dict(reversed(tuple(source.nets.items()))),
                "components": dict(reversed(tuple(source.components.items()))),
                "pin_functions": dict(reversed(tuple(source.pin_functions.items()))),
            }
        )
        self.assertEqual(
            connector_contact_rating_checks(requirement(), source),
            connector_contact_rating_checks(requirement(), reordered),
        )

    def test_requirement_order_is_semantic_invariant_and_current_mutation_is_local(self) -> None:
        observed = multi_connector_netlist()
        authored = multi_connector_requirement()
        reordered = multi_connector_requirement(reverse_order=True)
        baseline_checks = {
            item.id: (item.status, item.detail, item.observed, item.unit)
            for item in connector_contact_rating_checks(authored, observed)
        }
        reordered_checks = {
            item.id: (item.status, item.detail, item.observed, item.unit)
            for item in connector_contact_rating_checks(reordered, observed)
        }

        self.assertNotEqual(authored.model_dump_json(), reordered.model_dump_json())
        self.assertEqual(baseline_checks, reordered_checks)

        mutated = multi_connector_requirement(peer_current_a=1.61)
        mutated_checks = {
            item.id: (item.status, item.detail, item.observed, item.unit)
            for item in connector_contact_rating_checks(mutated, observed)
        }
        changed_rows = {
            check_id
            for check_id in baseline_checks
            if baseline_checks[check_id] != mutated_checks[check_id]
        }
        expected_changed_row = (
            "connector-contact-rating/peer-connector/contact-peer-vbus/utilization"
        )
        self.assertEqual(changed_rows, {expected_changed_row})
        self.assertEqual(baseline_checks[expected_changed_row][0], "PASS")
        self.assertEqual(mutated_checks[expected_changed_row][0], "FAIL")


if __name__ == "__main__":
    unittest.main()
