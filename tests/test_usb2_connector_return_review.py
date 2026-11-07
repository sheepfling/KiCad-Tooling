"""Review two-contact connectors assigned to a recognized USB 2.0 PHY pair."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.connector_coverage_models import (
    ConnectorCoverageEntry,
    ConnectorCoverageReport,
)
from kicad_tooling.hwrepo.contract_coach_models import ContractCoachReport
from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.design_lint_policy_models import (
    DesignLintIgnore,
    DesignLintPolicy,
    DesignLintRuleOverride,
)
from kicad_tooling.hwrepo.models import NetlistContract
from tests.design_lint_fixtures.usb2_connector_return import (
    ambiguous_usb2_phy_netlist,
    two_pin_usb2_connector_netlist,
    usb2_connector_coverage,
    usb2_data_path_map_without_reference,
)

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.connector_lint,
    pytest.mark.interface_lint,
    pytest.mark.return_path_lint,
]

RULE_ID = "connector.usb2_pair_without_return_review"


def _report(
    observed: NetlistContract | None = None,
    *,
    connector_coverage: ConnectorCoverageReport | None = None,
    policy: DesignLintPolicy | None = None,
):
    netlist = observed or two_pin_usb2_connector_netlist()
    coach = ContractCoachReport(
        status="READY_FOR_REVIEW",
        project_id="synthetic-two-pin-usb2-return",
        observed=netlist,
        netlist_sha256="a" * 64,
    )
    return evaluate(coach.project_id, coach, policy or DesignLintPolicy(), connector_coverage)


def _findings(report) -> tuple:
    return tuple(item for item in report.findings if item.rule_id == RULE_ID)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_complete_two_pin_usb2_data_pair_without_return_emits_review() -> None:
    report = _report()
    findings = _findings(report)

    assert report.status == "REVIEW"
    assert len(findings) == 1
    finding = findings[0]
    assert finding.mode == "review"
    assert finding.subject == (
        "J1: two-pin USB 2.0 connector pair has no identified reference return"
    )
    assert finding.evidence["connector_native_pin_count"] == ("2",)
    assert finding.evidence["USB_D+_connector_pin"] == ("J1.1",)
    assert finding.evidence["USB_D+_PHY_pins"] == ("U1.1",)
    assert finding.evidence["USB_D-_connector_pin"] == ("J1.2",)
    assert finding.evidence["USB_D-_PHY_pins"] == ("U1.2",)
    assert finding.evidence["USB_port_group"] == ("1",)
    assert "intentionally isolated" in finding.message
    assert "does not require board ground" in finding.message


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_named_usb_data_contact_functions_do_not_hide_missing_reference_review() -> None:
    observed = two_pin_usb2_connector_netlist(connector_functions=("D+", "D-"))

    assert len(_findings(_report(observed))) == 1


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_return_role_and_explicit_not_applicable_disposition_are_controls() -> None:
    native_return_role = two_pin_usb2_connector_netlist(connector_functions=("GND", "D-"))

    assert not _findings(_report(native_return_role))
    assert not _findings(_report(connector_coverage=usb2_connector_coverage(not_applicable=True)))
    assert not _findings(
        _report(connector_coverage=usb2_connector_coverage(map_return_to_data_contact=True))
    )


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_data_pin_map_does_not_stand_in_for_reference_return_review() -> None:
    data_path_only = DesignLintPolicy(usb_data_path_map=usb2_data_path_map_without_reference())

    assert len(_findings(_report(policy=data_path_only))) == 1


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_connectors_outside_exact_two_pin_scope_and_stale_maps_are_controls() -> None:
    with_return = two_pin_usb2_connector_netlist(connected_return_contact=True)
    stale_map = ConnectorCoverageReport(
        status="INCOMPLETE",
        scope="Synthetic stale USB connector review",
        entries=(ConnectorCoverageEntry(reference="J1", status="STALE"),),
    )

    assert not _findings(_report(with_return))
    assert len(_findings(_report(connector_coverage=stale_map))) == 1


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_dnp_incomplete_ambiguous_and_unrecognized_endpoints_stay_quiet() -> None:
    source = two_pin_usb2_connector_netlist()
    dnp_connector = source.model_copy(update={"dnp_components": ("J1",)})
    dnp_phy = source.model_copy(update={"dnp_components": ("U1",)})
    incomplete_connector = source.model_copy(
        update={"component_pin_numbers": {**source.component_pin_numbers, "J1": ("1",)}}
    )
    ambiguous_connector = source.model_copy(update={"nets": {**source.nets, "OTHER": ("J1.1",)}})
    unreferenced_phy = source.model_copy(
        update={"nets": {key: value for key, value in source.nets.items() if key != "PHY_GND"}}
    )
    ambiguous_endpoints = ambiguous_usb2_phy_netlist()

    for observed in (
        dnp_connector,
        dnp_phy,
        incomplete_connector,
        ambiguous_connector,
        unreferenced_phy,
        ambiguous_endpoints,
    ):
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
                        reason="Review every external USB 2.0 connector reference",
                    ),
                )
            )
        )
    )[0]
    off = _report(
        policy=DesignLintPolicy(
            rules=(DesignLintRuleOverride(rule_id=RULE_ID, mode="off", reason="No USB ports"),)
        )
    )
    ignored = _findings(
        _report(
            policy=DesignLintPolicy(
                ignores=(
                    DesignLintIgnore(
                        rule_id=RULE_ID,
                        fingerprint=base.fingerprint,
                        reason="The approved cable provides the signal reference",
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
    source = two_pin_usb2_connector_netlist()
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
