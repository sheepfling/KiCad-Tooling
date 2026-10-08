"""Pytest-invoked worker that emits complete synthetic lint reports."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Literal

from kicad_tooling.hwrepo.connector_contact_ratings import connector_contact_rating_checks
from kicad_tooling.hwrepo.connector_coverage import evaluate as evaluate_connector_coverage
from kicad_tooling.hwrepo.design_lint import (
    DigitalPeerVoltageLintContext,
    evaluate,
    scan_stm32_pin_maps,
)
from kicad_tooling.hwrepo.electrical import grounding_checks, pin_relationship_checks
from kicad_tooling.hwrepo.models import (
    ComponentContract,
    ConnectorInterfaceReview,
    DesignLintPolicy,
    GroundDomain,
    GroundingAnalysis,
    InterfacePin,
    InterfaceRecord,
    MosfetVoltageInterval,
    NetlistContract,
    PinConnectivityAnalysis,
    PinRelationshipRule,
)
from kicad_tooling.hwrepo.mosfet_stress import mosfet_stress_checks
from kicad_tooling.hwrepo.serial_heuristics import serial_peer_checks
from kicad_tooling.hwrepo.serial_participants import SerialPeerRosterContext
from tests.test_connector_contact_ratings import (
    contact as connector_contact,
)
from tests.test_connector_contact_ratings import (
    netlist as connector_rating_netlist,
)
from tests.test_connector_contact_ratings import (
    requirement as connector_rating_requirement,
)
from tests.test_connector_coverage import (
    connector_return_role_catalog,
    connector_return_role_netlist,
    connector_return_role_reviews,
    connector_supply_role_catalog,
    connector_supply_role_netlist,
    connector_supply_role_reviews,
    inventory_review,
    uart_header_coverage,
    uart_peer_netlist,
)
from tests.test_design_lint import (
    can_peer_netlist,
    coach,
    four_db9_return_domains,
    generic_component_power_input_netlist,
    generic_connector_power_input_netlist,
    header_only_spi_uart_netlist,
    peer_connector_pin_assignments,
    serial_peer_voltage_map,
    serial_peer_voltage_netlist,
    spi_peer_voltage_map,
    spi_peer_voltage_netlist,
)
from tests.test_electrical import serial_peer_netlist, serial_peer_requirement
from tests.test_led_output_heuristics import (
    observed_report as led_output_observed_report,
)
from tests.test_led_output_heuristics import (
    output_led_netlist as led_output_netlist,
)
from tests.test_mosfet_stress import multi_device_netlist, multi_device_requirement
from tests.test_pcb_decoupling import (
    coverage_report as pcb_decoupling_coverage_report,
)
from tests.test_pcb_decoupling import (
    mapping as pcb_decoupling_mapping,
)
from tests.test_pcb_decoupling import (
    requirement as pcb_decoupling_requirement,
)
from tests.test_pcb_decoupling import (
    snapshot as pcb_decoupling_snapshot,
)
from tests.test_power_paths import (
    lint_report as power_path_lint_report,
)
from tests.test_power_paths import (
    power_path_map,
    power_path_netlist,
)
from tests.test_power_sequences import (
    lint_report as power_sequence_lint_report,
)
from tests.test_power_sequences import (
    power_sequence_map,
    power_sequence_netlist,
)
from tests.test_serial_participants import (
    alternate_function_serial_netlist,
    alternate_function_serial_peer_analysis,
)
from tests.test_serial_peer_reference_review import (
    labelled_serial_reference_netlist,
    multi_uart_connector_reference_netlist,
)
from tests.test_stm32_pin_map import _IOC_FIXTURE
from tests.test_stm32_pin_map import sample_map as stm32_sample_map
from tests.test_stm32_pin_map import sample_netlist as stm32_sample_netlist
from tests.test_two_pin_crystals import crystal_netlist
from tests.test_two_pin_diodes import diode_netlist
from tests.test_two_pin_ferrites import ferrite_netlist
from tests.test_two_pin_fuses import fuse_netlist
from tests.test_two_pin_switches import switch_netlist
from tests.test_usb_data_paths import (
    usb_bonded_reference_map,
    usb_bonded_reference_netlist,
    usb_data_map,
    usb_netlist,
)
from tests.test_usb_peer_reference_review import usb_multiport_peer_netlist


def reviewed_connector_return_report(*, common_return: bool) -> dict[str, object]:
    observed = connector_return_role_netlist(common_return=common_return)
    coverage = evaluate_connector_coverage(
        observed,
        ("usb-interface", "serial-interface"),
        connector_return_role_reviews(),
        interfaces=connector_return_role_catalog(),
        interface_catalog_path="catalog/interfaces.json",
        interface_catalog_sha256="b" * 64,
        inventory_review=inventory_review(),
    )
    netlist_sha256 = hashlib.sha256(observed.model_dump_json().encode("utf-8")).hexdigest()
    report = evaluate(
        "synthetic-reviewed-return-common" if common_return else "synthetic-reviewed-return-split",
        coach(observed, netlist_sha256),
        DesignLintPolicy(),
        connector_coverage=coverage,
    )
    return report.model_dump(mode="json")


def mapped_connector_supply_report(*, open_supply: bool) -> dict[str, object]:
    """Serialize a mapped cross-symbol open-supply fault and common-rail control."""
    observed = connector_supply_role_netlist(
        common_supply=not open_supply,
        open_supply=open_supply,
    )
    coverage = evaluate_connector_coverage(
        observed,
        ("usb-power", "serial-power"),
        connector_supply_role_reviews(),
        interfaces=connector_supply_role_catalog(),
        interface_catalog_path="catalog/interfaces.json",
        interface_catalog_sha256="d" * 64,
        inventory_review=inventory_review(),
    )
    netlist_sha256 = hashlib.sha256(observed.model_dump_json().encode("utf-8")).hexdigest()
    report = evaluate(
        "synthetic-mapped-connector-open-supply"
        if open_supply
        else "synthetic-mapped-connector-common-supply",
        coach(observed, netlist_sha256),
        DesignLintPolicy(),
        connector_coverage=coverage,
    )
    return report.model_dump(mode="json")


def connector_contact_rating_check_result(
    *, maximum_expected_current_a: float
) -> dict[str, object]:
    """Serialize typed contact-rating checks at and over the authored limit."""
    specification = connector_rating_requirement(
        contacts=(connector_contact(maximum_expected_current_a=maximum_expected_current_a),)
    )
    observed = connector_rating_netlist()
    checks = connector_contact_rating_checks(specification, observed)
    return {
        "requirements_sha256": hashlib.sha256(
            specification.model_dump_json().encode("utf-8")
        ).hexdigest(),
        "netlist_sha256": hashlib.sha256(observed.model_dump_json().encode("utf-8")).hexdigest(),
        "checks": [check.model_dump(mode="json") for check in checks],
    }


def mosfet_stress_check_result(*, q2_over_limit: bool) -> dict[str, object]:
    """Serialize a multi-device MOSFET stress contract and its typed results."""
    requirement = multi_device_requirement(
        q2_drain_on=(
            MosfetVoltageInterval(minimum_v=0.0, maximum_v=60.0) if q2_over_limit else None
        )
    )
    observed = multi_device_netlist()
    checks = mosfet_stress_checks(requirement, observed)
    return {
        "requirements_sha256": hashlib.sha256(
            requirement.model_dump_json().encode("utf-8")
        ).hexdigest(),
        "netlist_sha256": hashlib.sha256(observed.model_dump_json().encode("utf-8")).hexdigest(),
        "checks": [check.model_dump(mode="json") for check in checks],
    }


def db9_grounding_check_result(
    *, observed_common: bool, required_common: bool
) -> dict[str, object]:
    """Serialize the same DB9 return netlist against common and isolated requirements."""
    observed = four_db9_return_domains(common=observed_common).model_copy(
        update={
            "components": {
                f"J{reference}": ComponentContract(value="Synthetic DB9", footprint="")
                for reference in range(1, 5)
            }
        }
    )
    all_return_pins = tuple(
        f"J{reference}.{pin_number}" for reference in range(1, 5) for pin_number in (7, 9)
    )
    domains = (
        (GroundDomain(net="0V PWM", pins=all_return_pins),)
        if required_common
        else tuple(
            GroundDomain(
                net=f"0V PWM {reference}",
                pins=(f"J{reference}.7", f"J{reference}.9"),
            )
            for reference in range(1, 5)
        )
    )
    requirement = GroundingAnalysis(
        basis=(
            "Synthetic reviewed requirement: DB9 returns share one domain"
            if required_common
            else "Synthetic reviewed requirement: each DB9 return remains isolated"
        ),
        domains=domains,
    )
    checks = grounding_checks(requirement, observed)
    connectivity_rules = (
        (
            PinRelationshipRule(
                id="db9-common-return",
                basis="Synthetic reviewed requirement for common DB9 returns",
                topology="common_net",
                pins=all_return_pins,
                net="0V PWM",
            ),
        )
        if required_common
        else tuple(
            PinRelationshipRule(
                id=f"db9-{reference}-isolated-return",
                basis="Synthetic reviewed per-connector isolated return requirement",
                topology="common_net",
                pins=(f"J{reference}.7", f"J{reference}.9"),
                net=f"0V PWM {reference}",
            )
            for reference in range(1, 5)
        )
    )
    connectivity = PinConnectivityAnalysis(
        basis=(
            "Synthetic reviewed pin-connectivity requirement: common DB9 return"
            if required_common
            else "Synthetic reviewed pin-connectivity requirement: isolated DB9 returns"
        ),
        rules=connectivity_rules,
    )
    connectivity_checks = pin_relationship_checks(connectivity, observed)
    return {
        "observed_common": observed_common,
        "required_common": required_common,
        "netlist_sha256": hashlib.sha256(observed.model_dump_json().encode("utf-8")).hexdigest(),
        "requirements_sha256": hashlib.sha256(
            requirement.model_dump_json().encode("utf-8")
        ).hexdigest(),
        "checks": [check.model_dump(mode="json") for check in checks],
        "connectivity_requirements_sha256": hashlib.sha256(
            connectivity.model_dump_json().encode("utf-8")
        ).hexdigest(),
        "pin_connectivity_checks": [check.model_dump(mode="json") for check in connectivity_checks],
    }


def unconnected_pin_inventory_check_result() -> dict[str, object]:
    """Compare absent and complete symbol-pin inventories for an unused pin."""
    requirement = PinConnectivityAnalysis(
        basis="Synthetic approved connector pin disposition",
        rules=(
            PinRelationshipRule(
                id="reserved-pin",
                basis="J1.2 is intentionally unused on this assembly",
                topology="unconnected",
                pins=("J1.2",),
            ),
        ),
    )
    missing_inventory = NetlistContract(
        components={"J1": ComponentContract(value="Synthetic port", footprint="")},
        nets={},
        component_symbols={"J1": "Synthetic:Port"},
        component_pin_numbers={},
    )
    complete_inventory = missing_inventory.model_copy(
        update={"component_pin_numbers": {"J1": ("1", "2")}}
    )
    results: dict[str, object] = {
        "requirements_sha256": hashlib.sha256(
            requirement.model_dump_json().encode("utf-8")
        ).hexdigest(),
    }
    for name, observed in (
        ("missing_inventory", missing_inventory),
        ("complete_inventory_control", complete_inventory),
    ):
        results[name] = {
            "netlist_sha256": hashlib.sha256(
                observed.model_dump_json().encode("utf-8")
            ).hexdigest(),
            "checks": [
                check.model_dump(mode="json")
                for check in pin_relationship_checks(requirement, observed)
            ],
        }
    return results


def mapped_peer_pin_report(*, complete_map: bool, common_supply: bool = False) -> dict[str, object]:
    """Keep mapped-role coverage and generic peer findings distinct and deterministic."""
    supply_net = (
        {"COMMON_SUPPLY": ("J1.1", "J2.1", "J3.1")}
        if common_supply
        else {"SUPPLY_A": ("J1.1", "J3.1"), "SUPPLY_B": ("J2.1",)}
    )
    observed = NetlistContract(
        components={},
        nets={**supply_net, "COMMON_RETURN": ("J1.2", "J2.2", "J3.2")},
        component_symbols={reference: "Synthetic:PeerPort" for reference in ("J1", "J2", "J3")},
        component_pin_numbers={reference: ("1", "2") for reference in ("J1", "J2", "J3")},
        pin_functions={
            **{f"{reference}.1": "Pin_1" for reference in ("J1", "J2", "J3")},
            **{f"{reference}.2": "GND" for reference in ("J1", "J2", "J3")},
        },
    )
    interface = InterfaceRecord(
        id="peer-port",
        revision="synthetic-1",
        pins=(
            InterfacePin(
                number="1",
                signal="POWER",
                role="supply",
                direction="passive",
                voltage_domain="external-5v",
                mating="POWER",
                orientation="straight",
                mechanical_clearance="synthetic",
            ),
            InterfacePin(
                number="2",
                signal="RETURN",
                role="return",
                direction="passive",
                voltage_domain="signal-return",
                mating="RETURN",
                orientation="straight",
                mechanical_clearance="synthetic",
            ),
        ),
    )
    references = ("J1", "J2", "J3") if complete_map else ("J1", "J2")
    reviews = tuple(
        ConnectorInterfaceReview(
            reference=reference,
            disposition="interface",
            basis="Synthetic peer connector pinout reviewed",
            interface_id="peer-port",
            pin_map={"1": "1", "2": "2"},
        )
        for reference in references
    )
    netlist_sha256 = hashlib.sha256(observed.model_dump_json().encode("utf-8")).hexdigest()
    coverage = evaluate_connector_coverage(
        observed,
        ("peer-port",),
        reviews,
        interfaces={"peer-port": interface},
        interface_catalog_path="catalog/interfaces.json",
        interface_catalog_sha256="c" * 64,
        inventory_review=inventory_review(),
    )
    report = evaluate(
        "synthetic-mapped-peer-pin-coverage",
        coach(observed, netlist_sha256),
        DesignLintPolicy(),
        connector_coverage=coverage,
    )
    return report.model_dump(mode="json")


def connector_peer_scope_report(*, shared_group: bool) -> dict[str, object]:
    """Serialize source-matched connector scopes for cross-process determinism checks."""
    observed = uart_peer_netlist(split_return=True)
    groups = ("uart-ports", "uart-ports") if shared_group else ("uart-1", "uart-2")
    coverage = uart_header_coverage(observed, groups=groups)
    netlist_sha256 = hashlib.sha256(observed.model_dump_json().encode("utf-8")).hexdigest()
    report = evaluate(
        "synthetic-connector-peer-scope-shared"
        if shared_group
        else "synthetic-connector-peer-scope-separate",
        coach(observed, netlist_sha256),
        DesignLintPolicy(),
        connector_coverage=coverage,
    )
    return report.model_dump(mode="json")


def mapped_generic_peer_scope_report(*, mode: str) -> dict[str, object]:
    """Serialize a three-port generic-pin scope with mapped split returns."""
    if mode not in {"separate-fault", "shared-fault", "shared-control"}:
        raise ValueError(f"Unsupported connector peer-scope probe mode: {mode}")
    shared_group = mode != "separate-fault"
    split_returns = mode != "shared-control"
    split_signals = mode != "shared-control"
    signal_nets = (
        ("SIGNAL_A", "SIGNAL_B", "SIGNAL_C") if split_signals else ("SIGNAL", "SIGNAL", "SIGNAL")
    )
    return_nets = ("RETURN_A", "RETURN_B", "RETURN_C") if split_returns else ("GND", "GND", "GND")
    nets: dict[str, tuple[str, ...]] = {}
    for reference, net in enumerate(signal_nets, start=1):
        nets.setdefault(net, ())
        nets[net] = (*nets[net], f"J{reference}.1")
    for reference, net in enumerate(return_nets, start=1):
        nets.setdefault(net, ())
        nets[net] = (*nets[net], f"J{reference}.2")
    observed = NetlistContract(
        components={},
        nets=nets,
        component_symbols={f"J{reference}": "Lint:PeerPowerPort" for reference in range(1, 4)},
        component_pin_numbers={f"J{reference}": ("1", "2") for reference in range(1, 4)},
        pin_functions={
            **{f"J{reference}.1": "Pin_1" for reference in range(1, 4)},
            **{f"J{reference}.2": "GND" for reference in range(1, 4)},
        },
    )
    interface = InterfaceRecord(
        id="peer-return",
        revision="synthetic-1",
        pins=(
            InterfacePin(
                number="2",
                signal="RETURN",
                role="return",
                direction="bidirectional",
                voltage_domain="signal-return",
                mating="RETURN",
                orientation="straight",
                mechanical_clearance="synthetic",
            ),
        ),
    )
    reviews = tuple(
        ConnectorInterfaceReview(
            reference=f"J{reference}",
            disposition="interface",
            basis=f"Reviewed J{reference} return contact against the synthetic pinout",
            interface_id="peer-return",
            pin_map={"2": "2"},
            unlisted_pin_reasons={
                "1": "Generic Pin_1 signal contact has no reviewed role in this fixture"
            },
            peer_assignment_group=("uart-peers" if shared_group else f"uart-{reference}"),
            peer_assignment_basis=(
                "Reviewed matching generic signal contacts as one UART peer set"
                if shared_group
                else f"Reviewed J{reference} as an independent UART interface"
            ),
        )
        for reference in range(1, 4)
    )
    coverage = evaluate_connector_coverage(
        observed,
        ("peer-return",),
        reviews,
        interfaces={"peer-return": interface},
        interface_catalog_path="catalog/interfaces.json",
        interface_catalog_sha256="c" * 64,
        inventory_review=inventory_review(),
    )
    project_id = f"synthetic-peer-scope-unlisted-{mode}"
    netlist_sha256 = hashlib.sha256(observed.model_dump_json().encode("utf-8")).hexdigest()
    report = evaluate(
        project_id,
        coach(observed, netlist_sha256),
        DesignLintPolicy(),
        connector_coverage=coverage,
    )
    return report.model_dump(mode="json")


def pcb_decoupling_lint_report(*, capacitor_distance_nm: int) -> dict[str, object]:
    """Serialize the mapped PCB decoupling boundary through the shared linter."""
    mapped = pcb_decoupling_mapping(pcb_decoupling_requirement(maximum_um=100))
    snapshot = pcb_decoupling_snapshot(distances_nm={"C1": capacitor_distance_nm})
    coverage = pcb_decoupling_coverage_report(mapped, snapshot)
    observed = NetlistContract(components={}, nets={})
    netlist_sha256 = hashlib.sha256(observed.model_dump_json().encode("utf-8")).hexdigest()
    report = evaluate(
        "synthetic-pcb-decoupling-distance-boundary",
        coach(observed, netlist_sha256),
        DesignLintPolicy(pcb_decoupling_map=mapped),
        pcb_decoupling_coverage=coverage,
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


def spi_peer_voltage_lint_report(*, mapped: bool) -> dict[str, object]:
    observed = spi_peer_voltage_netlist()
    netlist_sha256 = hashlib.sha256(observed.model_dump_json().encode("utf-8")).hexdigest()
    context = (
        DigitalPeerVoltageLintContext(
            state="required",
            analysis=spi_peer_voltage_map((("U1.1", "U2.1"), ("U1.2", "U2.2"))),
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
        DigitalPeerVoltageLintContext(
            state="required",
            analysis=serial_peer_voltage_map(),
        )
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


def can_peer_lint_report(*, divergent_peer: bool) -> dict[str, object]:
    observed = can_peer_netlist(divergent_peer=divergent_peer)
    netlist_sha256 = hashlib.sha256(observed.model_dump_json().encode("utf-8")).hexdigest()
    report = evaluate(
        "synthetic-can-peer-split" if divergent_peer else "synthetic-can-peer-common",
        coach(observed, netlist_sha256),
        DesignLintPolicy(),
    )
    return report.model_dump(mode="json")


def led_output_lint_report(*, topology: str) -> dict[str, object]:
    """Serialize direct-drive, parallel-resistor, or series-path LED evidence."""
    return led_output_observed_report(led_output_netlist(topology)).model_dump(mode="json")


def header_only_spi_uart_lint_report() -> dict[str, object]:
    observed = header_only_spi_uart_netlist()
    netlist_sha256 = hashlib.sha256(observed.model_dump_json().encode("utf-8")).hexdigest()
    report = evaluate(
        "synthetic-external-bus-headers",
        coach(observed, netlist_sha256),
        DesignLintPolicy(),
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


def serial_bonded_reference_checks(*, fault: bool) -> list[dict[str, object]]:
    """Serialize mapped UART bond checks for hash-seed stability."""
    spec = serial_peer_requirement(reference_policy="bonded")
    observed = serial_peer_netlist(spec, fault="bond-wrong-net" if fault else None)
    return [item.model_dump(mode="json") for item in serial_peer_checks(spec, observed)]


def test_emit_four_port_db9_fault_and_control_reports() -> None:
    reports = {
        "fault": evaluate(
            "synthetic-four-db9-hash-seed-fault",
            coach(four_db9_return_domains()),
            DesignLintPolicy(),
        ).model_dump(mode="json"),
        "common_control": evaluate(
            "synthetic-four-db9-hash-seed-common",
            coach(four_db9_return_domains(common=True)),
            DesignLintPolicy(),
        ).model_dump(mode="json"),
        "generic_power_input_fault": evaluate(
            "synthetic-generic-power-input-hash-seed-fault",
            coach(generic_connector_power_input_netlist()),
            DesignLintPolicy(),
        ).model_dump(mode="json"),
        "generic_power_input_control": evaluate(
            "synthetic-generic-power-input-hash-seed-control",
            coach(generic_connector_power_input_netlist(connected=True)),
            DesignLintPolicy(),
        ).model_dump(mode="json"),
        "generic_component_power_input_fault": evaluate(
            "synthetic-generic-component-power-input-hash-seed-fault",
            coach(generic_component_power_input_netlist()),
            DesignLintPolicy(),
        ).model_dump(mode="json"),
        "generic_component_power_input_control": evaluate(
            "synthetic-generic-component-power-input-hash-seed-control",
            coach(generic_component_power_input_netlist(connected=True)),
            DesignLintPolicy(),
        ).model_dump(mode="json"),
        "db9_split_against_common_requirement": db9_grounding_check_result(
            observed_common=False,
            required_common=True,
        ),
        "db9_split_against_isolated_requirement": db9_grounding_check_result(
            observed_common=False,
            required_common=False,
        ),
        "db9_common_against_common_requirement": db9_grounding_check_result(
            observed_common=True,
            required_common=True,
        ),
        "db9_common_against_isolated_requirement": db9_grounding_check_result(
            observed_common=True,
            required_common=False,
        ),
        "unconnected_pin_inventory": unconnected_pin_inventory_check_result(),
        "diode_fault": evaluate(
            "synthetic-two-pin-diode-hash-seed-fault",
            coach(diode_netlist()),
            DesignLintPolicy(),
        ).model_dump(mode="json"),
        "diode_control": evaluate(
            "synthetic-two-pin-diode-hash-seed-control",
            coach(diode_netlist(same_net=False)),
            DesignLintPolicy(),
        ).model_dump(mode="json"),
        "crystal_fault": evaluate(
            "synthetic-two-pin-crystal-hash-seed-fault",
            coach(crystal_netlist()),
            DesignLintPolicy(),
        ).model_dump(mode="json"),
        "crystal_control": evaluate(
            "synthetic-two-pin-crystal-hash-seed-control",
            coach(crystal_netlist(same_net=False)),
            DesignLintPolicy(),
        ).model_dump(mode="json"),
        "fuse_fault": evaluate(
            "synthetic-two-pin-fuse-hash-seed-fault",
            coach(fuse_netlist()),
            DesignLintPolicy(),
        ).model_dump(mode="json"),
        "fuse_control": evaluate(
            "synthetic-two-pin-fuse-hash-seed-control",
            coach(fuse_netlist(same_net=False)),
            DesignLintPolicy(),
        ).model_dump(mode="json"),
        "ferrite_fault": evaluate(
            "synthetic-two-pin-ferrite-hash-seed-fault",
            coach(ferrite_netlist()),
            DesignLintPolicy(),
        ).model_dump(mode="json"),
        "ferrite_control": evaluate(
            "synthetic-two-pin-ferrite-hash-seed-control",
            coach(ferrite_netlist(same_net=False)),
            DesignLintPolicy(),
        ).model_dump(mode="json"),
        "switch_fault": evaluate(
            "synthetic-two-pin-switch-hash-seed-fault",
            coach(switch_netlist()),
            DesignLintPolicy(),
        ).model_dump(mode="json"),
        "switch_control": evaluate(
            "synthetic-two-pin-switch-hash-seed-control",
            coach(switch_netlist(same_net=False)),
            DesignLintPolicy(),
        ).model_dump(mode="json"),
        "peer_pin_fault": evaluate(
            "synthetic-peer-pin-hash-seed-fault",
            coach(peer_connector_pin_assignments()),
            DesignLintPolicy(),
        ).model_dump(mode="json"),
        "peer_pin_control": evaluate(
            "synthetic-peer-pin-hash-seed-control",
            coach(peer_connector_pin_assignments(("RETURN", "RETURN", "RETURN"))),
            DesignLintPolicy(),
        ).model_dump(mode="json"),
        "mapped_return_fault": reviewed_connector_return_report(common_return=False),
        "mapped_return_control": reviewed_connector_return_report(common_return=True),
        "mapped_supply_open_peer_fault": mapped_connector_supply_report(open_supply=True),
        "mapped_supply_common_control": mapped_connector_supply_report(open_supply=False),
        "connector_peer_scope_separate": connector_peer_scope_report(shared_group=False),
        "connector_peer_scope_shared": connector_peer_scope_report(shared_group=True),
        "unlisted_peer_scope_separate_fault": mapped_generic_peer_scope_report(
            mode="separate-fault"
        ),
        "unlisted_peer_scope_shared_fault": mapped_generic_peer_scope_report(mode="shared-fault"),
        "unlisted_peer_scope_shared_control": mapped_generic_peer_scope_report(
            mode="shared-control"
        ),
        "connector_contact_rating_over_limit": connector_contact_rating_check_result(
            maximum_expected_current_a=1.61
        ),
        "connector_contact_rating_boundary_control": connector_contact_rating_check_result(
            maximum_expected_current_a=1.6
        ),
        "mosfet_stress_q2_over_limit": mosfet_stress_check_result(q2_over_limit=True),
        "mosfet_stress_multi_device_control": mosfet_stress_check_result(q2_over_limit=False),
        "partial_mapped_peer_pin_fault": mapped_peer_pin_report(complete_map=False),
        "complete_mapped_peer_pin_control": mapped_peer_pin_report(complete_map=True),
        "common_peer_pin_control": mapped_peer_pin_report(complete_map=True, common_supply=True),
        "pcb_decoupling_distance_fault": pcb_decoupling_lint_report(capacitor_distance_nm=100_001),
        "pcb_decoupling_distance_control": pcb_decoupling_lint_report(
            capacitor_distance_nm=100_000
        ),
        "mapped_power_path_fault": power_path_lint_report(
            power_path_netlist(fault="open-element"),
            power_path_map(),
        ).model_dump(mode="json"),
        "mapped_power_path_control": power_path_lint_report(
            power_path_netlist(),
            power_path_map(),
        ).model_dump(mode="json"),
        "mapped_power_sequence_fault": power_sequence_lint_report(
            power_sequence_netlist(fault="open-enable"),
            power_sequence_map(),
        ).model_dump(mode="json"),
        "mapped_power_sequence_control": power_sequence_lint_report(
            power_sequence_netlist(),
            power_sequence_map(),
        ).model_dump(mode="json"),
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
        "led_output_direct_fault": led_output_lint_report(topology="direct"),
        "led_output_parallel_resistor_fault": led_output_lint_report(topology="parallel-resistor"),
        "led_output_series_control": led_output_lint_report(topology="series-return-side"),
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
    payload = {
        "hash_marker": hash("kicad-tooling-hash-seed-probe"),
        "hash_randomization": sys.flags.hash_randomization,
        "reports": reports,
    }
    print(
        "DESIGN_LINT_HASHSEED_REPORTS="
        + json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    )
