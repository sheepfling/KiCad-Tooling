"""Review SWD connectors with no native or mapped reference return."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.connector_coverage_models import (
    ConnectorCoverageEntry,
    ConnectorCoverageReport,
    ConnectorMappedPinEvidence,
)
from kicad_tooling.hwrepo.contract_coach_models import ContractCoachReport
from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.design_lint_policy_models import (
    DesignLintIgnore,
    DesignLintPolicy,
    DesignLintRuleOverride,
)
from kicad_tooling.hwrepo.netlist_contract_models import NetlistContract
from tests.design_lint_fixtures.swd_generic_connector_pair import generic_swd_connector_netlist

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.connector_lint,
    pytest.mark.interface_lint,
    pytest.mark.return_path_lint,
]

RULE_ID = "connector.swd_pair_without_return_review"


def _report(
    observed: NetlistContract | None = None,
    *,
    connector_coverage: ConnectorCoverageReport | None = None,
    policy: DesignLintPolicy | None = None,
):
    netlist = observed or generic_swd_connector_netlist()
    coach = ContractCoachReport(
        status="READY_FOR_REVIEW",
        project_id="synthetic-swd-connector-return",
        observed=netlist,
        netlist_sha256="e" * 64,
    )
    return evaluate(
        coach.project_id,
        coach,
        policy or DesignLintPolicy(),
        connector_coverage,
    )


def _findings(report) -> tuple:
    return tuple(item for item in report.findings if item.rule_id == RULE_ID)


def _reviewed_return_map(observed: NetlistContract) -> ConnectorCoverageReport:
    pin_nets = {pin: net for net, pins in observed.nets.items() for pin in pins}
    return ConnectorCoverageReport(
        status="COMPLETE",
        scope="Synthetic reviewed SWD connector pinout",
        project_interfaces=("synthetic-swd-debug",),
        inventory_review_basis="Synthetic approved complete connector inventory",
        interface_catalog_sha256="e" * 64,
        entries=(
            ConnectorCoverageEntry(
                reference="J1",
                status="COVERED",
                interface_id="synthetic-swd-debug",
                basis="Synthetic reviewed return contact",
                interface_pin_map={"GND": "5"},
                unlisted_pin_reasons={
                    "1": "Mapped as SWDIO by native function review",
                    "2": "Mapped as SWCLK by native function review",
                    "3": "Auxiliary contact reviewed separately",
                    "4": "Auxiliary contact reviewed separately",
                },
                mapped_pins=(
                    ConnectorMappedPinEvidence(
                        interface_pin_number="GND",
                        interface_signal="GND",
                        component_pin="J1.5",
                        role="return",
                        symbol_function="Pin_5",
                        nets=(pin_nets["J1.5"],),
                    ),
                ),
            ),
        ),
    )


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_generic_contacts_on_swd_pair_without_return_emit_review() -> None:
    report = _report()
    findings = _findings(report)

    assert report.status == "REVIEW"
    assert len(findings) == 1
    finding = findings[0]
    assert finding.mode == "review"
    assert finding.subject == "J1: SWD connector has no identified reference return"
    assert finding.evidence["connector_native_pin_count"] == ("5",)
    assert finding.evidence["connector_native_pins"] == tuple(
        f"J1.{number}" for number in range(1, 6)
    )
    assert finding.evidence["SWDIO_generic_connector_pins"] == ("J1.1",)
    assert finding.evidence["SWCLK_generic_connector_pins"] == ("J1.2",)
    assert "supplied elsewhere" in finding.message
    assert "does not require board ground" in finding.message


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_native_return_role_and_current_mapped_return_suppress_prompt() -> None:
    observed = generic_swd_connector_netlist(
        connector_functions=("Pin_1", "Pin_2", "Pin_3", "Pin_4", "GND")
    )
    assert not _findings(_report(observed))

    mapped_observed = generic_swd_connector_netlist()
    assert not _findings(
        _report(
            mapped_observed,
            connector_coverage=_reviewed_return_map(mapped_observed),
        )
    )


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_reviewed_not_applicable_and_stale_return_maps_are_handled() -> None:
    observed = generic_swd_connector_netlist()
    not_applicable = ConnectorCoverageReport(
        status="COMPLETE",
        scope="Synthetic reviewed connector inventory",
        inventory_review_basis="Reviewed SWD applicability decision",
        entries=(ConnectorCoverageEntry(reference="J1", status="NOT_APPLICABLE"),),
    )
    stale = ConnectorCoverageReport(
        status="INCOMPLETE",
        scope="Synthetic stale connector map",
        entries=(ConnectorCoverageEntry(reference="J1", status="STALE"),),
    )

    assert not _findings(_report(observed, connector_coverage=not_applicable))
    assert len(_findings(_report(observed, connector_coverage=stale))) == 1


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_rule_policy_and_finding_order_are_deterministic() -> None:
    observed = generic_swd_connector_netlist()
    base = _findings(_report(observed))[0]
    blocked = _findings(
        _report(
            observed,
            policy=DesignLintPolicy(
                rules=(
                    DesignLintRuleOverride(
                        rule_id=RULE_ID,
                        mode="block",
                        reason="Review SWD connector return intent",
                    ),
                )
            ),
        )
    )[0]
    off = _report(
        observed,
        policy=DesignLintPolicy(
            rules=(DesignLintRuleOverride(rule_id=RULE_ID, mode="off", reason="No debug port"),)
        ),
    )
    ignored = _findings(
        _report(
            observed,
            policy=DesignLintPolicy(
                ignores=(
                    DesignLintIgnore(
                        rule_id=RULE_ID,
                        fingerprint=base.fingerprint,
                        reason="Reviewed isolated debug interface",
                    ),
                )
            ),
        )
    )[0]
    reordered = observed.model_copy(
        update={
            "nets": dict(reversed(tuple(observed.nets.items()))),
            "pin_functions": dict(reversed(tuple(observed.pin_functions.items()))),
        }
    )

    assert blocked.mode == "block"
    assert _findings(off)[0].disposition == "RULE_OFF"
    assert ignored.disposition == "IGNORED"
    assert _findings(_report(reordered))[0].fingerprint == base.fingerprint
