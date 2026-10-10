"""Interfaces report cases for deterministic synthetic verification."""

from __future__ import annotations

import hashlib
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Literal

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.design_lint_peer_candidates import DigitalPeerVoltageLintContext
from kicad_tooling.hwrepo.design_lint_stm32_coverage import scan_stm32_pin_maps
from kicad_tooling.hwrepo.i2c_pullup_contract import i2c_pullup_checks
from kicad_tooling.hwrepo.i2c_pullup_heuristics import i2c_pullup_heuristic_coverage
from kicad_tooling.hwrepo.models import (
    DesignLintPolicy,
)
from kicad_tooling.hwrepo.serial_heuristics import serial_peer_checks
from kicad_tooling.hwrepo.serial_participants import SerialPeerRosterContext
from tests.design_lint_fixtures import (
    can_peer_netlist,
    coach,
    header_only_spi_uart_netlist,
    serial_peer_voltage_map,
    serial_peer_voltage_netlist,
    spi_peer_voltage_map,
    spi_peer_voltage_netlist,
)
from tests.design_lint_fixtures.i2c_addresses import (
    address_map,
    address_netlist,
    responder,
)
from tests.design_lint_fixtures.i2c_addresses import (
    coach as i2c_address_coach,
)
from tests.design_lint_fixtures.i2c_arrays import array_netlist, array_requirement
from tests.external_protection_support import (
    observed_netlist as external_protection_netlist,
)
from tests.external_protection_support import (
    protection_lint_report,
    protection_map,
)
from tests.serial_participant_support import (
    alternate_function_serial_netlist,
    alternate_function_serial_peer_analysis,
)
from tests.serial_peer_reference_support import (
    labelled_serial_reference_netlist,
    multi_uart_connector_reference_netlist,
)
from tests.test_electrical import serial_peer_netlist, serial_peer_requirement
from tests.test_stm32_pin_map import _IOC_FIXTURE
from tests.test_stm32_pin_map import sample_map as stm32_sample_map
from tests.test_stm32_pin_map import sample_netlist as stm32_sample_netlist
from tests.usb_data_path_support import (
    usb_bonded_reference_map,
    usb_bonded_reference_netlist,
    usb_data_map,
    usb_netlist,
)
from tests.usb_peer_reference_support import usb_multiport_peer_netlist


def serial_reference_lint_report(*, common_references: bool) -> dict[str, object]:
    observed = multi_uart_connector_reference_netlist(common_first_return=common_references)
    netlist_sha256 = hashlib.sha256(observed.model_dump_json().encode("utf-8")).hexdigest()
    report = evaluate(
        "synthetic-multi-uart-common-reference"
        if common_references
        else "synthetic-multi-uart-split-reference",
        coach(observed, netlist_sha256),
        DesignLintPolicy(),
    )
    return report.model_dump(mode="json")


def serial_bonded_reference_checks(*, fault: bool) -> list[dict[str, object]]:
    """Serialize mapped UART bond checks for hash-seed stability."""
    spec = serial_peer_requirement(reference_policy="bonded")
    observed = serial_peer_netlist(spec, fault="bond-wrong-net" if fault else None)
    return [item.model_dump(mode="json") for item in serial_peer_checks(spec, observed)]


def can_peer_lint_report(*, divergent_peer: bool) -> dict[str, object]:
    observed = can_peer_netlist(divergent_peer=divergent_peer)
    netlist_sha256 = hashlib.sha256(observed.model_dump_json().encode("utf-8")).hexdigest()
    report = evaluate(
        "synthetic-can-peer-split" if divergent_peer else "synthetic-can-peer-common",
        coach(observed, netlist_sha256),
        DesignLintPolicy(),
    )
    return report.model_dump(mode="json")


