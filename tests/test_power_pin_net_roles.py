"""Named power-pin and net-role conflict review regressions."""

from __future__ import annotations

from collections.abc import Mapping

import pytest

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.models import (
    ComponentContract,
    DesignLintIgnore,
    DesignLintPolicy,
    DesignLintReport,
    DesignLintRuleOverride,
    NetlistContract,
)
from tests.design_lint_fixtures import coach
from tests.design_lint_fixtures.power_pin_net_roles import positive_supply_on_return_netlist

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.power_lint,
    pytest.mark.component_lint,
]

RULE_ID = "power.pin_function_net_role_conflict"


def _netlist(
    nets: Mapping[str, tuple[str, ...]],
    pin_functions: Mapping[str, str],
    *,
    dnp: tuple[str, ...] = (),
) -> NetlistContract:
    references = {pin.rsplit(".", 1)[0] for pin in pin_functions}
    return NetlistContract(
        components={
            reference: ComponentContract(value="Synthetic IC", footprint="Synthetic:IC")
            for reference in references
        },
        nets=nets,
        dnp_components=dnp,
        component_symbols={reference: "Synthetic:Logic" for reference in references},
        component_pin_numbers={
            reference: tuple(
                sorted(
                    pin.rsplit(".", 1)[1]
                    for pin in pin_functions
                    if pin.rsplit(".", 1)[0] == reference
                )
            )
            for reference in references
        },
        pin_functions=pin_functions,
        pin_electrical_types={pin: "passive" for pin in pin_functions},
    )


def _report(
    observed: NetlistContract,
    policy: DesignLintPolicy | None = None,
) -> DesignLintReport:
    return evaluate(
        "synthetic-power-pin-net-roles",
        coach(observed),
        policy or DesignLintPolicy(),
    )


def _findings(observed: NetlistContract):
    return tuple(item for item in _report(observed).findings if item.rule_id == RULE_ID)


def test_positive_supply_pin_on_return_net_is_reviewed_with_role_evidence() -> None:
    observed = positive_supply_on_return_netlist()

    report = _report(observed)
    findings = tuple(item for item in report.findings if item.rule_id == RULE_ID)

    assert report.status == "REVIEW"
    assert len(findings) == 1
    assert findings[0].subject == "U1.1: VDD pin assigned to GND"
    assert findings[0].evidence == {
        "U1.1": ("native_function=VDD", "pin_role=positive_supply:vdd"),
        "assigned_net": ("GND",),
        "opposite_net_role_sources": ("net_name=return_like",),
    }
    assert "not proof of electrical potential" in findings[0].message


def test_return_label_precedence_prevents_duplicate_peer_role_finding() -> None:
    observed = _netlist(
        {"GND": ("U1.1", "U1.2")},
        {"U1.1": "VDD", "U1.2": "GND"},
    )

    findings = _findings(observed)

    assert [item.subject for item in findings] == ["U1.1: VDD pin assigned to GND"]
    assert findings[0].evidence["opposite_net_role_sources"] == ("net_name=return_like",)


def test_net_role_can_come_from_a_peer_pin_function_without_a_named_rail() -> None:
    observed = _netlist(
        {"LOCAL_REFERENCE": ("U1.1", "U1.2", "U2.2")},
        {"U1.1": "VDD", "U1.2": "GND", "U2.2": "GND"},
    )

    findings = _findings(observed)
    assert {item.subject for item in findings} == {
        "U1.1: VDD pin assigned to LOCAL_REFERENCE",
        "U1.2: GND pin assigned to LOCAL_REFERENCE",
        "U2.2: GND pin assigned to LOCAL_REFERENCE",
    }
    assert next(item for item in findings if item.subject.startswith("U1.1")).evidence[
        "opposite_net_role_sources"
    ] == ("U1.2:native_function=GND", "U2.2:native_function=GND")


def test_return_pin_on_positive_rail_is_reported_and_connector_rule_owns_connector_returns() -> (
    None
):
    component = _netlist(
        {"+3V3": ("U1.1", "U1.2")},
        {"U1.1": "VDD", "U1.2": "GND"},
    )
    connector = _netlist(
        {"+3V3": ("J1.1", "J1.2")},
        {"J1.1": "VDD", "J1.2": "GND"},
    )

    component_findings = _findings(component)
    connector_report = _report(connector)

    assert {item.subject for item in component_findings} == {"U1.2: GND pin assigned to +3V3"}
    assert RULE_ID not in {item.rule_id for item in connector_report.findings}
    assert "connector.return_pin_on_positive_rail" in {
        item.rule_id for item in connector_report.findings
    }


def test_positive_supply_connector_pin_on_return_net_remains_in_scope() -> None:
    observed = _netlist({"GND": ("J1.1",)}, {"J1.1": "VBUS"})

    findings = _findings(observed)

    assert len(findings) == 1
    assert findings[0].subject == "J1.1: VBUS pin assigned to GND"


