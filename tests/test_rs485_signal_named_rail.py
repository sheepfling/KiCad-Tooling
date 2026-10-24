"""Focused regressions for explicit RS-485 data pins on named rails."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.design_lint_finding_models import DesignLintFinding, DesignLintIgnore
from kicad_tooling.hwrepo.design_lint_policy_models import DesignLintPolicy
from kicad_tooling.hwrepo.design_lint_report_models import DesignLintReport
from kicad_tooling.hwrepo.models import DesignLintRuleOverride, NetlistContract
from kicad_tooling.hwrepo.rs485_signal_named_rail import rs485_signal_on_named_rail_candidates
from tests.design_lint_fixtures import coach
from tests.design_lint_fixtures.rs485_signal_named_rail import rs485_signal_named_rail_netlist

RULE_ID = "bus.rs485_signal_on_named_rail"

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.interface_lint,
    pytest.mark.design_lint_rule(rule_id=RULE_ID),
]


def _report(source: NetlistContract, policy: DesignLintPolicy | None = None) -> DesignLintReport:
    return evaluate(
        "synthetic-rs485-signal-named-rail",
        coach(source),
        DesignLintPolicy() if policy is None else policy,
    )


def _findings(report: DesignLintReport) -> tuple[DesignLintFinding, ...]:
    return tuple(item for item in report.findings if item.rule_id == RULE_ID)


@pytest.mark.parametrize(
    ("pin", "rail", "function", "role"),
    (
        ("U1.1", "GND", "D", "tx"),
        ("U1.1", "+3V3", "DI", "tx"),
        ("U1.2", "GND", "R", "rx"),
        ("U1.2", "+5V", "RO", "rx"),
    ),
)
def test_explicit_rs485_data_pins_on_named_rails_request_review(
    pin: str, rail: str, function: str, role: str
) -> None:
    source = rs485_signal_named_rail_netlist(
        pin=pin, rail_name=rail, function=function, identity="MAX3485"
    )
    candidate = next(
        item for item in rs485_signal_on_named_rail_candidates(source) if item.rule_id == RULE_ID
    )
    finding = _findings(_report(source))[0]

    assert (
        candidate.subject
        == f"{pin}: {function} on {'return-like' if rail == 'GND' else 'supply-like'} net {rail}"
    )
    assert finding.mode == "review"
    assert finding.evidence["rs485_data_role"] == (role,)
    assert finding.evidence["identity_basis"] == ("Synthetic:Rs485Transceiver MAX3485",)
    assert _report(source).status == "REVIEW"
    assert "not proof of electrical potential" in finding.message


def test_generic_d_r_functions_and_neutral_net_labels_are_quiet() -> None:
    explicit = rs485_signal_named_rail_netlist(rail_name="HOST_TX")
    generic = rs485_signal_named_rail_netlist(
        identity="Generic logic IC", symbol="Logic:Device", rail_name="GND"
    )
    unsupported = rs485_signal_named_rail_netlist(function="DE")
    can_device = rs485_signal_named_rail_netlist(
        identity="SN65HVD230", symbol="Vendor:Transceiver", rail_name="GND"
    )

    for control in (explicit, generic, unsupported, can_device):
        assert not _findings(_report(control))


def test_bounded_identity_and_data_function_aliases_are_supported() -> None:
    controls = (
        rs485_signal_named_rail_netlist(identity="SP3485", symbol="Vendor:Transceiver"),
        rs485_signal_named_rail_netlist(
            identity="Synthetic IC", symbol="Vendor:SN65HVD485E", function="DriverDataIn"
        ),
        rs485_signal_named_rail_netlist(
            identity="ADM488", symbol="Vendor:Transceiver", pin="U1.2", function="ReceiverOutput"
        ),
    )
    for source in controls:
        assert len(_findings(_report(source))) == 1


def test_dnp_open_ambiguous_duplicate_and_incomplete_evidence_are_skipped() -> None:
    source = rs485_signal_named_rail_netlist()
    controls = (
        rs485_signal_named_rail_netlist(dnp=True),
        source.model_copy(update={"nets": {"HOST_RX": ("U1.2",)}}),
        source.model_copy(update={"nets": {**source.nets, "0V": ("U1.1",)}}),
        source.model_copy(update={"component_pin_numbers": {"U1": ("2",)}}),
        source.model_copy(
            update={
                "components": {
                    "U1": source.components["U1"].model_copy(update={"value": "Connector"})
                },
                "component_symbols": {"U1": "Connector:Conn_01x02"},
            }
        ),
    )
    for control in controls:
        assert not _findings(_report(control))


def test_project_policy_can_block_disable_or_ignore_an_intentional_strap() -> None:
    source = rs485_signal_named_rail_netlist()
    finding = _findings(_report(source))[0]
    blocked = _report(
        source,
        DesignLintPolicy(
            rules=(DesignLintRuleOverride(rule_id=RULE_ID, mode="block", reason="required"),)
        ),
    )
    disabled = _report(
        source,
        DesignLintPolicy(
            rules=(DesignLintRuleOverride(rule_id=RULE_ID, mode="off", reason="not used"),)
        ),
    )
    ignored = _report(
        source,
        DesignLintPolicy(
            ignores=(
                DesignLintIgnore(
                    rule_id=RULE_ID,
                    fingerprint=finding.fingerprint,
                    reason="intentional strap",
                ),
            )
        ),
    )

    assert blocked.status == "FAIL"
    assert _findings(disabled)[0].disposition == "RULE_OFF"
    assert _findings(ignored)[0].disposition == "IGNORED"


def test_reordering_is_stable_and_moving_the_pin_to_a_signal_net_clears_review() -> None:
    fault = rs485_signal_named_rail_netlist()
    reordered = fault.model_copy(
        update={
            "nets": dict(reversed(tuple(fault.nets.items()))),
            "pin_functions": dict(reversed(tuple(fault.pin_functions.items()))),
        }
    )
    repaired = fault.model_copy(update={"nets": {"HOST_TX": ("U1.1",), "HOST_RX": ("U1.2",)}})

    assert tuple(item.model_dump() for item in _findings(_report(fault))) == tuple(
        item.model_dump() for item in _findings(_report(reordered))
    )
    assert not _findings(_report(repaired))
