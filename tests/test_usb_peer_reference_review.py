"""Synthetic USB connector-to-PHY reference-domain lint regressions."""

from __future__ import annotations

from typing import Literal

import pytest
from pydantic import ValidationError

from kicad_tooling.hwrepo.bus_heuristics import (
    usb_data_function_identity,
    usb_data_function_side,
)
from kicad_tooling.hwrepo.design_lint import evaluate, text_report
from kicad_tooling.hwrepo.models import (
    ComponentContract,
    ContractCoachReport,
    DesignLintIgnore,
    DesignLintPolicy,
    DesignLintRuleOverride,
    NetlistContract,
    UsbDataInterfaceRequirement,
    UsbDataPathLineRequirement,
    UsbDataPathMap,
    UsbDataSeriesResistorRequirement,
    UsbPeerReferenceCoverageReport,
    UsbReferencePinRequirement,
)
from kicad_tooling.hwrepo.usb_peer_reference_review import (
    scan_usb_peer_reference_reviews,
    usb_peer_reference_reviews,
)

RULE_ID = "bus.usb_peer_reference_review"
PATH_RULE_ID = "bus.usb_data_path_mismatch"


def usb_peer_netlist(
    *,
    connector_reference_net: str = "USB_GND",
    phy_reference_net: str = "BOARD_GND",
    phy_positive_function: str = "USB_DP",
    phy_negative_function: str = "USB_DM",
    dnp: tuple[str, ...] = (),
    extra_positive_pin: bool = False,
    incomplete: bool = False,
) -> NetlistContract:
    components = {
        "J1": ComponentContract(value="Synthetic USB-A receptacle", footprint="Synthetic:USB-A"),
        "U1": ComponentContract(value="Synthetic USB PHY", footprint="Synthetic:QFN"),
    }
    symbols = {"J1": "Connector:USB_A", "U1": "Synthetic:UsbPhy"}
    nets: dict[str, tuple[str, ...]] = {
        "USB_DP": ("J1.1", "U1.1"),
        "USB_DM": ("J1.2", "U1.2"),
        "+3V3": ("U1.4",),
    }
    for reference_net, pin in (
        (connector_reference_net, "J1.3"),
        (phy_reference_net, "U1.3"),
    ):
        nets[reference_net] = (*nets.get(reference_net, ()), pin)
    functions = {
        "J1.1": "D+",
        "J1.2": "D-",
        "J1.3": "GND",
        "J1.4": "VBUS",
        "U1.1": phy_positive_function,
        "U1.2": phy_negative_function,
        "U1.3": "AGND",
        "U1.4": "VDD",
    }
    electrical_types = {
        "J1.1": "passive",
        "J1.2": "passive",
        "J1.3": "passive",
        "J1.4": "passive",
        "U1.1": "bidirectional",
        "U1.2": "bidirectional",
        "U1.3": "power_in",
        "U1.4": "power_in",
    }
    if extra_positive_pin:
        components["TP1"] = ComponentContract(
            value="Synthetic test point", footprint="Synthetic:TestPoint"
        )
        symbols["TP1"] = "Connector:TestPoint"
        nets["USB_DP"] = ("J1.1", "U1.1", "TP1.1")
        functions["TP1.1"] = "TestPoint"
        electrical_types["TP1.1"] = "passive"
    if incomplete:
        electrical_types.pop("U1.3")
    return NetlistContract(
        components=components,
        nets=nets,
        dnp_components=dnp,
        component_symbols=symbols,
        pin_functions=functions,
        pin_electrical_types=electrical_types,
        component_pin_numbers={
            "J1": ("1", "2", "3", "4"),
            "U1": ("1", "2", "3", "4"),
            **({"TP1": ("1",)} if extra_positive_pin else {}),
        },
    )


def usb_peer_series_netlist(
    *, connector_reference_net: str = "USB_GND", phy_reference_net: str = "BOARD_GND"
) -> NetlistContract:
    base = usb_peer_netlist(
        connector_reference_net=connector_reference_net,
        phy_reference_net=phy_reference_net,
    )

    nets = {name: pins for name, pins in base.nets.items() if name not in {"USB_DP", "USB_DM"}}
    nets.update(
        {
            "USB_DP": ("J1.1", "R1.1"),
            "USB_DP_PHY": ("R1.2", "U1.1"),
            "USB_DM": ("J1.2", "R2.1"),
            "USB_DM_PHY": ("R2.2", "U1.2"),
        }
    )
    components = dict(base.components)
    components.update(
        {
            "R1": ComponentContract(value="27R", footprint="Synthetic:0603"),
            "R2": ComponentContract(value="27R", footprint="Synthetic:0603"),
        }
    )
    symbols = dict(base.component_symbols)
    symbols.update({"R1": "Device:R", "R2": "Device:R"})
    functions = dict(base.pin_functions)
    functions.update({"R1.1": "~", "R1.2": "~", "R2.1": "~", "R2.2": "~"})
    electrical_types = dict(base.pin_electrical_types)
    electrical_types.update(
        {"R1.1": "passive", "R1.2": "passive", "R2.1": "passive", "R2.2": "passive"}
    )
    pin_numbers = dict(base.component_pin_numbers)
    pin_numbers.update({"R1": ("1", "2"), "R2": ("1", "2")})
    return base.model_copy(
        update={
            "components": components,
            "nets": nets,
            "component_symbols": symbols,
            "pin_functions": functions,
            "pin_electrical_types": electrical_types,
            "component_pin_numbers": pin_numbers,
        }
    )


def usb_multiport_peer_netlist(*, common_references: bool = False) -> NetlistContract:
    shared_reference = "BOARD_GND"
    connector_1_reference = shared_reference if common_references else "USB1_GND"
    connector_2_reference = shared_reference if common_references else "USB2_GND"
    phy_reference = shared_reference if common_references else "PHY_GND"
    nets = {
        "USB1_DP": ("J1.1", "U1.1"),
        "USB1_DM": ("J1.2", "U1.2"),
        "USB2_DP": ("J2.1", "U1.4"),
        "USB2_DM": ("J2.2", "U1.5"),
        "+5V": ("J1.4", "J2.4"),
        "+3V3": ("U1.7",),
    }
    for reference_net, pin in (
        (connector_1_reference, "J1.3"),
        (connector_2_reference, "J2.3"),
        (phy_reference, "U1.3"),
        (phy_reference, "U1.6"),
    ):
        nets[reference_net] = (*nets.get(reference_net, ()), pin)
    return NetlistContract(
        components={
            "J1": ComponentContract(value="Synthetic USB-A port 1", footprint="Synthetic:USB-A"),
            "J2": ComponentContract(value="Synthetic USB-A port 2", footprint="Synthetic:USB-A"),
            "U1": ComponentContract(value="Synthetic dual-port USB hub", footprint="Synthetic:QFN"),
        },
        nets=nets,
        component_symbols={
            "J1": "Connector:USB_A",
            "J2": "Connector:USB_A",
            "U1": "Synthetic:UsbHub",
        },
        pin_functions={
            "J1.1": "D+",
            "J1.2": "D-",
            "J1.3": "GND",
            "J1.4": "VBUS",
            "J2.1": "D+",
            "J2.2": "D-",
            "J2.3": "GND",
            "J2.4": "VBUS",
            "U1.1": "USB1D+",
            "U1.2": "USB1D-",
            "U1.3": "GND",
            "U1.4": "USB2D+",
            "U1.5": "USB2D-",
            "U1.6": "AGND",
            "U1.7": "VDD",
        },
        pin_electrical_types={
            "J1.1": "passive",
            "J1.2": "passive",
            "J1.3": "passive",
            "J1.4": "passive",
            "J2.1": "passive",
            "J2.2": "passive",
            "J2.3": "passive",
            "J2.4": "passive",
            "U1.1": "input",
            "U1.2": "input",
            "U1.3": "power_in",
            "U1.4": "input",
            "U1.5": "input",
            "U1.6": "power_in",
            "U1.7": "power_in",
        },
        component_pin_numbers={
            "J1": ("1", "2", "3", "4"),
            "J2": ("1", "2", "3", "4"),
            "U1": ("1", "2", "3", "4", "5", "6", "7"),
        },
    )


