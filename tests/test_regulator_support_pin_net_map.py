"""Project-authored net assignments for active regulator-support pins."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.models import (
    ContractCoachReport,
    DesignLintPolicy,
    DesignLintRuleOverride,
)
from kicad_tooling.hwrepo.regulator_support_models import (
    RegulatorSupportNetComponentRequirement,
    RegulatorSupportPinNetExpectation,
)
from tests.regulator_support_pin_net_support import support_pin_net_map, support_pin_netlist

pytestmark = [pytest.mark.design_lint, pytest.mark.power_lint]

RULE_ID = "power.regulator_support_pin_net_mismatch"


def _report(source, *, mode: str | None = None, mapped: bool = True):
    policy = DesignLintPolicy(
        regulator_support_pin_net_map=support_pin_net_map() if mapped else None,
        rules=()
        if mode is None
        else (DesignLintRuleOverride(rule_id=RULE_ID, mode=mode, reason="Synthetic policy case"),),
    )
    return evaluate(
        "synthetic-regulator-support-nets",
        ContractCoachReport(
            status="READY_FOR_REVIEW",
            project_id="synthetic-regulator-support-nets",
            observed=source,
            netlist_sha256="e" * 64,
        ),
        policy,
    )


def _finding(report):
    return next(item for item in report.findings if item.rule_id == RULE_ID)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_exact_active_support_pin_net_map_is_a_valid_control() -> None:
    report = _report(support_pin_netlist())

    assert RULE_ID not in {item.rule_id for item in report.findings}


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_pin_net_change_is_reviewed_while_role_metadata_stays_valid() -> None:
    report = _report(support_pin_netlist(fault="wrong-net"))
    finding = _finding(report)

    assert finding.mode == "review"
    assert finding.subject == "U2: mapped feedback isolator pin-to-net assignments differ"
    assert "U2.1 is assigned to OTHER_PRIMARY_FEEDBACK" in finding.message
    assert "expected 'PRIMARY_FEEDBACK'" in finding.message
    assert "power.regulator_support_pin_role_mismatch" not in {
        item.rule_id for item in report.findings
    }


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_unconnected_mapped_active_support_pin_is_reviewed() -> None:
    finding = _finding(_report(support_pin_netlist(fault="unconnected")))

    assert finding.subject == "U3: mapped secondary reference pin-to-net assignments differ"
    assert "U3.3 is assigned to unconnected" in finding.message
    assert "expected 'SECONDARY_FEEDBACK'" in finding.message


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_absent_project_map_emits_no_pin_net_claim() -> None:
    report = _report(support_pin_netlist(fault="wrong-net"), mapped=False)

    assert RULE_ID not in {item.rule_id for item in report.findings}


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
@pytest.mark.parametrize(
    ("mode", "expected_mode", "expected_disposition"),
    (("review", "review", "OPEN"), ("block", "block", "OPEN"), ("off", "off", "RULE_OFF")),
)
def test_project_policy_controls_the_pin_net_finding(
    mode: str,
    expected_mode: str,
    expected_disposition: str,
) -> None:
    finding = _finding(_report(support_pin_netlist(fault="wrong-net"), mode=mode))

    assert finding.mode == expected_mode
    assert finding.disposition == expected_disposition


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_pin_net_map_rejects_duplicate_and_foreign_component_pins() -> None:
    with pytest.raises(ValidationError, match="pins must be unique"):
        RegulatorSupportNetComponentRequirement(
            role="feedback isolator",
            reference="U2",
            value="SYNTH-ISO",
            symbol="Synthetic:FeedbackIsolator",
            footprint="Synthetic:SOIC-4",
            pins=(
                RegulatorSupportPinNetExpectation(pin="U2.1", expected_net="A"),
                RegulatorSupportPinNetExpectation(pin="U2.1", expected_net="B"),
            ),
        )

    with pytest.raises(ValidationError, match="must belong to their component"):
        RegulatorSupportNetComponentRequirement(
            role="feedback isolator",
            reference="U2",
            value="SYNTH-ISO",
            symbol="Synthetic:FeedbackIsolator",
            footprint="Synthetic:SOIC-4",
            pins=(
                RegulatorSupportPinNetExpectation(pin="U2.1", expected_net="A"),
                RegulatorSupportPinNetExpectation(pin="U3.2", expected_net="B"),
            ),
        )


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_expected_unconnected_pin_is_distinct_from_an_omitted_expectation() -> None:
    requirement = RegulatorSupportNetComponentRequirement(
        role="feedback isolator",
        reference="U2",
        value="SYNTH-ISO",
        symbol="Synthetic:FeedbackIsolator",
        footprint="Synthetic:SOIC-4",
        pins=(
            RegulatorSupportPinNetExpectation(pin="U2.1", expected_net="A"),
            RegulatorSupportPinNetExpectation(pin="U2.2", expected_net=None),
        ),
    )

    assert requirement.pins[1].expected_net is None
    with pytest.raises(ValidationError):
        RegulatorSupportPinNetExpectation.model_validate({"pin": "U2.2"})


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_pin_net_fingerprint_is_stable_under_native_mapping_order() -> None:
    source = support_pin_netlist(fault="wrong-net")
    reordered = source.model_copy(
        update={
            "nets": dict(reversed(tuple(source.nets.items()))),
            "components": dict(reversed(tuple(source.components.items()))),
            "component_symbols": dict(reversed(tuple(source.component_symbols.items()))),
        }
    )
    original = _finding(_report(source))
    shuffled = _finding(_report(reordered))

    assert (shuffled.fingerprint, shuffled.evidence) == (original.fingerprint, original.evidence)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_pin_net_change_changes_source_bound_evidence() -> None:
    wrong_net = _finding(_report(support_pin_netlist(fault="wrong-net")))
    unconnected = _finding(_report(support_pin_netlist(fault="unconnected")))

    assert wrong_net.fingerprint != unconnected.fingerprint
    assert wrong_net.evidence != unconnected.evidence
