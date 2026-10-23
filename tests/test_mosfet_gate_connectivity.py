"""Synthetic review cases for unsupported or unconnected MOSFET gate nets."""

from __future__ import annotations

from collections.abc import Mapping

import pytest

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.design_lint_finding_models import (
    DesignLintFinding,
    DesignLintIgnore,
    DesignLintRuleOverride,
)
from kicad_tooling.hwrepo.design_lint_policy_models import DesignLintPolicy
from kicad_tooling.hwrepo.design_lint_report_models import DesignLintReport
from kicad_tooling.hwrepo.models import ComponentContract, ContractCoachReport, NetlistContract

pytestmark = [pytest.mark.design_lint, pytest.mark.component_lint]

RULE_ID = "component.mosfet_gate_without_peer"
PROJECT_ID = "synthetic-mosfet-gate-connectivity"
SUPPORTED_NATIVE_SYMBOLS = (
    "Transistor_FET:Q_NMOS_DGS",
    "Transistor_FET:Q_NMOS_DSG",
    "Transistor_FET:Q_NMOS_GDS",
    "Transistor_FET:Q_NMOS_GSD",
    "Transistor_FET:Q_NMOS_SGD",
    "Transistor_FET:Q_PMOS_DGS",
    "Transistor_FET:Q_PMOS_DSG",
    "Transistor_FET:Q_PMOS_GDS",
    "Transistor_FET:Q_PMOS_GSD",
    "Transistor_FET:Q_PMOS_SDG",
    "Transistor_FET:Q_PMOS_SGD",
)


def mosfet_netlist(
    *,
    gate_net_members: tuple[str, ...] | None = None,
    symbol: str = "Transistor_FET:Q_NMOS_GDS",
    dnp: tuple[str, ...] = (),
    inventory: tuple[str, ...] = ("1", "2", "3"),
    functions: Mapping[str, str] | None = None,
) -> NetlistContract:
    """Build one supported device with an independently varied gate connection."""
    components = {"Q1": ComponentContract(value="Synthetic NMOS", footprint="Synthetic:TO-220")}
    component_symbols = {"Q1": symbol}
    component_pin_numbers = {"Q1": inventory}
    pin_functions = {"Q1.1": "D", "Q1.2": "G", "Q1.3": "S"}
    nets: dict[str, tuple[str, ...]] = {"DRAIN": ("Q1.1",), "SOURCE": ("Q1.3",)}
    unconnected_nets = {"unconnected": ("Q1.2",)}
    if gate_net_members is not None:
        pin_functions.update(functions or {})
        for member in gate_net_members:
            reference, number = member.rsplit(".", 1)
            components[reference] = ComponentContract(
                value="Synthetic peer", footprint="Synthetic:Peer"
            )
            component_symbols[reference] = {
                "U": "Synthetic:Driver_OUT",
                "J": "Connector_Generic:Conn_01x01",
                "R": "Device:R",
            }.get(reference[:1].upper(), "Synthetic:Peer")
            component_pin_numbers[reference] = (number,)
            pin_functions[member] = "OUT" if reference[:1].upper() == "U" else "Passive"
        nets["GATE_CONTROL"] = ("Q1.2", *gate_net_members)
        unconnected_nets = {}
    elif functions is not None:
        pin_functions.update(functions)
    return NetlistContract(
        components=components,
        nets=nets,
        unconnected_nets=unconnected_nets,
        dnp_components=dnp,
        component_symbols=component_symbols,
        component_pin_numbers=component_pin_numbers,
        pin_functions=pin_functions,
    )


def lint(netlist: NetlistContract, policy: DesignLintPolicy | None = None) -> DesignLintReport:
    coach = ContractCoachReport(
        status="READY_FOR_REVIEW",
        project_id=PROJECT_ID,
        observed=netlist,
        netlist_sha256="a" * 64,
    )
    return evaluate(PROJECT_ID, coach, policy or DesignLintPolicy())


def findings(report: DesignLintReport) -> tuple[DesignLintFinding, ...]:
    return tuple(item for item in report.findings if item.rule_id == RULE_ID)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_unconnected_supported_mosfet_gate_requests_review() -> None:
    report = lint(mosfet_netlist())

    assert report.status == "REVIEW"
    finding = findings(report)[0]
    assert finding.subject == "Q1.2: MOSFET gate has no other fitted pin on its net"
    assert finding.evidence == {
        "component": ("Q1",),
        "symbol": ("Transistor_FET:Q_NMOS_GDS",),
        "gate_pin": ("Q1.2",),
        "gate_function": ("G",),
        "assigned_net": ("<unassigned>",),
        "other_fitted_net_members": (),
    }


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
@pytest.mark.parametrize("symbol", SUPPORTED_NATIVE_SYMBOLS)
def test_supported_symbol_variants_request_review(symbol: str) -> None:
    report = lint(mosfet_netlist(symbol=symbol))

    assert len(findings(report)) == 1
    assert findings(report)[0].evidence["symbol"] == (symbol,)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
