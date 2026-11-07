"""Review two-contact I3C connectors without an identified return role."""

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
from kicad_tooling.hwrepo.netlist_contract_models import NetlistContract
from tests.design_lint_fixtures.i3c_connector_return import (
    i3c_not_applicable_map,
    two_pin_i3c_connector_map,
    two_pin_i3c_connector_netlist,
)

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.connector_lint,
    pytest.mark.interface_lint,
    pytest.mark.return_path_lint,
]

RULE_ID = "connector.i3c_pair_without_return_review"


def _report(
    observed: NetlistContract | None = None,
    *,
    connector_coverage: ConnectorCoverageReport | None = None,
    policy: DesignLintPolicy | None = None,
):
    netlist = observed or two_pin_i3c_connector_netlist()
    coach = ContractCoachReport(
        status="READY_FOR_REVIEW",
        project_id="synthetic-two-pin-i3c-return",
        observed=netlist,
        netlist_sha256="d" * 64,
    )
    return evaluate(coach.project_id, coach, policy or DesignLintPolicy(), connector_coverage)


def _findings(report) -> tuple:
    return tuple(item for item in report.findings if item.rule_id == RULE_ID)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_two_pin_generic_i3c_connector_without_return_emits_review() -> None:
    report = _report()
    findings = _findings(report)

    assert report.status == "REVIEW"
    assert len(findings) == 1
    finding = findings[0]
    assert finding.mode == "review"
    assert finding.subject == "J1: two-pin I3C connector has no identified reference return"
    assert finding.evidence["connector_native_pin_count"] == ("2",)
    assert finding.evidence["SDA_generic_connector_pins"] == ("J1.1",)
    assert finding.evidence["SCL_generic_connector_pins"] == ("J1.2",)
    assert finding.evidence["I3C_endpoint_pairs"] == (
        "U1:U1.1=SDA/I3C_SDA_NET;U1.2=SCL/I3C_SCL_NET",
    )
    assert "intentionally isolated" in finding.message
    assert "does not require connection to board ground" in finding.message


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_named_contacts_and_reviewed_pinout_or_disposition_suppress_prompt() -> None:
    named = two_pin_i3c_connector_netlist(connector_functions=("I3C_SDA", "I3C_SCL"))

    assert not _findings(_report(named))
    assert not _findings(_report(connector_coverage=two_pin_i3c_connector_map()))
    assert not _findings(_report(connector_coverage=i3c_not_applicable_map()))


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_stale_map_does_not_suppress_and_mapped_return_role_is_explicit() -> None:
    stale_map = ConnectorCoverageReport(
        status="INCOMPLETE",
        scope="Synthetic stale connector review",
        entries=(ConnectorCoverageEntry(reference="J1", status="STALE"),),
    )

    assert len(_findings(_report(connector_coverage=stale_map))) == 1
    assert not _findings(
        _report(connector_coverage=two_pin_i3c_connector_map(return_on_signal_contact=True))
    )


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_three_contact_connector_stays_with_existing_return_checks() -> None:
    report = _report(two_pin_i3c_connector_netlist(connected_return_contact=True))

    assert not _findings(report)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_dnp_incomplete_ambiguous_and_mismatched_channels_stay_quiet() -> None:
    source = two_pin_i3c_connector_netlist()
    dnp_connector = source.model_copy(update={"dnp_components": ("J1",)})
    dnp_endpoint = source.model_copy(update={"dnp_components": ("U1",)})
    incomplete = source.model_copy(
        update={"component_pin_numbers": {"J1": ("1",), "U1": ("1", "2", "3", "4")}}
    )
    ambiguous_connector = source.model_copy(update={"nets": {**source.nets, "OTHER": ("J1.1",)}})
    duplicate_endpoint_role = source.model_copy(
        update={"pin_functions": {**source.pin_functions, "U1.4": "I3C_SDA"}}
    )
    mismatched_channels = source.model_copy(
        update={
            "pin_functions": {
                **source.pin_functions,
                "U1.1": "I3C0_SDA",
                "U1.2": "I3C1_SCL",
            }
        }
    )

    for observed in (
        dnp_connector,
        dnp_endpoint,
        incomplete,
        ambiguous_connector,
        duplicate_endpoint_role,
        mismatched_channels,
    ):
        assert not _findings(_report(observed))


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_channel_indexed_i3c_pair_is_recognized() -> None:
    report = _report(two_pin_i3c_connector_netlist(channel="0"))

    assert len(_findings(report)) == 1
    finding = _findings(report)[0]
    assert finding.evidence["I3C_endpoint_pairs"] == (
        "U1:U1.1=SDA/I3C0_SDA_NET;U1.2=SCL/I3C0_SCL_NET",
    )


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
                        reason="This project requires reviewed I3C connector pinouts",
                    ),
                )
            )
        )
    )[0]
    off = _report(
        policy=DesignLintPolicy(
            rules=(DesignLintRuleOverride(rule_id=RULE_ID, mode="off", reason="No I3C port"),)
        )
    )
    ignored = _findings(
        _report(
            policy=DesignLintPolicy(
                ignores=(
                    DesignLintIgnore(
                        rule_id=RULE_ID,
                        fingerprint=base.fingerprint,
                        reason="Reviewed isolated test header",
                    ),
                )
            )
        )
    )[0]

    assert blocked.mode == "block"
    assert any(item.rule_id == RULE_ID and item.disposition == "RULE_OFF" for item in off.findings)
    assert ignored.disposition == "IGNORED"


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_findings_are_stable_when_netlist_mappings_are_reordered() -> None:
    source = two_pin_i3c_connector_netlist()
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
