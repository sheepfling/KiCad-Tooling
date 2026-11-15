"""Review native SWD signals assigned to rail-like schematic nets."""

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
from kicad_tooling.hwrepo.models import ComponentContract, ContractCoachReport, NetlistContract
from kicad_tooling.hwrepo.swd_endpoint_inventory import SwdEndpointInventory, swd_function_role
from kicad_tooling.hwrepo.swd_signal_named_rail import swd_signal_on_named_rail_candidates
from tests.design_lint_fixtures.swd_signal_named_rail import swd_signal_named_rail_netlist

RULE_ID = "bus.swd_signal_on_named_rail"

pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint]


def _report(
    netlist: NetlistContract,
    *,
    override: DesignLintRuleOverride | None = None,
    ignore: DesignLintIgnore | None = None,
) -> DesignLintReport:
    project_id = "synthetic-swd-signal-named-rail"
    coach = ContractCoachReport(
        status="READY_FOR_REVIEW",
        project_id=project_id,
        observed=netlist,
        netlist_sha256="b" * 64,
    )
    return evaluate(
        project_id,
        coach,
        DesignLintPolicy(
            rules=() if override is None else (override,),
            ignores=() if ignore is None else (ignore,),
        ),
    )


def _findings(report: DesignLintReport) -> tuple[DesignLintFinding, ...]:
    return tuple(item for item in report.findings if item.rule_id == RULE_ID)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_complete_swd_pair_on_named_rails_requests_review_with_source_evidence() -> None:
    source = swd_signal_named_rail_netlist(rail_pins={"1": "GND", "2": "+3V3"})
    candidates = swd_signal_on_named_rail_candidates(source)
    findings = _findings(_report(source))

    assert len(candidates) == len(findings) == 2
    assert tuple(item.subject for item in findings) == (
        "U1.1: SYS_JTMS-SWDIO on return-like net GND",
        "U1.2: SYS_JTCK-SWCLK on supply-like net +3V3",
    )
    assert tuple(item.evidence["swd_role"] for item in findings) == (("swdio",), ("swclk",))
    assert all(
        item.evidence["swd_identity_basis"] == ("unique assigned native SWDIO/SWCLK pair",)
        for item in findings
    )
    assert all(item.mode == "review" for item in findings)
    assert all("do not prove that SWD is enabled" in item.message for item in findings)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_explicit_connector_pair_is_reviewed_but_neutral_signal_nets_are_quiet() -> None:
    connector_fault = swd_signal_named_rail_netlist(reference="J1", rail_pins={"1": "GND"})
    connector_control = swd_signal_named_rail_netlist(reference="J1")

    assert tuple(item.subject for item in _findings(_report(connector_fault))) == (
        "J1.1: SYS_JTMS-SWDIO on return-like net GND",
    )
    assert not swd_signal_on_named_rail_candidates(connector_control)
    assert not _findings(_report(connector_control))


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_explicit_swo_pin_on_a_named_rail_is_reviewed_for_ic_and_connector() -> None:
    ic_fault = swd_signal_named_rail_netlist(rail_pins={"3": "GND"})
    connector_fault = swd_signal_named_rail_netlist(reference="J1", rail_pins={"3": "+3V3"})
    ic_findings = _findings(_report(ic_fault))
    connector_findings = _findings(_report(connector_fault))

    assert tuple(item.subject for item in ic_findings) == ("U1.3: SWO on return-like net GND",)
    assert ic_findings[0].evidence["swd_role"] == ("swo",)
    assert ic_findings[0].evidence["swd_identity_basis"] == (
        "unique assigned native SWDIO/SWCLK pair with one explicit SWO function",
    )
    assert tuple(item.subject for item in connector_findings) == (
        "J1.3: SWO on supply-like net +3V3",
    )


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_swo_is_optional_and_requires_one_explicit_unique_distinct_assignment() -> None:
    source = swd_signal_named_rail_netlist(rail_pins={"1": "GND", "2": "+3V3", "3": "+1V8"})
    open_nets = {
        name: tuple(pin for pin in pins if pin != "U1.3") for name, pins in source.nets.items()
    }
    open_swo = source.model_copy(
        update={"nets": {name: pins for name, pins in open_nets.items() if pins}}
    )
    multiple_swo_nets = source.model_copy(update={"nets": {**source.nets, "ALT": ("U1.3",)}})
    duplicate_swo = swd_signal_named_rail_netlist(
        functions=("SYS_JTMS-SWDIO", "SYS_JTCK-SWCLK", "SWO", "JTDO-SWO"),
        rail_pins={"1": "GND", "2": "+3V3"},
    )
    tdo_without_swo = swd_signal_named_rail_netlist(
        functions=("SYS_JTMS-SWDIO", "SYS_JTCK-SWCLK", "JTDO", "GPIO"),
        rail_pins={"1": "GND", "2": "+3V3"},
    )
    swo_on_swdio_net = swd_signal_named_rail_netlist(rail_pins={"1": "GND"})
    same_net_nets = {
        name: (*pins, "U1.3") if name == "GND" else pins
        for name, pins in swo_on_swdio_net.nets.items()
        if name != "SWD_SIGNAL_3"
    }
    same_net_swo = swo_on_swdio_net.model_copy(update={"nets": same_net_nets})

    assert swd_function_role("SWO") == "swo"
    assert swd_function_role("JTDO-SWO") == "swo"
    assert swd_function_role("JTDO") is None
    assert swd_function_role("SWO-SWDIO") is None
    endpoints = SwdEndpointInventory.from_netlist(source).endpoint_pairs()
    assert len(endpoints) == 1
    assert (endpoints[0].swdio_pin, endpoints[0].swclk_pin) == ("U1.1", "U1.2")
    assert tuple(item.subject for item in _findings(_report(same_net_swo))) == (
        "U1.1: SYS_JTMS-SWDIO on return-like net GND",
    )
    expected_pair_findings = (
        "U1.1: SYS_JTMS-SWDIO on return-like net GND",
        "U1.2: SYS_JTCK-SWCLK on supply-like net +3V3",
    )
    for case in (open_swo, multiple_swo_nets, duplicate_swo, tdo_without_swo):
        assert (
            tuple(item.subject for item in swd_signal_on_named_rail_candidates(case))
            == expected_pair_findings
        )
        assert tuple(item.subject for item in _findings(_report(case))) == expected_pair_findings


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_normal_resistor_bias_paths_are_outside_direct_pin_assignment_predicate() -> None:
    source = swd_signal_named_rail_netlist()
    biased = source.model_copy(
        update={
            "components": {
                **source.components,
                "R1": ComponentContract(value="100k", footprint="Resistor_SMD:R_0402"),
                "R2": ComponentContract(value="100k", footprint="Resistor_SMD:R_0402"),
            },
            "component_symbols": {**source.component_symbols, "R1": "Device:R", "R2": "Device:R"},
            "component_pin_numbers": {
                **source.component_pin_numbers,
                "R1": ("1", "2"),
                "R2": ("1", "2"),
            },
            "pin_functions": {
                **source.pin_functions,
                "R1.1": "R1.1",
                "R1.2": "R1.2",
                "R2.1": "R2.1",
                "R2.2": "R2.2",
            },
            "pin_electrical_types": {
                **source.pin_electrical_types,
                "R1.1": "passive",
                "R1.2": "passive",
                "R2.1": "passive",
                "R2.2": "passive",
            },
            "nets": {
                "SWD_SIGNAL_1": ("U1.1", "R1.1"),
                "SWD_SIGNAL_2": ("U1.2", "R2.1"),
                "+3V3": ("R1.2",),
                "GND": ("R2.2",),
                "SWD_SIGNAL_3": ("U1.3",),
                "SWD_SIGNAL_4": ("U1.4",),
            },
        }
    )

    assert not swd_signal_on_named_rail_candidates(biased)
    assert not _findings(_report(biased))


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_only_a_complete_unique_distinct_assigned_swd_pair_establishes_identity() -> None:
    source = swd_signal_named_rail_netlist(rail_pins={"1": "GND"})
    duplicate_role = source.model_copy(
        update={"pin_functions": {**source.pin_functions, "U1.3": "SWDIO"}}
    )
    open_clock = source.model_copy(
        update={
            "nets": {
                name: tuple(pin for pin in pins if pin != "U1.2")
                for name, pins in source.nets.items()
                if any(pin != "U1.2" for pin in pins)
            }
        }
    )
    multiple_clock_nets = source.model_copy(update={"nets": {**source.nets, "ALT": ("U1.2",)}})
    incomplete = source.model_copy(
        update={
            "pin_electrical_types": {
                pin: kind for pin, kind in source.pin_electrical_types.items() if pin != "U1.2"
            }
        }
    )
    same_net_pair = swd_signal_named_rail_netlist(rail_pins={"1": "GND", "2": "GND"})
    swd_without_peer = swd_signal_named_rail_netlist(
        functions=("SWDIO", "GPIO", "GPIO_AUX", "GPIO_OTHER"),
        rail_pins={"1": "GND"},
    )
    jtag_aliases_only = swd_signal_named_rail_netlist(
        functions=("JTMS", "JTCK", "GPIO_AUX", "GPIO_OTHER"),
        rail_pins={"1": "GND"},
    )

    assert swd_function_role("SYS_JTMS-SWDIO") == "swdio"
    assert swd_function_role("SYS_JTCK-SWCLK") == "swclk"
    assert swd_function_role("SWDCLK") == "swclk"
    assert swd_function_role("JTMS") is None
    for case in (
        swd_signal_named_rail_netlist(dnp=True, rail_pins={"1": "GND"}),
        duplicate_role,
        open_clock,
        multiple_clock_nets,
        incomplete,
        same_net_pair,
        swd_without_peer,
        jtag_aliases_only,
    ):
        assert not swd_signal_on_named_rail_candidates(case)
        assert not _findings(_report(case))


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_project_policy_and_exact_fingerprint_ignore_apply() -> None:
    source = swd_signal_named_rail_netlist(rail_pins={"1": "GND"})
    finding = _findings(_report(source))[0]
    blocked = _report(
        source,
        override=DesignLintRuleOverride(
            rule_id=RULE_ID,
            mode="block",
            reason="Synthetic project policy",
        ),
    )
    ignored = _report(
        source,
        ignore=DesignLintIgnore(
            rule_id=RULE_ID,
            fingerprint=finding.fingerprint,
            reason="Synthetic reviewed SWD assignment",
        ),
    )

    assert _findings(blocked)[0].mode == "block"
    assert _findings(ignored)[0].disposition == "IGNORED"


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_reordered_mappings_keep_fingerprint_and_evidence_stable() -> None:
    source = swd_signal_named_rail_netlist(rail_pins={"1": "GND", "2": "+3V3"})
    reordered = source.model_copy(
        update={
            "nets": dict(reversed(tuple(source.nets.items()))),
            "components": dict(reversed(tuple(source.components.items()))),
            "pin_functions": dict(reversed(tuple(source.pin_functions.items()))),
        }
    )

    assert tuple((item.fingerprint, item.evidence) for item in _findings(_report(source))) == tuple(
        (item.fingerprint, item.evidence) for item in _findings(_report(reordered))
    )
