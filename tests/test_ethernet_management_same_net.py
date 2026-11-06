"""Focused regressions for Ethernet MDC and MDIO sharing one net."""

from __future__ import annotations

from typing import Literal

import pytest

from kicad_tooling.hwrepo.bus_ethernet_management_named_rail import (
    ethernet_management_signal_on_named_rail_candidates,
)
from kicad_tooling.hwrepo.bus_ethernet_management_same_net import (
    RULE_ID,
    ethernet_management_same_net_candidates,
)
from kicad_tooling.hwrepo.bus_ethernet_pair_labels import (
    ethernet_management_label_mismatch_candidates,
)
from kicad_tooling.hwrepo.bus_ethernet_unconnected_management import (
    ethernet_management_unconnected_pin_candidates,
)
from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.design_lint_finding_models import (
    DesignLintFinding,
    DesignLintIgnore,
    DesignLintRuleOverride,
)
from kicad_tooling.hwrepo.design_lint_policy_models import DesignLintPolicy
from kicad_tooling.hwrepo.design_lint_report_models import DesignLintReport
from kicad_tooling.hwrepo.models import NetlistContract
from tests.design_lint_fixtures import coach
from tests.design_lint_fixtures.ethernet_management_same_net import (
    ethernet_management_same_net_netlist,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint]


def _findings(source: NetlistContract) -> tuple[DesignLintFinding, ...]:
    report = evaluate("synthetic-ethernet-management-same-net", coach(source), DesignLintPolicy())
    return tuple(item for item in report.findings if item.rule_id == RULE_ID)


def _report(
    source: NetlistContract,
    *,
    mode: Literal["review", "block", "off"] | None = None,
    ignore: DesignLintIgnore | None = None,
) -> DesignLintReport:
    overrides = (
        ()
        if mode is None
        else (
            DesignLintRuleOverride(
                rule_id=RULE_ID,
                mode=mode,
                reason="Review the synthetic Ethernet management assignment",
            ),
        )
    )
    return evaluate(
        "synthetic-ethernet-management-same-net",
        coach(source),
        DesignLintPolicy(rules=overrides, ignores=() if ignore is None else (ignore,)),
    )


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_shared_management_net_is_reviewed_and_separate_nets_are_control() -> None:
    findings = _findings(ethernet_management_same_net_netlist())

    assert len(findings) == 1
    assert findings[0].subject == "U1: MDC U1.5 and MDIO U1.6 share MII_MANAGEMENT"
    assert findings[0].evidence == {
        "component": ("U1",),
        "MDC_pin": ("U1.5",),
        "MDC_function": ("MDC",),
        "MDIO_pin": ("U1.6",),
        "MDIO_function": ("MDIO",),
        "MDC_electrical_type": ("input",),
        "MDIO_electrical_type": ("bidirectional",),
        "net": ("MII_MANAGEMENT",),
    }
    assert not _findings(ethernet_management_same_net_netlist(shared=False))


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_existing_management_checks_leave_this_same_net_case_unclassified() -> None:
    source = ethernet_management_same_net_netlist()

    assert not ethernet_management_label_mismatch_candidates(source)
    assert not ethernet_management_unconnected_pin_candidates(source)
    assert not ethernet_management_signal_on_named_rail_candidates(source)
    assert len(ethernet_management_same_net_candidates(source)) == 1


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_dnp_open_ambiguous_duplicate_and_incomplete_pins_are_skipped() -> None:
    source = ethernet_management_same_net_netlist()
    dnp = ethernet_management_same_net_netlist(dnp=True)
    open_clock = ethernet_management_same_net_netlist(open_pin="U1.5")
    ambiguous_data = ethernet_management_same_net_netlist(ambiguous_pin="U1.6")
    duplicate_role = source.model_copy(
        update={
            "pin_functions": {**source.pin_functions, "U1.7": "MDC"},
            "component_pin_numbers": {"U1": ("5", "6", "7")},
            "nets": {"MII_MANAGEMENT": ("U1.5", "U1.6", "U1.7")},
        }
    )
    missing_inventory = source.model_copy(update={"component_pin_numbers": {}})
    incomplete_inventory = source.model_copy(
        update={"component_pin_numbers": {"U1": ("5", "6", "7")}}
    )
    non_ic_reference = ethernet_management_same_net_netlist(reference="J1")

    for control in (
        dnp,
        open_clock,
        ambiguous_data,
        duplicate_role,
        missing_inventory,
        incomplete_inventory,
        non_ic_reference,
    ):
        assert not _findings(control)
        assert not ethernet_management_same_net_candidates(control)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_two_output_pins_are_left_to_native_erc() -> None:
    outputs = ethernet_management_same_net_netlist(pin_types=("output", "output"))

    assert not _findings(outputs)
    assert not ethernet_management_same_net_candidates(outputs)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_mapping_order_is_stable_and_assigning_separate_nets_clears_candidate() -> None:
    source = ethernet_management_same_net_netlist()
    reversed_source = source.model_copy(
        update={
            "nets": dict(reversed(tuple(source.nets.items()))),
            "pin_functions": dict(reversed(tuple(source.pin_functions.items()))),
        }
    )

    assert _findings(source) == _findings(reversed_source)
    assert not _findings(ethernet_management_same_net_netlist(shared=False))


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_policy_override_and_exact_ignore_control_review() -> None:
    source = ethernet_management_same_net_netlist()
    default_report = _report(source)
    default = next(item for item in default_report.findings if item.rule_id == RULE_ID)
    assert default.mode == "review"

    blocked = _report(source, mode="block")
    assert blocked.status == "FAIL"

    disabled = _report(source, mode="off")
    disabled_finding = next(item for item in disabled.findings if item.rule_id == RULE_ID)
    assert disabled_finding.disposition == "RULE_OFF"

    ignore = DesignLintIgnore(
        rule_id=RULE_ID,
        fingerprint=default.fingerprint,
        reason="Synthetic intentional shared management net",
    )
    ignored = _report(source, ignore=ignore)
    ignored_finding = next(item for item in ignored.findings if item.rule_id == RULE_ID)
    assert ignored_finding.disposition == "IGNORED"
