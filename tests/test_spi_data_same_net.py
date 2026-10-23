"""Focused SPI data input/output same-net review regressions."""

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
from kicad_tooling.hwrepo.spi_participants import spi_data_function_role_and_channel
from kicad_tooling.hwrepo.spi_same_net import spi_data_input_output_same_net_candidates
from tests.design_lint_fixtures import coach
from tests.design_lint_fixtures.spi_data_same_net import spi_data_same_net_netlist

pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint]

RULE_ID = "bus.spi_data_input_output_same_net"


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
                reason="Review synthetic SPI data pin assignments",
            ),
        ),
        ignores=() if ignore is None else (ignore,),
    )
    return evaluate("synthetic-spi-data-same-net", coach(netlist), policy)


def _findings(report: DesignLintReport) -> tuple[DesignLintFinding, ...]:
    return tuple(item for item in report.findings if item.rule_id == RULE_ID)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_same_ic_spi_data_input_and_output_on_one_net_prompt_review() -> None:
    fault = spi_data_same_net_netlist()
    finding = _findings(_report(fault))[0]

    assert finding.subject == "U1: SPI data-role pins share SPI_DATA"
    assert finding.evidence == {
        "component": ("U1",),
        "channel": ("SPI",),
        "controller_to_peripheral_pin": ("U1.1",),
        "controller_to_peripheral_function": ("COPI",),
        "controller_to_peripheral_type": ("input",),
        "peripheral_to_controller_pin": ("U1.2",),
        "peripheral_to_controller_function": ("CIPO",),
        "peripheral_to_controller_type": ("tri_state",),
        "net": ("SPI_DATA",),
    }
    default = evaluate("synthetic-spi-data-same-net", coach(fault), DesignLintPolicy())
    assert _findings(default)[0].mode == "off"
    assert _findings(default)[0].disposition == "RULE_OFF"
    assert not spi_data_input_output_same_net_candidates(spi_data_same_net_netlist(shared=False))


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_aliases_pair_only_within_the_same_spi_channel() -> None:
    for input_function, output_function in (
        ("MOSI", "MISO"),
        ("SDI", "SDO"),
        ("COPI", "CIPO"),
        ("SPI1_COPI", "SPI1_CIPO"),
    ):
        netlist = spi_data_same_net_netlist(
            input_function=input_function,
            output_function=output_function,
        )
        assert len(spi_data_input_output_same_net_candidates(netlist)) == 1

    assert spi_data_function_role_and_channel("SPI1_COPI") == ("input", "index1")
    assert spi_data_function_role_and_channel("SPI2_CIPO") == ("output", "index2")
    cross_channel = spi_data_same_net_netlist(
        input_function="SPI1_COPI",
        output_function="SPI2_CIPO",
    )
    assert not spi_data_input_output_same_net_candidates(cross_channel)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_dnp_open_ambiguous_duplicate_and_incomplete_cases_are_skipped() -> None:
    source = spi_data_same_net_netlist()
    dnp = source.model_copy(update={"dnp_components": ("U1",)})
    open_pin = source.model_copy(update={"nets": {"SPI_DATA": ("U1.1",)}})
    multiply_assigned = source.model_copy(
        update={"nets": {**source.nets, "SPI_DATA_ALT": ("U1.2",)}}
    )
    duplicate_input = source.model_copy(
        update={
            "nets": {"SPI_DATA": ("U1.1", "U1.2", "U1.3")},
            "pin_functions": {**source.pin_functions, "U1.3": "MOSI"},
            "component_pin_numbers": {"U1": ("1", "2", "3")},
        }
    )
    missing_inventory = source.model_copy(update={"component_pin_numbers": {}})
    inconsistent_inventory = source.model_copy(update={"component_pin_numbers": {"U1": ("1",)}})
    output_conflict = source.model_copy(
        update={"pin_electrical_types": {"U1.1": "output", "U1.2": "output"}}
    )
    unknown_types = source.model_copy(update={"pin_electrical_types": {}})
    connector = source.model_copy(
        update={
            "components": {"J1": source.components["U1"]},
            "component_symbols": {"J1": "Synthetic:SpiDevice"},
            "nets": {"SPI_DATA": ("J1.1", "J1.2")},
            "pin_functions": {"J1.1": "COPI", "J1.2": "CIPO"},
            "component_pin_numbers": {"J1": ("1", "2")},
            "pin_electrical_types": {"J1.1": "input", "J1.2": "tri_state"},
        }
    )

    for unsupported in (
        dnp,
        open_pin,
        multiply_assigned,
        duplicate_input,
        missing_inventory,
        inconsistent_inventory,
        output_conflict,
        connector,
    ):
        assert spi_data_input_output_same_net_candidates(unsupported) == ()
    assert len(spi_data_input_output_same_net_candidates(unknown_types)) == 1


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_project_policy_can_block_disable_or_ignore_an_intentional_pair() -> None:
    initial = _findings(_report(spi_data_same_net_netlist()))[0]
    blocked = _findings(_report(spi_data_same_net_netlist(), "block"))[0]
    disabled = _findings(_report(spi_data_same_net_netlist(), "off"))[0]
    ignored = _findings(
        _report(
            spi_data_same_net_netlist(),
            ignore=DesignLintIgnore(
                rule_id=RULE_ID,
                fingerprint=initial.fingerprint,
                reason="The reviewed device supports this single-wire SPI mode",
            ),
        )
    )[0]

    assert _report(spi_data_same_net_netlist(), "block").status == "FAIL"
    assert blocked.mode == "block"
    assert disabled.disposition == "RULE_OFF"
    assert ignored.disposition == "IGNORED"


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_ordering_is_stable_and_separating_the_pair_clears_the_candidate() -> None:
    source = spi_data_same_net_netlist()
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
    assert not _findings(_report(spi_data_same_net_netlist(shared=False)))
