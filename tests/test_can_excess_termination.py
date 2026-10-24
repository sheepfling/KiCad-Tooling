"""CAN over-termination review lint regressions."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.design_lint_finding_models import DesignLintFinding
from kicad_tooling.hwrepo.design_lint_report_models import DesignLintReport
from kicad_tooling.hwrepo.models import (
    ComponentContract,
    DesignLintIgnore,
    DesignLintPolicy,
    DesignLintRuleOverride,
    NetlistContract,
)
from tests.design_lint_fixtures import can_netlist, coach

RULE_ID = "bus.can_excess_termination"

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.interface_lint,
    pytest.mark.design_lint_rule(rule_id=RULE_ID),
]


def _can_netlist_with_direct_terminators(
    values: tuple[str, ...], *, dnp: tuple[str, ...] = ()
) -> NetlistContract:
    source = can_netlist()
    components = dict(source.components)
    symbols = dict(source.component_symbols)
    pin_functions = dict(source.pin_functions)
    nets = dict(source.nets)
    for index, value in enumerate(values, start=1):
        reference = f"R{index}"
        components[reference] = ComponentContract(value=value, footprint="Synthetic:R")
        symbols[reference] = "Device:R"
        pin_functions[f"{reference}.1"] = "1"
        pin_functions[f"{reference}.2"] = "2"
        nets["CAN_HIGH"] = (*nets["CAN_HIGH"], f"{reference}.1")
        nets["CAN_LOW"] = (*nets["CAN_LOW"], f"{reference}.2")
    return source.model_copy(
        update={
            "components": components,
            "component_symbols": symbols,
            "pin_functions": pin_functions,
            "nets": nets,
            "dnp_components": dnp,
        }
    )


def _findings(report: DesignLintReport, rule_id: str = RULE_ID) -> tuple[DesignLintFinding, ...]:
    return tuple(item for item in report.findings if item.rule_id == rule_id)


def test_three_fitted_direct_terminators_prompt_for_bus_topology_review() -> None:
    source = _can_netlist_with_direct_terminators(("108R", "120R", "132R"))
    fault = evaluate("synthetic-can-overtermination", coach(source), DesignLintPolicy())

    assert fault.status == "REVIEW"
    assert len(_findings(fault)) == 1
    finding = _findings(fault)[0]
    assert finding.mode == "review"
    assert finding.subject == "CANH CAN_HIGH / CANL CAN_LOW"
    assert finding.evidence == {
        "CANH": ("CAN_HIGH",),
        "CANL": ("CAN_LOW",),
        "pins": ("U1.1", "U1.2"),
        "terminations": ("R1=108 Ω", "R2=120 Ω", "R3=132 Ω"),
    }
    assert "physical bus ends" in finding.message

    crossed_peer = source.model_copy(
        update={
            "components": {
                **source.components,
                "U2": ComponentContract(value="Synthetic CAN transceiver", footprint=""),
            },
            "component_symbols": {**source.component_symbols, "U2": "Synthetic:CanTransceiver"},
            "pin_functions": {
                **source.pin_functions,
                "U2.1": "CANH",
                "U2.2": "CAN_L",
            },
            "nets": {
                **source.nets,
                "CAN_HIGH": (*source.nets["CAN_HIGH"], "U2.2"),
                "CAN_LOW": (*source.nets["CAN_LOW"], "U2.1"),
            },
        }
    )
    crossed_peer_report = evaluate(
        "synthetic-can-overtermination", coach(crossed_peer), DesignLintPolicy()
    )
    assert len(_findings(crossed_peer_report)) == 1

    blocked = evaluate(
        "synthetic-can-overtermination",
        coach(_can_netlist_with_direct_terminators(("108R", "120R", "132R"))),
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=RULE_ID,
                    mode="block",
                    reason="Review the mapped bus before release",
                ),
            )
        ),
    )
    assert blocked.status == "FAIL"

    ignored = evaluate(
        "synthetic-can-overtermination",
        coach(_can_netlist_with_direct_terminators(("108R", "120R", "132R"))),
        DesignLintPolicy(
            ignores=(
                DesignLintIgnore(
                    rule_id=RULE_ID,
                    fingerprint=finding.fingerprint,
                    reason="Synthetic multi-drop termination control",
                ),
            )
        ),
    )
    assert ignored.status == "PASS"
    assert _findings(ignored)[0].disposition == "IGNORED"


def test_two_terminators_and_nonlocal_or_unfitted_parts_are_valid_controls() -> None:
    two_terminators = evaluate(
        "synthetic-can-overtermination",
        coach(_can_netlist_with_direct_terminators(("120R", "121R"))),
        DesignLintPolicy(),
    )
    assert not _findings(two_terminators)

    dnp_third_terminator = evaluate(
        "synthetic-can-overtermination",
        coach(_can_netlist_with_direct_terminators(("120R", "121R", "122R"), dnp=("R3",))),
        DesignLintPolicy(),
    )
    assert not _findings(dnp_third_terminator)

    dnp_controller_source = _can_netlist_with_direct_terminators(
        ("120R", "121R", "122R")
    ).model_copy(update={"dnp_components": ("U1",)})
    dnp_controller = evaluate(
        "synthetic-can-overtermination", coach(dnp_controller_source), DesignLintPolicy()
    )
    assert not _findings(dnp_controller)

    outside_window = evaluate(
        "synthetic-can-overtermination",
        coach(_can_netlist_with_direct_terminators(("100R", "100R", "100R"))),
        DesignLintPolicy(),
    )
    assert not _findings(outside_window)

    off = evaluate(
        "synthetic-can-overtermination",
        coach(_can_netlist_with_direct_terminators(("108R", "120R", "132R"))),
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=RULE_ID,
                    mode="off",
                    reason="Exercise a project-configured opt-out",
                ),
            )
        ),
    )
    assert off.status == "PASS"


def test_overtermination_evidence_is_order_stable_and_repair_clears_it() -> None:
    source = _can_netlist_with_direct_terminators(("108R", "120R", "132R"))
    first = evaluate("synthetic-can-overtermination", coach(source), DesignLintPolicy())
    finding = _findings(first)[0]
    reordered_source = source.model_copy(
        update={
            "components": dict(reversed(tuple(source.components.items()))),
            "nets": dict(reversed(tuple(source.nets.items()))),
            "component_symbols": dict(reversed(tuple(source.component_symbols.items()))),
            "pin_functions": dict(reversed(tuple(source.pin_functions.items()))),
        }
    )
    reordered = evaluate(
        "synthetic-can-overtermination", coach(reordered_source), DesignLintPolicy()
    )
    reordered_finding = _findings(reordered)[0]
    assert (reordered_finding.fingerprint, reordered_finding.evidence) == (
        finding.fingerprint,
        finding.evidence,
    )

    repaired = evaluate(
        "synthetic-can-overtermination",
        coach(_can_netlist_with_direct_terminators(("120R", "121R"))),
        DesignLintPolicy(),
    )
    assert not _findings(repaired)