def usb_multiport_data_map(*, second_port_group: str = "2") -> UsbDataPathMap:
    def interface(
        connector: str,
        port_group: str,
        connector_reference_net: str,
    ) -> UsbDataInterfaceRequirement:
        phy_positive_pin = "U1.1" if port_group == "1" else "U1.4"
        phy_negative_pin = "U1.2" if port_group == "1" else "U1.5"
        phy_reference_pins = (
            UsbReferencePinRequirement(pin="U1.3", net="PHY_GND"),
            UsbReferencePinRequirement(pin="U1.6", net="PHY_GND"),
        )
        return UsbDataInterfaceRequirement(
            id=f"usb-port-{port_group}",
            basis=f"Synthetic exact USB hub port {port_group} mapping",
            connector_reference=connector,
            expected_connector_symbol="Connector:USB_A",
            expected_connector_footprint="Synthetic:USB-A",
            phy_reference="U1",
            expected_phy_symbol="Synthetic:UsbHub",
            expected_phy_footprint="Synthetic:QFN",
            data_port_group=port_group,
            positive=UsbDataPathLineRequirement(
                line="D+",
                connector_pin=f"{connector}.1",
                phy_pin=phy_positive_pin,
                connector_net=f"USB{port_group}_DP",
                phy_net=f"USB{port_group}_DP",
                topology="direct",
            ),
            negative=UsbDataPathLineRequirement(
                line="D-",
                connector_pin=f"{connector}.2",
                phy_pin=phy_negative_pin,
                connector_net=f"USB{port_group}_DM",
                phy_net=f"USB{port_group}_DM",
                topology="direct",
            ),
            connector_reference_pins=(
                UsbReferencePinRequirement(pin=f"{connector}.3", net=connector_reference_net),
            ),
            phy_reference_pins=phy_reference_pins,
            reference_policy="separate_nets",
        )

    return UsbDataPathMap(
        basis="Synthetic dual-port USB hub mapping",
        interfaces=(
            interface("J1", "1", "USB1_GND"),
            interface("J2", second_port_group, "USB2_GND"),
        ),
    )


def usb_series_data_map(
    *,
    reference_policy: str | None = "separate_nets",
    connector_reference_net: str = "USB_GND",
    phy_reference_net: str = "BOARD_GND",
    positive_resistor: str = "R1",
    negative_resistor: str = "R2",
) -> UsbDataPathMap:
    reference_pins: dict[str, object] = {}
    if reference_policy is not None:
        reference_pins = {
            "connector_reference_pins": (
                UsbReferencePinRequirement(pin="J1.3", net=connector_reference_net),
            ),
            "phy_reference_pins": (UsbReferencePinRequirement(pin="U1.3", net=phy_reference_net),),
            "reference_policy": reference_policy,
        }

    def line_requirement(
        line: Literal["D+", "D-"],
        connector_net: str,
        phy_net: str,
        resistor: str,
        connector_pin: str,
        phy_pin: str,
    ) -> UsbDataPathLineRequirement:
        return UsbDataPathLineRequirement(
            line=line,
            connector_pin=connector_pin,
            phy_pin=phy_pin,
            connector_net=connector_net,
            phy_net=phy_net,
            topology="series_resistor",
            series_resistor=UsbDataSeriesResistorRequirement(
                reference=resistor,
                expected_symbol="Device:R",
                expected_footprint="Synthetic:0603",
                minimum_ohms=27,
                maximum_ohms=27,
            ),
        )

    return UsbDataPathMap(
        basis="Synthetic USB series-resistor peer reference test",
        interfaces=(
            UsbDataInterfaceRequirement(
                id="usb-series-interface-1",
                basis="Synthetic USB pair with one fitted series resistor on each data line",
                connector_reference="J1",
                expected_connector_symbol="Connector:USB_A",
                expected_connector_footprint="Synthetic:USB-A",
                phy_reference="U1",
                expected_phy_symbol="Synthetic:UsbPhy",
                expected_phy_footprint="Synthetic:QFN",
                positive=line_requirement(
                    "D+", "USB_DP", "USB_DP_PHY", positive_resistor, "J1.1", "U1.1"
                ),
                negative=line_requirement(
                    "D-", "USB_DM", "USB_DM_PHY", negative_resistor, "J1.2", "U1.2"
                ),
                **reference_pins,
            ),
        ),
    )


def usb_data_map(
    *,
    reference_policy: str | None = None,
    expected_connector_reference_net: str = "USB_GND",
    expected_phy_reference_net: str = "BOARD_GND",
    phy_reference_pin: str = "U1.3",
) -> UsbDataPathMap:
    reference_pins: dict[str, object] = {}
    if reference_policy is not None:
        reference_pins = {
            "connector_reference_pins": (
                UsbReferencePinRequirement(pin="J1.3", net=expected_connector_reference_net),
            ),
            "phy_reference_pins": (
                UsbReferencePinRequirement(
                    pin=phy_reference_pin,
                    net=expected_phy_reference_net,
                ),
            ),
            "reference_policy": reference_policy,
        }
    return UsbDataPathMap(
        basis="Synthetic USB peer and explicit endpoint-reference review",
        interfaces=(
            UsbDataInterfaceRequirement(
                id="usb-interface-1",
                basis="Synthetic direct integrated USB PHY path",
                connector_reference="J1",
                expected_connector_symbol="Connector:USB_A",
                expected_connector_footprint="Synthetic:USB-A",
                phy_reference="U1",
                expected_phy_symbol="Synthetic:UsbPhy",
                expected_phy_footprint="Synthetic:QFN",
                positive=UsbDataPathLineRequirement(
                    line="D+",
                    connector_pin="J1.1",
                    phy_pin="U1.1",
                    connector_net="USB_DP",
                    phy_net="USB_DP",
                    topology="direct",
                ),
                negative=UsbDataPathLineRequirement(
                    line="D-",
                    connector_pin="J1.2",
                    phy_pin="U1.2",
                    connector_net="USB_DM",
                    phy_net="USB_DM",
                    topology="direct",
                ),
                **reference_pins,
            ),
        ),
    )


