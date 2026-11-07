"""Review exact two-pin USB SuperSpeed connector pairs without a return role."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.connector_coverage_models import ConnectorCoverageReport
from kicad_tooling.hwrepo.contract_coach_models import ContractCoachReport
from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.design_lint_policy_models import (
    DesignLintIgnore,
    DesignLintPolicy,
    DesignLintRuleOverride,
)
from kicad_tooling.hwrepo.models import NetlistContract
from tests.design_lint_fixtures.usb_superspeed_connector_return import (
    two_pin_usb_superspeed_connector_netlist,
    usb_superspeed_connector_coverage,
)

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.connector_lint,
    pytest.mark.interface_lint,
    pytest.mark.return_path_lint,
]

RULE_ID = "connector.usb_superspeed_pair_without_return_review"


def _report(
    observed: NetlistContract | None = None,
    *,
    connector_coverage: ConnectorCoverageReport | None = None,
    policy: DesignLintPolicy | None = None,
):
    netlist = observed or two_pin_usb_superspeed_connector_netlist()
    coach = ContractCoachReport(
        status="READY_FOR_REVIEW",
        project_id="synthetic-two-pin-usb-superspeed-return",
        observed=netlist,
        netlist_sha256="e" * 64,
    )
    return evaluate(coach.project_id, coach, policy or DesignLintPolicy(), connector_coverage)


def _findings(report) -> tuple:
    return tuple(item for item in report.findings if item.rule_id == RULE_ID)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_two_pin_connector_on_exact_superspeed_tx_pair_emits_review() -> None:
    report = _report()
    findings = _findings(report)

    assert report.status == "REVIEW"
    assert len(findings) == 1
    finding = findings[0]
    assert finding.mode == "review"
    assert finding.subject == (
        "J1: two-pin USB SuperSpeed connector pair has no identified reference return"
    )
    assert finding.evidence["connector_native_pin_count"] == ("2",)
    assert finding.evidence["USB_SuperSpeed_family"] == ("USB SuperSpeed TX",)
    assert finding.evidence["USB_SuperSpeed_positive_connector_pin"] == ("J1.1",)
    assert finding.evidence["USB_SuperSpeed_positive_PHY_pins"] == ("U1.1",)
    assert finding.evidence["USB_SuperSpeed_negative_connector_pin"] == ("J1.2",)
    assert finding.evidence["USB_SuperSpeed_negative_PHY_pins"] == ("U1.2",)
    assert "intentionally isolated" in finding.message
    assert "does not require board ground" in finding.message


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_exact_superspeed_rx_pair_and_named_data_contacts_are_recognized() -> None:
    observed = two_pin_usb_superspeed_connector_netlist(
        phy_family="RX",
        connector_functions=("SSRX+", "SSRX-"),
    )
    findings = _findings(_report(observed))

    assert len(findings) == 1
    assert findings[0].evidence["USB_SuperSpeed_family"] == ("USB SuperSpeed RX",)
    assert findings[0].evidence["USB_SuperSpeed_positive_connector_function"] == ("SSRX+",)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_native_and_source_matched_return_roles_and_not_applicable_are_controls() -> None:
    native_role = two_pin_usb_superspeed_connector_netlist(connector_functions=("GND", "SSTX-"))

    assert not _findings(_report(native_role))
    assert not _findings(
        _report(connector_coverage=usb_superspeed_connector_coverage(not_applicable=True))
    )
    assert not _findings(
        _report(
            connector_coverage=usb_superspeed_connector_coverage(map_return_to_data_contact=True)
        )
    )


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_data_only_map_does_not_claim_reference_return_intent() -> None:
    assert (
        len(
            _findings(_report(connector_coverage=usb_superspeed_connector_coverage(data_only=True)))
        )
        == 1
    )


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_extra_contact_and_incomplete_or_ambiguous_evidence_stay_quiet() -> None:
    cases = (
        two_pin_usb_superspeed_connector_netlist(
            connector_functions=("SSTX+", "SSTX-"), include_return_contact=True
        ),
        two_pin_usb_superspeed_connector_netlist(connector_dnp=True),
        two_pin_usb_superspeed_connector_netlist(endpoint_dnp=True),
        two_pin_usb_superspeed_connector_netlist(include_negative_contact=False),
        two_pin_usb_superspeed_connector_netlist(ambiguous_connector_contact=True),
        two_pin_usb_superspeed_connector_netlist(ambiguous_phy_endpoint=True),
        two_pin_usb_superspeed_connector_netlist().model_copy(
            update={
                "component_pin_numbers": {
                    **two_pin_usb_superspeed_connector_netlist().component_pin_numbers,
                    "J1": ("1",),
                }
            }
        ),
    )

    for observed in cases:
        assert not _findings(_report(observed))


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_rule_override_and_exact_ignore_remain_available() -> None:
    base = _findings(_report())[0]
    blocked = _findings(
        _report(
            policy=DesignLintPolicy(
                rules=(
                    DesignLintRuleOverride(
                        rule_id=RULE_ID,
                        mode="block",
                        reason="Review each mapped SuperSpeed connector",
                    ),
                )
            )
        )
    )[0]
    off = _report(
        policy=DesignLintPolicy(
            rules=(DesignLintRuleOverride(rule_id=RULE_ID, mode="off", reason="No such port"),)
        )
    )
    ignored = _findings(
        _report(
            policy=DesignLintPolicy(
                ignores=(
                    DesignLintIgnore(
                        rule_id=RULE_ID,
                        fingerprint=base.fingerprint,
                        reason="Approved interface uses an external signal reference",
                    ),
                )
            )
        )
    )[0]

    assert blocked.mode == "block"
    assert any(item.rule_id == RULE_ID and item.disposition == "RULE_OFF" for item in off.findings)
    assert ignored.disposition == "IGNORED"


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_finding_is_stable_when_native_mappings_are_reordered() -> None:
    source = two_pin_usb_superspeed_connector_netlist()
    reordered = source.model_copy(
        update={
            "components": dict(reversed(tuple(source.components.items()))),
            "nets": dict(reversed(tuple(source.nets.items()))),
            "component_symbols": dict(reversed(tuple(source.component_symbols.items()))),
            "pin_functions": dict(reversed(tuple(source.pin_functions.items()))),
            "pin_electrical_types": dict(reversed(tuple(source.pin_electrical_types.items()))),
            "component_pin_numbers": dict(reversed(tuple(source.component_pin_numbers.items()))),
        }
    )

    baseline = _findings(_report(source))[0]
    actual = _findings(_report(reordered))[0]
    assert baseline.evidence == actual.evidence
    assert baseline.fingerprint == actual.fingerprint