def i2c_array_lint_report(*, wrong_sda_channel: bool) -> dict[str, object]:
    """Serialize an I2C array channel fault or control with authored coverage."""
    observed = array_netlist(wrong_sda_net=wrong_sda_channel)
    netlist_sha256 = hashlib.sha256(observed.model_dump_json().encode("utf-8")).hexdigest()
    requirement = array_requirement()
    requirement_sha256 = hashlib.sha256(requirement.model_dump_json().encode("utf-8")).hexdigest()
    coverage = i2c_pullup_heuristic_coverage(
        observed,
        netlist_sha256=netlist_sha256,
        source_path="projects/synthetic-i2c-array/tests/electrical.json",
        source_sha256=requirement_sha256,
        state="required",
        spec=requirement,
    )
    report = evaluate(
        "synthetic-i2c-array-channel-fault"
        if wrong_sda_channel
        else "synthetic-i2c-array-channel-control",
        coach(observed, netlist_sha256),
        DesignLintPolicy(),
        i2c_pullup_heuristic_coverage=coverage,
    )
    return report.model_dump(mode="json")


def i2c_array_contract_checks(*, wrong_sda_channel: bool) -> dict[str, object]:
    """Serialize typed checks for the I2C array fault/control pair."""
    observed = array_netlist(wrong_sda_net=wrong_sda_channel)
    requirement = array_requirement()
    return {
        "netlist_sha256": hashlib.sha256(observed.model_dump_json().encode("utf-8")).hexdigest(),
        "requirement_sha256": hashlib.sha256(
            requirement.model_dump_json().encode("utf-8")
        ).hexdigest(),
        "checks": [
            item.model_dump(mode="json") for item in i2c_pullup_checks(requirement, observed)
        ],
    }


def i2c_address_map_lint_report(*, strap_fault: bool) -> dict[str, object]:
    """Serialize a source-bound address mismatch and same-segment collision pair."""
    specification = address_map(
        responder("U1", address=0x50),
        responder("U2", address=0x51, strap=False),
    )
    observed = address_netlist(specification, strap_values={"U1": int(strap_fault)})
    netlist_sha256 = hashlib.sha256(observed.model_dump_json().encode("utf-8")).hexdigest()
    requirement_sha256 = hashlib.sha256(specification.model_dump_json().encode("utf-8")).hexdigest()
    report = evaluate(
        "synthetic-i2c-address-map-fault" if strap_fault else "synthetic-i2c-address-map-control",
        i2c_address_coach(observed, netlist_sha256),
        DesignLintPolicy(i2c_address_map=specification),
    )
    return {
        "requirement_sha256": requirement_sha256,
        "report": report.model_dump(mode="json"),
    }


def external_protection_lint_report(*, fault: bool) -> dict[str, object]:
    """Serialize a mapped protector net fault and its repaired control."""
    requirement = protection_map()
    observed = external_protection_netlist(fault="protector-wrong-net" if fault else None)
    netlist_sha256, report = protection_lint_report(requirement, observed)
    return {
        "requirement_sha256": hashlib.sha256(
            requirement.model_dump_json().encode("utf-8")
        ).hexdigest(),
        "report": report.model_dump(mode="json"),
        "netlist_sha256": netlist_sha256,
    }


def spi_peer_voltage_lint_report(*, mapped: bool) -> dict[str, object]:
    observed = spi_peer_voltage_netlist()
    netlist_sha256 = hashlib.sha256(observed.model_dump_json().encode("utf-8")).hexdigest()
    context = (
        DigitalPeerVoltageLintContext(
            state="required", analysis=spi_peer_voltage_map((("U1.1", "U2.1"), ("U1.2", "U2.2")))
        )
        if mapped
        else DigitalPeerVoltageLintContext(state="not_configured")
    )
    report = evaluate(
        "synthetic-spi-peer-voltage-map-control"
        if mapped
        else "synthetic-spi-peer-voltage-unmapped-review",
        coach(observed, netlist_sha256),
        DesignLintPolicy(),
        digital_peer_voltage_context=context,
    )
    return report.model_dump(mode="json")


