"""Regressions for shared JTAG TAP test-data outputs."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.design_lint_finding_models import DesignLintIgnore, DesignLintRuleOverride
from kicad_tooling.hwrepo.design_lint_policy_models import DesignLintPolicy
from kicad_tooling.hwrepo.jtag_tdo_output_sharing import (
    jtag_tdo_output_role,
    jtag_tdo_outputs_share_net_candidates,
)
from kicad_tooling.hwrepo.netlist_contract_models import NetlistContract
from tests.design_lint_fixtures import coach
from tests.design_lint_fixtures.jtag_tdo_output_sharing import jtag_tdo_output_sharing_netlist

pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint]

RULE_ID = "bus.jtag_tdo_outputs_share_net"
SHARED_NET = "JTAG_TDO_SHARED"


def _source(
    *,
    shared: bool = True,
    functions: tuple[str, ...] | None = None,
    references: tuple[str, ...] = ("U1", "U2"),
    dnp_references: tuple[str, ...] = (),
    pin_type: str = "passive",
) -> NetlistContract:
    return jtag_tdo_output_sharing_netlist(
        shared=shared,
        references=references,
        functions=functions,
        dnp_references=dnp_references,
        pin_type=pin_type,
    )


def _report(
    netlist: NetlistContract,
    mode: str | None = None,
    *,
    ignore: DesignLintIgnore | None = None,
):
    overrides = (
        ()
        if mode is None
        else (
            DesignLintRuleOverride(
                rule_id=RULE_ID,
                mode=mode,
                reason="Review synthetic shared JTAG TAP outputs",
            ),
        )
    )
    policy = DesignLintPolicy(rules=overrides, ignores=() if ignore is None else (ignore,))
    return evaluate("synthetic-jtag-tdo-output-sharing", coach(netlist), policy)


def _findings(report):
    return tuple(item for item in report.findings if item.rule_id == RULE_ID)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_shared_jtag_tdo_outputs_from_fitted_ics_are_reviewed() -> None:
    finding = _findings(_report(_source()))[0]

    assert finding.mode == "review"
    assert finding.subject == f"U1, U2: JTAG TDO outputs share {SHARED_NET}"
    assert finding.evidence == {
        "components": ("U1", "U2"),
        "functions": ("JTAG_TDO", "JTAG_TDO"),
        "pins": ("U1.4", "U2.4"),
        "pin_types": ("passive", "passive"),
        "net": (SHARED_NET,),
    }
    assert "mux or selected debug topology" in finding.message


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_exact_jtag_tdo_aliases_and_non_jtag_compounds_are_bounded() -> None:
    for function in ("TDO", "JTAG_TDO", "TDO_JTAG", "JTAG-TDO"):
        assert jtag_tdo_output_role("U1", function) == ("jtag_tdo", "jtag-tap")
    for function in ("TDO/SWO", "TDO_GPIO", "JTDO/RESET", "DATA_OUT", "TDI"):
        assert jtag_tdo_output_role("U1", function) is None

    assert not _findings(_report(_source(shared=False)))
    assert not _findings(_report(_source(functions=("JTAG_TDO", "JTAG_TDI"))))
    assert not _findings(_report(_source(references=("J1", "J2"))))


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_dnp_open_ambiguous_incomplete_and_duplicate_role_evidence_suppress() -> None:
    source = _source()
    dnp = _source(dnp_references=("U2",))
    open_pin = source.model_copy(update={"nets": {SHARED_NET: ("U1.4",)}})
    multiply_assigned = source.model_copy(update={"nets": {**source.nets, "EXTRA": ("U2.4",)}})
    missing_inventory = source.model_copy(
        update={"component_pin_numbers": {"U1": ("1", "2", "3", "4"), "U2": ()}}
    )
    duplicate_role = source.model_copy(
        update={
            "nets": {**source.nets, SHARED_NET: ("U1.4", "U1.5", "U2.4")},
            "pin_functions": {**source.pin_functions, "U1.5": "JTAG_TDO"},
            "pin_electrical_types": {**source.pin_electrical_types, "U1.5": "passive"},
            "component_pin_numbers": {"U1": ("1", "2", "3", "4", "5"), "U2": ("1", "2", "3", "4")},
        }
    )

    for case in (dnp, open_pin, multiply_assigned, missing_inventory, duplicate_role):
        assert not jtag_tdo_outputs_share_net_candidates(case)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_return_nets_and_native_output_conflicts_are_left_to_existing_checks() -> None:
    source = _source()
    return_net = source.model_copy(update={"nets": {"GND": ("U1.4", "U2.4")}})
    native_outputs = source.model_copy(
        update={
            "pin_electrical_types": {
                **source.pin_electrical_types,
                "U1.4": "output",
                "U2.4": "output",
            }
        }
    )

    assert not jtag_tdo_outputs_share_net_candidates(return_net)
    assert not jtag_tdo_outputs_share_net_candidates(native_outputs)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_project_policy_can_block_disable_or_exactly_ignore_review() -> None:
    finding = _findings(_report(_source()))[0]
    blocked = _findings(_report(_source(), "block"))[0]
    disabled = _findings(_report(_source(), "off"))[0]
    ignored = _findings(
        _report(
            _source(),
            ignore=DesignLintIgnore(
                rule_id=RULE_ID,
                fingerprint=finding.fingerprint,
                reason="A reviewed target mux selects one TAP at a time",
            ),
        )
    )[0]

    assert _report(_source(), "block").status == "FAIL"
    assert blocked.mode == "block"
    assert disabled.disposition == "RULE_OFF"
    assert ignored.disposition == "IGNORED"


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_fingerprint_is_order_stable_and_separating_outputs_clears_finding() -> None:
    original = _findings(_report(_source()))[0]
    reversed_references = _findings(_report(_source(references=("U2", "U1"))))[0]

    assert original.fingerprint == reversed_references.fingerprint
    assert not jtag_tdo_outputs_share_net_candidates(_source(shared=False))
