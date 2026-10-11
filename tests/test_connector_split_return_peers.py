"""Synthetic regressions for split returns on comparable connectors."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.models import DesignLintPolicy, NetlistContract
from tests.design_lint_fixtures import coach

pytestmark = [pytest.mark.design_lint, pytest.mark.connector_lint]

RULE_ID = "connector.peer_pin_assignment_divergence"
CONNECTORS = ("J1", "J2", "J3", "J4")
PIN_NUMBERS = tuple(str(number) for number in range(1, 10))
RETURN_PINS = ("7", "9")


def nine_contact_peer_netlist(*, split_returns: bool) -> NetlistContract:
    nets: dict[str, tuple[str, ...]] = {}
    for pin_number in PIN_NUMBERS:
        if pin_number in RETURN_PINS:
            if split_returns:
                for index, reference in enumerate(CONNECTORS, start=1):
                    net = f"SYNTHETIC_RETURN_{index}"
                    nets[net] = (*nets.get(net, ()), f"{reference}.{pin_number}")
            else:
                for reference in CONNECTORS:
                    nets["SYNTHETIC_COMMON_RETURN"] = (
                        *nets.get("SYNTHETIC_COMMON_RETURN", ()),
                        f"{reference}.{pin_number}",
                    )
        else:
            nets[f"SYNTHETIC_SIGNAL_{pin_number}"] = tuple(
                f"{reference}.{pin_number}" for reference in CONNECTORS
            )

    return NetlistContract(
        components={},
        nets=nets,
        component_symbols={reference: "Synthetic:9PinConnector" for reference in CONNECTORS},
        component_pin_numbers={reference: PIN_NUMBERS for reference in CONNECTORS},
        pin_functions={
            f"{reference}.{pin_number}": f"Pin_{pin_number}"
            for reference in CONNECTORS
            for pin_number in PIN_NUMBERS
        },
    )


def test_four_peer_connectors_with_two_split_return_pins_are_reviewed() -> None:
    report = evaluate(
        "synthetic-nine-contact-split-returns",
        coach(nine_contact_peer_netlist(split_returns=True)),
        DesignLintPolicy(),
    )
    findings = [item for item in report.findings if item.rule_id == RULE_ID]

    assert report.status == "REVIEW"
    assert {item.subject for item in findings} == {
        "Synthetic:9PinConnector pin 7",
        "Synthetic:9PinConnector pin 9",
    }
    for finding in findings:
        pin_number = finding.subject.rsplit(" ", maxsplit=1)[1]
        assert {
            reference: finding.evidence[f"{reference}.{pin_number}"] for reference in CONNECTORS
        } == {
            reference: (f"SYNTHETIC_RETURN_{index}",)
            for index, reference in enumerate(CONNECTORS, start=1)
        }
        assert "does not establish a required connection" in finding.message


def test_four_peer_connectors_with_common_return_pins_do_not_diverge() -> None:
    report = evaluate(
        "synthetic-nine-contact-common-returns",
        coach(nine_contact_peer_netlist(split_returns=False)),
        DesignLintPolicy(),
    )

    assert not any(item.rule_id == RULE_ID for item in report.findings)
