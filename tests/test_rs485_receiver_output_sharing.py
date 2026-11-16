"""Focused review tests for shared RS-485 receiver-output nets."""

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
from kicad_tooling.hwrepo.rs485_receiver_output_sharing import (
    rs485_receiver_output_sharing_candidates,
)
from tests.design_lint_fixtures import coach
from tests.design_lint_fixtures.rs485_receiver_output_sharing import (
    rs485_receiver_output_sharing_netlist,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint]

RULE_ID = "bus.rs485_receiver_outputs_share_net"


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
                reason="Review synthetic RS-485 receiver-output assignments",
            ),
        ),
        ignores=() if ignore is None else (ignore,),
    )
    return evaluate("synthetic-rs485-receiver-output-sharing", coach(netlist), policy)


def _findings(report: DesignLintReport) -> tuple[DesignLintFinding, ...]:
    return tuple(item for item in report.findings if item.rule_id == RULE_ID)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_multiple_fitted_rs485_receiver_outputs_on_one_net_are_reviewed() -> None:
    source = rs485_receiver_output_sharing_netlist()
    candidates = rs485_receiver_output_sharing_candidates(source)
    findings = _findings(_report(source))

    assert tuple(item.subject for item in candidates) == (
        "U1, U2: RS-485 receiver-output pins share RX_SHARED",
    )
    assert candidates[0].evidence["pins"] == ("U1.4", "U2.4")
    assert candidates[0].evidence["functions"] == ("RO", "RO")
    assert candidates[0].evidence["pin_types"] == ("passive", "passive")
    assert candidates[0].evidence["identity_basis"] == (
        "Synthetic:Rs485_Transceiver RS-485 transceiver",
    )
    assert findings[0].mode == "review"
    assert _report(source).status == "REVIEW"


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
@pytest.mark.parametrize(
    "functions",
    (("R", "RO"), ("receiver output", "RO"), ("RECEIVERDATAOUT", "R")),
)
def test_bounded_receiver_output_aliases_are_recognized(
    functions: tuple[str, str],
) -> None:
    assert (
        len(
            rs485_receiver_output_sharing_candidates(
                rs485_receiver_output_sharing_netlist(functions=functions)
            )
        )
        == 1
    )


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_separate_nets_and_one_dnp_endpoint_are_valid_controls() -> None:
    assert not rs485_receiver_output_sharing_candidates(
        rs485_receiver_output_sharing_netlist(shared=False)
    )
    assert not rs485_receiver_output_sharing_candidates(
        rs485_receiver_output_sharing_netlist(dnp=("U2",))
    )


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_non_rs485_devices_and_connectors_are_not_inferred_as_endpoints() -> None:
    generic = rs485_receiver_output_sharing_netlist(
        identities=("Logic IC", "Logic IC"),
        symbol="Synthetic:Logic",
    )
    connector = generic.model_copy(
        update={
            "components": {"J1": generic.components["U1"], "J2": generic.components["U2"]},
            "nets": {"RX_SHARED": ("J1.4", "J2.4")},
            "component_symbols": {
                "J1": "Synthetic:Rs485_Transceiver",
                "J2": "Synthetic:Rs485_Transceiver",
            },
            "pin_functions": {"J1.4": "RO", "J2.4": "RO"},
            "component_pin_numbers": {"J1": ("4",), "J2": ("4",)},
            "pin_electrical_types": {"J1.4": "passive", "J2.4": "passive"},
        }
    )

    assert not rs485_receiver_output_sharing_candidates(generic)
    assert not rs485_receiver_output_sharing_candidates(connector)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_ambiguous_or_incomplete_receiver_output_evidence_is_skipped() -> None:
    source = rs485_receiver_output_sharing_netlist()
    cases = (
        source.model_copy(
            update={
                "component_pin_numbers": {
                    "U1": ("1", "2", "3", "4", "4"),
                    "U2": ("1", "2", "3", "4", "5"),
                }
            }
        ),
        source.model_copy(
            update={
                "component_pin_numbers": {
                    "U1": ("1", "2", "3", "5"),
                    "U2": ("1", "2", "3", "4", "5"),
                }
            }
        ),
        source.model_copy(update={"pin_electrical_types": {"U1.4": "input", "U2.4": "passive"}}),
        source.model_copy(
            update={
                "pin_functions": {**source.pin_functions, "U1.5": "R"},
                "nets": {**source.nets, "U1_REF": ("U1.5",)},
            }
        ),
        source.model_copy(update={"nets": {**source.nets, "RX_AUX": ("U1.4",)}}),
    )

    for case in cases:
        assert not rs485_receiver_output_sharing_candidates(case)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_typed_output_conflicts_and_return_like_nets_are_left_to_existing_checks() -> None:
    output_conflict = rs485_receiver_output_sharing_netlist(pin_type="output")
    return_source = rs485_receiver_output_sharing_netlist()
    return_net = return_source.model_copy(
        update={
            "nets": {
                **{net: pins for net, pins in return_source.nets.items() if net != "RX_SHARED"},
                "GND": ("U1.4", "U2.4"),
            }
        }
    )

    assert not rs485_receiver_output_sharing_candidates(output_conflict)
    assert not rs485_receiver_output_sharing_candidates(return_net)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_project_policy_can_review_block_disable_or_ignore_the_exact_finding() -> None:
    source = rs485_receiver_output_sharing_netlist()
    initial = _findings(_report(source))[0]
    blocked = _findings(_report(source, "block"))[0]
    disabled = _findings(_report(source, "off"))[0]
    ignored = _findings(
        _report(
            source,
            ignore=DesignLintIgnore(
                rule_id=RULE_ID,
                fingerprint=initial.fingerprint,
                reason="Receiver outputs are multiplexed in this synthetic control",
            ),
        )
    )[0]

    assert _report(source, "block").status == "FAIL"
    assert blocked.mode == "block"
    assert disabled.disposition == "RULE_OFF"
    assert ignored.disposition == "IGNORED"


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_reordering_is_stable_and_separating_receiver_nets_clears_the_finding() -> None:
    source = rs485_receiver_output_sharing_netlist()
    reordered = source.model_copy(
        update={
            "components": dict(reversed(tuple(source.components.items()))),
            "nets": dict(reversed(tuple(source.nets.items()))),
            "pin_functions": dict(reversed(tuple(source.pin_functions.items()))),
            "pin_electrical_types": dict(reversed(tuple(source.pin_electrical_types.items()))),
        }
    )

    assert _findings(_report(reordered)) == _findings(_report(source))
    assert not rs485_receiver_output_sharing_candidates(
        rs485_receiver_output_sharing_netlist(shared=False)
    )