def serial_peer_voltage_lint_report(*, mapped: bool) -> dict[str, object]:
    observed = serial_peer_voltage_netlist()
    netlist_sha256 = hashlib.sha256(observed.model_dump_json().encode("utf-8")).hexdigest()
    context = (
        DigitalPeerVoltageLintContext(state="required", analysis=serial_peer_voltage_map())
        if mapped
        else DigitalPeerVoltageLintContext(state="not_configured")
    )
    report = evaluate(
        "synthetic-uart-peer-voltage-map-control"
        if mapped
        else "synthetic-uart-peer-voltage-unmapped-review",
        coach(observed, netlist_sha256),
        DesignLintPolicy(),
        digital_peer_voltage_context=context,
    )
    return report.model_dump(mode="json")


def usb_bonded_reference_lint_report(*, fault: bool) -> dict[str, object]:
    """Serialize a mapped USB reference bond fault or exact control."""
    observed = usb_bonded_reference_netlist(fault="wrong-net" if fault else None)
    netlist_sha256 = hashlib.sha256(observed.model_dump_json().encode("utf-8")).hexdigest()
    report = evaluate(
        "synthetic-usb-bonded-reference-fault"
        if fault
        else "synthetic-usb-bonded-reference-control",
        coach(observed, netlist_sha256),
        DesignLintPolicy(usb_data_path_map=usb_bonded_reference_map()),
    )
    return report.model_dump(mode="json")


def stm32_pin_map_lint_report(*, mismatch: bool) -> dict[str, object]:
    with TemporaryDirectory(prefix="stm32-hash-seed-") as temporary:
        root = Path(temporary)
        source = root / "firmware/controller.ioc"
        source.parent.mkdir(parents=True)
        content = _IOC_FIXTURE.read_bytes()
        if mismatch:
            content = content.replace(b"PB6.Signal=I2C1_SCL", b"PB6.Signal=I2C1_SDA", 1)
        source.write_bytes(content)
        observed = stm32_sample_netlist()
        netlist_sha256 = hashlib.sha256(observed.model_dump_json().encode("utf-8")).hexdigest()
        policy = DesignLintPolicy(stm32_pin_maps=(stm32_sample_map("firmware/controller.ioc"),))
        coverage = scan_stm32_pin_maps(root, policy, observed, netlist_sha256)
        report = evaluate(
            "synthetic-stm32-map",
            coach(observed, netlist_sha256),
            policy,
            stm32_pin_map_coverage=coverage,
        )
        return report.model_dump(mode="json")


def header_only_spi_uart_lint_report() -> dict[str, object]:
    observed = header_only_spi_uart_netlist()
    netlist_sha256 = hashlib.sha256(observed.model_dump_json().encode("utf-8")).hexdigest()
    report = evaluate(
        "synthetic-external-bus-headers", coach(observed, netlist_sha256), DesignLintPolicy()
    )
    return report.model_dump(mode="json")


def usb_data_path_lint_report(
    *, topology: Literal["direct", "series_resistor"], fault: str | None = None
) -> dict[str, object]:
    """Serialize a project-mapped USB data path with source-bound typed evidence."""
    observed = usb_netlist(topology, fault=fault)
    netlist_sha256 = hashlib.sha256(observed.model_dump_json().encode("utf-8")).hexdigest()
    report = evaluate(
        f"synthetic-usb-data-path-{topology}-{fault or 'control'}",
        coach(observed, netlist_sha256),
        DesignLintPolicy(usb_data_path_map=usb_data_map(topology)),
    )
    return report.model_dump(mode="json")


