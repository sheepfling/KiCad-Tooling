"""Connectors report cases for deterministic synthetic verification."""

from __future__ import annotations

import hashlib
from typing import Literal

from kicad_tooling.hwrepo.connector_contact_ratings import connector_contact_rating_checks
from kicad_tooling.hwrepo.connector_coverage import evaluate as evaluate_connector_coverage
from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.models import (
    ConnectorInterfaceReview,
    DesignLintPolicy,
    InterfacePin,
    InterfaceRecord,
    NetlistContract,
)
from tests.design_lint_fixtures import (
    coach,
    generic_connector_power_input_netlist,
    peer_connector_pin_assignments,
)
from tests.design_lint_fixtures.connector_coverage import (
    connector_supply_role_catalog,
    connector_supply_role_netlist,
    connector_supply_role_reviews,
    inventory_review,
    uart_header_coverage,
    uart_peer_netlist,
)
from tests.design_lint_fixtures.connector_peer_pin_cases import peer_pin_case_contracts
from tests.test_connector_contact_ratings import contact as connector_contact
from tests.test_connector_contact_ratings import netlist as connector_rating_netlist
from tests.test_connector_contact_ratings import requirement as connector_rating_requirement


def mapped_connector_supply_report(*, open_supply: bool) -> dict[str, object]:
    """Serialize a mapped cross-symbol open-supply fault and common-rail control."""
    observed = connector_supply_role_netlist(common_supply=not open_supply, open_supply=open_supply)
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
            peer_assignment_group="uart-peers" if shared_group else f"uart-{reference}",
            peer_assignment_basis="Reviewed matching generic signal contacts as one UART peer set"
            if shared_group
            else f"Reviewed J{reference} as an independent UART interface",
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
        project_id, coach(observed, netlist_sha256), DesignLintPolicy(), connector_coverage=coverage
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


def part_id_connector_peer_report(*, mode: Literal["open", "split", "common"]) -> dict[str, object]:
    """Serialize a guarded cross-symbol PART_ID peer fault or valid control."""
    case_name = {
        "open": "peer-pin-part-id-open-fault",
        "split": "peer-pin-part-id-split-fault",
        "common": "peer-pin-part-id-common-control",
    }[mode]
    observed = peer_pin_case_contracts()[case_name]
    netlist_sha256 = hashlib.sha256(observed.model_dump_json().encode("utf-8")).hexdigest()
    report = evaluate(
        f"synthetic-connector-part-id-hash-seed-{mode}",
        coach(observed, netlist_sha256),
        DesignLintPolicy(),
    )
    return report.model_dump(mode="json")


def report_cases() -> dict[str, object]:
    return {
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
        "peer_pin_fault": evaluate(
            "synthetic-peer-pin-hash-seed-fault",
            coach(peer_connector_pin_assignments()),
            DesignLintPolicy(),
        ).model_dump(mode="json"),
        "connector_part_id_alias_open_fault": part_id_connector_peer_report(mode="open"),
        "connector_part_id_alias_split_fault": part_id_connector_peer_report(mode="split"),
        "connector_part_id_alias_common_control": part_id_connector_peer_report(mode="common"),
        "peer_pin_control": evaluate(
            "synthetic-peer-pin-hash-seed-control",
            coach(peer_connector_pin_assignments(("RETURN", "RETURN", "RETURN"))),
            DesignLintPolicy(),
        ).model_dump(mode="json"),
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
        "partial_mapped_peer_pin_fault": mapped_peer_pin_report(complete_map=False),
        "complete_mapped_peer_pin_control": mapped_peer_pin_report(complete_map=True),
        "common_peer_pin_control": mapped_peer_pin_report(complete_map=True, common_supply=True),
    }