@pytest.mark.parametrize("gate_function", ("G", "Gate"))
def test_supported_gate_function_aliases_request_review(gate_function: str) -> None:
    report = lint(mosfet_netlist(functions={"Q1.2": gate_function}))

    assert findings(report)[0].evidence["gate_function"] == (gate_function,)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_single_pin_assigned_gate_net_requests_review() -> None:
    report = lint(mosfet_netlist(gate_net_members=()))

    assert findings(report)[0].evidence["assigned_net"] == ("GATE_CONTROL",)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
@pytest.mark.parametrize(
    "peer",
    (
        pytest.param("U1.1", id="driver-peer"),
        pytest.param("J1.1", id="external-connector-peer"),
        pytest.param("R1.1", id="passive-bias-peer"),
    ),
)
def test_any_fitted_peer_on_the_gate_net_is_a_control(peer: str) -> None:
    report = lint(mosfet_netlist(gate_net_members=(peer,)))

    assert report.status == "PASS"
    assert not findings(report)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_dnp_peer_does_not_clear_gate_review() -> None:
    observed = mosfet_netlist(gate_net_members=("U1.1",), dnp=("U1",))

    report = lint(observed)

    assert report.status == "REVIEW"
    assert len(findings(report)) == 1


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
@pytest.mark.parametrize(
    ("symbol", "inventory", "functions", "dnp"),
    (
        pytest.param("Synthetic:Q_NMOS_GDS", ("1", "2", "3"), None, (), id="unknown-symbol"),
        pytest.param("Transistor_FET:Q_NMOS_GDSD", ("1", "2", "3", "4"), None, (), id="multi-gate"),
        pytest.param("Transistor_FET:Q_NMOS_GDS", ("1", "2"), None, (), id="incomplete-inventory"),
        pytest.param(
            "Transistor_FET:Q_NMOS_GDS",
            ("1", "2", "3"),
            {"Q1.2": "G1"},
            (),
            id="unrecognized-gate-function",
        ),
        pytest.param("Transistor_FET:Q_NMOS_GDS", ("1", "2", "3"), None, ("Q1",), id="dnp-device"),
    ),
)
def test_unsupported_or_unfitted_devices_are_controls(
    symbol: str,
    inventory: tuple[str, ...],
    functions: Mapping[str, str] | None,
    dnp: tuple[str, ...],
) -> None:
    report = lint(mosfet_netlist(symbol=symbol, inventory=inventory, functions=functions, dnp=dnp))

    assert report.status == "PASS"
    assert not findings(report)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_unlisted_native_symbol_is_not_assumed_supported() -> None:
    report = lint(mosfet_netlist(symbol="Transistor_FET:Q_NMOS_SDG"))

    assert report.status == "PASS"
    assert not findings(report)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_peer_membership_order_does_not_change_the_finding_or_its_fingerprint() -> None:
    first = lint(mosfet_netlist())
    reordered = mosfet_netlist().model_copy(
        update={"nets": dict(reversed(tuple(mosfet_netlist().nets.items())))}
    )

    assert (findings(first)[0].fingerprint, findings(first)[0].evidence) == (
        findings(lint(reordered))[0].fingerprint,
        findings(lint(reordered))[0].evidence,
    )


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_project_can_block_disable_or_exact_ignore_the_gate_review() -> None:
    default = lint(mosfet_netlist())
    default_finding = findings(default)[0]
    blocked = lint(
        mosfet_netlist(),
        DesignLintPolicy(
            rules=(DesignLintRuleOverride(rule_id=RULE_ID, mode="block", reason="Review gates"),)
        ),
    )
    disabled = lint(
        mosfet_netlist(),
        DesignLintPolicy(
            rules=(DesignLintRuleOverride(rule_id=RULE_ID, mode="off", reason="Unused switch"),)
        ),
    )
    ignored = lint(
        mosfet_netlist(),
        DesignLintPolicy(
            ignores=(
                DesignLintIgnore(
                    rule_id=RULE_ID,
                    fingerprint=default_finding.fingerprint,
                    reason="Reviewed as intentionally open",
                ),
            )
        ),
    )

    assert blocked.status == "FAIL"
    assert findings(blocked)[0].mode == "block"
    assert disabled.status == "PASS"
    assert findings(disabled)[0].disposition == "RULE_OFF"
    assert ignored.status == "PASS"
    assert findings(ignored)[0].disposition == "IGNORED"
