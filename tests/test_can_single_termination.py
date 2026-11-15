"""Review one local CAN terminator when multiple fitted endpoints share a pair."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.design_lint_finding_models import DesignLintFinding
from kicad_tooling.hwrepo.design_lint_report_models import DesignLintReport
from kicad_tooling.hwrepo.models import (
    DesignLintIgnore,
    DesignLintPolicy,
    DesignLintRuleOverride,
)
from kicad_tooling.hwrepo.netlist_contract_models import ComponentContract, NetlistContract
from tests.design_lint_fixtures import can_netlist, can_peer_netlist, coach

RULE_ID = "bus.can_single_local_termination"

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.interface_lint,
    pytest.mark.design_lint_rule(rule_id=RULE_ID),
]


def _with_second_terminator(source: NetlistContract, *, value: str = "121R") -> NetlistContract:
    components = dict(source.components)
    components["R2"] = ComponentContract(value=value, footprint="Synthetic:0603")
    symbols = dict(source.component_symbols)
    symbols["R2"] = "Device:R"
    functions = dict(source.pin_functions)
    functions.update({"R2.1": "1", "R2.2": "2"})
    nets = {name: tuple(pins) for name, pins in source.nets.items()}
    nets["NET_A"] = (*nets["NET_A"], "R2.1")
    nets["NET_B"] = (*nets["NET_B"], "R2.2")
    return source.model_copy(
        update={
            "components": components,
            "component_symbols": symbols,
            "pin_functions": functions,
            "nets": nets,
        }
    )


def _single_findings(report: DesignLintReport) -> tuple[DesignLintFinding, ...]:
    return tuple(item for item in report.findings if item.rule_id == RULE_ID)


def test_multi_endpoint_can_pair_with_one_local_terminator_prompts_for_review() -> None:
    report = evaluate(
        "synthetic-can-single-termination", coach(can_peer_netlist()), DesignLintPolicy()
    )

    assert report.status == "REVIEW"
    (finding,) = _single_findings(report)
    assert finding.mode == "review"
    assert finding.subject == (
        "CANH NET_A / CANL NET_B: one local terminator across 3 fitted endpoints"
    )
    assert finding.evidence == {
        "CANH": ("NET_A",),
        "CANL": ("NET_B",),
        "pins": ("U1.1", "U2.1", "U3.1", "U1.2", "U2.2", "U3.2"),
        "endpoint_components": ("U1", "U2", "U3"),
        "terminations": ("R1=120 Ω",),
    }
    assert "cannot identify physical bus ends" in finding.message


def test_single_local_termination_rule_uses_fitted_state_and_policy() -> None:
    two_local = _with_second_terminator(can_peer_netlist())
    assert not _single_findings(
        evaluate("synthetic-can-two-local", coach(two_local), DesignLintPolicy())
    )

    for value in ("108R", "132R"):
        at_boundary = can_peer_netlist().model_copy(
            update={
                "components": {
                    **can_peer_netlist().components,
                    "R1": ComponentContract(value=value, footprint="Synthetic:0603"),
                }
            }
        )
        assert _single_findings(
            evaluate(f"synthetic-can-boundary-{value}", coach(at_boundary), DesignLintPolicy())
        )

    for value in ("107R", "133R"):
        outside_range = can_peer_netlist().model_copy(
            update={
                "components": {
                    **can_peer_netlist().components,
                    "R1": ComponentContract(value=value, footprint="Synthetic:0603"),
                }
            }
        )
        assert not _single_findings(
            evaluate(
                f"synthetic-can-outside-range-{value}",
                coach(outside_range),
                DesignLintPolicy(),
            )
        )

    assert not _single_findings(
        evaluate(
            "synthetic-can-one-endpoint",
            coach(can_netlist("120R")),
            DesignLintPolicy(),
        )
    )

    one_fitted = _with_second_terminator(can_peer_netlist()).model_copy(
        update={"dnp_components": ("R2",)}
    )
    (finding,) = _single_findings(
        evaluate("synthetic-can-one-fitted", coach(one_fitted), DesignLintPolicy())
    )
    for mode, status in (("block", "FAIL"), ("off", "PASS")):
        report = evaluate(
            "synthetic-can-one-fitted",
            coach(one_fitted),
            DesignLintPolicy(
                rules=(
                    DesignLintRuleOverride(
                        rule_id=RULE_ID,
                        mode=mode,
                        reason="Exercise the project-configurable CAN review policy",
                    ),
                )
            ),
        )
        assert report.status == status

    ignored = evaluate(
        "synthetic-can-one-fitted",
        coach(one_fitted),
        DesignLintPolicy(
            ignores=(
                DesignLintIgnore(
                    rule_id=RULE_ID,
                    fingerprint=finding.fingerprint,
                    reason="The second endpoint is terminated externally",
                ),
            )
        ),
    )
    assert ignored.status == "PASS"
    assert _single_findings(ignored)[0].disposition == "IGNORED"


def test_single_local_termination_is_order_stable_and_repairs_clear() -> None:
    source = can_peer_netlist()
    report = evaluate("synthetic-can-order", coach(source), DesignLintPolicy())
    (finding,) = _single_findings(report)
    reordered = source.model_copy(
        update={
            "components": dict(reversed(tuple(source.components.items()))),
            "nets": dict(reversed(tuple(source.nets.items()))),
            "component_symbols": dict(reversed(tuple(source.component_symbols.items()))),
            "pin_functions": dict(reversed(tuple(source.pin_functions.items()))),
        }
    )
    (reordered_finding,) = _single_findings(
        evaluate("synthetic-can-order", coach(reordered), DesignLintPolicy())
    )
    assert (reordered_finding.fingerprint, reordered_finding.evidence) == (
        finding.fingerprint,
        finding.evidence,
    )

    repaired = _with_second_terminator(source)
    assert not _single_findings(
        evaluate("synthetic-can-order", coach(repaired), DesignLintPolicy())
    )
