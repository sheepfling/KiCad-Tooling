"""Four-port USB composite protection path regressions."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.netlist_contract_models import ComponentContract, NetlistContract
from kicad_tooling.hwrepo.usb_data_path_component_models import (
    UsbDataPathInlinePinRequirement,
    UsbDataPathProtectionShuntDataPinRequirement,
    UsbDataPathProtectionShuntRequirement,
)
from kicad_tooling.hwrepo.usb_data_path_models import (
    UsbDataInterfaceRequirement,
    UsbDataPathInlineComponentRequirement,
    UsbDataPathLineRequirement,
    UsbDataPathMap,
)
from tests.usb_data_path_support import lint_report

pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint]

PATH_RULE = "bus.usb_data_path_mismatch"
PEER_RULE = "bus.usb_peer_reference_review"
TOPOLOGY_RULE = "bus.usb_unmapped_multi_pin_topology"


def _four_port_composite_case() -> tuple[NetlistContract, UsbDataPathMap]:
    components: dict[str, ComponentContract] = {
        "U1": ComponentContract(value="Synthetic USB PHY", footprint="Synthetic:QFN")
    }
    symbols = {"U1": "Synthetic:UsbPhy"}
    pin_numbers = {"U1": tuple(str(number) for number in range(1, 10))}
    functions = {"U1.9": "GND"}
    electrical_types = {"U1.9": "power_in"}
    nets: dict[str, list[str]] = {"GND": ["U1.9"]}
    unconnected: dict[str, tuple[str, ...]] = {}
    interfaces: list[UsbDataInterfaceRequirement] = []

    for port in range(1, 5):
        connector = f"J{port}"
        protector = f"U{port + 1}"
        positive_phy_pin = f"U1.{port * 2 - 1}"
        negative_phy_pin = f"U1.{port * 2}"
        positive_connector_net = f"USB_DP_PORT_{port}"
        positive_phy_net = f"USB_DP_PHY_{port}"
        negative_connector_net = f"USB_DM_PORT_{port}"
        negative_phy_net = f"USB_DM_PHY_{port}"
        component_pin_nets = (
            (f"{protector}.1", positive_connector_net),
            (f"{protector}.2", positive_phy_net),
            (f"{protector}.3", negative_connector_net),
            (f"{protector}.4", negative_phy_net),
            (f"{protector}.5", "GND"),
        )
        components[connector] = ComponentContract(
            value="Synthetic USB-A connector", footprint="Synthetic:USB-A"
        )
        components[protector] = ComponentContract(
            value="Synthetic USB protection", footprint="Synthetic:QFN"
        )
        symbols[connector] = "Connector:USB_A"
        symbols[protector] = "Synthetic:UsbProtection"
        pin_numbers[connector] = ("1", "2", "4")
        pin_numbers[protector] = ("1", "2", "3", "4", "5", "6")
        functions.update(
            {
                f"{connector}.1": "D+",
                f"{connector}.2": "D-",
                f"{connector}.4": "GND",
                positive_phy_pin: f"DP{port}",
                negative_phy_pin: f"DM{port}",
                f"{protector}.1": "I/O1",
                f"{protector}.2": "I/O2",
                f"{protector}.3": "I/O2",
                f"{protector}.4": "I/O1",
                f"{protector}.5": "GND",
                f"{protector}.6": "NC",
            }
        )
        electrical_types.update(
            {
                f"{connector}.1": "passive",
                f"{connector}.2": "passive",
                f"{connector}.4": "passive",
                positive_phy_pin: "input",
                negative_phy_pin: "input",
                f"{protector}.1": "passive",
                f"{protector}.2": "passive",
                f"{protector}.3": "passive",
                f"{protector}.4": "passive",
                f"{protector}.5": "passive",
                f"{protector}.6": "no_connect",
            }
        )
        for net, pins in (
            (positive_connector_net, (f"{connector}.1", f"{protector}.1")),
            (positive_phy_net, (positive_phy_pin, f"{protector}.2")),
            (negative_connector_net, (f"{connector}.2", f"{protector}.3")),
            (negative_phy_net, (negative_phy_pin, f"{protector}.4")),
            ("GND", (f"{connector}.4", f"{protector}.5")),
        ):
            nets.setdefault(net, []).extend(pins)
        unconnected[f"NC_{protector}"] = (f"{protector}.6",)

        pin_map = tuple(
            UsbDataPathInlinePinRequirement(
                pin=pin,
                disposition="net" if net is not None else "unconnected",
                net=net,
            )
            for pin, net in (*component_pin_nets, (f"{protector}.6", None))
        )
        inline = UsbDataPathInlineComponentRequirement(
            reference=protector,
            expected_symbol=symbols[protector],
            expected_footprint=components[protector].footprint,
            positive_connector_pin=f"{protector}.1",
            positive_phy_pin=f"{protector}.2",
            negative_connector_pin=f"{protector}.3",
            negative_phy_pin=f"{protector}.4",
            pins=pin_map,
        )
        protection = UsbDataPathProtectionShuntRequirement(
            reference=protector,
            expected_symbol=symbols[protector],
            expected_footprint=components[protector].footprint,
            data_pins=(
                UsbDataPathProtectionShuntDataPinRequirement(
                    pin=f"{protector}.1", line="D+", net=positive_connector_net
                ),
                UsbDataPathProtectionShuntDataPinRequirement(
                    pin=f"{protector}.2", line="D+", net=positive_phy_net
                ),
                UsbDataPathProtectionShuntDataPinRequirement(
                    pin=f"{protector}.3", line="D-", net=negative_connector_net
                ),
                UsbDataPathProtectionShuntDataPinRequirement(
                    pin=f"{protector}.4", line="D-", net=negative_phy_net
                ),
            ),
            pins=pin_map,
        )
        interfaces.append(
            UsbDataInterfaceRequirement(
                id=f"usb-port-{port}",
                basis="Synthetic reviewed four-port USB inline-protection map",
                connector_reference=connector,
                expected_connector_symbol=symbols[connector],
                expected_connector_footprint=components[connector].footprint,
                phy_reference="U1",
                expected_phy_symbol=symbols["U1"],
                expected_phy_footprint=components["U1"].footprint,
                data_port_group=str(port),
                positive=UsbDataPathLineRequirement(
                    line="D+",
                    connector_pin=f"{connector}.1",
                    phy_pin=positive_phy_pin,
                    connector_net=positive_connector_net,
                    phy_net=positive_phy_net,
                    topology="inline_component",
                ),
                negative=UsbDataPathLineRequirement(
                    line="D-",
                    connector_pin=f"{connector}.2",
                    phy_pin=negative_phy_pin,
                    connector_net=negative_connector_net,
                    phy_net=negative_phy_net,
                    topology="inline_component",
                ),
                inline_component=inline,
                protection_shunts=(protection,),
            )
        )

    observed = NetlistContract(
        components=components,
        nets={name: tuple(sorted(pins)) for name, pins in sorted(nets.items())},
        unconnected_nets=unconnected,
        component_symbols=symbols,
        pin_functions=functions,
        pin_electrical_types=electrical_types,
        component_pin_numbers=pin_numbers,
    )
    requirements = UsbDataPathMap(
        basis="Synthetic project-authored USB multiport path contract",
        interfaces=tuple(interfaces),
    )
    return observed, requirements


def _miswire_port_four_positive_phy(observed: NetlistContract) -> NetlistContract:
    nets = {name: list(pins) for name, pins in observed.nets.items()}
    nets["USB_DP_PHY_4"].remove("U5.2")
    nets["USB_DP_PORT_4"].append("U5.2")
    return observed.model_copy(update={"nets": {name: tuple(pins) for name, pins in nets.items()}})


@pytest.mark.design_lint_rule(rule_id=PATH_RULE)
@pytest.mark.design_lint_rule(rule_id=PEER_RULE)
@pytest.mark.design_lint_rule(rule_id=TOPOLOGY_RULE)
def test_four_composite_ports_share_one_phy_and_resolve_topology_prompts() -> None:
    observed, requirements = _four_port_composite_case()

    unmapped = lint_report(observed, None)
    assert sum(item.rule_id == TOPOLOGY_RULE for item in unmapped.findings) == 4

    report = lint_report(observed, requirements)
    assert not any(
        item.rule_id in {PATH_RULE, PEER_RULE, TOPOLOGY_RULE} for item in report.findings
    )
    assert report.usb_peer_reference_coverage is not None
    assert report.usb_peer_reference_coverage.supported_data_path_count == 4


@pytest.mark.design_lint_rule(rule_id=PATH_RULE)
@pytest.mark.design_lint_rule(rule_id=PEER_RULE)
@pytest.mark.design_lint_rule(rule_id=TOPOLOGY_RULE)
def test_four_port_map_localizes_one_wrong_composite_pin() -> None:
    observed, requirements = _four_port_composite_case()
    fault = _miswire_port_four_positive_phy(observed)

    report = lint_report(fault, requirements)
    findings = tuple(item for item in report.findings if item.rule_id == PATH_RULE)

    assert len(findings) == 1
    assert findings[0].evidence["interface"] == ("usb-port-4",)
    assert findings[0].evidence["line"] == ("D+",)
    assert "U5.2 is on USB_DP_PORT_4; expected USB_DP_PHY_4" in findings[0].evidence["issues"]
    assert not any(item.rule_id in {PEER_RULE, TOPOLOGY_RULE} for item in report.findings)
    assert report.usb_peer_reference_coverage is not None
    assert report.usb_peer_reference_coverage.supported_data_path_count == 3


@pytest.mark.design_lint_rule(rule_id=PATH_RULE)
@pytest.mark.design_lint_rule(rule_id=PEER_RULE)
def test_four_port_composite_findings_are_stable_under_mapping_order() -> None:
    observed, requirements = _four_port_composite_case()
    fault = _miswire_port_four_positive_phy(observed)
    reordered = fault.model_copy(
        update={
            "components": dict(reversed(tuple(fault.components.items()))),
            "nets": dict(reversed(tuple(fault.nets.items()))),
            "component_symbols": dict(reversed(tuple(fault.component_symbols.items()))),
            "component_pin_numbers": dict(reversed(tuple(fault.component_pin_numbers.items()))),
            "pin_functions": dict(reversed(tuple(fault.pin_functions.items()))),
            "pin_electrical_types": dict(reversed(tuple(fault.pin_electrical_types.items()))),
        }
    )

    first = lint_report(fault, requirements)
    second = lint_report(reordered, requirements)

    assert tuple((item.fingerprint, item.evidence) for item in first.findings) == tuple(
        (item.fingerprint, item.evidence) for item in second.findings
    )
    assert first.usb_peer_reference_coverage == second.usb_peer_reference_coverage