def usb_c_peer_netlist(
    *, connector_reference_net: str = "USB_GND", phy_reference_net: str = "BOARD_GND"
) -> NetlistContract:
    connector_ground_pins = ("J1.A1", "J1.A12", "J1.B1", "J1.B12")
    phy_ground_pins = ("U1.3", "U1.5")
    nets = {
        "USB_DP": ("J1.A6", "J1.B6", "U1.1", "D1.2"),
        "USB_DM": ("J1.A7", "J1.B7", "U1.2", "D2.2"),
        connector_reference_net: (
            *connector_ground_pins,
            "J1.S1",
            "D1.1",
            "D2.1",
        ),
        phy_reference_net: phy_ground_pins,
        "+3V3": ("U1.4",),
    }
    if connector_reference_net.casefold() == phy_reference_net.casefold():
        nets[connector_reference_net] = (
            *connector_ground_pins,
            *phy_ground_pins,
            "J1.S1",
            "D1.1",
            "D2.1",
        )
    return NetlistContract(
        components={
            "J1": ComponentContract(
                value="Synthetic USB-C receptacle", footprint="Synthetic:USB-C"
            ),
            "U1": ComponentContract(value="Synthetic USB PHY", footprint="Synthetic:QFN"),
            "D1": ComponentContract(value="Synthetic TVS branch", footprint="Synthetic:SOD-323"),
            "D2": ComponentContract(value="Synthetic TVS branch", footprint="Synthetic:SOD-323"),
        },
        nets=nets,
        component_symbols={
            "J1": "Connector:USB_C",
            "U1": "Synthetic:UsbPhy",
            "D1": "Synthetic:TVS",
            "D2": "Synthetic:TVS",
        },
        pin_functions={
            "J1.A1": "GND",
            "J1.A12": "GND",
            "J1.B1": "GND",
            "J1.B12": "GND",
            "J1.S1": "SHIELD",
            "J1.A6": "D+",
            "J1.B6": "D+",
            "J1.A7": "D-",
            "J1.B7": "D-",
            "U1.1": "D+",
            "U1.2": "D-",
            "U1.3": "AGND",
            "U1.4": "VDD",
            "U1.5": "GND",
            "D1.1": "A",
            "D1.2": "K",
            "D2.1": "A",
            "D2.2": "K",
        },
        pin_electrical_types={
            **{pin: "passive" for pin in connector_ground_pins},
            "J1.S1": "passive",
            "J1.A6": "passive",
            "J1.B6": "passive",
            "J1.A7": "passive",
            "J1.B7": "passive",
            "U1.1": "bidirectional",
            "U1.2": "bidirectional",
            "U1.3": "power_in",
            "U1.4": "power_in",
            "U1.5": "passive",
            "D1.1": "passive",
            "D1.2": "passive",
            "D2.1": "passive",
            "D2.2": "passive",
        },
        component_pin_numbers={
            "J1": ("A1", "A12", "B1", "B12", "S1", "A6", "B6", "A7", "B7"),
            "U1": ("1", "2", "3", "4", "5"),
            "D1": ("1", "2"),
            "D2": ("1", "2"),
        },
    )


def usb_c_data_map(*, include_duplicate_contacts: bool = True) -> UsbDataPathMap:
    reference_pins = {
        "connector_reference_pins": tuple(
            UsbReferencePinRequirement(pin=pin, net="USB_GND")
            for pin in ("J1.A1", "J1.A12", "J1.B1", "J1.B12")
        ),
        "phy_reference_pins": (
            UsbReferencePinRequirement(pin="U1.3", net="BOARD_GND"),
            UsbReferencePinRequirement(pin="U1.5", net="BOARD_GND"),
        ),
        "reference_policy": "separate_nets",
    }
    return UsbDataPathMap(
        basis="Synthetic USB-C duplicate-contact reference-domain test",
        interfaces=(
            UsbDataInterfaceRequirement(
                id="usb-c-interface-1",
                basis="Synthetic direct USB-C path with two same-net contacts per data side",
                connector_reference="J1",
                expected_connector_symbol="Connector:USB_C",
                expected_connector_footprint="Synthetic:USB-C",
                phy_reference="U1",
                expected_phy_symbol="Synthetic:UsbPhy",
                expected_phy_footprint="Synthetic:QFN",
                positive=UsbDataPathLineRequirement(
                    line="D+",
                    connector_pin="J1.A6",
                    connector_parallel_pins=("J1.B6",) if include_duplicate_contacts else (),
                    phy_pin="U1.1",
                    connector_net="USB_DP",
                    phy_net="USB_DP",
                    topology="direct",
                ),
                negative=UsbDataPathLineRequirement(
                    line="D-",
                    connector_pin="J1.A7",
                    connector_parallel_pins=("J1.B7",) if include_duplicate_contacts else (),
                    phy_pin="U1.2",
                    connector_net="USB_DM",
                    phy_net="USB_DM",
                    topology="direct",
                ),
                **reference_pins,
            ),
        ),
    )


def lint_report(
    observed: NetlistContract,
    *,
    path_map: UsbDataPathMap | None = None,
    override: DesignLintRuleOverride | None = None,
    ignore: DesignLintIgnore | None = None,
):
    coach = ContractCoachReport(
        status="READY_FOR_REVIEW",
        project_id="synthetic-usb-peer-reference",
        observed=observed,
        netlist_sha256="b" * 64,
    )
    return evaluate(
        "synthetic-usb-peer-reference",
        coach,
        DesignLintPolicy(
            usb_data_path_map=path_map,
            rules=() if override is None else (override,),
            ignores=() if ignore is None else (ignore,),
        ),
    )


