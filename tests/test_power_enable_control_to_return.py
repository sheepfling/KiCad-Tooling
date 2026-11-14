"""Conservative lint for fitted enable inputs on return-like net labels."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.design_lint_finding_models import (
    DesignLintIgnore,
    DesignLintRuleOverride,
)
from kicad_tooling.hwrepo.design_lint_policy_models import DesignLintPolicy
from kicad_tooling.hwrepo.power_enable_controls import enable_control_tied_to_return_candidates
from tests.design_lint_fixtures import coach
from tests.design_lint_fixtures.power_enable_control import enable_control_netlist

pytestmark = [pytest.mark.design_lint, pytest.mark.power_lint]

RULE_ID = "power.enable_control_tied_to_return"


def _report(source, policy: DesignLintPolicy | None = None):
    resolved = policy or DesignLintPolicy()
    if not any(item.rule_id == "power.ic_rail_without_fitted_capacitor" for item in resolved.rules):
        resolved = resolved.model_copy(
            update={
                "rules": (
                    *resolved.rules,
                    DesignLintRuleOverride(
                        rule_id="power.ic_rail_without_fitted_capacitor",
                        mode="off",
                        reason="Synthetic enable-control fixture has no decoupling requirements",
                    ),
                )
            }
        )
    return evaluate(
        "synthetic-enable-control-return",
        coach(source),
        resolved,
    )


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_exact_enable_input_on_return_label_requests_review() -> None:
    (candidate,) = enable_control_tied_to_return_candidates(enable_control_netlist("GND"))

    assert candidate.rule_id == RULE_ID
    assert candidate.subject == "U1.3: EN control input assigned to GND"
    assert candidate.evidence == {
        "U1.3": ("native_function=EN",),
        "assigned_net": ("GND",),
        "electrical_type": ("input",),
    }
    assert "do not establish active polarity" in candidate.message
    (finding,) = [
        item for item in _report(enable_control_netlist("GND")).findings if item.rule_id == RULE_ID
    ]
    assert finding.mode == "review"


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
@pytest.mark.parametrize(
    ("net", "function", "electrical_type", "dnp", "assigned", "ambiguous"),
    (
        ("CONTROL", "EN", "input", False, True, False),
        ("VSS", "EN", "input", False, True, False),
        ("VSSA", "ENABLE", "input", False, True, False),
        ("GND", "~{EN}", "input", False, True, False),
        ("GND", "EN_N", "input", False, True, False),
        ("GND", "SHDN", "input", False, True, False),
        ("GND", "EN", "passive", False, True, False),
        ("GND", "EN", "input", True, True, False),
        ("GND", "EN", "input", False, False, False),
        ("GND", "EN", "input", False, True, True),
    ),
)
def test_unqualified_scope_and_ambiguous_cases_are_controls(
    net: str,
    function: str,
    electrical_type: str,
    dnp: bool,
    assigned: bool,
    ambiguous: bool,
) -> None:
    source = enable_control_netlist(
        net,
        function=function,
        electrical_type=electrical_type,
        dnp=dnp,
        assigned=assigned,
        ambiguous=ambiguous,
    )

    assert enable_control_tied_to_return_candidates(source) == ()


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
@pytest.mark.parametrize(
    "net", ("GND", "AGND", "DGND", "PGND", "0V", "RTN", "RETURN", "GROUND", "RET")
)
def test_supported_return_label_families_request_review(net: str) -> None:
    candidates = enable_control_tied_to_return_candidates(enable_control_netlist(net))

    assert len(candidates) == 1
    assert candidates[0].evidence["assigned_net"] == (net,)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_assignment_correction_clears_candidate_and_order_does_not_change_fingerprint() -> None:
    fault = enable_control_netlist("GND")
    corrected = enable_control_netlist("CONTROL")
    reordered = fault.model_copy(
        update={
            "nets": dict(reversed(tuple(fault.nets.items()))),
            "pin_functions": dict(reversed(tuple(fault.pin_functions.items()))),
        }
    )

    (first,) = enable_control_tied_to_return_candidates(fault)
    (repeat,) = enable_control_tied_to_return_candidates(reordered)
    assert first.evidence == repeat.evidence
    assert not any(item.rule_id == RULE_ID for item in _report(corrected).findings)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_project_policy_can_block_disable_or_ignore_exact_review() -> None:
    source = enable_control_netlist("GND")
    default = _report(source)
    (finding,) = [item for item in default.findings if item.rule_id == RULE_ID]

    blocked = _report(
        source,
        DesignLintPolicy(
            rules=(DesignLintRuleOverride(rule_id=RULE_ID, mode="block", reason="Required state"),)
        ),
    )
    disabled = _report(
        source,
        DesignLintPolicy(
            rules=(DesignLintRuleOverride(rule_id=RULE_ID, mode="off", reason="Reviewed scope"),)
        ),
    )
    ignored = _report(
        source,
        DesignLintPolicy(
            ignores=(
                DesignLintIgnore(
                    rule_id=RULE_ID,
                    fingerprint=finding.fingerprint,
                    reason="Grounded enable is intentional",
                ),
            )
        ),
    )

    assert default.status == "REVIEW"
    assert blocked.status == "FAIL"
    assert disabled.status == "PASS"
    assert (
        next(item for item in disabled.findings if item.rule_id == RULE_ID).disposition
        == "RULE_OFF"
    )
    assert ignored.status == "PASS"
    assert (
        next(item for item in ignored.findings if item.rule_id == RULE_ID).disposition == "IGNORED"
    )
