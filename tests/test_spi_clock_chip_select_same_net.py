"""Focused same-net review regressions for SPI clock and chip-select roles."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.design_lint_finding_models import (
    DesignLintFinding,
    DesignLintIgnore,
    DesignLintRuleOverride,
)
from kicad_tooling.hwrepo.design_lint_policy_models import DesignLintPolicy
from kicad_tooling.hwrepo.design_lint_report_models import DesignLintReport
from kicad_tooling.hwrepo.models import NetlistContract
from kicad_tooling.hwrepo.spi_clock_data_same_net import (
    spi_clock_control_data_same_net_candidates,
)
from kicad_tooling.hwrepo.spi_control_same_net import spi_clock_chip_select_same_net_candidates
from kicad_tooling.hwrepo.spi_participants import spi_signal_role_and_channel
from tests.design_lint_fixtures import coach
from tests.design_lint_fixtures.spi_clock_control_same_net import (
    spi_clock_chip_select_same_net_netlist,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint]

RULE_ID = "bus.spi_clock_chip_select_same_net"


def _report(
    netlist: NetlistContract,
    mode: str = "review",
    *,
    ignore: DesignLintIgnore | None = None,
) -> DesignLintReport:
    policy = DesignLintPolicy(
        rules=(
            DesignLintRuleOverride(
                rule_id=RULE_ID,
                mode=mode,
                reason="Review synthetic SPI clock and chip-select assignments",
            ),
        ),
        ignores=() if ignore is None else (ignore,),
    )
    return evaluate("synthetic-spi-clock-chip-select-same-net", coach(netlist), policy)


def _findings(report: DesignLintReport) -> tuple[DesignLintFinding, ...]:
    return tuple(item for item in report.findings if item.rule_id == RULE_ID)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_same_channel_spi_clock_and_chip_select_sharing_one_net_is_reviewed() -> None:
    assert spi_signal_role_and_channel("SPI2_SCLK") == ("clock", "index2")
    assert spi_signal_role_and_channel("SPI2_NSS") == ("chip_select", "index2")
    assert spi_signal_role_and_channel("SPI2_CHIP_SELECT") == ("chip_select", "index2")

    fault = spi_clock_chip_select_same_net_netlist(
        clock_function="SCLK",
        select_function="CSN",
        clock_channel=2,
        select_channel=2,
    )
    assert len(spi_clock_chip_select_same_net_candidates(fault)) == 1
    finding = _findings(_report(fault))[0]
    assert finding.subject == (
        "U1: SPI channel 2 clock SPI2_SCLK and chip select SPI2_CSN share SPI_CONTROL_SHARED"
    )
    assert finding.evidence == {
        "component": ("U1",),
        "channel": ("SPI channel 2",),
        "clock_pin": ("U1.1",),
        "clock_function": ("SPI2_SCLK",),
        "clock_electrical_type": ("input",),
        "chip_select_pin": ("U1.2",),
        "chip_select_function": ("SPI2_CSN",),
        "chip_select_electrical_type": ("input",),
        "net": ("SPI_CONTROL_SHARED",),
    }


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_separate_controls_and_other_supported_cases_are_quiet() -> None:
    separated = spi_clock_chip_select_same_net_netlist(shared=False)
    data_pair = separated.model_copy(
        update={
            "nets": {
                "SPI_SCK": ("U1.1",),
                "SPI_CS": ("U1.2",),
                "SPI_DATA": ("U1.3", "U1.4"),
            }
        }
    )

    assert not spi_clock_chip_select_same_net_candidates(separated)
    assert not spi_clock_chip_select_same_net_candidates(data_pair)
    assert not spi_clock_control_data_same_net_candidates(separated)
    assert not _findings(_report(separated))


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_dnp_channel_mismatch_duplicate_roles_and_incomplete_assignments_are_skipped() -> None:
    source = spi_clock_chip_select_same_net_netlist()
    cross_channel = spi_clock_chip_select_same_net_netlist(clock_channel=1, select_channel=2)
    dnp = spi_clock_chip_select_same_net_netlist(dnp=True)
    open_clock = source.model_copy(
        update={"nets": {"SPI_CS": ("U1.2",), "SPI_MOSI": ("U1.3",), "SPI_MISO": ("U1.4",)}}
    )
    multiply_assigned = source.model_copy(update={"nets": {**source.nets, "SPI_ALT": ("U1.1",)}})
    duplicate_clock = source.model_copy(
        update={
            "nets": {
                "SPI_CONTROL_SHARED": ("U1.1", "U1.2", "U1.5"),
                "SPI_MOSI": ("U1.3",),
                "SPI_MISO": ("U1.4",),
            },
            "pin_functions": {**source.pin_functions, "U1.5": "SCLK"},
            "component_pin_numbers": {"U1": ("1", "2", "3", "4", "5")},
        }
    )
    missing_inventory = source.model_copy(update={"component_pin_numbers": {}})
    pin_missing_from_inventory = source.model_copy(
        update={"component_pin_numbers": {"U1": ("2", "3", "4")}}
    )
    connector = source.model_copy(
        update={
            "components": {"J1": source.components["U1"]},
            "component_symbols": {"J1": "Connector:USB_C_Receptacle"},
            "nets": {
                "SPI_CONTROL_SHARED": ("J1.1", "J1.2"),
                "SPI_MOSI": ("J1.3",),
                "SPI_MISO": ("J1.4",),
            },
            "pin_functions": {
                "J1.1": "SCK",
                "J1.2": "NSS",
                "J1.3": "MOSI",
                "J1.4": "MISO",
            },
            "pin_electrical_types": {
                "J1.1": "input",
                "J1.2": "input",
                "J1.3": "input",
                "J1.4": "tri_state",
            },
            "component_pin_numbers": {"J1": ("1", "2", "3", "4")},
        }
    )

    for unsupported in (
        cross_channel,
        dnp,
        open_clock,
        multiply_assigned,
        duplicate_clock,
        missing_inventory,
        pin_missing_from_inventory,
        connector,
    ):
        assert not spi_clock_chip_select_same_net_candidates(unsupported)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_two_explicit_outputs_defer_to_erc_and_unknown_types_remain_reviewable() -> None:
    source = spi_clock_chip_select_same_net_netlist(
        clock_type="output",
        select_type="output",
    )
    unknown_types = source.model_copy(update={"pin_electrical_types": {}})

    assert not spi_clock_chip_select_same_net_candidates(source)
    finding = spi_clock_chip_select_same_net_candidates(unknown_types)[0]
    assert finding.evidence["clock_electrical_type"] == ("unknown",)
    assert finding.evidence["chip_select_electrical_type"] == ("unknown",)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_project_policy_can_block_disable_or_ignore_the_exact_pair() -> None:
    source = spi_clock_chip_select_same_net_netlist()
    initial = _findings(_report(source))[0]
    blocked = _findings(_report(source, "block"))[0]
    disabled = _findings(_report(source, "off"))[0]
    ignored = _findings(
        _report(
            source,
            ignore=DesignLintIgnore(
                rule_id=RULE_ID,
                fingerprint=initial.fingerprint,
                reason="The device intentionally multiplexes these SPI roles",
            ),
        )
    )[0]

    assert _report(source, "block").status == "FAIL"
    assert blocked.mode == "block"
    assert disabled.disposition == "RULE_OFF"
    assert ignored.disposition == "IGNORED"


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_fingerprints_are_stable_and_repair_clears_candidate() -> None:
    source = spi_clock_chip_select_same_net_netlist()
    reordered = source.model_copy(
        update={
            "components": dict(reversed(tuple(source.components.items()))),
            "nets": dict(reversed(tuple(source.nets.items()))),
            "pin_functions": dict(reversed(tuple(source.pin_functions.items()))),
            "pin_electrical_types": dict(reversed(tuple(source.pin_electrical_types.items()))),
        }
    )
    first = _findings(_report(source))[0]
    second = _findings(_report(reordered))[0]

    assert (first.fingerprint, first.evidence) == (second.fingerprint, second.evidence)
    assert not _findings(_report(spi_clock_chip_select_same_net_netlist(shared=False)))