def test_coverage_binds_common_split_and_mapped_peer_paths() -> None:
    split = lint_report(usb_peer_netlist())
    split_coverage = split.usb_peer_reference_coverage
    assert (split_coverage) is not None
    assert split_coverage is not None
    assert (split_coverage.status) == ("EVALUATED")
    assert (split_coverage.netlist_sha256) == (split.netlist_sha256)
    assert (split_coverage.recognized_connector_group_count) == (1)
    assert (split_coverage.supported_connector_group_count) == (1)
    assert (split_coverage.recognized_phy_group_count) == (1)
    assert (split_coverage.supported_phy_group_count) == (1)
    assert (split_coverage.supported_data_path_count) == (1)
    assert (split_coverage.separate_reference_path_count) == (1)
    assert (split_coverage.candidate_group_count) == (1)
    split_path = split_coverage.path_entries[0]
    assert (split_path.connector_reference, split_path.phy_reference) == ("J1", "U1")
    assert (split_path.reference_disposition) == ("SEPARATE_REFERENCE_REVIEW")
    assert (split_path.connector_reference_net, split_path.phy_reference_net) == (
        "USB_GND",
        "BOARD_GND",
    )
    assert tuple(item.pin for item in split_path.connector_reference_pins) == ("J1.3",)
    assert tuple(item.pin for item in split_path.phy_reference_pins) == ("U1.3",)
    assert (split_path.data_path.positive.connector_pins) == ("J1.1",)
    assert (split_path.data_path.positive.phy_pins) == ("U1.1",)
    assert (split_path.data_path.positive.connector_net) == "USB_DP"
    assert (split_path.data_path.negative.connector_net) == "USB_DM"
    assert ("USB peer-reference heuristic coverage:") in (text_report(split))
    assert ("At least one supported connector-to-PHY path was checked.") in (text_report(split))
    assert ("J1 -> U1 (unnumbered port): SEPARATE_REFERENCE_REVIEW") in (text_report(split))

    common = lint_report(
        usb_peer_netlist(connector_reference_net="BOARD_GND", phy_reference_net="BOARD_GND")
    )
    common_coverage = common.usb_peer_reference_coverage
    assert (common_coverage) is not None
    assert common_coverage is not None
    assert (common_coverage.common_reference_path_count) == (1)
    assert (common_coverage.separate_reference_path_count) == (0)
    assert (common_coverage.candidate_group_count) == (0)
    assert (common_coverage.path_entries[0].reference_disposition) == ("COMMON_REFERENCE")
    assert (
        common_coverage.path_entries[0].connector_reference_net
        == common_coverage.path_entries[0].phy_reference_net
    )

    mapped = lint_report(
        usb_peer_netlist(), path_map=usb_data_map(reference_policy="separate_nets")
    )
    mapped_coverage = mapped.usb_peer_reference_coverage
    assert (mapped_coverage) is not None
    assert mapped_coverage is not None
    assert (mapped_coverage.usb_data_path_map_sha256) is not None
    assert (mapped_coverage.mapped_separate_reference_path_count) == (1)
    assert (mapped_coverage.candidate_group_count) == (0)
    assert mapped_coverage.path_entries[0].reference_disposition == "MAP_COVERED_SEPARATE_REFERENCE"


def test_coverage_marks_missing_usb_endpoints_and_incomplete_groups() -> None:
    empty = NetlistContract(components={}, nets={})
    empty_scan = scan_usb_peer_reference_reviews(empty)
    assert (empty_scan.coverage.recognized_connector_group_count) == (0)
    assert (empty_scan.coverage.recognized_phy_group_count) == (0)
    empty_coverage = lint_report(empty).usb_peer_reference_coverage
    assert (empty_coverage) is not None
    assert empty_coverage is not None
    assert (empty_coverage.status) == ("NO_USB_ENDPOINTS")
    assert (empty_coverage.path_entries) == ()
    assert ("No supported USB data-pin function groups were recognized") in (
        text_report(lint_report(empty))
    )

    incomplete = usb_peer_netlist(incomplete=True)
    incomplete_coverage = lint_report(incomplete).usb_peer_reference_coverage
    assert (incomplete_coverage) is not None
    assert incomplete_coverage is not None
    assert (incomplete_coverage.status) == ("INCOMPLETE")
    assert (incomplete_coverage.incomplete_group_count) == (1)
    assert (incomplete_coverage.path_entries) == ()
    assert (
        tuple(
            (item.endpoint_role, item.reference, item.port_group, item.disposition)
            for item in incomplete_coverage.endpoint_groups or ()
        )
    ) == (
        (
            ("connector", "J1", None, "SUPPORTED"),
            ("phy", "U1", None, "INCOMPLETE"),
        )
    )
    incomplete_text = text_report(lint_report(incomplete))
    assert ("lacked complete evidence") in (incomplete_text)
    assert ("PHY U1 (unnumbered port): INCOMPLETE") in (incomplete_text)

    legacy_payload = incomplete_coverage.model_dump()
    legacy_payload.pop("endpoint_groups")
    legacy_payload.pop("path_entries")
    legacy = UsbPeerReferenceCoverageReport.model_validate(legacy_payload)
    assert (legacy.endpoint_groups) is None
    assert (legacy.path_entries) is None
    inconsistent_payload = incomplete_coverage.model_dump()
    inconsistent_payload["incomplete_group_count"] = 0
    with pytest.raises(ValidationError, match="incomplete group count"):
        UsbPeerReferenceCoverageReport.model_validate(inconsistent_payload)
    inconsistent_paths = incomplete_coverage.model_dump(mode="python")
    inconsistent_paths["supported_data_path_count"] = 1
    with pytest.raises(ValidationError, match="path coverage entries"):
        UsbPeerReferenceCoverageReport.model_validate(inconsistent_paths)


def test_coverage_distinguishes_unsupported_paths_and_dnp_endpoints() -> None:
    observed = usb_peer_netlist()
    uncoupled = observed.model_copy(
        update={
            "nets": {
                **observed.nets,
                "USB_DP": ("J1.1",),
                "USB_DP_PHY": ("U1.1",),
            }
        }
    )
    uncoupled_coverage = lint_report(uncoupled).usb_peer_reference_coverage
    assert (uncoupled_coverage) is not None
    assert uncoupled_coverage is not None
    assert (uncoupled_coverage.status) == ("NO_SUPPORTED_PEER_PATHS")
    assert (uncoupled_coverage.supported_connector_group_count) == (1)
    assert (uncoupled_coverage.supported_phy_group_count) == (1)
    assert (uncoupled_coverage.incomplete_group_count) == (0)
    assert (uncoupled_coverage.supported_data_path_count) == (0)
    assert (uncoupled_coverage.path_entries) == ()
    assert ("No direct or single-resistor USB D+/D− connector-to-PHY path matched") in (
        text_report(lint_report(uncoupled))
    )

    dnp_coverage = lint_report(usb_peer_netlist(dnp=("U1",))).usb_peer_reference_coverage
    assert (dnp_coverage) is not None
    assert dnp_coverage is not None
    assert (dnp_coverage.status) == ("NO_SUPPORTED_PEER_PATHS")
    assert (dnp_coverage.dnp_group_count) == (1)
    assert (dnp_coverage.incomplete_group_count) == (0)
    assert (dnp_coverage.supported_phy_group_count) == (0)
    assert (dnp_coverage.path_entries) == ()
    assert (
        tuple(
            (item.endpoint_role, item.reference, item.port_group, item.disposition)
            for item in dnp_coverage.endpoint_groups or ()
        )
    ) == (
        (
            ("connector", "J1", None, "SUPPORTED"),
            ("phy", "U1", None, "DNP"),
        )
    )


