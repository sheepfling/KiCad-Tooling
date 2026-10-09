"""Pytest regressions for source-matched connector peer comparison scopes."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from kicad_tooling.hwrepo.connector_coverage import (
    evaluate as evaluate_connector_coverage,
)
from kicad_tooling.hwrepo.connector_coverage import (
    source_matched_connector_peer_assignment_groups,
)
from kicad_tooling.hwrepo.connector_pins import connector_peer_pin_assignment_outliers
from kicad_tooling.hwrepo.design_lint import evaluate as evaluate_design_lint
from kicad_tooling.hwrepo.design_lint import text_report
from kicad_tooling.hwrepo.models import (
    ConnectorCoverageReport,
    ConnectorInterfaceReview,
    ContractCoachReport,
    DesignLintPolicy,
    InterfacePin,
    InterfaceRecord,
    NetlistContract,
)
from tests.test_connector_coverage import (
    inventory_review,
    uart_header_coverage,
    uart_header_interface,
    uart_peer_netlist,
)


@pytest.mark.parametrize(
    "groups",
    (
        pytest.param(("uart-1", "uart-2"), id="independent-interfaces"),
        pytest.param(("uart-ports", "uart-ports"), id="shared-peer-set"),
    ),
)
def test_peer_assignment_scope_report_is_stable_under_input_reordering(
    groups: tuple[str, str],
) -> None:
    observed = uart_peer_netlist(split_return=True)
    reordered = observed.model_copy(
        update={
            "nets": dict(reversed(tuple(observed.nets.items()))),
            "component_symbols": dict(reversed(tuple(observed.component_symbols.items()))),
            "component_pin_numbers": {
                reference: tuple(reversed(pin_numbers))
                for reference, pin_numbers in reversed(
                    tuple(observed.component_pin_numbers.items())
                )
            },
            "pin_functions": dict(reversed(tuple(observed.pin_functions.items()))),
        }
    )

    reports = tuple(
        evaluate_design_lint(
            "synthetic-peer-assignment-order",
            ContractCoachReport(
                status="READY_FOR_REVIEW",
                project_id="synthetic-peer-assignment-order",
                observed=netlist,
                netlist_sha256="f" * 64,
            ),
            DesignLintPolicy(),
            connector_coverage=uart_header_coverage(
                netlist,
                groups=groups,
                reverse_inputs=reverse_inputs,
            ),
        ).model_dump(mode="json")
        for netlist, reverse_inputs in ((observed, False), (reordered, True))
    )

    assert reports[0] == reports[1]


def test_peer_assignment_groups_scope_generic_pins_but_keep_return_review_global() -> None:
    with pytest.raises(ValidationError):
        ConnectorInterfaceReview(
            reference="J1",
            disposition="interface",
            basis="Reviewed J1's interface pinout",
            interface_id="uart-header-1",
            pin_map={"1": "1"},
            peer_assignment_group="uart-1",
        )
    split = uart_peer_netlist(split_return=True)
    separate_groups = uart_header_coverage(split, groups=("uart-1", "uart-2"))
    assert source_matched_connector_peer_assignment_groups(split, separate_groups) == {
        "J1": ("uart-1", "Reviewed J1 as a member of peer-assignment group uart-1"),
        "J2": ("uart-2", "Reviewed J2 as a member of peer-assignment group uart-2"),
    }
    separate_report = evaluate_design_lint(
        "synthetic-separate-uart-peer-groups",
        ContractCoachReport(
            status="READY_FOR_REVIEW",
            project_id="synthetic-separate-uart-peer-groups",
            observed=split,
            netlist_sha256="b" * 64,
        ),
        DesignLintPolicy(),
        connector_coverage=separate_groups,
    )
    assert not {
        finding.rule_id
        for finding in separate_report.findings
        if finding.rule_id
        in {"connector.peer_pin_assignment_outlier", "connector.peer_pin_assignment_divergence"}
    }
    return_finding = next(
        finding
        for finding in separate_report.findings
        if finding.rule_id == "connector.repeated_pin_function"
    )
    assert return_finding.evidence["J1.3"] == ("UART1_RETURN",)
    assert return_finding.evidence["J2.3"] == ("UART2_RETURN",)
    supply_netlist = NetlistContract(
        components={},
        nets={"PORT1_3V3": ("J1.2",), "PORT2_3V3": ("J2.2",)},
        component_symbols={
            "J1": "Connector_Generic:Conn_01x02",
            "J2": "Connector_Generic:Conn_01x02",
        },
        component_pin_numbers={"J1": ("1", "2"), "J2": ("1", "2")},
        pin_functions={"J1.1": "Pin_1", "J1.2": "Pin_2", "J2.1": "Pin_1", "J2.2": "Pin_2"},
    )
    supply_interface = InterfaceRecord(
        id="two-pin-supply",
        revision="synthetic-1",
        pins=(
            InterfacePin(
                number="1",
                signal="SIGNAL",
                role="signal",
                direction="bidirectional",
                voltage_domain="logic-3v3",
                mating="SIGNAL",
                orientation="straight",
                mechanical_clearance="synthetic",
            ),
            InterfacePin(
                number="2",
                signal="3V3",
                role="supply",
                direction="power_out",
                voltage_domain="logic-3v3",
                mating="3V3",
                orientation="straight",
                mechanical_clearance="synthetic",
            ),
        ),
    )
    supply_reviews = tuple(
        ConnectorInterfaceReview(
            reference=reference,
            disposition="interface",
            basis=f"Reviewed {reference} supply interface",
            interface_id="two-pin-supply",
            pin_map={"1": "1", "2": "2"},
            peer_assignment_group=group,
            peer_assignment_basis=f"Reviewed {reference} in group {group}",
        )
        for (reference, group) in (("J1", "power-domain-1"), ("J2", "power-domain-2"))
    )
    supply_coverage = evaluate_connector_coverage(
        supply_netlist,
        ("two-pin-supply",),
        supply_reviews,
        interfaces={"two-pin-supply": supply_interface},
        interface_catalog_path="catalog/interfaces.json",
        interface_catalog_sha256="f" * 64,
        inventory_review=inventory_review(),
    )
    supply_report = evaluate_design_lint(
        "synthetic-cross-group-supply-review",
        ContractCoachReport(
            status="READY_FOR_REVIEW",
            project_id="synthetic-cross-group-supply-review",
            observed=supply_netlist,
            netlist_sha256="f" * 64,
        ),
        DesignLintPolicy(),
        connector_coverage=supply_coverage,
    )
    supply_finding = next(
        finding
        for finding in supply_report.findings
        if finding.rule_id == "connector.repeated_pin_function"
    )
    assert supply_finding.evidence["J1.2"] == ("PORT1_3V3",)
    assert supply_finding.evidence["J2.2"] == ("PORT2_3V3",)
    same_group = uart_header_coverage(split, groups=("uart-ports", "uart-ports"))
    same_group_report = evaluate_design_lint(
        "synthetic-same-uart-peer-group",
        ContractCoachReport(
            status="READY_FOR_REVIEW",
            project_id="synthetic-same-uart-peer-group",
            observed=split,
            netlist_sha256="c" * 64,
        ),
        DesignLintPolicy(),
        connector_coverage=same_group,
    )
    generic_findings = tuple(
        finding
        for finding in same_group_report.findings
        if finding.rule_id == "connector.peer_pin_assignment_divergence"
    )
    assert len(generic_findings) == 2
    assert all(
        finding.evidence["peer_assignment_group"] == ("uart-ports",) for finding in generic_findings
    )
    assert all("peer-assignment group" in finding.message for finding in generic_findings)
    expected_peer_basis = (
        "J1: uart-ports; Reviewed J1 as a member of peer-assignment group uart-ports",
        "J2: uart-ports; Reviewed J2 as a member of peer-assignment group uart-ports",
    )
    assert all(
        finding.evidence["peer_assignment_basis"] == expected_peer_basis
        for finding in generic_findings
    )
    rendered = text_report(same_group_report)
    assert "Peer-assignment group: uart-ports" in rendered, rendered
    assert "Peer-assignment basis: Reviewed J1 as a member" in rendered, rendered
    outlier_netlist = NetlistContract(
        components={},
        nets={"UART1_TX": ("J1.1", "J2.1"), "UART2_TX": ("J3.1",)},
        component_symbols={
            reference: "Synthetic:PeripheralPort" for reference in ("J1", "J2", "J3")
        },
        component_pin_numbers={reference: ("1",) for reference in ("J1", "J2", "J3")},
        pin_functions={f"J{index}.1": "Pin_1" for index in (1, 2, 3)},
    )
    assert connector_peer_pin_assignment_outliers(outlier_netlist)[0].outlier_pins == ("J3.1",)
    assert not connector_peer_pin_assignment_outliers(
        outlier_netlist,
        peer_assignment_groups={
            "J1": ("uart-1", "Reviewed UART1 peer pins"),
            "J2": ("uart-1", "Reviewed UART1 peer pins"),
            "J3": ("uart-2", "Reviewed UART2 peer pins"),
        },
    )
    incomplete = evaluate_connector_coverage(
        split,
        ("uart-header-1",),
        (
            ConnectorInterfaceReview(
                reference="J1",
                disposition="interface",
                basis="Reviewed J1 as a 3.3 V UART interface",
                interface_id="uart-header-1",
                pin_map={"1": "1", "2": "2", "3": "3"},
                peer_assignment_group="uart-1",
                peer_assignment_basis="Reviewed J1's comparison group",
            ),
        ),
        interfaces={"uart-header-1": uart_header_interface("uart-header-1")},
        interface_catalog_path="catalog/interfaces.json",
        interface_catalog_sha256="a" * 64,
        inventory_review=inventory_review(),
    )
    incomplete_report = evaluate_design_lint(
        "synthetic-incomplete-uart-peer-groups",
        ContractCoachReport(
            status="READY_FOR_REVIEW",
            project_id="synthetic-incomplete-uart-peer-groups",
            observed=split,
            netlist_sha256="d" * 64,
        ),
        DesignLintPolicy(),
        connector_coverage=incomplete,
    )
    assert any(
        finding.rule_id == "connector.peer_pin_assignment_divergence"
        for finding in incomplete_report.findings
    ), "an unreviewed peer keeps the conservative comparison active"
    changed_nets = dict(split.nets)
    changed_nets.pop("UART2_TX")
    changed_nets["UART2_TX_CHANGED"] = ("J2.1",)
    changed = split.model_copy(update={"nets": changed_nets})
    assert set(source_matched_connector_peer_assignment_groups(changed, separate_groups)) == {"J1"}
    stale_report = evaluate_design_lint(
        "synthetic-stale-uart-peer-group",
        ContractCoachReport(
            status="READY_FOR_REVIEW",
            project_id="synthetic-stale-uart-peer-group",
            observed=changed,
            netlist_sha256="e" * 64,
        ),
        DesignLintPolicy(),
        connector_coverage=separate_groups,
    )
    assert any(
        finding.rule_id == "connector.peer_pin_assignment_divergence"
        for finding in stale_report.findings
    ), "a source mismatch cannot silence the generic peer comparison"


def test_peer_groups_scope_generic_pins_while_mapped_returns_remain_global() -> None:
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

    def peer_netlist(*, split_returns: bool, split_signals: bool) -> NetlistContract:
        signal_nets = (
            ("SIGNAL_A", "SIGNAL_B", "SIGNAL_C")
            if split_signals
            else ("SIGNAL", "SIGNAL", "SIGNAL")
        )
        return_nets = (
            ("RETURN_A", "RETURN_B", "RETURN_C") if split_returns else ("GND", "GND", "GND")
        )
        nets: dict[str, tuple[str, ...]] = {}
        for index, net in enumerate(signal_nets, start=1):
            nets.setdefault(net, ())
            nets[net] = (*nets[net], f"J{index}.1")
        for index, net in enumerate(return_nets, start=1):
            nets.setdefault(net, ())
            nets[net] = (*nets[net], f"J{index}.2")
        return NetlistContract(
            components={},
            nets=nets,
            component_symbols={f"J{index}": "Lint:PeerPowerPort" for index in range(1, 4)},
            component_pin_numbers={f"J{index}": ("1", "2") for index in range(1, 4)},
            pin_functions={
                **{f"J{index}.1": "Pin_1" for index in range(1, 4)},
                **{f"J{index}.2": "GND" for index in range(1, 4)},
            },
        )

    def mapped_coverage(
        observed: NetlistContract, *, shared_group: bool
    ) -> ConnectorCoverageReport:
        reviews = tuple(
            ConnectorInterfaceReview(
                reference=f"J{index}",
                disposition="interface",
                basis=f"Reviewed J{index} return contact against the synthetic pinout",
                interface_id="peer-return",
                pin_map={"2": "2"},
                unlisted_pin_reasons={
                    "1": "Generic Pin_1 signal contact has no reviewed role in this fixture"
                },
                peer_assignment_group="uart-peers" if shared_group else f"uart-{index}",
                peer_assignment_basis="Reviewed matching generic signal contacts as one UART peer set"
                if shared_group
                else f"Reviewed J{index} as an independent UART interface",
            )
            for index in range(1, 4)
        )
        return evaluate_connector_coverage(
            observed,
            ("peer-return",),
            reviews,
            interfaces={"peer-return": interface},
            interface_catalog_path="catalog/interfaces.json",
            interface_catalog_sha256="f" * 64,
            inventory_review=inventory_review(),
        )

    split = peer_netlist(split_returns=True, split_signals=True)
    separate_coverage = mapped_coverage(split, shared_group=False)
    assert separate_coverage.status == "COMPLETE"
    separate_report = evaluate_design_lint(
        "synthetic-peer-groups-split-return",
        ContractCoachReport(
            status="READY_FOR_REVIEW",
            project_id="synthetic-peer-groups-split-return",
            observed=split,
            netlist_sha256="a" * 64,
        ),
        DesignLintPolicy(),
        connector_coverage=separate_coverage,
    )
    separate_rule_ids = {finding.rule_id for finding in separate_report.findings}
    assert separate_rule_ids == {"connector.repeated_pin_function"}
    return_finding = separate_report.findings[0]
    assert {pin: return_finding.evidence[pin] for pin in ("J1.2", "J2.2", "J3.2")} == {
        "J1.2": ("RETURN_A",),
        "J2.2": ("RETURN_B",),
        "J3.2": ("RETURN_C",),
    }
    shared_coverage = mapped_coverage(split, shared_group=True)
    shared_report = evaluate_design_lint(
        "synthetic-peer-groups-shared-signals",
        ContractCoachReport(
            status="READY_FOR_REVIEW",
            project_id="synthetic-peer-groups-shared-signals",
            observed=split,
            netlist_sha256="a" * 64,
        ),
        DesignLintPolicy(),
        connector_coverage=shared_coverage,
    )
    shared_findings = {finding.rule_id: finding for finding in shared_report.findings}
    assert set(shared_findings) == {
        "connector.repeated_pin_function",
        "connector.peer_pin_assignment_divergence",
    }
    divergence = shared_findings["connector.peer_pin_assignment_divergence"]
    assert divergence.evidence["peer_assignment_group"] == ("uart-peers",)
    assert len(divergence.evidence["peer_assignment_basis"]) == 3
    assert {
        pin: shared_findings["connector.repeated_pin_function"].evidence[pin]
        for pin in ("J1.2", "J2.2", "J3.2")
    } == {"J1.2": ("RETURN_A",), "J2.2": ("RETURN_B",), "J3.2": ("RETURN_C",)}, (
        "a shared signal peer group must not scope away cross-port return review"
    )
    control = peer_netlist(split_returns=False, split_signals=False)
    control_report = evaluate_design_lint(
        "synthetic-peer-groups-common-control",
        ContractCoachReport(
            status="READY_FOR_REVIEW",
            project_id="synthetic-peer-groups-common-control",
            observed=control,
            netlist_sha256="b" * 64,
        ),
        DesignLintPolicy(),
        connector_coverage=mapped_coverage(control, shared_group=True),
    )
    assert control_report.status == "PASS"
    assert control_report.findings == ()
