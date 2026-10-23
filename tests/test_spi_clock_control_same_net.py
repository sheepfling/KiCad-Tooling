"""Focused SPI clock/control and data-role same-net review regressions."""

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
from kicad_tooling.hwrepo.spi_participants import spi_signal_role_and_channel
from tests.design_lint_fixtures import coach
from tests.design_lint_fixtures.spi_clock_control_same_net import (
    spi_clock_control_same_net_netlist,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint]

RULE_ID = "bus.spi_clock_control_data_same_net"


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
                reason="Review synthetic SPI signal assignments",
            ),
        ),
        ignores=() if ignore is None else (ignore,),
    )
    return evaluate("synthetic-spi-clock-control-same-net", coach(netlist), policy)


def _findings(report: DesignLintReport) -> tuple[DesignLintFinding, ...]:
    return tuple(item for item in report.findings if item.rule_id == RULE_ID)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_bounded_spi_clock_control_and_data_aliases_keep_channel_identity() -> None:
    assert spi_signal_role_and_channel("SCK") == ("clock", "default")
    assert spi_signal_role_and_channel("SPI1_SCLK") == ("clock", "index1")
    assert spi_signal_role_and_channel("SPI1_COPI") == ("data_input", "index1")
    assert spi_signal_role_and_channel("SDO") == ("data_output", "default")
    assert spi_signal_role_and_channel("SPI2_NSS") == ("chip_select", "index2")
    assert spi_signal_role_and_channel("CHIP_ENABLE") is None

    fault = spi_clock_control_same_net_netlist(
        control_function="SCLK",
        data_function="COPI",
        control_channel=1,
        data_channel=1,
    )
    candidates = spi_clock_control_data_same_net_candidates(fault)
    assert len(candidates) == 1
    finding = _findings(_report(fault))[0]
    assert (
        finding.subject
        == "U1: SPI channel 1 clock SPI1_SCLK and data input SPI1_COPI share SPI_ROLE_SHARED"
    )
    assert finding.evidence == {
        "component": ("U1",),
        "channel": ("SPI channel 1",),
        "spi_role_pin": ("U1.1",),
        "spi_role": ("clock",),
        "spi_function": ("SPI1_SCLK",),
        "spi_electrical_type": ("input",),
        "data_pin": ("U1.2",),
        "data_role": ("data_input",),
        "data_function": ("SPI1_COPI",),
        "data_electrical_type": ("input",),
        "net": ("SPI_ROLE_SHARED",),
    }


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_data_pair_rule_owns_data_input_output_shorts_and_control_nets_are_quiet() -> None:
    separate = spi_clock_control_same_net_netlist(shared=False)
    data_pair_only = separate.model_copy(
        update={
            "nets": {
                "SPI_SCK": ("U1.1",),
                "SPI_DATA": ("U1.2", "U1.3"),
                "SPI_CS": ("U1.4",),
            },
            "pin_functions": {
                "U1.1": "SCK",
                "U1.2": "MOSI",
                "U1.3": "MISO",
                "U1.4": "CS",
            },
            "pin_electrical_types": {
                "U1.1": "input",
                "U1.2": "input",
                "U1.3": "tri_state",
                "U1.4": "input",
            },
        }
    )

    assert not spi_clock_control_data_same_net_candidates(separate)
    assert not spi_clock_control_data_same_net_candidates(data_pair_only)
    assert _findings(_report(spi_clock_control_same_net_netlist(shared=False))) == ()
    assert _findings(_report(data_pair_only)) == ()


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_channel_mismatch_duplicate_roles_dnp_and_incomplete_assignments_are_skipped() -> None:
    source = spi_clock_control_same_net_netlist()
    cross_channel = spi_clock_control_same_net_netlist(
        control_channel=1,
        data_channel=2,
    )
    dnp = spi_clock_control_same_net_netlist(dnp=True)
    open_data = source.model_copy(
        update={"nets": {"SPI_ROLE_SHARED": ("U1.1",), "SPI_MISO": ("U1.3",), "SPI_CS": ("U1.4",)}}
    )
    multiply_assigned = source.model_copy(update={"nets": {**source.nets, "SPI_ALT": ("U1.2",)}})
    duplicate_clock = source.model_copy(
        update={
            "nets": {
                "SPI_ROLE_SHARED": ("U1.1", "U1.2", "U1.5"),
                "SPI_MISO": ("U1.3",),
                "SPI_CS": ("U1.4",),
            },
            "pin_functions": {**source.pin_functions, "U1.5": "SCLK"},
            "component_pin_numbers": {"U1": ("1", "2", "3", "4", "5")},
        }
    )
    missing_inventory = source.model_copy(update={"component_pin_numbers": {}})
    missing_function_pin = source.model_copy(update={"component_pin_numbers": {"U1": ("1",)}})
    connector = source.model_copy(
        update={
            "components": {"J1": source.components["U1"]},
            "component_symbols": {"J1": "Synthetic:SpiDevice"},
            "nets": {"SPI_ROLE_SHARED": ("J1.1", "J1.2")},
            "pin_functions": {"J1.1": "SCK", "J1.2": "MOSI"},
            "pin_electrical_types": {"J1.1": "input", "J1.2": "input"},
            "component_pin_numbers": {"J1": ("1", "2")},
        }
    )

    for unsupported in (
        cross_channel,
        dnp,
        open_data,
        multiply_assigned,
        duplicate_clock,
        missing_inventory,
        missing_function_pin,
        connector,
    ):
        assert spi_clock_control_data_same_net_candidates(unsupported) == ()


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_output_conflicts_are_deferred_to_erc_and_unknown_types_remain_reviewable() -> None:
    source = spi_clock_control_same_net_netlist()
    output_conflict = source.model_copy(
        update={
            "pin_electrical_types": {
                "U1.1": "output",
                "U1.2": "output",
                "U1.3": "tri_state",
                "U1.4": "input",
            }
        }
    )
    unknown_types = source.model_copy(update={"pin_electrical_types": {}})

    assert not spi_clock_control_data_same_net_candidates(output_conflict)
    assert len(spi_clock_control_data_same_net_candidates(unknown_types)) == 1
    assert _findings(_report(unknown_types))[0].evidence["spi_electrical_type"] == ("unknown",)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_project_policy_can_block_disable_or_ignore_an_intentional_pair() -> None:
    source = spi_clock_control_same_net_netlist()
    initial = _findings(_report(source))[0]
    blocked = _findings(_report(source, "block"))[0]
    disabled = _findings(_report(source, "off"))[0]
    ignored = _findings(
        _report(
            source,
            ignore=DesignLintIgnore(
                rule_id=RULE_ID,
                fingerprint=initial.fingerprint,
                reason="The device intentionally multiplexes these SPI signals",
            ),
        )
    )[0]

    assert _report(source, "block").status == "FAIL"
    assert blocked.mode == "block"
    assert disabled.disposition == "RULE_OFF"
    assert ignored.disposition == "IGNORED"


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_fingerprints_are_order_stable_and_separating_roles_clears_candidate() -> None:
    source = spi_clock_control_same_net_netlist()
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
    assert not _findings(_report(spi_clock_control_same_net_netlist(shared=False)))