def test_single_port_numbered_usb_data_functions_are_recognized() -> None:
    assert (usb_data_function_side("DP1")) == ("positive")
    assert (usb_data_function_side("DM1")) == ("negative")
    assert (usb_data_function_side("DP2")) == ("positive")
    assert (usb_data_function_side("DM2")) == ("negative")
    assert (usb_data_function_identity("USB_DP3")) == (("3", "positive"))
    assert (usb_data_function_identity("DP2")) == (("2", "positive"))
    assert (usb_data_function_identity("USB1D+")) == (("1", "positive"))
    assert (usb_data_function_identity("USB2D-")) == (("2", "negative"))
    assert (usb_data_function_identity("USB0D+")) == (None)
    assert (usb_data_function_identity("1D+")) == (None)
    assert (usb_data_function_identity("D-")) == ((None, "negative"))


@pytest.mark.parametrize(
    ("function", "expected_identity"),
    (("UD+", (None, "positive")), ("UD-", (None, "negative"))),
)
def test_ud_pin_function_aliases_are_recognized_as_usb_data(
    function: str, expected_identity: tuple[str | None, str]
) -> None:
    assert usb_data_function_identity(function) == expected_identity


def test_ud_phy_aliases_retain_split_fault_and_common_reference_control() -> None:
    split = lint_report(usb_peer_netlist(phy_positive_function="UD+", phy_negative_function="UD-"))
    split_coverage = split.usb_peer_reference_coverage
    assert split_coverage is not None
    assert split_coverage.recognized_phy_group_count == 1
    assert split_coverage.supported_phy_group_count == 1
    assert split_coverage.supported_data_path_count == 1
    assert split_coverage.separate_reference_path_count == 1
    assert split_coverage.path_entries[0].reference_disposition == "SEPARATE_REFERENCE_REVIEW"
    assert sum(item.rule_id == RULE_ID for item in split.findings) == 1

    common = lint_report(
        usb_peer_netlist(
            connector_reference_net="BOARD_GND",
            phy_reference_net="BOARD_GND",
            phy_positive_function="UD+",
            phy_negative_function="UD-",
        )
    )
    common_coverage = common.usb_peer_reference_coverage
    assert common_coverage is not None
    assert common_coverage.common_reference_path_count == 1
    assert common_coverage.separate_reference_path_count == 0
    assert RULE_ID not in {item.rule_id for item in common.findings}


def test_numbered_multiport_hub_groups_each_connector_with_its_usb_port() -> None:
    observed = usb_multiport_peer_netlist()
    reviews = usb_peer_reference_reviews(observed)
    assert (
        tuple(
            (
                item.connector_reference,
                item.phy_reference,
                item.data_link.port_group,
                item.data_link.phy_positive_pins,
                item.data_link.phy_negative_pins,
            )
            for item in reviews
        )
    ) == (
        (
            ("J1", "U1", "1", ("U1.1",), ("U1.2",)),
            ("J2", "U1", "2", ("U1.4",), ("U1.5",)),
        )
    )
    report = lint_report(observed)
    findings = tuple(item for item in report.findings if item.rule_id == RULE_ID)
    coverage = report.usb_peer_reference_coverage
    assert (coverage) is not None
    assert coverage is not None
    assert (
        tuple(
            (item.endpoint_role, item.reference, item.port_group, item.disposition)
            for item in coverage.endpoint_groups or ()
        )
    ) == (
        (
            ("connector", "J1", None, "SUPPORTED"),
            ("connector", "J2", None, "SUPPORTED"),
            ("phy", "U1", "1", "SUPPORTED"),
            ("phy", "U1", "2", "SUPPORTED"),
        )
    )
    assert (report.status) == ("REVIEW")
    assert tuple(
        (
            item.connector_reference,
            item.phy_reference,
            item.data_path.port_group,
            item.reference_disposition,
            item.connector_reference_net,
            item.phy_reference_net,
        )
        for item in coverage.path_entries
    ) == (
        (
            ("J1", "U1", "1", "SEPARATE_REFERENCE_REVIEW", "USB1_GND", "PHY_GND"),
            ("J2", "U1", "2", "SEPARATE_REFERENCE_REVIEW", "USB2_GND", "PHY_GND"),
        )
    )
    assert tuple(
        tuple(item.pin for item in path.phy_reference_pins) for path in coverage.path_entries
    ) == (("U1.3", "U1.6"), ("U1.3", "U1.6"))
    assert (tuple((item.subject, item.evidence["USB_port_group"]) for item in findings)) == (
        (
            ("J1 / U1: USB reference-domain review (port 1)", ("1",)),
            ("J2 / U1: USB reference-domain review (port 2)", ("2",)),
        )
    )
    reordered = observed.model_copy(
        update={
            "components": dict(reversed(tuple(observed.components.items()))),
            "nets": dict(reversed(tuple(observed.nets.items()))),
            "component_symbols": dict(reversed(tuple(observed.component_symbols.items()))),
            "pin_functions": dict(reversed(tuple(observed.pin_functions.items()))),
            "pin_electrical_types": dict(reversed(tuple(observed.pin_electrical_types.items()))),
            "component_pin_numbers": dict(reversed(tuple(observed.component_pin_numbers.items()))),
        }
    )
    assert (lint_report(observed)) == (lint_report(reordered))

    common = usb_multiport_peer_netlist(common_references=True)
    assert (usb_peer_reference_reviews(common)) == (())
    common_report = lint_report(common)
    assert (RULE_ID) not in ({item.rule_id for item in common_report.findings})
    assert tuple(
        item.reference_disposition
        for item in common_report.usb_peer_reference_coverage.path_entries
    ) == (
        "COMMON_REFERENCE",
        "COMMON_REFERENCE",
    )

    exact_map = usb_multiport_data_map()
    mapped = lint_report(observed, path_map=exact_map)
    assert (RULE_ID) not in ({item.rule_id for item in mapped.findings})
    assert (PATH_RULE_ID) not in ({item.rule_id for item in mapped.findings})
    assert tuple(
        item.reference_disposition for item in mapped.usb_peer_reference_coverage.path_entries
    ) == (
        "MAP_COVERED_SEPARATE_REFERENCE",
        "MAP_COVERED_SEPARATE_REFERENCE",
    )

    stale_map = lint_report(
        observed,
        path_map=usb_multiport_data_map(second_port_group="3"),
    )
    stale_peer_findings = tuple(item for item in stale_map.findings if item.rule_id == RULE_ID)
    assert (tuple(item.subject for item in stale_peer_findings)) == (
        ("J2 / U1: USB reference-domain review (port 2)",)
    )
    assert tuple(
        item.reference_disposition for item in stale_map.usb_peer_reference_coverage.path_entries
    ) == (
        "MAP_COVERED_SEPARATE_REFERENCE",
        "SEPARATE_REFERENCE_REVIEW",
    )
    assert (PATH_RULE_ID) in ({item.rule_id for item in stale_map.findings})


