"""Review JTAG connectors whose return-role intent is not identified."""

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
from tests.design_lint_fixtures.jtag_generic_connector_pair import generic_jtag_connector_netlist

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.connector_lint,
    pytest.mark.interface_lint,
    pytest.mark.return_path_lint,
]

RULE_ID = "connector.jtag_pair_without_return_review"


def _report(
    observed: NetlistContract | None = None,
    *,
    connector_coverage: ConnectorCoverageReport | None = None,
    policy: DesignLintPolicy | None = None,
):
    netlist = observed or generic_jtag_connector_netlist(
        connector_functions=("Pin_1", "Pin_2", "Pin_3", "Pin_4", "Pin_5")
    )
    coach = ContractCoachReport(
        status="READY_FOR_REVIEW",
        project_id="synthetic-jtag-connector-return",
        observed=netlist,
        netlist_sha256="f" * 64,
    )
    return evaluate(
        coach.project_id,
        coach,
        policy or DesignLintPolicy(),
        connector_coverage,
    )


def _findings(report) -> tuple:
    return tuple(item for item in report.findings if item.rule_id == RULE_ID)


def _mapped_role(
    observed: NetlistContract,
    *,
    return_pin: bool,
) -> ConnectorCoverageReport:
    pin_nets = {pin: net for net, pins in observed.nets.items() for pin in pins}
    if return_pin:
        mapped = (
            ConnectorMappedPinEvidence(
                interface_pin_number="GND",
                interface_signal="GND",
                component_pin="J1.5",
                role="return",
                symbol_function=observed.pin_functions["J1.5"],
                nets=(pin_nets["J1.5"],),
            ),
        )
        pin_map = {"GND": "5"}
        unlisted = {str(number): "Reviewed separately" for number in range(1, 5)}
    else:
        mapped = (
            ConnectorMappedPinEvidence(
                interface_pin_number="TCK",
                interface_signal="TCK",
                component_pin="J1.1",
                symbol_function=observed.pin_functions["J1.1"],
                nets=(pin_nets["J1.1"],),
            ),
            ConnectorMappedPinEvidence(
                interface_pin_number="TMS",
                interface_signal="TMS",
                component_pin="J1.2",
                symbol_function=observed.pin_functions["J1.2"],
                nets=(pin_nets["J1.2"],),
            ),
        )
        pin_map = {"TCK": "1", "TMS": "2"}
        unlisted = {str(number): "No return role identified" for number in range(3, 6)}
    return ConnectorCoverageReport(
        status="COMPLETE",
        scope="Synthetic reviewed JTAG connector pinout",
        project_interfaces=("synthetic-jtag-debug",),
        inventory_review_basis="Synthetic approved complete connector inventory",
        interface_catalog_sha256="e" * 64,
        entries=(
            ConnectorCoverageEntry(
                reference="J1",
                status="COVERED",
                interface_id="synthetic-jtag-debug",
                basis="Synthetic reviewed connector pinout",
                interface_pin_map=pin_map,
                unlisted_pin_reasons=unlisted,
                mapped_pins=mapped,
            ),
        ),
    )


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_generic_contacts_on_jtag_pair_without_return_emit_review() -> None:
    report = _report()
    findings = _findings(report)

    assert report.status == "REVIEW"
    assert len(findings) == 1
    finding = findings[0]
    assert finding.mode == "review"
    assert finding.subject == "J1: JTAG connector has no identified reference return"
    assert finding.evidence["connector_native_pin_count"] == ("5",)
    assert finding.evidence["connector_native_pins"] == tuple(
        f"J1.{number}" for number in range(1, 6)
    )
    assert finding.evidence["TCK_generic_connector_pins"] == ("J1.1",)
    assert finding.evidence["TMS_generic_connector_pins"] == ("J1.2",)
    assert "supplied elsewhere" in finding.message
    assert "does not require board ground" in finding.message


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_native_return_and_current_mapped_return_are_valid_controls() -> None:
    native_return = generic_jtag_connector_netlist()
    assert not _findings(_report(native_return))

    observed = generic_jtag_connector_netlist(
        connector_functions=("Pin_1", "Pin_2", "Pin_3", "Pin_4", "Pin_5")
    )
    assert not _findings(
        _report(observed, connector_coverage=_mapped_role(observed, return_pin=True))
    )


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_complete_signal_map_without_return_still_prompts_and_not_applicable_suppresses() -> None:
    observed = generic_jtag_connector_netlist(
        connector_functions=("Pin_1", "Pin_2", "Pin_3", "Pin_4", "Pin_5")
    )
    signal_map = _mapped_role(observed, return_pin=False)
    assert len(_findings(_report(observed, connector_coverage=signal_map))) == 1

    not_applicable = ConnectorCoverageReport(
        status="COMPLETE",
        scope="Synthetic reviewed connector inventory",
        inventory_review_basis="Reviewed JTAG applicability decision",
        entries=(ConnectorCoverageEntry(reference="J1", status="NOT_APPLICABLE"),),
    )
    stale_return = _mapped_role(observed, return_pin=True).model_copy(
        update={
            "status": "INCOMPLETE",
            "entries": (
                _mapped_role(observed, return_pin=True)
                .entries[0]
                .model_copy(update={"status": "STALE"}),
            ),
        }
    )
    assert not _findings(_report(observed, connector_coverage=not_applicable))
    assert len(_findings(_report(observed, connector_coverage=stale_return))) == 1


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_policy_override_exact_ignore_and_mapping_order_are_deterministic() -> None:
    observed = generic_jtag_connector_netlist(
        connector_functions=("Pin_1", "Pin_2", "Pin_3", "Pin_4", "Pin_5")
    )
    base = _findings(_report(observed))[0]
    blocked = _findings(
        _report(
            observed,
            policy=DesignLintPolicy(
                rules=(
                    DesignLintRuleOverride(
                        rule_id=RULE_ID,
                        mode="block",
                        reason="Review JTAG connector reference requirements",
                    ),
                )
            ),
        )
    )[0]
    off = _report(
        observed,
        policy=DesignLintPolicy(
            rules=(DesignLintRuleOverride(rule_id=RULE_ID, mode="off", reason="Not applicable"),)
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
                        reason="Reference provided by reviewed cable assembly",
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
