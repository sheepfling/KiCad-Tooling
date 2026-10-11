"""Synthetic connector identity and population regressions."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.models import (
    ComponentContract,
    ConnectorCoverageEntry,
    ConnectorCoverageReport,
    DesignLintPolicy,
    NetlistContract,
)
from tests.design_lint_fixtures import (
    coach,
    custom_reviewed_connector_peers,
    multiconductor_connector,
    standard_connector_identity_peers,
)

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.connector_lint,
    pytest.mark.power_lint,
    pytest.mark.return_path_lint,
]


def test_connector_population_heuristics_ignore_dnp_instances() -> None:
    peers = NetlistContract(
        components={},
        nets={
            "USB_RETURN": ("J1.1",),
            "SERIAL_RETURN": ("J2.1",),
            "DATA_A": ("J2.3",),
            "DATA_B": ("J2.4",),
            "DATA_C": ("J2.5",),
        },
        component_symbols={"J1": "Synthetic:Port", "J2": "Synthetic:Port"},
        pin_functions={
            "J1.1": "GND",
            "J2.1": "GND",
            "J2.2": "VBUS",
            "J2.3": "1",
            "J2.4": "2",
            "J2.5": "3",
        },
    )
    populated = evaluate("synthetic-populated-ports", coach(peers), DesignLintPolicy())
    assert {item.rule_id for item in populated.findings} == {
        "connector.repeated_pin_function",
        "connector.unconnected_supply_pin",
    }
    dnp_peers = peers.model_copy(update={"dnp_components": ("j2",)})
    dnp = evaluate("synthetic-dnp-ports", coach(dnp_peers), DesignLintPolicy())
    assert not dnp.findings
    open_named_pins = NetlistContract(
        components={},
        nets={"DATA": ("J3.1",)},
        dnp_components=("J3",),
        component_symbols={"J3": "Synthetic:Port"},
        pin_functions={"J3.1": "DATA", "J3.2": "VBUS", "J3.3": "GND"},
    )
    open_pin_report = evaluate(
        "synthetic-dnp-open-pins", coach(open_named_pins), DesignLintPolicy()
    )
    assert not open_pin_report.findings
    no_return = multiconductor_connector(return_named=False)
    fitted_no_return = evaluate("synthetic-fitted-no-return", coach(no_return), DesignLintPolicy())
    assert "connector.no_connected_return" in {item.rule_id for item in fitted_no_return.findings}
    dnp_no_return = evaluate(
        "synthetic-dnp-no-return",
        coach(no_return.model_copy(update={"dnp_components": ("J1",)})),
        DesignLintPolicy(),
    )
    assert "connector.no_connected_return" not in {item.rule_id for item in dnp_no_return.findings}


def test_connector_identity_uses_standard_symbols_and_project_reviewed_custom_refs() -> None:
    fault = evaluate(
        "synthetic-standard-connector-identities",
        coach(standard_connector_identity_peers()),
        DesignLintPolicy(),
    )
    fault_rules = {item.rule_id for item in fault.findings}
    assert "connector.repeated_pin_function" in fault_rules
    assert "component.unconnected_supply_pin" not in fault_rules
    assert "power.ic_rail_without_fitted_capacitor" not in fault_rules
    repeated = next(
        item for item in fault.findings if item.rule_id == "connector.repeated_pin_function"
    )
    assert "U7.2" in repeated.evidence
    control = evaluate(
        "synthetic-standard-connector-control",
        coach(standard_connector_identity_peers(common_return=True, supply_connected=True)),
        DesignLintPolicy(),
    )
    assert not control.findings
    dnp = evaluate(
        "synthetic-standard-connector-dnp-control",
        coach(standard_connector_identity_peers(dnp=("U7",))),
        DesignLintPolicy(),
    )
    assert not dnp.findings
    generic_peer_fault = NetlistContract(
        components={
            reference: ComponentContract(value="Synthetic connector", footprint="")
            for reference in ("J1", "U7", "J2")
        },
        nets={"GND": ("J1.1", "U7.1", "J2.1"), "DATA": ("J1.2", "J2.2")},
        component_symbols={
            reference: "Connector_Generic:Conn_01x02" for reference in ("J1", "U7", "J2")
        },
        component_pin_numbers={reference: ("1", "2") for reference in ("J1", "U7", "J2")},
        pin_functions={f"{reference}.1": "GND" for reference in ("J1", "U7", "J2")},
    )
    peer_fault = evaluate(
        "synthetic-standard-connector-peer-outlier", coach(generic_peer_fault), DesignLintPolicy()
    )
    peer_finding = next(
        item
        for item in peer_fault.findings
        if item.rule_id == "connector.peer_pin_assignment_outlier"
    )
    assert "U7.2" in peer_finding.evidence
    peer_control = evaluate(
        "synthetic-standard-connector-peer-control",
        coach(
            generic_peer_fault.model_copy(
                update={"nets": {"GND": ("J1.1", "U7.1", "J2.1"), "DATA": ("J1.2", "U7.2", "J2.2")}}
            )
        ),
        DesignLintPolicy(),
    )
    assert "connector.peer_pin_assignment_outlier" not in {
        item.rule_id for item in peer_control.findings
    }
    custom = custom_reviewed_connector_peers()
    unreviewed = evaluate(
        "synthetic-custom-connector-unreviewed", coach(custom), DesignLintPolicy()
    )
    assert "connector.repeated_pin_function" not in {item.rule_id for item in unreviewed.findings}
    coverage = ConnectorCoverageReport(
        status="COMPLETE",
        scope="Synthetic project-reviewed interface references",
        inventory_review_basis="The synthetic interface inventory is complete",
        entries=(
            ConnectorCoverageEntry(
                reference="A1",
                status="COVERED",
                interface_id="synthetic_port",
                basis="The symbol was reviewed as an external connector",
            ),
            ConnectorCoverageEntry(
                reference="A2",
                status="COVERED",
                interface_id="synthetic_port",
                basis="The symbol was reviewed as an external connector",
            ),
        ),
    )
    reviewed = evaluate(
        "synthetic-custom-connector-reviewed",
        coach(custom),
        DesignLintPolicy(),
        connector_coverage=coverage,
    )
    assert "connector.repeated_pin_function" in {item.rule_id for item in reviewed.findings}

    def return_coverage_netlist(*, connected_return: bool) -> NetlistContract:
        nets = {"DATA_A": ("U8.1",), "DATA_B": ("U8.2",), "DATA_C": ("U8.3",)}
        pin_functions = {f"U8.{number}": str(number) for number in (1, 2, 3)}
        pin_numbers = ("1", "2", "3")
        if connected_return:
            nets["GND"] = ("U8.4",)
            pin_functions["U8.4"] = "GND"
            pin_numbers = (*pin_numbers, "4")
        return NetlistContract(
            components={"U8": ComponentContract(value="Synthetic port", footprint="")},
            nets=nets,
            component_symbols={"U8": "Connector_Generic:Conn_01x04"},
            component_pin_numbers={"U8": pin_numbers},
            pin_functions=pin_functions,
        )

    no_return = evaluate(
        "synthetic-standard-connector-no-return",
        coach(return_coverage_netlist(connected_return=False)),
        DesignLintPolicy(),
    )
    assert "connector.no_connected_return" in {item.rule_id for item in no_return.findings}
    with_return = evaluate(
        "synthetic-standard-connector-return-control",
        coach(return_coverage_netlist(connected_return=True)),
        DesignLintPolicy(),
    )
    assert "connector.no_connected_return" not in {item.rule_id for item in with_return.findings}