def test_positive_supply_connector_pin_on_positive_rail_is_a_valid_control() -> None:
    observed = _netlist({"+5V": ("J1.1",)}, {"J1.1": "VBUS"})

    assert not _findings(observed)


@pytest.mark.parametrize(
    "observed",
    (
        _netlist(
            {"+3V3": ("U1.1",), "GND": ("U1.2",)},
            {"U1.1": "VDD", "U1.2": "GND"},
        ),
        _netlist(
            {"-5V": ("U1.1",), "GND": ("U1.2",)},
            {"U1.1": "VDD", "U1.2": "GND"},
        ),
        _netlist(
            {"GND": ("U1.1",), "SIGNAL": ("U1.2",)},
            {"U1.1": "BIAS", "U1.2": "DATA"},
        ),
        _netlist(
            {"LOCAL": ("U1.1",), "GND": ("U1.2",)},
            {"U1.1": "VDD", "U1.2": "GND"},
        ),
        _netlist(
            {"GND": ("U1.2",)},
            {"U1.1": "VDD", "U1.2": "GND"},
        ),
        _netlist(
            {"GND": ("U1.1", "U1.2")},
            {"U1.1": "VDD", "U1.2": "GND"},
            dnp=("U1",),
        ),
    ),
)
def test_common_negative_unrecognized_open_and_dnp_cases_are_controls(
    observed: NetlistContract,
) -> None:
    assert not _findings(observed)


def test_multi_assigned_pin_and_self_role_do_not_create_conflict_evidence() -> None:
    multi_assigned = _netlist(
        {"GND": ("U1.1",), "+3V3": ("U1.1",), "SIGNAL": ("U1.2",)},
        {"U1.1": "VDD", "U1.2": "DATA"},
    )
    custom_net_without_peer_role = _netlist(
        {"LOCAL": ("U1.1",)},
        {"U1.1": "VDD"},
    )

    assert not _findings(multi_assigned)
    assert not _findings(custom_net_without_peer_role)


def test_project_policy_can_block_turn_off_or_exactly_ignore_the_candidate() -> None:
    observed = _netlist(
        {"GND": ("U1.1",)},
        {"U1.1": "VDD"},
    )
    initial = _report(observed)
    finding = next(item for item in initial.findings if item.rule_id == RULE_ID)
    blocked = _report(
        observed,
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=RULE_ID,
                    mode="block",
                    reason="Synthetic project requires named power-pin role review",
                ),
            )
        ),
    )
    disabled = _report(
        observed,
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=RULE_ID,
                    mode="off",
                    reason="Synthetic project documents this intentional net assignment",
                ),
            )
        ),
    )
    ignored = _report(
        observed,
        DesignLintPolicy(
            ignores=(
                DesignLintIgnore(
                    rule_id=RULE_ID,
                    fingerprint=finding.fingerprint,
                    reason="Synthetic project documents an intentional isolated reference",
                ),
            )
        ),
    )

    assert blocked.status == "FAIL"
    assert next(item for item in blocked.findings if item.rule_id == RULE_ID).mode == "block"
    assert disabled.status == "PASS"
    assert (
        next(item for item in disabled.findings if item.rule_id == RULE_ID).disposition
        == "RULE_OFF"
    )
    assert ignored.status == "PASS"
    assert (
        next(item for item in ignored.findings if item.rule_id == RULE_ID).disposition == "IGNORED"
    )


def test_fingerprint_is_order_stable_and_reassignment_clears_the_candidate() -> None:
    observed = _netlist(
        {"GND": ("U1.1",), "SIGNAL": ("U1.2",)},
        {"U1.1": "VDD", "U1.2": "DATA"},
    )
    reordered = observed.model_copy(
        update={
            "nets": dict(reversed(tuple(observed.nets.items()))),
            "pin_functions": dict(reversed(tuple(observed.pin_functions.items()))),
        }
    )
    corrected = observed.model_copy(update={"nets": {"+3V3": ("U1.1",), "SIGNAL": ("U1.2",)}})

    original = _findings(observed)[0]
    stable = _findings(reordered)[0]
    assert (stable.fingerprint, stable.evidence) == (original.fingerprint, original.evidence)
    assert not _findings(corrected)


def test_peer_pin_role_evidence_is_order_stable() -> None:
    observed = _netlist(
        {"LOCAL": ("U1.1", "U2.2", "U3.2")},
        {"U1.1": "VDD", "U2.2": "GND", "U3.2": "GND"},
    )
    reordered = observed.model_copy(
        update={"nets": {"LOCAL": tuple(reversed(observed.nets["LOCAL"]))}}
    )

    original = next(item for item in _findings(observed) if item.subject.startswith("U1.1"))
    stable = next(item for item in _findings(reordered) if item.subject.startswith("U1.1"))
    assert (stable.fingerprint, stable.evidence) == (original.fingerprint, original.evidence)