def test_numbered_multiport_pairing_rejects_crossed_and_incomplete_channels() -> None:
    observed = usb_multiport_peer_netlist()
    crossed = observed.model_copy(
        update={
            "nets": {
                **observed.nets,
                "USB1_DM": ("J1.2", "U1.5"),
                "USB2_DM": ("J2.2", "U1.2"),
            }
        }
    )
    assert (usb_peer_reference_reviews(crossed)) == (())

    one_channel_open = observed.model_copy(
        update={
            "nets": {
                name: tuple(pin for pin in pins if pin != "U1.5")
                for name, pins in observed.nets.items()
            }
        }
    )
    reviews = usb_peer_reference_reviews(one_channel_open)
    assert (tuple((item.connector_reference, item.data_link.port_group) for item in reviews)) == (
        (("J1", "1"),)
    )


def test_split_reference_direct_usb_pair_emits_exact_review_evidence() -> None:
    observed = usb_peer_netlist()
    reviews = usb_peer_reference_reviews(observed)
    assert (len(reviews)) == (1)
    review = reviews[0]
    assert ((review.connector_reference, review.phy_reference)) == (("J1", "U1"))
    assert (review.connector_reference_net) == ("USB_GND")
    assert (review.phy_reference_net) == ("BOARD_GND")
    assert (tuple(item.pin for item in review.connector_reference_pins)) == (("J1.3",))
    assert (tuple(item.pin for item in review.phy_reference_pins)) == (("U1.3",))
    report = lint_report(observed)
    finding = next(item for item in report.findings if item.rule_id == RULE_ID)
    assert (report.status) == ("REVIEW")
    assert (finding.subject) == ("J1 / U1: USB reference-domain review")
    assert (finding.evidence["USB_D+_link"]) == (("J1.1 / U1.1=USB_DP",))
    assert (finding.evidence["USB_D-_link"]) == (("J1.2 / U1.2=USB_DM",))


def test_common_reference_is_a_quiet_control() -> None:
    observed = usb_peer_netlist(connector_reference_net="BOARD_GND", phy_reference_net="BOARD_GND")
    assert (usb_peer_reference_reviews(observed)) == (())
    assert (RULE_ID) not in ({item.rule_id for item in lint_report(observed).findings})


def test_fitted_series_resistors_preserve_usb_peer_reference_review() -> None:
    observed = usb_peer_series_netlist()
    reviews = usb_peer_reference_reviews(observed)
    assert (len(reviews)) == (1)
    link = reviews[0].data_link
    assert (link.connector_positive_net) == ("USB_DP")
    assert (link.phy_positive_net) == ("USB_DP_PHY")
    assert (link.connector_negative_net) == ("USB_DM")
    assert (link.phy_negative_net) == ("USB_DM_PHY")
    assert (link.positive_series_resistor.reference) == ("R1")
    assert (link.positive_series_resistor.connector_pin) == ("R1.1")
    assert (link.positive_series_resistor.phy_pin) == ("R1.2")
    assert (link.negative_series_resistor.reference) == ("R2")

    path = lint_report(observed).usb_peer_reference_coverage.path_entries[0]
    assert (path.data_path.positive.series_resistor.reference) == ("R1")
    assert (path.data_path.positive.series_resistor.connector_net) == "USB_DP"
    assert (path.data_path.positive.series_resistor.phy_net) == "USB_DP_PHY"
    assert (path.data_path.negative.series_resistor.reference) == "R2"

    report = lint_report(observed)
    finding = next(item for item in report.findings if item.rule_id == RULE_ID)
    assert (finding.evidence["USB_D+_link"]) == (("J1.1 / U1.1=USB_DP to USB_DP_PHY through R1",))
    assert (finding.evidence["USB_D+_series_resistor"]) == (
        ("R1 (Device:R, 27R; R1.1=USB_DP, R1.2=USB_DP_PHY)",)
    )

    mapped = lint_report(observed, path_map=usb_series_data_map())
    assert (RULE_ID) not in ({item.rule_id for item in mapped.findings})
    assert (PATH_RULE_ID) not in ({item.rule_id for item in mapped.findings})

    stale_map = lint_report(
        observed,
        path_map=usb_series_data_map(positive_resistor="R9"),
    )
    assert (RULE_ID) in ({item.rule_id for item in stale_map.findings})
    assert (PATH_RULE_ID) in ({item.rule_id for item in stale_map.findings})

    common = usb_peer_series_netlist(
        connector_reference_net="BOARD_GND", phy_reference_net="BOARD_GND"
    )
    assert (usb_peer_reference_reviews(common)) == (())
    assert (RULE_ID) not in ({item.rule_id for item in lint_report(common).findings})


def test_series_resistor_recognition_rejects_dnp_incomplete_and_extra_peers() -> None:
    observed = usb_peer_series_netlist()
    dnp = observed.model_copy(update={"dnp_components": ("R1",)})
    assert (usb_peer_reference_reviews(dnp)) == (())

    incomplete = observed.model_copy(
        update={
            "component_pin_numbers": {
                **observed.component_pin_numbers,
                "R1": ("1", "2", "3"),
            }
        }
    )
    assert (usb_peer_reference_reviews(incomplete)) == (())

    extra_peer = observed.model_copy(
        update={
            "components": {
                **observed.components,
                "TP1": ComponentContract(
                    value="Synthetic test point", footprint="Synthetic:TestPoint"
                ),
            },
            "component_symbols": {**observed.component_symbols, "TP1": "Connector:TestPoint"},
            "component_pin_numbers": {
                **observed.component_pin_numbers,
                "TP1": ("1",),
            },
            "pin_functions": {**observed.pin_functions, "TP1.1": "TestPoint"},
            "pin_electrical_types": {
                **observed.pin_electrical_types,
                "TP1.1": "passive",
            },
            "nets": {
                **observed.nets,
                "USB_DP": (*observed.nets["USB_DP"], "TP1.1"),
            },
        }
    )
    assert (usb_peer_reference_reviews(extra_peer)) == (())


def test_usb_c_duplicate_contacts_and_two_pin_diode_shunts_emit_exact_review() -> None:
    observed = usb_c_peer_netlist()
    reviews = usb_peer_reference_reviews(observed)
    assert (len(reviews)) == (1)
    link = reviews[0].data_link
    assert (link.connector_positive_pins) == (("J1.A6", "J1.B6"))
    assert (link.connector_negative_pins) == (("J1.A7", "J1.B7"))
    assert (link.phy_positive_pins) == (("U1.1",))
    assert (link.phy_negative_pins) == (("U1.2",))
    assert (
        (
            link.positive_shunt_branches[0].data_pin,
            link.positive_shunt_branches[0].reference_pin,
        )
    ) == (("D1.2", "D1.1"))
    report = lint_report(observed)
    finding = next(item for item in report.findings if item.rule_id == RULE_ID)
    assert (finding.evidence["USB_D+_link"]) == (("J1.A6, J1.B6 / U1.1=USB_DP",))
    assert (finding.evidence["USB_D+_shunt_branches"]) == (
        ("D1.2 (Synthetic:TVS) to D1.1=USB_GND",)
    )


