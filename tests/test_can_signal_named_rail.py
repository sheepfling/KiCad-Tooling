"""Focused regressions for CAN signal pins assigned to named rails."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.can_signal_functions import (
    can_module_data_role,
    can_signal_role_and_channel,
)
from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.design_lint_finding_models import DesignLintIgnore
from kicad_tooling.hwrepo.design_lint_policy_models import DesignLintPolicy
from kicad_tooling.hwrepo.design_lint_report_models import DesignLintReport
from kicad_tooling.hwrepo.models import (
    DesignLintRuleOverride,
    NetlistContract,
)
from tests.design_lint_fixtures import coach
from tests.design_lint_fixtures.can_signal_named_rail import (
    can_connector_signal_on_named_rail_netlist,
    can_module_connector_named_rail_netlist,
    can_signal_on_named_rail_netlist,
)

RULE_ID = "bus.can_signal_on_named_rail"

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.interface_lint,
    pytest.mark.design_lint_rule(rule_id=RULE_ID),
]


def _report(
    source: NetlistContract,
    policy: DesignLintPolicy | None = None,
) -> DesignLintReport:
    return evaluate(
        "synthetic-can-signal-named-rail",
        coach(source),
        DesignLintPolicy() if policy is None else policy,
    )


@pytest.mark.parametrize(
    ("pin", "rail", "function", "role", "channel", "rail_role"),
    (
        ("U1.1", "GND", "CAN1_TX", "tx", "can:index1", "return-like"),
        ("U1.2", "+3V3", "CAN1_RX", "rx", "can:index1", "supply-like"),
    ),
)
def test_can_controller_signal_on_named_rail_requests_review(
    pin: str, rail: str, function: str, role: str, channel: str, rail_role: str
) -> None:
    report = _report(can_signal_on_named_rail_netlist(rail_name=rail, pin=pin))
    finding = next(item for item in report.findings if item.rule_id == RULE_ID)

    assert report.status == "REVIEW"
    assert finding.subject == f"{pin}: {function} on {rail_role} net {rail}"
    assert finding.evidence == {
        "pin": (pin,),
        "pin_function": (function,),
        "pin_role": (role,),
        "can_channel": (channel,),
        "assigned_net": (rail,),
        "net_label_role_clue": (rail_role,),
        "component_pin_inventory": ("1", "2"),
    }
    assert "not proof of electrical potential" in finding.message
    assert "intentional rail strap" in finding.message


@pytest.mark.parametrize(
    ("pin", "rail", "function", "role", "rail_role"),
    (
        ("J1.1", "GND", "CAN2_TX", "tx", "return-like"),
        ("J1.2", "+3V3", "CAN2_RX", "rx", "supply-like"),
    ),
)
def test_can_connector_signal_on_named_rail_requests_review(
    pin: str, rail: str, function: str, role: str, rail_role: str
) -> None:
    report = _report(can_connector_signal_on_named_rail_netlist(rail_name=rail, pin=pin))
    finding = next(item for item in report.findings if item.rule_id == RULE_ID)

    assert report.status == "REVIEW"
    assert finding.subject == f"{pin}: {function} on {rail_role} net {rail}"
    assert finding.evidence == {
        "pin": (pin,),
        "pin_function": (function,),
        "pin_role": (role,),
        "can_channel": ("can:index2",),
        "assigned_net": (rail,),
        "net_label_role_clue": (rail_role,),
        "component_pin_inventory": ("1", "2"),
    }
    assert "not proof of electrical potential" in finding.message
    assert "intentional rail strap" in finding.message


def test_bounded_can_aliases_and_non_can_or_bus_line_aliases() -> None:
    assert can_signal_role_and_channel("CAN1_TX") == ("tx", "can:index1")
    assert can_signal_role_and_channel("FDCAN2_RXD") == ("rx", "fdcan:index2")
    assert can_signal_role_and_channel("TXD_CAN") == ("tx", "can:default")
    assert can_signal_role_and_channel("CANH") is None
    assert can_signal_role_and_channel("TXD") is None
    assert can_signal_role_and_channel("UART1_TX") is None
    assert can_module_data_role("TXD") == "tx"
    assert can_module_data_role("RX") == "rx"
    assert can_module_data_role("CAN1_TX") is None
    assert can_module_data_role("CANH") is None


def test_identified_can_module_generic_txd_rxd_pins_on_rails_request_review() -> None:
    source = can_module_connector_named_rail_netlist()
    findings = tuple(item for item in _report(source).findings if item.rule_id == RULE_ID)

    assert tuple(item.subject for item in findings) == (
        "J1.1: TXD on return-like net GND",
        "J1.2: RXD on supply-like net +3V3",
    )
    assert findings[0].evidence == {
        "pin": ("J1.1",),
        "pin_function": ("TXD",),
        "pin_role": ("tx",),
        "can_channel": ("can:module",),
        "assigned_net": ("GND",),
        "net_label_role_clue": ("return-like",),
        "component_pin_inventory": ("1", "2"),
        "can_module_identity": ("Connector_Generic:Conn_01x02 CAN transceiver module",),
    }
    assert all("explicitly identified CAN module" in item.message for item in findings)


def test_generic_serial_connectors_and_unidentified_modules_are_quiet() -> None:
    controls = (
        can_module_connector_named_rail_netlist(value="Serial connector"),
        can_module_connector_named_rail_netlist(value="CAN controller"),
        can_module_connector_named_rail_netlist(functions=("TXD", "RXD"), value="Module"),
    )
    for source in controls:
        assert not any(item.rule_id == RULE_ID for item in _report(source).findings)


def test_incomplete_or_ambiguous_can_module_pins_are_quiet() -> None:
    source = can_module_connector_named_rail_netlist()
    controls = (
        can_module_connector_named_rail_netlist(dnp=True),
        source.model_copy(update={"component_pin_numbers": {"J1": ("3", "4")}}),
        source.model_copy(update={"nets": {"GND": ("J1.1",), "+3V3": ("J1.1",)}}),
    )
    for control in controls:
        assert not any(item.rule_id == RULE_ID for item in _report(control).findings)

    one_unsupported_function = source.model_copy(
        update={"pin_functions": {"J1.1": "CANH", "J1.2": "RXD"}}
    )
    findings = tuple(
        item for item in _report(one_unsupported_function).findings if item.rule_id == RULE_ID
    )
    assert tuple(item.subject for item in findings) == ("J1.2: RXD on supply-like net +3V3",)


def test_neutral_labels_and_unsupported_functions_are_quiet() -> None:
    source = can_signal_on_named_rail_netlist(rail_name="CAN_TX")
    unsupported = source.model_copy(update={"pin_functions": {"U1.1": "CANH", "U1.2": "CANL"}})
    incomplete = source.model_copy(update={"component_pin_numbers": {"U1": ("2",)}})
    connector = can_connector_signal_on_named_rail_netlist(rail_name="CAN2_TX")
    connector_unsupported = connector.model_copy(
        update={"pin_functions": {**connector.pin_functions, "J1.1": "CANH"}}
    )

    for control in (source, unsupported, incomplete, connector, connector_unsupported):
        assert not any(item.rule_id == RULE_ID for item in _report(control).findings)


def test_dnp_open_ambiguous_duplicate_and_incomplete_connector_cases_are_skipped() -> None:
    source = can_signal_on_named_rail_netlist()
    controls = (
        source.model_copy(update={"dnp_components": ("U1",)}),
        source.model_copy(update={"nets": {"CAN1_RX": ("U1.2",)}}),
        source.model_copy(update={"nets": {**source.nets, "0V": ("U1.1",)}}),
        source.model_copy(update={"pin_functions": {"U1.1": "CAN1_TX", "u1.1": "CAN1_RX"}}),
        can_connector_signal_on_named_rail_netlist(rail_name="CAN2_TX"),
    )
    for control in controls:
        assert not any(item.rule_id == RULE_ID for item in _report(control).findings)

    connector = can_connector_signal_on_named_rail_netlist()
    connector_controls = (
        connector.model_copy(update={"dnp_components": ("J1",)}),
        connector.model_copy(update={"nets": {"CAN2_RX": ("J1.2",)}}),
        connector.model_copy(update={"nets": {"GND": ("J1.1",), "0V": ("J1.1",)}}),
        can_connector_signal_on_named_rail_netlist(pin="J1.2").model_copy(
            update={"component_pin_numbers": {"J1": ("1",)}}
        ),
    )
    for control in connector_controls:
        assert not any(item.rule_id == RULE_ID for item in _report(control).findings)


def test_project_policy_can_block_disable_or_ignore_an_intentional_strap() -> None:
    source = can_signal_on_named_rail_netlist(rail_name="GND")
    finding = next(item for item in _report(source).findings if item.rule_id == RULE_ID)
    blocked = _report(
        source,
        DesignLintPolicy(
            rules=(DesignLintRuleOverride(rule_id=RULE_ID, mode="block", reason="reviewed policy"),)
        ),
    )
    disabled = _report(
        source,
        DesignLintPolicy(
            rules=(DesignLintRuleOverride(rule_id=RULE_ID, mode="off", reason="reviewed policy"),)
        ),
    )
    ignored = _report(
        source,
        DesignLintPolicy(
            ignores=(
                DesignLintIgnore(
                    rule_id=RULE_ID,
                    fingerprint=finding.fingerprint,
                    reason="CAN TX is intentionally held inactive",
                ),
            )
        ),
    )

    assert blocked.status == "FAIL"
    assert (
        next(item for item in disabled.findings if item.rule_id == RULE_ID).disposition
        == "RULE_OFF"
    )
    assert (
        next(item for item in ignored.findings if item.rule_id == RULE_ID).disposition == "IGNORED"
    )


def test_mapping_order_is_stable_and_repaired_assignment_clears_review() -> None:
    fault = can_signal_on_named_rail_netlist()
    reordered = fault.model_copy(
        update={
            "nets": dict(reversed(tuple(fault.nets.items()))),
            "pin_functions": dict(reversed(tuple(fault.pin_functions.items()))),
        }
    )
    repaired = fault.model_copy(update={"nets": {"CAN1_TX": ("U1.1",), "CAN1_RX": ("U1.2",)}})

    findings = tuple(item for item in _report(fault).findings if item.rule_id == RULE_ID)
    reordered_findings = tuple(
        item for item in _report(reordered).findings if item.rule_id == RULE_ID
    )
    assert tuple(item.model_dump() for item in findings) == tuple(
        item.model_dump() for item in reordered_findings
    )
    assert not any(item.rule_id == RULE_ID for item in _report(repaired).findings)

    connector_fault = can_connector_signal_on_named_rail_netlist()
    connector_reordered = connector_fault.model_copy(
        update={
            "nets": dict(reversed(tuple(connector_fault.nets.items()))),
            "pin_functions": dict(reversed(tuple(connector_fault.pin_functions.items()))),
        }
    )
    connector_repaired = can_connector_signal_on_named_rail_netlist(rail_name="CAN2_TX")
    connector_findings = tuple(
        item for item in _report(connector_fault).findings if item.rule_id == RULE_ID
    )
    connector_reordered_findings = tuple(
        item for item in _report(connector_reordered).findings if item.rule_id == RULE_ID
    )
    assert tuple(item.model_dump() for item in connector_findings) == tuple(
        item.model_dump() for item in connector_reordered_findings
    )
    assert not any(item.rule_id == RULE_ID for item in _report(connector_repaired).findings)

    module_fault = can_module_connector_named_rail_netlist()
    module_reordered = module_fault.model_copy(
        update={
            "nets": dict(reversed(tuple(module_fault.nets.items()))),
            "pin_functions": dict(reversed(tuple(module_fault.pin_functions.items()))),
        }
    )
    module_repaired = module_fault.model_copy(
        update={"nets": {"CAN_TXD": ("J1.1",), "CAN_RXD": ("J1.2",)}}
    )
    module_findings = tuple(
        item for item in _report(module_fault).findings if item.rule_id == RULE_ID
    )
    module_reordered_findings = tuple(
        item for item in _report(module_reordered).findings if item.rule_id == RULE_ID
    )
    assert tuple(item.model_dump() for item in module_findings) == tuple(
        item.model_dump() for item in module_reordered_findings
    )
    assert not any(item.rule_id == RULE_ID for item in _report(module_repaired).findings)
