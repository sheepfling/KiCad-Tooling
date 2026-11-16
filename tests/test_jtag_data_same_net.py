"""Regressions for JTAG endpoints whose TDI and TDO pins share a net."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.design_lint_finding_models import DesignLintIgnore, DesignLintRuleOverride
from kicad_tooling.hwrepo.design_lint_policy_models import DesignLintPolicy
from kicad_tooling.hwrepo.jtag_data_same_net import jtag_tdi_tdo_same_net_candidates
from tests.design_lint_fixtures import coach
from tests.design_lint_fixtures.jtag_data_same_net import jtag_data_same_net_netlist

pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint]

RULE_ID = "bus.jtag_tdi_tdo_same_net"


def _report(netlist, mode: str | None = None, *, ignore: DesignLintIgnore | None = None):
    overrides = (
        ()
        if mode is None
        else (
            DesignLintRuleOverride(
                rule_id=RULE_ID,
                mode=mode,
                reason="Review synthetic JTAG TDI/TDO assignment",
            ),
        )
    )
    policy = DesignLintPolicy(rules=overrides, ignores=() if ignore is None else (ignore,))
    return evaluate("synthetic-jtag-data-same-net", coach(netlist), policy)


def _findings(report):
    return tuple(item for item in report.findings if item.rule_id == RULE_ID)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_jtag_tdi_and_tdo_on_one_fitted_ic_net_are_reviewed() -> None:
    finding = _findings(_report(jtag_data_same_net_netlist()))[0]

    assert finding.mode == "review"
    assert finding.subject == "U1: JTAG TDI U1.3 and TDO U1.4 share JTAG_DATA_SHARED"
    assert finding.evidence == {
        "component": ("U1",),
        "TDI_pin": ("U1.3",),
        "TDI_function": ("JTAG_TDI",),
        "TDI_electrical_type": ("passive",),
        "TDO_pin": ("U1.4",),
        "TDO_function": ("JTAG_TDO",),
        "TDO_electrical_type": ("passive",),
        "shared_net": ("JTAG_DATA_SHARED",),
        "identity_basis": (
            "explicit JTAG pin-function metadata",
            "explicit JTAG pin-function metadata",
        ),
    }
    assert "Review whether this loopback is intentional" in finding.message


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_separate_data_nets_and_complete_generic_jtag_roles_are_controls() -> None:
    generic_names = jtag_data_same_net_netlist(functions=("TCK", "TMS", "TDI", "TDO"))

    assert not jtag_tdi_tdo_same_net_candidates(jtag_data_same_net_netlist(shared=False))
    assert len(jtag_tdi_tdo_same_net_candidates(generic_names)) == 1
    assert not _findings(_report(jtag_data_same_net_netlist(shared=False)))


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_dnp_non_ic_incomplete_ambiguous_open_and_multiply_assigned_cases_suppress() -> None:
    source = jtag_data_same_net_netlist()
    non_ic = jtag_data_same_net_netlist(reference="J1")
    incomplete = source.model_copy(update={"component_pin_numbers": {"U1": ("1", "2", "3")}})
    duplicate_role = source.model_copy(
        update={
            "pin_functions": {**source.pin_functions, "U1.5": "JTAG_TDI"},
            "pin_electrical_types": {**source.pin_electrical_types, "U1.5": "passive"},
            "component_pin_numbers": {"U1": ("1", "2", "3", "4", "5")},
            "nets": {**source.nets, "JTAG_DATA_SHARED": ("U1.3", "U1.4", "U1.5")},
        }
    )
    open_tdi = source.model_copy(
        update={
            "nets": {
                "JTAG_TCK_U1": ("U1.1",),
                "JTAG_TMS_U1": ("U1.2",),
                "JTAG_DATA_SHARED": ("U1.4",),
            }
        }
    )
    multiply_assigned = source.model_copy(update={"nets": {**source.nets, "ALTERNATE": ("U1.3",)}})
    case_distinct_nets = source.model_copy(
        update={
            "nets": {
                "JTAG_TCK_U1": ("U1.1",),
                "JTAG_TMS_U1": ("U1.2",),
                "JTAG_DATA_SHARED": ("U1.3",),
                "jtag_data_shared": ("U1.4",),
            }
        }
    )
    ambiguous_roles = source.model_copy(
        update={
            "pin_functions": {**source.pin_functions, "U1.5": "JTAG_TDI_TDO"},
            "pin_electrical_types": {**source.pin_electrical_types, "U1.5": "passive"},
            "component_pin_numbers": {"U1": ("1", "2", "3", "4", "5")},
            "nets": {**source.nets, "AUX": ("U1.5",)},
        }
    )

    cases = (
        jtag_data_same_net_netlist(dnp=True),
        non_ic,
        incomplete,
        duplicate_role,
        open_tdi,
        multiply_assigned,
        case_distinct_nets,
        ambiguous_roles,
    )
    assert all(not jtag_tdi_tdo_same_net_candidates(case) for case in cases)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_return_net_and_two_native_output_conflict_are_left_to_existing_checks() -> None:
    source = jtag_data_same_net_netlist()
    return_net = source.model_copy(update={"nets": {"GND": ("U1.3", "U1.4")}})
    native_outputs = jtag_data_same_net_netlist(pin_types=("output", "output"))
    one_output = jtag_data_same_net_netlist(pin_types=("input", "output"))

    assert not jtag_tdi_tdo_same_net_candidates(return_net)
    assert not jtag_tdi_tdo_same_net_candidates(native_outputs)
    assert len(jtag_tdi_tdo_same_net_candidates(one_output)) == 1


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_project_policy_can_block_disable_or_exactly_ignore_review() -> None:
    source = jtag_data_same_net_netlist()
    finding = _findings(_report(source))[0]
    blocked = _findings(_report(source, "block"))[0]
    disabled = _findings(_report(source, "off"))[0]
    ignored = _findings(
        _report(
            source,
            ignore=DesignLintIgnore(
                rule_id=RULE_ID,
                fingerprint=finding.fingerprint,
                reason="A reviewed test loopback is intentional",
            ),
        )
    )[0]

    assert _report(source, "block").status == "FAIL"
    assert blocked.mode == "block"
    assert disabled.disposition == "RULE_OFF"
    assert ignored.disposition == "IGNORED"


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_mapping_order_preserves_fingerprint_and_separation_repairs_candidate() -> None:
    source = jtag_data_same_net_netlist()
    original = _findings(_report(source))[0]
    reordered = source.model_copy(
        update={
            "nets": dict(reversed(tuple(source.nets.items()))),
            "pin_functions": dict(reversed(tuple(source.pin_functions.items()))),
        }
    )

    assert _findings(_report(reordered))[0].fingerprint == original.fingerprint
    assert not jtag_tdi_tdo_same_net_candidates(jtag_data_same_net_netlist(shared=False))
