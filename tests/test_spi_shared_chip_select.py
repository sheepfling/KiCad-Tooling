"""Focused review tests for fitted SPI chip-select inputs sharing one net."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.design_lint_finding_models import (
    DesignLintFinding,
    DesignLintIgnore,
    DesignLintRuleOverride,
)
from kicad_tooling.hwrepo.design_lint_policy_models import DesignLintPolicy
from kicad_tooling.hwrepo.models import NetlistContract
from kicad_tooling.hwrepo.spi_participants import (
    is_spi_chip_select_function,
    is_spi_ic_reference,
)
from kicad_tooling.hwrepo.spi_shared_chip_select import (
    spi_chip_select_inputs_share_net_candidates,
)
from tests.design_lint_fixtures import coach
from tests.design_lint_fixtures.spi_shared_chip_select import spi_shared_chip_select_netlist

pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint]

RULE_ID = "bus.spi_chip_select_inputs_share_net"


def _report(netlist: NetlistContract, mode: str = "review", *, ignore=None):
    policy = DesignLintPolicy(
        rules=(
            DesignLintRuleOverride(
                rule_id=RULE_ID,
                mode=mode,
                reason="Review shared SPI chip-select inputs",
            ),
        ),
        ignores=() if ignore is None else (ignore,),
    )
    return evaluate("synthetic-spi-shared-chip-select", coach(netlist), policy)


def _findings(report) -> tuple[DesignLintFinding, ...]:
    return tuple(item for item in report.findings if item.rule_id == RULE_ID)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_multiple_fitted_device_select_inputs_on_one_net_are_reviewed() -> None:
    netlist = spi_shared_chip_select_netlist()
    finding = _findings(_report(netlist))[0]

    assert finding.subject == "U2, U3: SPI chip-select inputs share SPI_CS0"
    assert finding.message.startswith(
        "Fitted IC chip-select input pins U2.1, U3.1 share one schematic net"
    )
    assert finding.evidence == {
        "components": ("U2", "U3"),
        "functions": ("CS_N", "NSS"),
        "pins": ("U2.1", "U3.1"),
        "pin_types": ("input", "input"),
        "net": ("SPI_CS0",),
    }
    default = evaluate(
        "synthetic-spi-shared-chip-select",
        coach(netlist),
        DesignLintPolicy(),
    )
    assert _findings(default)[0].mode == "off"
    assert _findings(default)[0].disposition == "RULE_OFF"


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_separate_select_nets_and_controller_to_one_device_are_valid_controls() -> None:
    assert not spi_chip_select_inputs_share_net_candidates(
        spi_shared_chip_select_netlist(shared=False)
    )
    one_receiver = spi_shared_chip_select_netlist().model_copy(
        update={
            "components": {
                key: value
                for key, value in spi_shared_chip_select_netlist().components.items()
                if key != "U3"
            },
            "nets": {"SPI_CS0": ("U1.1", "U2.1")},
            "pin_functions": {
                key: value
                for key, value in spi_shared_chip_select_netlist().pin_functions.items()
                if key != "U3.1"
            },
            "pin_electrical_types": {
                key: value
                for key, value in spi_shared_chip_select_netlist().pin_electrical_types.items()
                if key != "U3.1"
            },
            "component_pin_numbers": {"U1": ("1", "2"), "U2": ("1",)},
        }
    )
    assert not spi_chip_select_inputs_share_net_candidates(one_receiver)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_unfitted_ambiguous_unsupported_and_non_ic_endpoints_are_skipped() -> None:
    source = spi_shared_chip_select_netlist()
    dnp = source.model_copy(update={"dnp_components": ("U3",)})
    ambiguous = source.model_copy(update={"nets": {**source.nets, "SPI_CS1": ("U3.1",)}})
    missing_type = source.model_copy(
        update={"pin_electrical_types": {"U1.1": "output", "U2.1": "input"}}
    )
    output_only = source.model_copy(
        update={
            "pin_electrical_types": {
                "U1.1": "output",
                "U2.1": "output",
                "U3.1": "output",
            }
        }
    )
    missing_inventory = source.model_copy(
        update={"component_pin_numbers": {"U1": ("1", "2"), "U2": ("1",)}}
    )
    two_selects_on_one_component = source.model_copy(
        update={
            "nets": {"SPI_CS0": ("U1.1", "U2.1", "U2.2", "U3.1")},
            "pin_functions": {**source.pin_functions, "U2.2": "SPI2_NSS"},
            "pin_electrical_types": {**source.pin_electrical_types, "U2.2": "input"},
            "component_pin_numbers": {**source.component_pin_numbers, "U2": ("1", "2")},
        }
    )
    connectors = source.model_copy(
        update={
            "components": {
                "U1": source.components["U1"],
                "J1": source.components["U2"],
                "J2": source.components["U3"],
            },
            "nets": {"SPI_CS0": ("U1.1", "J1.1", "J2.1")},
            "pin_functions": {
                "U1.1": "SPI1_NSS",
                "J1.1": "CS_N",
                "J2.1": "NSS",
            },
            "pin_electrical_types": {
                "U1.1": "output",
                "J1.1": "input",
                "J2.1": "input",
            },
            "component_pin_numbers": {"U1": ("1",), "J1": ("1",), "J2": ("1",)},
        }
    )

    for unsupported in (dnp, ambiguous, missing_type, output_only, missing_inventory):
        assert spi_chip_select_inputs_share_net_candidates(unsupported) == ()
    assert spi_chip_select_inputs_share_net_candidates(two_selects_on_one_component) == ()
    assert spi_chip_select_inputs_share_net_candidates(connectors) == ()


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_policy_can_block_disable_or_ignore_intentional_broadcast_selection() -> None:
    netlist = spi_shared_chip_select_netlist()
    reviewed = _findings(_report(netlist))[0]
    blocked = _findings(_report(netlist, "block"))[0]
    disabled = _findings(_report(netlist, "off"))[0]
    ignored = _findings(
        _report(
            netlist,
            ignore=DesignLintIgnore(
                rule_id=RULE_ID,
                fingerprint=reviewed.fingerprint,
                reason="Synthetic SPI devices intentionally accept a broadcast selection",
            ),
        )
    )[0]

    assert _report(netlist, "block").status == "FAIL"
    assert blocked.mode == "block"
    assert disabled.disposition == "RULE_OFF"
    assert ignored.disposition == "IGNORED"


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_alias_recognition_ordering_and_separating_one_select_is_metamorphic() -> None:
    for function in ("CS", "CS_N", "NCS", "NSS", "SS", "SS_N", "SSEL", "SPI2_NSS"):
        assert is_spi_chip_select_function(function)
    assert not is_spi_chip_select_function("MOSI")
    assert is_spi_ic_reference("IC12")
    assert not is_spi_ic_reference("J12")

    source = spi_shared_chip_select_netlist()
    reordered = source.model_copy(
        update={
            "components": dict(reversed(tuple(source.components.items()))),
            "nets": dict(reversed(tuple(source.nets.items()))),
            "pin_functions": dict(reversed(tuple(source.pin_functions.items()))),
            "pin_electrical_types": dict(reversed(tuple(source.pin_electrical_types.items()))),
        }
    )
    assert spi_chip_select_inputs_share_net_candidates(source) == (
        spi_chip_select_inputs_share_net_candidates(reordered)
    )
    assert not spi_chip_select_inputs_share_net_candidates(
        spi_shared_chip_select_netlist(shared=False)
    )
