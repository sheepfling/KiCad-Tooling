"""Review complete two-contact RS-485 connectors without a return role."""

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
from tests.design_lint_fixtures.rs485_connector_return import (
    two_pin_rs485_connector_map,
    two_pin_rs485_connector_netlist,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.connector_lint, pytest.mark.return_path_lint]

RULE_ID = "connector.rs485_pair_without_return_review"


def _report(
    observed: NetlistContract | None = None,
    *,
    connector_coverage: ConnectorCoverageReport | None = None,
    policy: DesignLintPolicy | None = None,
):
    netlist = observed or two_pin_rs485_connector_netlist()
    coach = ContractCoachReport(
        status="READY_FOR_REVIEW",
        project_id="synthetic-two-pin-rs485-return",
        observed=netlist,
        netlist_sha256="d" * 64,
    )
    return evaluate(coach.project_id, coach, policy or DesignLintPolicy(), connector_coverage)


def _findings(report) -> tuple:
    return tuple(item for item in report.findings if item.rule_id == RULE_ID)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_two_pin_generic_rs485_pair_without_return_emits_review() -> None:
    report = _report()
    findings = _findings(report)

    assert report.status == "REVIEW"
    assert len(findings) == 1
    finding = findings[0]
    assert finding.mode == "review"
    assert finding.subject == "J1: two-pin RS-485 connector has no identified reference return"
    assert finding.evidence["connector_native_pin_count"] == ("2",)
    assert finding.evidence["A_generic_connector_pins"] == ("J1.1",)
    assert finding.evidence["B_generic_connector_pins"] == ("J1.2",)
    assert finding.evidence["RS485_endpoint_pairs"] == ("U1:U1.1=A/LINE_A;U1.2=B/LINE_B",)
    assert "intentionally isolated" in finding.message
    assert "does not require connection to board ground" in finding.message


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_named_roles_current_map_and_not_applicable_are_controls() -> None:
    named = two_pin_rs485_connector_netlist(connector_functions=("A", "B"))
    not_applicable = ConnectorCoverageReport(
        status="COMPLETE",
        scope="Synthetic reviewed connector inventory",
        inventory_review_basis="Reviewed two-contact connector disposition",
        entries=(ConnectorCoverageEntry(reference="J1", status="NOT_APPLICABLE"),),
    )
    stale = ConnectorCoverageReport(
        status="INCOMPLETE",
        scope="Synthetic stale connector review",
        entries=(ConnectorCoverageEntry(reference="J1", status="STALE"),),
    )

    assert not _findings(_report(named))
    assert not _findings(_report(connector_coverage=two_pin_rs485_connector_map()))
    assert not _findings(_report(connector_coverage=not_applicable))
    assert len(_findings(_report(connector_coverage=stale))) == 1


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_extra_return_contact_and_mapped_return_role_suppress_the_prompt() -> None:
    connector_with_return = two_pin_rs485_connector_netlist(
        connector_functions=("Pin_1", "Pin_2", "GND")
    )

    assert not _findings(_report(connector_with_return))
    assert not _findings(
        _report(connector_coverage=two_pin_rs485_connector_map(return_on_line_contact=True))
    )


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_dnp_incomplete_ambiguous_and_unsupported_inputs_stay_quiet() -> None:
    source = two_pin_rs485_connector_netlist()
    dnp_connector = source.model_copy(update={"dnp_components": ("J1",)})
    dnp_endpoint = source.model_copy(update={"dnp_components": ("U1",)})
    incomplete = source.model_copy(
        update={"component_pin_numbers": {**source.component_pin_numbers, "J1": ("1",)}}
    )
    ambiguous = two_pin_rs485_connector_netlist(ambiguous_connector_contact=True)
    one_sided = two_pin_rs485_connector_netlist(include_b_contact=False)
    unsupported_identity = source.model_copy(
        update={
            "components": {
                **source.components,
                "U1": source.components["U1"].model_copy(update={"value": "Generic line driver"}),
            },
            "component_symbols": {**source.component_symbols, "U1": "Synthetic:GenericLineDriver"},
        }
    )

    for candidate in (
        dnp_connector,
        dnp_endpoint,
        incomplete,
        ambiguous,
        one_sided,
        unsupported_identity,
    ):
        assert not _findings(_report(candidate))


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_policy_override_and_exact_ignore_remain_available() -> None:
    base = _findings(_report())[0]
    blocked = _findings(
        _report(
            policy=DesignLintPolicy(
                rules=(
                    DesignLintRuleOverride(
                        rule_id=RULE_ID,
                        mode="block",
                        reason="This project requires reviewed RS-485 connector reference intent",
                    ),
                )
            )
        )
    )[0]
    off = _report(
        policy=DesignLintPolicy(
            rules=(DesignLintRuleOverride(rule_id=RULE_ID, mode="off", reason="No RS-485 port"),)
        )
    )
    ignored = _findings(
        _report(
            policy=DesignLintPolicy(
                ignores=(
                    DesignLintIgnore(
                        rule_id=RULE_ID,
                        fingerprint=base.fingerprint,
                        reason="Reference is provided by the reviewed external cable",
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
    source = two_pin_rs485_connector_netlist()
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
