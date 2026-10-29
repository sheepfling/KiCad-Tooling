"""Focused checks for asymmetric USB-C SBU function assignments."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.design_lint_finding_models import DesignLintIgnore
from kicad_tooling.hwrepo.design_lint_policy_models import DesignLintPolicy
from kicad_tooling.hwrepo.design_lint_report_models import DesignLintReport
from kicad_tooling.hwrepo.models import ComponentContract, DesignLintRuleOverride, NetlistContract
from kicad_tooling.hwrepo.usb_c_sbu_same_net import usb_c_sbu_same_net_candidates
from tests.design_lint_fixtures import coach
from tests.design_lint_fixtures.usb_c_sbu_named_rail import usb_c_sbu_named_rail_netlist
from tests.design_lint_fixtures.usb_c_sbu_same_net import usb_c_sbu_same_net_netlist

RULE_ID = "bus.usb_c_sbu_unconnected_pin"

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.interface_lint,
    pytest.mark.design_lint_rule(rule_id=RULE_ID),
]


def _report(source: NetlistContract, policy: DesignLintPolicy | None = None) -> DesignLintReport:
    return evaluate(
        "synthetic-usb-c-sbu-unconnected",
        coach(source),
        DesignLintPolicy() if policy is None else policy,
    )


@pytest.mark.parametrize(
    ("sbu1_net", "sbu2_net", "open_pin", "open_function", "paired_pin", "paired_net"),
    (
        (None, "SBU2_BUS", "U1.1", "SBU1", "U1.2", "SBU2_BUS"),
        ("SBU1_BUS", None, "U1.2", "SBU2", "U1.1", "SBU1_BUS"),
    ),
)
def test_one_open_sbu_pin_beside_assigned_peer_requests_review(
    sbu1_net: str | None,
    sbu2_net: str | None,
    open_pin: str,
    open_function: str,
    paired_pin: str,
    paired_net: str,
) -> None:
    report = _report(usb_c_sbu_named_rail_netlist(sbu1_net=sbu1_net, sbu2_net=sbu2_net))
    finding = next(item for item in report.findings if item.rule_id == RULE_ID)

    assert report.status == "REVIEW"
    assert finding.subject == f"{open_pin}: {open_function}"
    assert finding.evidence == {
        open_pin: (),
        "function": (open_function,),
        "usb_c_sbu_role": (open_function,),
        "paired_pin": (paired_pin,),
        "paired_function": ("SBU2" if open_function == "SBU1" else "SBU1",),
        "paired_net": (paired_net,),
    }
    assert "Function names do not establish controller identity" in finding.message


def test_both_connected_and_both_open_pairs_are_quiet() -> None:
    controls = (
        usb_c_sbu_named_rail_netlist(sbu1_net="AUX1", sbu2_net="AUX2"),
        usb_c_sbu_named_rail_netlist(sbu1_net=None, sbu2_net=None),
    )

    for source in controls:
        assert not any(item.rule_id == RULE_ID for item in _report(source).findings)


def test_dnp_connector_duplicate_role_incomplete_inventory_and_ambiguous_pin_are_skipped() -> None:
    source = usb_c_sbu_named_rail_netlist(sbu1_net=None, sbu2_net="AUX2")
    duplicate = source.model_copy(
        update={
            "pin_functions": {**source.pin_functions, "U1.3": "SBU1"},
            "component_pin_numbers": {"U1": ("1", "2", "3")},
        }
    )
    connector = source.model_copy(
        update={
            "components": {"J1": source.components["U1"]},
            "component_symbols": {"J1": "Synthetic:USB_C_Controller"},
            "pin_functions": {"J1.1": "SBU1", "J1.2": "SBU2"},
            "component_pin_numbers": {"J1": ("1", "2")},
            "nets": {"AUX2": ("J1.2",)},
        }
    )
    ambiguous = source.model_copy(update={"nets": {"AUX2": ("U1.2",), "AUX3": ("U1.2",)}})
    controls = (
        usb_c_sbu_named_rail_netlist(sbu1_net=None, sbu2_net="AUX2", dnp=True),
        duplicate,
        connector,
        source.model_copy(update={"component_pin_numbers": {"U1": ("2",)}}),
        ambiguous,
    )

    for control in controls:
        assert not any(item.rule_id == RULE_ID for item in _report(control).findings)


def test_aliases_require_unique_native_sbu_roles_on_fitted_ic() -> None:
    source = usb_c_sbu_named_rail_netlist(
        sbu1_net=None, sbu2_net="AUX2", sbu1_function="sbu_1", sbu2_function="SBU-2"
    )
    non_ic = source.model_copy(
        update={
            "components": {"Q1": ComponentContract(value="SBU switch", footprint="Synthetic:QFN")},
            "component_symbols": {"Q1": "Synthetic:USB_C_Controller"},
            "pin_functions": {"Q1.1": "SBU1", "Q1.2": "SBU2"},
            "component_pin_numbers": {"Q1": ("1", "2")},
            "nets": {"AUX2": ("Q1.2",)},
        }
    )

    assert any(item.rule_id == RULE_ID for item in _report(source).findings)
    assert not any(item.rule_id == RULE_ID for item in _report(non_ic).findings)


def test_policy_can_block_turn_off_or_exact_ignore() -> None:
    source = usb_c_sbu_named_rail_netlist(sbu1_net=None, sbu2_net="AUX2")
    finding = next(item for item in _report(source).findings if item.rule_id == RULE_ID)
    blocked = _report(
        source,
        DesignLintPolicy(
            rules=(DesignLintRuleOverride(rule_id=RULE_ID, mode="block", reason="reviewed"),)
        ),
    )
    disabled = _report(
        source,
        DesignLintPolicy(
            rules=(DesignLintRuleOverride(rule_id=RULE_ID, mode="off", reason="reviewed"),)
        ),
    )
    ignored = _report(
        source,
        DesignLintPolicy(
            ignores=(
                DesignLintIgnore(rule_id=RULE_ID, fingerprint=finding.fingerprint, reason="unused"),
            )
        ),
    )

    assert blocked.status == "FAIL"
    assert (
        next(item for item in disabled.findings if item.rule_id == RULE_ID).disposition
        == "RULE_OFF"
    )
    assert (
        next(item for item in ignored.findings if item.rule_id == RULE_ID).disposition == "IGNORED"
    )


def test_reordering_and_repair_preserve_expected_finding_behavior() -> None:
    source = usb_c_sbu_named_rail_netlist(sbu1_net="AUX1", sbu2_net=None)
    reordered = source.model_copy(update={"nets": dict(reversed(tuple(source.nets.items())))})
    original = tuple(item for item in _report(source).findings if item.rule_id == RULE_ID)
    reversed_findings = tuple(
        item for item in _report(reordered).findings if item.rule_id == RULE_ID
    )
    repaired = usb_c_sbu_named_rail_netlist(sbu1_net="AUX1", sbu2_net="AUX2")

    assert tuple(item.model_dump() for item in original) == tuple(
        item.model_dump() for item in reversed_findings
    )
    assert not any(item.rule_id == RULE_ID for item in _report(repaired).findings)


SAME_NET_RULE_ID = "bus.usb_c_sbu_same_net"


@pytest.mark.design_lint_rule(rule_id=SAME_NET_RULE_ID)
def test_controller_sbu1_sbu2_on_one_net_request_review() -> None:
    source = usb_c_sbu_same_net_netlist()
    report = evaluate("synthetic-usb-c-sbu-same-net", coach(source), DesignLintPolicy())
    findings = tuple(item for item in report.findings if item.rule_id == SAME_NET_RULE_ID)

    assert report.status == "REVIEW"
    assert len(findings) == 1
    assert findings[0].subject == "U1: USB-C SBU1/SBU2 pins share SBU_SHARED"
    assert findings[0].evidence == {
        "component": ("U1",),
        "SBU1_pin": ("U1.1",),
        "SBU1_function": ("SBU1",),
        "SBU2_pin": ("U1.2",),
        "SBU2_function": ("SBU2",),
        "net": ("SBU_SHARED",),
    }
    assert "exact controller pinout" in findings[0].message


@pytest.mark.design_lint_rule(rule_id=SAME_NET_RULE_ID)
def test_distinct_nets_dnp_connector_duplicate_and_incomplete_inputs_are_quiet() -> None:
    source = usb_c_sbu_same_net_netlist()
    cases = (
        usb_c_sbu_same_net_netlist(shared=False),
        usb_c_sbu_same_net_netlist(dnp=True),
        usb_c_sbu_same_net_netlist(reference="J1"),
        usb_c_sbu_same_net_netlist(functions=("SBU1", "SBU1")),
        usb_c_sbu_same_net_netlist(reference="UFO"),
        usb_c_sbu_same_net_netlist(inventory=("1",)),
        source.model_copy(update={"nets": {"SBU_SHARED": ("U1.1",)}}),
        source.model_copy(update={"nets": {"SBU_SHARED": ("U1.1", "U1.2"), "OTHER": ("U1.2",)}}),
    )

    assert usb_c_sbu_same_net_candidates(source)
    for case in cases:
        assert not usb_c_sbu_same_net_candidates(case)


@pytest.mark.design_lint_rule(rule_id=SAME_NET_RULE_ID)
def test_two_native_output_pins_are_left_to_erc() -> None:
    source = usb_c_sbu_same_net_netlist()
    outputs = source.model_copy(
        update={"pin_electrical_types": {"U1.1": "output", "U1.2": "output"}}
    )
    one_output = source.model_copy(
        update={"pin_electrical_types": {"U1.1": "output", "U1.2": "bidirectional"}}
    )

    assert not usb_c_sbu_same_net_candidates(outputs)
    assert usb_c_sbu_same_net_candidates(one_output)


@pytest.mark.design_lint_rule(rule_id=SAME_NET_RULE_ID)
def test_sbu_same_net_policy_can_block_disable_or_exactly_ignore() -> None:
    source = usb_c_sbu_same_net_netlist()
    finding = next(
        item
        for item in evaluate(
            "synthetic-usb-c-sbu-same-net", coach(source), DesignLintPolicy()
        ).findings
        if item.rule_id == SAME_NET_RULE_ID
    )

    def reviewed(mode: str) -> DesignLintReport:
        policy = DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=SAME_NET_RULE_ID,
                    mode=mode,
                    reason="Reviewed synthetic SBU topology",
                ),
            )
        )
        return evaluate("synthetic-usb-c-sbu-same-net", coach(source), policy)

    blocked = reviewed("block")
    disabled = reviewed("off")
    ignored = evaluate(
        "synthetic-usb-c-sbu-same-net",
        coach(source),
        DesignLintPolicy(
            ignores=(
                DesignLintIgnore(
                    rule_id=SAME_NET_RULE_ID,
                    fingerprint=finding.fingerprint,
                    reason="Reviewed controller-specific pinout",
                ),
            )
        ),
    )

    assert blocked.status == "FAIL"
    assert (
        next(item for item in blocked.findings if item.rule_id == SAME_NET_RULE_ID).mode == "block"
    )
    assert (
        next(item for item in disabled.findings if item.rule_id == SAME_NET_RULE_ID).disposition
        == "RULE_OFF"
    )
    assert (
        next(item for item in ignored.findings if item.rule_id == SAME_NET_RULE_ID).disposition
        == "IGNORED"
    )


@pytest.mark.design_lint_rule(rule_id=SAME_NET_RULE_ID)
def test_sbu_same_net_ordering_is_stable_and_separating_lines_clears_finding() -> None:
    source = usb_c_sbu_same_net_netlist()
    reordered = source.model_copy(
        update={
            "components": dict(reversed(tuple(source.components.items()))),
            "nets": dict(reversed(tuple(source.nets.items()))),
            "pin_functions": dict(reversed(tuple(source.pin_functions.items()))),
        }
    )
    first = usb_c_sbu_same_net_candidates(source)
    second = usb_c_sbu_same_net_candidates(reordered)

    assert first == second
    assert not usb_c_sbu_same_net_candidates(usb_c_sbu_same_net_netlist(shared=False))