def serial_label_lint_report(*, mapped: bool) -> dict[str, object]:
    observed = alternate_function_serial_netlist()
    netlist_sha256 = hashlib.sha256(observed.model_dump_json().encode("utf-8")).hexdigest()
    if mapped:
        analysis = alternate_function_serial_peer_analysis()
        map_sha256 = hashlib.sha256(analysis.model_dump_json().encode("utf-8")).hexdigest()
        context = SerialPeerRosterContext(
            state="required",
            analysis=analysis,
            source_path="projects/synthetic-serial-label/tests/electrical.json",
            source_sha256=map_sha256,
        )
    else:
        context = SerialPeerRosterContext(state="not_configured")
    report = evaluate(
        "synthetic-serial-label-mapped" if mapped else "synthetic-serial-label-unmapped",
        coach(observed, netlist_sha256),
        DesignLintPolicy(),
        serial_peer_roster=context,
    )
    return report.model_dump(mode="json")


def report_cases() -> dict[str, object]:
    return {
        "i2c_array_fault": i2c_array_lint_report(wrong_sda_channel=True),
        "i2c_array_control": i2c_array_lint_report(wrong_sda_channel=False),
        "i2c_array_contract_fault": i2c_array_contract_checks(wrong_sda_channel=True),
        "i2c_array_contract_control": i2c_array_contract_checks(wrong_sda_channel=False),
        "i2c_address_map_fault": i2c_address_map_lint_report(strap_fault=True),
        "i2c_address_map_control": i2c_address_map_lint_report(strap_fault=False),
        "external_protection_fault": external_protection_lint_report(fault=True),
        "external_protection_control": external_protection_lint_report(fault=False),
        "serial_label_unmapped": serial_label_lint_report(mapped=False),
        "serial_label_mapped_control": serial_label_lint_report(mapped=True),
        "serial_reference_fault": serial_reference_lint_report(common_references=False),
        "serial_reference_control": serial_reference_lint_report(common_references=True),
        "spi_peer_voltage_unmapped": spi_peer_voltage_lint_report(mapped=False),
        "spi_peer_voltage_mapped_control": spi_peer_voltage_lint_report(mapped=True),
        "serial_peer_voltage_unmapped": serial_peer_voltage_lint_report(mapped=False),
        "serial_peer_voltage_mapped_control": serial_peer_voltage_lint_report(mapped=True),
        "can_peer_fault": can_peer_lint_report(divergent_peer=True),
        "can_peer_control": can_peer_lint_report(divergent_peer=False),
        "usb_data_path_series_fault": usb_data_path_lint_report(
            topology="series_resistor", fault="missing-dp-resistor"
        ),
        "usb_data_path_series_control": usb_data_path_lint_report(topology="series_resistor"),
        "usb_data_path_direct_topology_control": usb_data_path_lint_report(topology="direct"),
        "usb_reference_bond_fault": usb_bonded_reference_lint_report(fault=True),
        "usb_reference_bond_control": usb_bonded_reference_lint_report(fault=False),
        "serial_reference_bond_fault": serial_bonded_reference_checks(fault=True),
        "serial_reference_bond_control": serial_bonded_reference_checks(fault=False),
        "usb_multiport_peer_fault": evaluate(
            "synthetic-usb-multiport-peer-reference-fault",
            coach(usb_multiport_peer_netlist()),
            DesignLintPolicy(),
        ).model_dump(mode="json"),
        "usb_multiport_peer_control": evaluate(
            "synthetic-usb-multiport-peer-reference-control",
            coach(usb_multiport_peer_netlist(common_references=True)),
            DesignLintPolicy(),
        ).model_dump(mode="json"),
        "header_only_spi_uart_boundary": header_only_spi_uart_lint_report(),
        "serial_label_reference_fault": evaluate(
            "synthetic-uart-label-reference-fault",
            coach(labelled_serial_reference_netlist()),
            DesignLintPolicy(),
        ).model_dump(mode="json"),
        "serial_label_reference_control": evaluate(
            "synthetic-uart-label-reference-control",
            coach(
                labelled_serial_reference_netlist(
                    first_reference_net="GND", second_reference_net="GND"
                )
            ),
            DesignLintPolicy(),
        ).model_dump(mode="json"),
        "stm32_pin_map_fault": stm32_pin_map_lint_report(mismatch=True),
        "stm32_pin_map_control": stm32_pin_map_lint_report(mismatch=False),
    }
