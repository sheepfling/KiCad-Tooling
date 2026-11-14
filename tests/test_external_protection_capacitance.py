"""Project-authored ESD channel capacitance budget regressions."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from kicad_tooling.hwrepo.design_lint_finding_models import DesignLintRuleOverride
from kicad_tooling.hwrepo.design_lint_interfaces_protection_capacitance import (
    protection_capacitance_candidates,
)
from kicad_tooling.hwrepo.external_protection import (
    ExternalProtectionCoverageRequest,
    resolve_external_protection_coverage,
)
from kicad_tooling.hwrepo.external_protection_models import ExternalProtectionInterfaceRequirement
from kicad_tooling.hwrepo.models import DesignLintPolicy, ExternalProtectionMap
from tests.external_protection_support import (
    observed_netlist,
    protection_lint_report,
    protection_map,
)

RULE_ID = "protection.channel_capacitance_budget_exceeded"

pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint]


def _finding(report, rule_id: str = RULE_ID):
    return next(item for item in report.findings if item.rule_id == rule_id)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_protector_channel_maximum_above_project_budget_prompts_review() -> None:
    requirements = protection_map(channel_capacitance_pf=2.4, signal_capacitance_limit_pf=2.0)

    _, report = protection_lint_report(requirements, observed_netlist())

    finding = _finding(report)
    assert finding.mode == "review"
    assert finding.subject == "USB_DP: external-protection capacitance budget"
    assert finding.evidence["total_channel_capacitance_pf"] == ("2.4",)
    assert finding.evidence["maximum_signal_capacitance_pf"] == ("2",)
    assert finding.evidence["channel_maxima"] == ("D1.1: 2.4 pF max (Synthetic TVS)",)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_channel_maximum_equal_to_project_budget_is_a_valid_control() -> None:
    requirements = protection_map(channel_capacitance_pf=2.0, signal_capacitance_limit_pf=2.0)

    _, report = protection_lint_report(requirements, observed_netlist())

    assert RULE_ID not in {item.rule_id for item in report.findings}


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_budget_finding_is_stable_when_native_mapping_order_changes() -> None:
    requirements = protection_map(channel_capacitance_pf=2.4, signal_capacitance_limit_pf=2.0)
    observed = observed_netlist()
    _, first_report = protection_lint_report(requirements, observed)
    reordered = observed.model_copy(
        update={
            "components": dict(reversed(tuple(observed.components.items()))),
            "nets": dict(reversed(tuple(observed.nets.items()))),
            "component_symbols": dict(reversed(tuple(observed.component_symbols.items()))),
            "component_pin_numbers": dict(reversed(tuple(observed.component_pin_numbers.items()))),
        }
    )
    _, reordered_report = protection_lint_report(requirements, reordered)

    first = _finding(first_report)
    second = _finding(reordered_report)
    assert first.fingerprint == second.fingerprint
    assert first.evidence == second.evidence


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_capacitance_review_is_opt_in_when_protector_data_is_not_authored() -> None:
    _, report = protection_lint_report(protection_map(), observed_netlist())

    assert report.external_protection_coverage is not None
    assert report.external_protection_coverage.capacitance_reviews == ()
    assert RULE_ID not in {item.rule_id for item in report.findings}


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_optional_capacitance_fields_do_not_expand_unconfigured_contract_json() -> None:
    serialized = protection_map().model_dump(mode="json")

    assert "expected_value" not in serialized["devices"][0]
    assert "maximum_channel_capacitance_pf" not in serialized["interfaces"][0]["channels"][0]
    assert "maximum_signal_capacitance_pf" not in serialized["interfaces"][0]


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_changed_native_part_value_blocks_budget_assessment() -> None:
    original = observed_netlist()
    observed = original.model_copy(
        update={
            "components": {
                **original.components,
                "D1": original.components["D1"].model_copy(update={"value": "Different TVS"}),
            }
        }
    )
    requirements = protection_map(
        channel_capacitance_pf=2.4,
        signal_capacitance_limit_pf=2.0,
    )

    _, report = protection_lint_report(requirements, observed)

    assert report.external_protection_coverage is not None
    assert report.external_protection_coverage.capacitance_reviews == ()
    mismatch = _finding(report, "protection.mapped_device_mismatch")
    assert any(
        "D1 value is Different TVS; expected Synthetic TVS" in issue
        for issue in mismatch.evidence["issues"]
    )
    assert RULE_ID not in {item.rule_id for item in report.findings}


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_stale_netlist_binding_removes_capacitance_candidate_evidence() -> None:
    requirements = protection_map(channel_capacitance_pf=2.4, signal_capacitance_limit_pf=2.0)
    current_hash, report = protection_lint_report(requirements, observed_netlist())
    assert report.external_protection_coverage is not None

    resolution = resolve_external_protection_coverage(
        ExternalProtectionCoverageRequest(
            coverage=report.external_protection_coverage,
            current_netlist_sha256="b" * 64,
        )
    )

    assert resolution.coverage.status == "BLOCKED"
    assert resolution.coverage.capacitance_reviews == ()
    assert protection_capacitance_candidates(resolution.coverage) == ()
    assert resolution.binding_issue is not None
    assert resolution.coverage.netlist_sha256 == current_hash


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_duplicate_connector_entries_do_not_double_count_one_channel() -> None:
    authored = protection_map(channel_capacitance_pf=1.2, signal_capacitance_limit_pf=1.5)
    first = authored.interfaces[0]
    second = first.model_copy(update={"connector_pin": "J1.3"})
    requirements = ExternalProtectionMap(
        basis=authored.basis,
        interfaces=(first, second),
        devices=authored.devices,
    )
    observed = observed_netlist().model_copy(
        update={
            "nets": {
                "USB_DP": ("J1.1", "J1.3", "D1.1"),
                "USB_DM": ("J1.2",),
                "GND": ("D1.2",),
            },
            "component_pin_numbers": {"J1": ("1", "2", "3"), "D1": ("1", "2")},
        }
    )

    _, report = protection_lint_report(requirements, observed)

    assert report.external_protection_coverage is not None
    review = report.external_protection_coverage.capacitance_reviews[0]
    assert review.total_channel_capacitance_pf == 1.2
    assert len(review.channels) == 1
    assert RULE_ID not in {item.rule_id for item in report.findings}


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_project_rule_override_can_block_an_exceeded_budget() -> None:
    requirements = protection_map(channel_capacitance_pf=2.4, signal_capacitance_limit_pf=2.0)
    policy = DesignLintPolicy(
        rules=(DesignLintRuleOverride(rule_id=RULE_ID, mode="block", reason="Reviewed budget"),)
    )

    _, report = protection_lint_report(requirements, observed_netlist(), policy)

    assert _finding(report).mode == "block"
    assert report.status == "FAIL"


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_capacitance_limit_requires_channel_ratings_and_exact_part_identity() -> None:
    authored = protection_map(channel_capacitance_pf=2.4, signal_capacitance_limit_pf=2.0)
    channel = authored.interfaces[0].channels[0]
    with pytest.raises(ValidationError, match="limit and a maximum for every channel"):
        ExternalProtectionInterfaceRequirement.model_validate(
            {
                **authored.interfaces[0].model_dump(),
                "maximum_signal_capacitance_pf": None,
                "capacitance_limit_basis": None,
            }
        )
    with pytest.raises(ValidationError, match="exact expected value"):
        ExternalProtectionMap(
            basis=authored.basis,
            interfaces=authored.interfaces,
            devices=(authored.devices[0].model_copy(update={"expected_value": None}),),
        )
    assert channel.maximum_channel_capacitance_pf == 2.4
