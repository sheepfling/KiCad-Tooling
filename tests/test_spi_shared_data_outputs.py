"""Focused review tests for fitted SPI data-output pins sharing one net."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.design_lint_finding_models import DesignLintIgnore, DesignLintRuleOverride
from kicad_tooling.hwrepo.design_lint_policy_models import DesignLintPolicy
from kicad_tooling.hwrepo.models import NetlistContract
from kicad_tooling.hwrepo.spi_participants import is_spi_data_output_function
from kicad_tooling.hwrepo.spi_shared_data_outputs import spi_data_outputs_share_net_candidates
from tests.design_lint_fixtures import coach
from tests.design_lint_fixtures.spi_shared_data_outputs import spi_shared_data_output_netlist

pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint]

RULE_ID = "bus.spi_data_outputs_share_net"


def _report(netlist: NetlistContract, mode: str = "review", *, ignore=None):
    policy = DesignLintPolicy(
        rules=(
            DesignLintRuleOverride(
                rule_id=RULE_ID,
                mode=mode,
                reason="Review shared SPI data outputs",
            ),
        ),
        ignores=() if ignore is None else (ignore,),
    )
    return evaluate("synthetic-spi-shared-data-outputs", coach(netlist), policy)


def _findings(report):
    return tuple(item for item in report.findings if item.rule_id == RULE_ID)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_multiple_fitted_spi_data_outputs_on_one_net_are_reviewed() -> None:
    netlist = spi_shared_data_output_netlist()
    finding = _findings(_report(netlist))[0]

    assert finding.subject == "U2, U3: SPI data-output pins share SPI_MISO"
    assert finding.message.startswith(
        "Fitted IC SPI MISO/SDO/CIPO pins U2.1, U3.1 share one schematic net"
    )
    assert finding.evidence == {
        "components": ("U2", "U3"),
        "functions": ("MISO", "SPI2_SDO"),
        "pins": ("U2.1", "U3.1"),
        "pin_types": ("passive", "tri_state"),
        "net": ("SPI_MISO",),
    }
    default = evaluate(
        "synthetic-spi-shared-data-outputs",
        coach(netlist),
        DesignLintPolicy(),
    )
    assert _findings(default)[0].mode == "off"
    assert _findings(default)[0].disposition == "RULE_OFF"


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_separate_output_nets_and_one_device_to_controller_are_valid_controls() -> None:
    assert not spi_data_outputs_share_net_candidates(spi_shared_data_output_netlist(shared=False))
    one_device = spi_shared_data_output_netlist().model_copy(
        update={
            "components": {
                key: value
                for key, value in spi_shared_data_output_netlist().components.items()
                if key != "U3"
            },
            "nets": {"SPI_MISO": ("U1.1", "U2.1")},
            "pin_functions": {"U1.1": "MISO", "U2.1": "MISO"},
            "pin_electrical_types": {"U1.1": "input", "U2.1": "passive"},
            "component_pin_numbers": {"U1": ("1",), "U2": ("1",)},
        }
    )
    assert not spi_data_outputs_share_net_candidates(one_device)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_native_output_conflicts_and_incomplete_groups_are_skipped() -> None:
    source = spi_shared_data_output_netlist()
    output_conflict = source.model_copy(
        update={
            "pin_electrical_types": {
                "U1.1": "input",
                "U2.1": "output",
                "U3.1": "output",
            }
        }
    )
    dnp = source.model_copy(update={"dnp_components": ("U3",)})
    open_pin = source.model_copy(update={"nets": {"SPI_MISO": ("U1.1", "U2.1")}})
    ambiguous = source.model_copy(update={"nets": {**source.nets, "SPI_MISO_ALT": ("U3.1",)}})
    missing_type = source.model_copy(
        update={"pin_electrical_types": {"U1.1": "input", "U2.1": "passive"}}
    )
    unsupported_type = source.model_copy(
        update={
            "pin_electrical_types": {
                "U1.1": "input",
                "U2.1": "passive",
                "U3.1": "power_out",
            }
        }
    )
    missing_inventory = source.model_copy(
        update={"component_pin_numbers": {"U1": ("1",), "U2": ("1",)}}
    )
    return_net = source.model_copy(update={"nets": {"GND": ("U1.1", "U2.1", "U3.1")}})
    duplicate_role_on_one_reference = source.model_copy(
        update={
            "nets": {"SPI_MISO": ("U1.1", "U2.1", "U2.2", "U3.1")},
            "pin_functions": {**source.pin_functions, "U2.2": "CIPO"},
            "pin_electrical_types": {**source.pin_electrical_types, "U2.2": "passive"},
            "component_pin_numbers": {**source.component_pin_numbers, "U2": ("1", "2")},
        }
    )

    for unsupported in (
        output_conflict,
        dnp,
        open_pin,
        ambiguous,
        missing_type,
        unsupported_type,
        missing_inventory,
        return_net,
        duplicate_role_on_one_reference,
    ):
        assert spi_data_outputs_share_net_candidates(unsupported) == ()


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_connectors_and_unrecognized_pin_functions_are_excluded() -> None:
    source = spi_shared_data_output_netlist()
    connectors = source.model_copy(
        update={
            "components": {
                "U1": source.components["U1"],
                "J1": source.components["U2"],
                "J2": source.components["U3"],
            },
            "nets": {"SPI_MISO": ("U1.1", "J1.1", "J2.1")},
            "pin_functions": {"U1.1": "MISO", "J1.1": "MISO", "J2.1": "SDO"},
            "pin_electrical_types": {"U1.1": "input", "J1.1": "passive", "J2.1": "passive"},
            "component_pin_numbers": {"U1": ("1",), "J1": ("1",), "J2": ("1",)},
        }
    )
    unknown = source.model_copy(
        update={"pin_functions": {**source.pin_functions, "U3.1": "DATA_OUT"}}
    )
    assert spi_data_outputs_share_net_candidates(connectors) == ()
    assert spi_data_outputs_share_net_candidates(unknown) == ()


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_rule_policy_can_block_disable_or_ignore_an_intentional_shared_bus() -> None:
    netlist = spi_shared_data_output_netlist()
    reviewed = _findings(_report(netlist))[0]
    blocked = _findings(_report(netlist, "block"))[0]
    disabled = _findings(_report(netlist, "off"))[0]
    ignored = _findings(
        _report(
            netlist,
            ignore=DesignLintIgnore(
                rule_id=RULE_ID,
                fingerprint=reviewed.fingerprint,
                reason="Synthetic SPI devices use a reviewed tri-state MISO bus",
            ),
        )
    )[0]

    assert _report(netlist, "block").status == "FAIL"
    assert blocked.mode == "block"
    assert disabled.disposition == "RULE_OFF"
    assert ignored.disposition == "IGNORED"


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_aliases_ordering_and_separating_an_endpoint_are_metamorphic() -> None:
    for function in ("MISO", "SDO", "CIPO", "SPI2_CIPO"):
        assert is_spi_data_output_function(function)
    for function in ("MOSI", "COPI", "SCK", "NSS", "DATA_OUT"):
        assert not is_spi_data_output_function(function)

    source = spi_shared_data_output_netlist()
    reordered = source.model_copy(
        update={
            "components": dict(reversed(tuple(source.components.items()))),
            "nets": dict(reversed(tuple(source.nets.items()))),
            "pin_functions": dict(reversed(tuple(source.pin_functions.items()))),
            "pin_electrical_types": dict(reversed(tuple(source.pin_electrical_types.items()))),
        }
    )
    assert spi_data_outputs_share_net_candidates(source) == (
        spi_data_outputs_share_net_candidates(reordered)
    )
    assert not spi_data_outputs_share_net_candidates(spi_shared_data_output_netlist(shared=False))
