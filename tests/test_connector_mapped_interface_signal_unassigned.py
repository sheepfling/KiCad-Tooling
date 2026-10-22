"""Review generic signal contacts mapped by a complete connector interface."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.connector_coverage import evaluate as evaluate_connector_coverage
from kicad_tooling.hwrepo.design_lint import evaluate, fingerprint
from kicad_tooling.hwrepo.models import (
    ConnectorInterfaceReview,
    ConnectorInventoryReview,
    ContractCoachReport,
    DesignLintIgnore,
    DesignLintPolicy,
    DesignLintRuleOverride,
    InterfacePin,
    InterfaceRecord,
    NetlistContract,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.connector_lint, pytest.mark.interface_lint]

RULE_ID = "connector.mapped_interface_signal_unassigned"
PROJECT_ID = "synthetic-mapped-interface-signal"
NETLIST_SHA256 = "a" * 64
CATALOG_SHA256 = "b" * 64


def _interface(*, target_role: str = "signal") -> InterfaceRecord:
    return InterfaceRecord(
        id="synthetic-uart-port",
        revision="synthetic-1",
        pins=(
            InterfacePin(
                number="1",
                signal="UART_TX",
                role="signal",
                direction="output",
                voltage_domain="logic-3v3",
                mating="UART_RX",
                orientation="straight",
                mechanical_clearance="synthetic",
            ),
            InterfacePin(
                number="2",
                signal="UART_RX",
                role=target_role,
                direction="input",
                voltage_domain="logic-3v3",
                mating="UART_TX",
                orientation="straight",
                mechanical_clearance="synthetic",
            ),
            InterfacePin(
                number="3",
                signal="SIGNAL_RETURN",
                role="return",
                direction="passive",
                voltage_domain="signal-return",
                mating="SIGNAL_RETURN",
                orientation="straight",
                mechanical_clearance="synthetic",
            ),
        ),
    )


def _netlist(
    *,
    target_net: str | None = None,
    target_function: str = "Pin_2",
    target_type: str = "input",
    dnp: tuple[str, ...] = (),
) -> NetlistContract:
    nets = {"UART_TX": ("J1.1",), "SIGNAL_RETURN": ("J1.3",)}
    if target_net is not None:
        nets[target_net] = ("J1.2",)
    return NetlistContract(
        components={},
        nets=nets,
        dnp_components=dnp,
        component_symbols={"J1": "Synthetic:GenericUartPort"},
        component_pin_numbers={"J1": ("1", "2", "3")},
        pin_functions={"J1.1": "Pin_1", "J1.2": target_function, "J1.3": "Pin_3"},
        pin_electrical_types={"J1.1": "output", "J1.2": target_type, "J1.3": "passive"},
    )


def _coverage(
    source: NetlistContract,
    *,
    unconnected_reason: str | None = None,
    target_role: str = "signal",
):
    interface = _interface(target_role=target_role)
    review = ConnectorInterfaceReview(
        reference="J1",
        disposition="interface",
        basis="Synthetic independently reviewed UART connector pinout",
        interface_id=interface.id,
        pin_map={"1": "1", "2": "2", "3": "3"},
        unconnected_pin_reasons=({} if unconnected_reason is None else {"2": unconnected_reason}),
    )
    return evaluate_connector_coverage(
        source,
        (interface.id,),
        (review,),
        interfaces={interface.id: interface},
        interface_catalog_path="catalog/interfaces.json",
        interface_catalog_sha256=CATALOG_SHA256,
        inventory_review=ConnectorInventoryReview(
            basis="Synthetic review covered the complete connector inventory"
        ),
    )


def _lint(
    source: NetlistContract,
    *,
    unconnected_reason: str | None = None,
    target_role: str = "signal",
    policy: DesignLintPolicy | None = None,
):
    coverage = _coverage(
        source,
        unconnected_reason=unconnected_reason,
        target_role=target_role,
    )
    return _lint_with_coverage(source, coverage, policy=policy), coverage


def _lint_with_coverage(
    source: NetlistContract,
    coverage,
    *,
    policy: DesignLintPolicy | None = None,
):
    coach = ContractCoachReport(
        status="READY_FOR_REVIEW",
        project_id=PROJECT_ID,
        observed=source,
        netlist_sha256=NETLIST_SHA256,
    )
    return evaluate(
        PROJECT_ID,
        coach,
        policy or DesignLintPolicy(),
        connector_coverage=coverage,
    )


def _rule_findings(report):
    return tuple(item for item in report.findings if item.rule_id == RULE_ID)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_open_generic_mapped_signal_pin_requests_review_with_source_evidence() -> None:
    report, coverage = _lint(_netlist())

    assert coverage.status == "COMPLETE"
    assert len(_rule_findings(report)) == 1
    finding = _rule_findings(report)[0]
    assert report.status == "REVIEW"
    assert finding.subject == "J1.2: reviewed signal contact has no net assignment"
    assert finding.evidence == {
        "component_pin": ("J1.2",),
        "interface_pin_number": ("2",),
        "interface_signal": ("UART_RX",),
        "interface_role": ("signal",),
        "native_pin_function": ("Pin_2",),
        "native_pin_electrical_type": ("input",),
        "assigned_nets": (),
        "interface_catalog_sha256": (CATALOG_SHA256,),
    }


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_connected_documented_open_and_ineligible_pins_are_controls() -> None:
    connected, _ = _lint(_netlist(target_net="UART_RX"))
    documented_open, coverage = _lint(
        _netlist(),
        unconnected_reason="Reviewed as an intentionally unused service contact",
    )
    dnp, _ = _lint(_netlist(dnp=("J1",)))
    other_role, _ = _lint(_netlist(), target_role="return")
    native_power, _ = _lint(_netlist(target_type="power_in"))

    assert not _rule_findings(connected)
    assert not _rule_findings(documented_open)
    assert coverage.entries[0].mapped_pins[1].unconnected_reason == (
        "Reviewed as an intentionally unused service contact"
    )
    assert not _rule_findings(dnp)
    assert not _rule_findings(other_role)
    assert not _rule_findings(native_power)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_reasoned_open_pin_with_a_net_assignment_invalidates_coverage() -> None:
    report, coverage = _lint(
        _netlist(target_net="UART_RX"),
        unconnected_reason="Reviewed as intentionally unused",
    )

    assert coverage.status == "INCOMPLETE"
    assert coverage.entries[0].status == "INCOMPLETE"
    assert (
        "Pins with intentional no-connect reasons have net assignments"
        in (coverage.entries[0].issues[0])
    )
    assert not _rule_findings(report)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_source_mismatched_or_digestless_coverage_cannot_trigger_review() -> None:
    source = _netlist()
    coverage = _coverage(source)
    changed_source = source.model_copy(update={"nets": {**source.nets, "UART_RX": ("J1.2",)}})
    stale = _lint_with_coverage(changed_source, coverage)
    digestless = _lint_with_coverage(
        source,
        coverage.model_copy(update={"interface_catalog_sha256": None}),
    )

    assert not _rule_findings(stale)
    assert not _rule_findings(digestless)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_review_is_stable_under_input_order_and_clears_when_connected() -> None:
    source = _netlist()
    reordered = source.model_copy(
        update={
            "nets": dict(reversed(tuple(source.nets.items()))),
            "pin_functions": dict(reversed(tuple(source.pin_functions.items()))),
            "pin_electrical_types": dict(reversed(tuple(source.pin_electrical_types.items()))),
            "component_pin_numbers": dict(reversed(tuple(source.component_pin_numbers.items()))),
        }
    )
    first = _rule_findings(_lint(source)[0])[0]
    second = _rule_findings(_lint(reordered)[0])[0]
    repaired, _ = _lint(_netlist(target_net="UART_RX"))

    assert (first.fingerprint, first.evidence) == (second.fingerprint, second.evidence)
    assert first.fingerprint == fingerprint(first)
    assert not _rule_findings(repaired)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_review_obeys_project_policy_and_exact_ignore() -> None:
    source = _netlist()
    baseline = _rule_findings(_lint(source)[0])[0]
    blocked, _ = _lint(
        source,
        policy=DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=RULE_ID,
                    mode="block",
                    reason="Synthetic project requires mapped signal review.",
                ),
            )
        ),
    )
    disabled, _ = _lint(
        source,
        policy=DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=RULE_ID,
                    mode="off",
                    reason="Synthetic control disables this review.",
                ),
            )
        ),
    )
    ignored, _ = _lint(
        source,
        policy=DesignLintPolicy(
            ignores=(
                DesignLintIgnore(
                    rule_id=RULE_ID,
                    fingerprint=baseline.fingerprint,
                    reason="Synthetic control records an intentional open contact.",
                ),
            )
        ),
    )

    assert blocked.status == "FAIL"
    assert disabled.status == "PASS"
    assert any(item.disposition == "RULE_OFF" for item in _rule_findings(disabled))
    assert any(item.disposition == "IGNORED" for item in _rule_findings(ignored))