def test_usb_c_common_reference_with_duplicate_contacts_and_diodes_is_control() -> None:
    observed = usb_c_peer_netlist(
        connector_reference_net="BOARD_GND", phy_reference_net="BOARD_GND"
    )
    assert (usb_peer_reference_reviews(observed)) == (())
    assert (RULE_ID) not in ({item.rule_id for item in lint_report(observed).findings})


def test_usb_c_does_not_accept_extra_peers_incomplete_or_non_diode_branches() -> None:
    base = usb_c_peer_netlist()
    extra_peer = base.model_copy(
        update={
            "components": {
                **base.components,
                "TP1": ComponentContract(
                    value="Synthetic test point", footprint="Synthetic:TestPoint"
                ),
            },
            "component_symbols": {**base.component_symbols, "TP1": "Connector:TestPoint"},
            "component_pin_numbers": {**base.component_pin_numbers, "TP1": ("1",)},
            "pin_functions": {**base.pin_functions, "TP1.1": "TestPoint"},
            "pin_electrical_types": {**base.pin_electrical_types, "TP1.1": "passive"},
            "nets": {
                **base.nets,
                "USB_DP": (*base.nets["USB_DP"], "TP1.1"),
            },
        }
    )
    assert (usb_peer_reference_reviews(extra_peer)) == (())

    resistor_branch = base.model_copy(
        update={
            "components": {
                **base.components,
                "R1": ComponentContract(value="Synthetic resistor", footprint="Synthetic:0603"),
            },
            "component_symbols": {**base.component_symbols, "R1": "Device:R"},
            "component_pin_numbers": {**base.component_pin_numbers, "R1": ("1", "2")},
            "pin_functions": {**base.pin_functions, "R1.1": "~", "R1.2": "~"},
            "pin_electrical_types": {
                **base.pin_electrical_types,
                "R1.1": "passive",
                "R1.2": "passive",
            },
            "nets": {
                **base.nets,
                "USB_DP": (*base.nets["USB_DP"], "R1.2"),
                "USB_GND": (*base.nets["USB_GND"], "R1.1"),
            },
        }
    )
    assert (usb_peer_reference_reviews(resistor_branch)) == (())

    incomplete_diode = base.model_copy(
        update={
            "component_pin_numbers": {
                **base.component_pin_numbers,
                "D1": ("1", "2", "3"),
            }
        }
    )
    assert (usb_peer_reference_reviews(incomplete_diode)) == (())

    split_contacts = base.model_copy(
        update={
            "nets": {
                **base.nets,
                "USB_DP": ("J1.A6", "U1.1", "D1.2"),
                "USB_DP_B": ("J1.B6",),
            }
        }
    )
    assert (usb_peer_reference_reviews(split_contacts)) == (())


def test_usb_c_map_must_name_every_duplicate_contact_before_suppressing_review() -> None:
    observed = usb_c_peer_netlist()
    exact = usb_c_data_map()
    exact_report = lint_report(observed, path_map=exact)
    assert (RULE_ID) not in ({item.rule_id for item in exact_report.findings})
    assert (PATH_RULE_ID) not in ({item.rule_id for item in exact_report.findings})

    incomplete_report = lint_report(
        observed,
        path_map=usb_c_data_map(include_duplicate_contacts=False),
    )
    assert (RULE_ID) in ({item.rule_id for item in incomplete_report.findings})
    path_findings = tuple(
        item for item in incomplete_report.findings if item.rule_id == PATH_RULE_ID
    )
    assert ({item.evidence["line"][0] for item in path_findings}) == ({"D+", "D-"})
    assert all(
        "mapped D+ pin inventory" in " ".join(item.evidence["issues"])
        or "mapped D- pin inventory" in " ".join(item.evidence["issues"])
        for item in path_findings
    )


def test_input_order_is_stable_and_commoning_clears_only_this_review() -> None:
    observed = usb_peer_netlist()
    reordered = observed.model_copy(
        update={
            "components": dict(reversed(tuple(observed.components.items()))),
            "nets": dict(reversed(tuple(observed.nets.items()))),
            "component_symbols": dict(reversed(tuple(observed.component_symbols.items()))),
            "pin_functions": dict(reversed(tuple(observed.pin_functions.items()))),
            "pin_electrical_types": dict(reversed(tuple(observed.pin_electrical_types.items()))),
            "component_pin_numbers": dict(reversed(tuple(observed.component_pin_numbers.items()))),
        }
    )
    assert (lint_report(observed)) == (lint_report(reordered))
    commoned = observed.model_copy(
        update={
            "nets": {
                **{
                    name: pins
                    for name, pins in observed.nets.items()
                    if name not in {"USB_GND", "BOARD_GND"}
                },
                "BOARD_GND": ("J1.3", "U1.3"),
            }
        }
    )
    commoned_report = lint_report(commoned)
    assert (RULE_ID) not in ({item.rule_id for item in commoned_report.findings})


def test_exact_common_and_separate_usb_maps_resolve_the_review() -> None:
    cases = (
        (
            usb_peer_netlist(connector_reference_net="BOARD_GND", phy_reference_net="BOARD_GND"),
            usb_data_map(
                reference_policy="common_net",
                expected_connector_reference_net="BOARD_GND",
                expected_phy_reference_net="BOARD_GND",
            ),
        ),
        (
            usb_peer_netlist(),
            usb_data_map(reference_policy="separate_nets"),
        ),
    )
    for observed, path_map in cases:
        report = lint_report(observed, path_map=path_map)
        rule_ids = {item.rule_id for item in report.findings}
        context = path_map.interfaces[0].reference_policy
        assert RULE_ID not in rule_ids, context
        assert PATH_RULE_ID not in rule_ids, context


def test_source_matched_map_reports_stale_reference_assignment() -> None:
    report = lint_report(
        usb_peer_netlist(),
        path_map=usb_data_map(reference_policy="common_net", expected_phy_reference_net="USB_GND"),
    )
    assert (RULE_ID) not in ({item.rule_id for item in report.findings}), (
        "the explicit current map owns this decision and should avoid a duplicate prompt"
    )
    mismatch = next(item for item in report.findings if item.rule_id == PATH_RULE_ID)
    assert (mismatch.subject) == ("usb-interface-1: USB reference path")
    assert ("U1 reference assignments differ") in (" ".join(mismatch.evidence["issues"]))


