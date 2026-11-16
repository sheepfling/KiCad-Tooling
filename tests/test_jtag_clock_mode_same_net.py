"""Regressions for JTAG TCK and TMS pins sharing a fitted IC net."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.design_lint_finding_models import DesignLintIgnore, DesignLintRuleOverride
from kicad_tooling.hwrepo.design_lint_policy_models import DesignLintPolicy
from kicad_tooling.hwrepo.jtag_clock_mode_same_net import jtag_tck_tms_same_net_candidates
from kicad_tooling.hwrepo.jtag_data_same_net import jtag_tdi_tdo_same_net_candidates
from tests.design_lint_fixtures import coach
from tests.design_lint_fixtures.jtag_clock_mode_same_net import (
    jtag_clock_mode_same_net_netlist,
)
from tests.design_lint_fixtures.jtag_data_same_net import jtag_data_same_net_netlist

pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint]

RULE_ID = "bus.jtag_tck_tms_same_net"


def _report(netlist, mode: str | None = None, *, ignore: DesignLintIgnore | None = None):
    overrides = (
        ()
        if mode is None
        else (
            DesignLintRuleOverride(
                rule_id=RULE_ID,
                mode=mode,
                reason="Review synthetic JTAG clock/mode assignment",
            ),
        )
    )
    policy = DesignLintPolicy(rules=overrides, ignores=() if ignore is None else (ignore,))
    return evaluate("synthetic-jtag-clock-mode-same-net", coach(netlist), policy)


def _findings(report):
    return tuple(item for item in report.findings if item.rule_id == RULE_ID)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_jtag_tck_and_tms_on_one_fitted_ic_net_are_reviewed() -> None:
    source = jtag_clock_mode_same_net_netlist()
    finding = _findings(_report(source))[0]

    assert finding.mode == "review"
    assert finding.subject == ("U1: JTAG TCK U1.1 and TMS U1.2 share JTAG_CLOCK_MODE_SHARED")
    assert finding.evidence == {
        "component": ("U1",),
        "TCK_pin": ("U1.1",),
        "TCK_function": ("JTAG_TCK",),
        "TCK_electrical_type": ("passive",),
        "TMS_pin": ("U1.2",),
        "TMS_function": ("JTAG_TMS",),
        "TMS_electrical_type": ("passive",),
        "shared_net": ("JTAG_CLOCK_MODE_SHARED",),
        "identity_basis": (
            "explicit JTAG pin-function metadata",
            "explicit JTAG pin-function metadata",
        ),
    }
    assert "Review whether this clock and mode-control connection is intentional" in finding.message
    assert not jtag_tdi_tdo_same_net_candidates(source)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_separate_tck_tms_nets_and_generic_jtag_pair_are_controls() -> None:
    separate = jtag_data_same_net_netlist(shared=False)
    generic = separate.model_copy(
        update={
            "pin_functions": {
                **separate.pin_functions,
                "U1.1": "TCK",
                "U1.2": "TMS",
                "U1.3": "TDI",
                "U1.4": "TDO",
            }
        }
    )

    assert not jtag_tck_tms_same_net_candidates(separate)
    assert not _findings(_report(separate))
    generic_shared = generic.model_copy(update={"nets": jtag_clock_mode_same_net_netlist().nets})
    assert len(jtag_tck_tms_same_net_candidates(generic_shared)) == 1


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_dnp_non_ic_incomplete_duplicate_open_and_ambiguous_cases_suppress() -> None:
    source = jtag_clock_mode_same_net_netlist()
    non_ic = source.model_copy(
        update={
            "components": {"J1": source.components["U1"]},
            "component_symbols": {"J1": source.component_symbols["U1"]},
            "component_pin_numbers": {"J1": source.component_pin_numbers["U1"]},
            "pin_functions": {
                pin.replace("U1", "J1"): function for pin, function in source.pin_functions.items()
            },
            "pin_electrical_types": {
                pin.replace("U1", "J1"): kind for pin, kind in source.pin_electrical_types.items()
            },
            "nets": {
                name: tuple(pin.replace("U1", "J1") for pin in pins)
                for name, pins in source.nets.items()
            },
        }
    )
    incomplete = source.model_copy(update={"component_pin_numbers": {"U1": ("1", "2", "3")}})
    duplicate_role = source.model_copy(
        update={
            "component_pin_numbers": {"U1": ("1", "2", "3", "4", "5")},
            "pin_functions": {**source.pin_functions, "U1.5": "JTAG_TCK"},
            "pin_electrical_types": {**source.pin_electrical_types, "U1.5": "input"},
            "nets": {**source.nets, "AUX": ("U1.5",)},
        }
    )
    open_tms = source.model_copy(
        update={
            "nets": {
                "JTAG_CLOCK_MODE_SHARED": ("U1.1",),
                "JTAG_TDI_U1": ("U1.3",),
                "JTAG_TDO_U1": ("U1.4",),
            }
        }
    )
    multiply_assigned = source.model_copy(update={"nets": {**source.nets, "ALTERNATE": ("U1.2",)}})
    case_distinct = source.model_copy(
        update={
            "nets": {
                "JTAG_CLOCK_MODE_SHARED": ("U1.1",),
                "jtag_clock_mode_shared": ("U1.2",),
                "JTAG_TDI_U1": ("U1.3",),
                "JTAG_TDO_U1": ("U1.4",),
            }
        }
    )

    cases = (
        source.model_copy(update={"dnp_components": ("U1",)}),
        non_ic,
        incomplete,
        duplicate_role,
        open_tms,
        multiply_assigned,
        case_distinct,
    )
    assert all(not jtag_tck_tms_same_net_candidates(case) for case in cases)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_return_net_and_two_native_output_conflict_are_left_to_existing_checks() -> None:
    source = jtag_clock_mode_same_net_netlist()
    return_net = source.model_copy(update={"nets": {"GND": ("U1.1", "U1.2")}})
    native_outputs = source.model_copy(
        update={
            "pin_electrical_types": {
                **source.pin_electrical_types,
                "U1.1": "output",
                "U1.2": "output",
            }
        }
    )
    one_output = source.model_copy(
        update={
            "pin_electrical_types": {
                **source.pin_electrical_types,
                "U1.1": "output",
            }
        }
    )

    assert not jtag_tck_tms_same_net_candidates(return_net)
    assert not jtag_tck_tms_same_net_candidates(native_outputs)
    assert len(jtag_tck_tms_same_net_candidates(one_output)) == 1


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_project_policy_can_block_disable_or_exactly_ignore_review() -> None:
    source = jtag_clock_mode_same_net_netlist()
    finding = _findings(_report(source))[0]
    blocked = _findings(_report(source, "block"))[0]
    disabled = _findings(_report(source, "off"))[0]
    ignored = _findings(
        _report(
            source,
            ignore=DesignLintIgnore(
                rule_id=RULE_ID,
                fingerprint=finding.fingerprint,
                reason="A reviewed test topology intentionally shares these pins",
            ),
        )
    )[0]

    assert _report(source, "block").status == "FAIL"
    assert blocked.mode == "block"
    assert disabled.disposition == "RULE_OFF"
    assert ignored.disposition == "IGNORED"


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_mapping_order_preserves_fingerprint_and_separation_repairs_candidate() -> None:
    source = jtag_clock_mode_same_net_netlist()
    original = _findings(_report(source))[0]
    reordered = source.model_copy(
        update={
            "nets": dict(reversed(tuple(source.nets.items()))),
            "pin_functions": dict(reversed(tuple(source.pin_functions.items()))),
        }
    )

    assert _findings(_report(reordered))[0].fingerprint == original.fingerprint
    assert not jtag_tck_tms_same_net_candidates(jtag_data_same_net_netlist(shared=False))
