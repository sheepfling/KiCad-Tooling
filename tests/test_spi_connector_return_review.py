"""Review mapped SPI connector pinouts that omit an identified return role."""

from __future__ import annotations

import pytest

from kicad_tooling.ci_hosted_spi_generic_connector_cases import spi_connector_role_map
from kicad_tooling.hwrepo.connector_coverage_models import ConnectorCoverageReport
from kicad_tooling.hwrepo.contract_coach_models import ContractCoachReport
from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.design_lint_policy_models import (
    DesignLintIgnore,
    DesignLintPolicy,
    DesignLintRuleOverride,
)
from kicad_tooling.hwrepo.netlist_contract_models import NetlistContract
from tests.design_lint_fixtures.spi_generic_connector_triad import (
    generic_spi_connector_triad_netlist,
)

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.connector_lint,
    pytest.mark.interface_lint,
    pytest.mark.return_path_lint,
]

RULE_ID = "connector.spi_triad_without_return_review"


def _report(
    *,
    observed: NetlistContract | None = None,
    has_return_role: bool = False,
    connector_coverage: ConnectorCoverageReport | None = None,
    policy: DesignLintPolicy | None = None,
):
    observed = observed or generic_spi_connector_triad_netlist()
    coverage = connector_coverage or spi_connector_role_map(
        observed,
        has_return_role=has_return_role,
    )
    coach = ContractCoachReport(
        status="READY_FOR_REVIEW",
        project_id="synthetic-spi-return-review",
        observed=observed,
        netlist_sha256="a" * 64,
    )
    return evaluate(coach.project_id, coach, policy or DesignLintPolicy(), coverage)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_complete_spi_map_without_a_return_role_emits_review() -> None:
    report = _report()
    findings = tuple(item for item in report.findings if item.rule_id == RULE_ID)

    assert report.status == "REVIEW"
    assert len(findings) == 1
    assert findings[0].mode == "review"
    assert findings[0].subject == "J1: mapped SPI connector has no identified return role"
    assert findings[0].evidence["identified_return_contacts"] == ()
    assert findings[0].evidence["mapped_connector_pins"][-1].startswith("J1.4:AUX:role=other")
    assert "BOARD_GND" in findings[0].evidence["mapped_connector_pins"][-1]
    assert "does not require connection to board ground" in findings[0].message


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_source_mapped_return_role_is_a_valid_control() -> None:
    report = _report(has_return_role=True)

    assert RULE_ID not in {item.rule_id for item in report.findings}


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_unreviewed_or_stale_connector_maps_do_not_claim_return_coverage() -> None:
    observed = generic_spi_connector_triad_netlist()
    current = spi_connector_role_map(observed, has_return_role=False)
    stale = current.model_copy(
        update={
            "status": "INCOMPLETE",
            "entries": (current.entries[0].model_copy(update={"status": "STALE"}),),
        }
    )
    report = _report(connector_coverage=stale)

    assert RULE_ID not in {item.rule_id for item in report.findings}


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_rule_override_and_exact_ignore_remain_available() -> None:
    finding = next(item for item in _report().findings if item.rule_id == RULE_ID)
    blocked = _report(
        policy=DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=RULE_ID,
                    mode="block",
                    reason="Review the synthetic SPI connector map",
                ),
            )
        )
    )
    ignored = _report(
        policy=DesignLintPolicy(
            ignores=(
                DesignLintIgnore(
                    rule_id=RULE_ID,
                    fingerprint=finding.fingerprint,
                    reason="Synthetic interface reference is reviewed elsewhere",
                ),
            )
        )
    )

    assert blocked.status == "FAIL"
    assert next(item for item in blocked.findings if item.rule_id == RULE_ID).mode == "block"
    assert (
        next(item for item in ignored.findings if item.rule_id == RULE_ID).disposition == "IGNORED"
    )


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_finding_is_stable_when_native_mappings_are_reordered() -> None:
    observed = generic_spi_connector_triad_netlist()
    coverage = spi_connector_role_map(observed, has_return_role=False)
    reordered_observed = observed.model_copy(
        update={
            "components": dict(reversed(tuple(observed.components.items()))),
            "component_symbols": dict(reversed(tuple(observed.component_symbols.items()))),
            "nets": dict(reversed(tuple(observed.nets.items()))),
            "pin_functions": dict(reversed(tuple(observed.pin_functions.items()))),
            "pin_electrical_types": dict(reversed(tuple(observed.pin_electrical_types.items()))),
        }
    )
    entry = coverage.entries[0]
    reordered_coverage = coverage.model_copy(
        update={
            "entries": (
                entry.model_copy(
                    update={
                        "interface_pin_map": dict(reversed(tuple(entry.interface_pin_map.items()))),
                        "mapped_pins": tuple(reversed(entry.mapped_pins)),
                    }
                ),
            )
        }
    )

    first = next(
        item for item in _report(connector_coverage=coverage).findings if item.rule_id == RULE_ID
    )
    second = next(
        item
        for item in _report(
            observed=reordered_observed,
            connector_coverage=reordered_coverage,
        ).findings
        if item.rule_id == RULE_ID
    )

    assert first == second