def test_stale_map_identity_does_not_suppress_peer_review() -> None:
    path_map = usb_data_map(reference_policy="separate_nets", phy_reference_pin="U1.8")
    report = lint_report(usb_peer_netlist(), path_map=path_map)
    assert (RULE_ID) in ({item.rule_id for item in report.findings})
    assert (PATH_RULE_ID) in ({item.rule_id for item in report.findings})


def test_extra_data_peers_and_ambiguous_metadata_fail_closed() -> None:
    assert (usb_peer_reference_reviews(usb_peer_netlist(dnp=("U1",)))) == (())
    assert (usb_peer_reference_reviews(usb_peer_netlist(incomplete=True))) == (())
    assert (usb_peer_reference_reviews(usb_peer_netlist(extra_positive_pin=True))) == (())
    explicit_suffix = usb_peer_netlist()
    explicit_suffix_functions = dict(explicit_suffix.pin_functions)
    explicit_suffix_functions["J1.3"] = "GND_A"
    explicit_suffix_functions["U1.3"] = "VSSA1"
    explicit_suffix = explicit_suffix.model_copy(
        update={"pin_functions": explicit_suffix_functions}
    )
    assert (len(usb_peer_reference_reviews(explicit_suffix))) == (1)
    shield_only = usb_peer_netlist()
    shield_functions = dict(shield_only.pin_functions)
    shield_functions["J1.3"] = "GND_SHIELD"
    shield_only = shield_only.model_copy(update={"pin_functions": shield_functions})
    assert (usb_peer_reference_reviews(shield_only)) == (())


def test_phy_with_multiple_reference_domains_is_outside_predicate() -> None:
    observed = usb_peer_netlist()
    nets = dict(observed.nets)
    nets["ISOLATED_GND"] = ("U1.5",)
    functions = dict(observed.pin_functions)
    functions["U1.5"] = "GND"
    electrical_types = dict(observed.pin_electrical_types)
    electrical_types["U1.5"] = "power_in"
    pin_numbers = dict(observed.component_pin_numbers)
    pin_numbers["U1"] = (*pin_numbers["U1"], "5")
    isolated_reference = observed.model_copy(
        update={
            "nets": nets,
            "pin_functions": functions,
            "pin_electrical_types": electrical_types,
            "component_pin_numbers": pin_numbers,
        }
    )

    assert (usb_peer_reference_reviews(isolated_reference)) == (())
    report = lint_report(isolated_reference)
    assert (RULE_ID) not in ({item.rule_id for item in report.findings})


def test_isolator_mediated_usb_path_is_not_traced_across_domains() -> None:
    observed = NetlistContract(
        components={
            "J1": ComponentContract(value="Synthetic USB connector", footprint="Synthetic:J"),
            "U1": ComponentContract(value="Synthetic USB isolator", footprint="Synthetic:SOIC"),
            "U2": ComponentContract(value="Synthetic USB PHY", footprint="Synthetic:QFN"),
        },
        nets={
            "HOST_DP": ("J1.1", "U1.1"),
            "HOST_DM": ("J1.2", "U1.2"),
            "HOST_GND": ("J1.3", "U1.5"),
            "DEVICE_DP": ("U1.3", "U2.1"),
            "DEVICE_DM": ("U1.4", "U2.2"),
            "DEVICE_GND": ("U1.6", "U2.3"),
            "+3V3": ("U2.4",),
        },
        component_symbols={
            "J1": "Connector:USB_A",
            "U1": "Synthetic:UsbIsolator",
            "U2": "Synthetic:UsbPhy",
        },
        pin_functions={
            "J1.1": "D+",
            "J1.2": "D-",
            "J1.3": "GND",
            "J1.4": "VBUS",
            "U1.1": "DP1",
            "U1.2": "DM1",
            "U1.3": "DP2",
            "U1.4": "DM2",
            "U1.5": "GND1",
            "U1.6": "GND2",
            "U2.1": "D+",
            "U2.2": "D-",
            "U2.3": "GND",
            "U2.4": "VDD",
        },
        pin_electrical_types={
            "J1.1": "passive",
            "J1.2": "passive",
            "J1.3": "passive",
            "J1.4": "passive",
            "U1.1": "bidirectional",
            "U1.2": "bidirectional",
            "U1.3": "bidirectional",
            "U1.4": "bidirectional",
            "U1.5": "power_in",
            "U1.6": "power_in",
            "U2.1": "bidirectional",
            "U2.2": "bidirectional",
            "U2.3": "power_in",
            "U2.4": "power_in",
        },
        component_pin_numbers={
            "J1": ("1", "2", "3", "4"),
            "U1": ("1", "2", "3", "4", "5", "6"),
            "U2": ("1", "2", "3", "4"),
        },
    )

    assert (usb_peer_reference_reviews(observed)) == (())
    report = lint_report(observed)
    assert (RULE_ID) not in ({item.rule_id for item in report.findings})
    coverage = report.usb_peer_reference_coverage
    assert (coverage) is not None
    assert coverage is not None
    assert (coverage.status) == ("INCOMPLETE")
    assert (coverage.recognized_connector_group_count) == (1)
    assert (coverage.recognized_phy_group_count) == (3)
    assert (coverage.supported_phy_group_count) == (1)
    assert (coverage.incomplete_group_count) == (2)
    assert (coverage.supported_data_path_count) == (0)


def test_review_block_off_and_exact_ignore_are_project_configurable() -> None:
    fault = lint_report(usb_peer_netlist())
    finding = next(item for item in fault.findings if item.rule_id == RULE_ID)
    ignored = lint_report(
        usb_peer_netlist(),
        ignore=DesignLintIgnore(
            rule_id=RULE_ID,
            fingerprint=finding.fingerprint,
            reason="Synthetic owner decision: retain separate interface references",
        ),
    )
    ignored_finding = next(item for item in ignored.findings if item.rule_id == RULE_ID)
    assert (ignored_finding.disposition) == ("IGNORED")
    blocked = lint_report(
        usb_peer_netlist(),
        override=DesignLintRuleOverride(
            rule_id=RULE_ID,
            mode="block",
            reason="Synthetic acceptance mode",
        ),
    )
    assert (blocked.status) == ("FAIL")
    disabled = lint_report(
        usb_peer_netlist(),
        override=DesignLintRuleOverride(
            rule_id=RULE_ID,
            mode="off",
            reason="Synthetic not-applicable decision",
        ),
    )
    disabled_finding = next(item for item in disabled.findings if item.rule_id == RULE_ID)
    assert (disabled_finding.disposition) == ("RULE_OFF")


def test_reference_map_requires_complete_commonality_decision_shape() -> None:
    with pytest.raises(ValidationError):
        usb_data_map(reference_policy="common_net")
    with pytest.raises(ValidationError):
        UsbDataInterfaceRequirement.model_validate(
            {
                **usb_data_map(reference_policy="separate_nets").interfaces[0].model_dump(),
                "reference_policy": "common_net",
                "phy_reference_pins": ({"pin": "U1.3", "net": "BOARD_GND"},),
            }
        )
