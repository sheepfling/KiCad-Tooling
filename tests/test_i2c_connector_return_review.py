"""Review complete two-pin I2C connectors without an identified return role."""

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
from tests.design_lint_fixtures.i2c_connector_return import (
    two_pin_i2c_connector_map,
    two_pin_i2c_connector_netlist,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.connector_lint, pytest.mark.return_path_lint]

RULE_ID = "connector.i2c_pair_without_return_review"


def _report(
    observed: NetlistContract | None = None,
    *,
    connector_coverage: ConnectorCoverageReport | None = None,
    policy: DesignLintPolicy | None = None,
):
    netlist = observed or two_pin_i2c_connector_netlist()
    coach = ContractCoachReport(
        status="READY_FOR_REVIEW",
        project_id="synthetic-two-pin-i2c-return",
        observed=netlist,
        netlist_sha256="a" * 64,
    )
    return evaluate(coach.project_id, coach, policy or DesignLintPolicy(), connector_coverage)


def _findings(report) -> tuple:
    return tuple(item for item in report.findings if item.rule_id == RULE_ID)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_two_pin_generic_i2c_connector_without_return_emits_review() -> None:
    report = _report()
    findings = _findings(report)

    assert report.status == "REVIEW"
    assert len(findings) == 1
    finding = findings[0]
    assert finding.mode == "review"
    assert finding.subject == "J1: two-pin I2C connector has no identified reference return"
    assert finding.evidence["connector_native_pin_count"] == ("2",)
    assert finding.evidence["SDA_generic_connector_pins"] == ("J1.1",)
    assert finding.evidence["SCL_generic_connector_pins"] == ("J1.2",)
    assert finding.evidence["I2C_endpoint_pairs"] == ("U1:U1.1=SDA/I2C_SDA;U1.2=SCL/I2C_SCL",)
    assert "intentionally isolated" in finding.message
    assert "does not require connection to board ground" in finding.message


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_named_contacts_and_reviewed_maps_suppress_generic_pair_prompt() -> None:
    named = two_pin_i2c_connector_netlist(connector_functions=("SDA", "SCL"))
    not_applicable = ConnectorCoverageReport(
        status="COMPLETE",
        scope="Synthetic reviewed connector inventory",
        inventory_review_basis="Reviewed two-contact connector disposition",
        entries=(ConnectorCoverageEntry(reference="J1", status="NOT_APPLICABLE"),),
    )

    assert not _findings(_report(named))
    assert not _findings(_report(connector_coverage=two_pin_i2c_connector_map()))
    assert not _findings(_report(connector_coverage=not_applicable))


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_stale_map_does_not_suppress_and_mapped_return_role_stays_with_role_check() -> None:
    stale_map = ConnectorCoverageReport(
        status="INCOMPLETE",
        scope="Synthetic stale connector review",
        entries=(ConnectorCoverageEntry(reference="J1", status="STALE"),),
    )
    return_role = two_pin_i2c_connector_map(return_on_signal_contact=True)

    assert len(_findings(_report(connector_coverage=stale_map))) == 1
    assert not _findings(_report(connector_coverage=return_role))


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_extra_return_contact_is_left_to_existing_connector_return_rules() -> None:
    report = _report(two_pin_i2c_connector_netlist(connected_return_contact=True))

    assert not _findings(report)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_dnp_incomplete_and_ambiguous_inputs_stay_quiet() -> None:
    source = two_pin_i2c_connector_netlist()
    dnp_connector = source.model_copy(update={"dnp_components": ("J1",)})
    dnp_endpoint = source.model_copy(update={"dnp_components": ("U1",)})
    incomplete = source.model_copy(
        update={"component_pin_numbers": {"J1": ("1",), "U1": ("1", "2", "3", "4")}}
    )
    ambiguous = source.model_copy(update={"nets": {**source.nets, "OTHER": ("J1.1",)}})
    duplicate_endpoint_role = source.model_copy(
        update={"pin_functions": {**source.pin_functions, "U1.4": "SDA"}}
    )

    for observed in (dnp_connector, dnp_endpoint, incomplete, ambiguous, duplicate_endpoint_role):
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
                        reason="This project requires reviewed I2C reference pinouts",
                    ),
                )
            )
        )
    )[0]
    off = _report(
        policy=DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=RULE_ID, mode="off", reason="No external I2C connectors"
                ),
            )
        )
    )
    ignored = _findings(
        _report(
            policy=DesignLintPolicy(
                ignores=(
                    DesignLintIgnore(
                        rule_id=RULE_ID,
                        fingerprint=base.fingerprint,
                        reason="Reviewed as an isolated two-wire accessory",
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
    source = two_pin_i2c_connector_netlist()
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
