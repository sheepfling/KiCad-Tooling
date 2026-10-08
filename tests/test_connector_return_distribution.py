"""Synthetic regressions for project-scoped connector return-contact review."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from kicad_tooling.hwrepo.connector_coverage import evaluate as evaluate_connector_coverage
from kicad_tooling.hwrepo.design_lint import candidates, evaluate, text_report
from kicad_tooling.hwrepo.models import (
    ConnectorInterfaceReview,
    ConnectorInventoryReview,
    ConnectorPinRole,
    ConnectorReturnDistributionMap,
    ConnectorReturnDistributionRequirement,
    ContractCoachReport,
    DesignLintIgnore,
    DesignLintPolicy,
    DesignLintRuleOverride,
    InterfacePin,
    InterfaceRecord,
    NetlistContract,
)


def distribution_map(
    *, minimum_signal_pin_count: int = 4, maximum_signal_to_return_ratio: float = 3.0
) -> ConnectorReturnDistributionMap:
    return ConnectorReturnDistributionMap(
        requirements=(
            ConnectorReturnDistributionRequirement(
                id="external-link",
                interface_id="synthetic-link",
                minimum_signal_pin_count=minimum_signal_pin_count,
                maximum_signal_to_return_ratio=maximum_signal_to_return_ratio,
                basis="Synthetic reviewed interface contact-allocation requirement",
            ),
        )
    )


def observed_link(
    roles: tuple[ConnectorPinRole | None, ...], *, shared_returns: bool = False
) -> NetlistContract:
    nets: dict[str, tuple[str, ...]] = {}
    return_pins: list[str] = []
    for number, role in enumerate(roles, start=1):
        pin = f"J1.{number}"
        if role == "return":
            return_pins.append(pin)
            if shared_returns:
                continue
        nets[f"NET_{number:02d}"] = (pin,)
    if shared_returns and return_pins:
        nets["RETURN"] = tuple(return_pins)
    return NetlistContract(
        components={},
        nets=nets,
        component_symbols={"J1": "Synthetic:ExternalPort"},
        component_pin_numbers={"J1": tuple(str(number) for number in range(1, len(roles) + 1))},
        pin_functions={
            f"J1.{number}": (
                f"SIG{number}"
                if role == "signal"
                else "GND"
                if role == "return"
                else "VCC"
                if role == "supply"
                else "SHIELD"
                if role == "shield"
                else f"PIN{number}"
            )
            for number, role in enumerate(roles, start=1)
        },
    )


def interface_record(roles: tuple[ConnectorPinRole | None, ...]) -> InterfaceRecord:
    return InterfaceRecord(
        id="synthetic-link",
        revision="synthetic-1",
        pins=tuple(
            InterfacePin(
                number=str(number),
                signal=f"contact-{number}",
                role=role,
                direction="bidirectional",
                voltage_domain="synthetic-domain",
                mating="synthetic peer",
                orientation="straight",
                mechanical_clearance="synthetic",
            )
            for number, role in enumerate(roles, start=1)
        ),
    )


def connector_coverage(
    roles: tuple[ConnectorPinRole | None, ...],
    *,
    observed: NetlistContract | None = None,
    omit_interface_pin: str | None = None,
):
    record = interface_record(roles)
    pin_map = {pin.number: pin.number for pin in record.pins if pin.number != omit_interface_pin}
    return evaluate_connector_coverage(
        observed or observed_link(roles),
        ("synthetic-link",),
        (
            ConnectorInterfaceReview(
                reference="J1",
                disposition="interface",
                basis="Synthetic reviewed interface mapping",
                interface_id="synthetic-link",
                pin_map=pin_map,
            ),
        ),
        interfaces={"synthetic-link": record},
        interface_catalog_path="catalog/interfaces.json",
        interface_catalog_sha256="f" * 64,
        inventory_review=ConnectorInventoryReview(
            basis="Synthetic review covered the complete connector inventory"
        ),
    )


def lint_report(
    roles: tuple[ConnectorPinRole | None, ...],
    *,
    policy: DesignLintPolicy | None = None,
    omit_interface_pin: str | None = None,
    shared_returns: bool = False,
    observed_override: NetlistContract | None = None,
):
    observed = (
        observed_override
        if observed_override is not None
        else observed_link(roles, shared_returns=shared_returns)
    )
    coverage = connector_coverage(
        roles,
        observed=observed,
        omit_interface_pin=omit_interface_pin,
    )
    coach = ContractCoachReport(
        status="READY_FOR_REVIEW",
        project_id="synthetic-return-distribution",
        observed=observed,
        netlist_sha256="e" * 64,
    )
    return evaluate(
        "synthetic-return-distribution",
        coach,
        policy or DesignLintPolicy(),
        connector_coverage=coverage,
    )


def test_ratio_adds_a_distinct_finding_with_explicit_pin_evidence() -> None:
    roles = ("signal",) * 6 + ("return", "supply", "shield")
    observed = observed_link(roles)
    coverage = connector_coverage(roles)
    baseline = candidates(observed)
    assert not (
        {
            "connector.repeated_pin_function",
            "connector.no_connected_return",
            "connector.unconnected_return_pin",
        }
        & {item.rule_id for item in baseline}
    )

    result = lint_report(
        roles,
        policy=DesignLintPolicy(connector_return_distribution_map=distribution_map()),
    )
    assert coverage.status == "COMPLETE"
    assert result.status == "REVIEW"
    assert {item.rule_id for item in result.findings} == {"connector.return_distribution"}
    finding = result.findings[0]
    assert finding.evidence["signal_contact_count"] == ("6",)
    assert finding.evidence["return_contact_count"] == ("1",)
    assert "interface 7 -> J1.7" in finding.evidence["return_pins"]
    assert "interface 8 -> J1.8" in finding.evidence["supply_pins_excluded"]
    assert "interface 9 -> J1.9" in finding.evidence["shield_pins_excluded"]
    assert "Connector return-distribution coverage: COMPLETE" in text_report(result)
    assert "this ratio does not require returns to share a net" in finding.message


def test_mapping_order_preserves_findings_and_ratio_threshold_is_causal() -> None:
    roles = ("signal",) * 8 + ("return", "return", "supply", "shield")
    policy = DesignLintPolicy(connector_return_distribution_map=distribution_map())
    boundary_roles = ("signal",) * 6 + ("return", "return")
    boundary_report = lint_report(
        boundary_roles,
        policy=policy,
        shared_returns=True,
    )
    assert boundary_report.connector_return_distribution.status == "COMPLETE"
    assert boundary_report.connector_return_distribution.entries[0].signal_to_return_ratio == 3.0
    assert "connector.return_distribution" not in {
        finding.rule_id for finding in boundary_report.findings
    }

    observed = observed_link(roles, shared_returns=True)
    reordered = observed.model_copy(
        update={
            "nets": dict(reversed(tuple(observed.nets.items()))),
            "component_pin_numbers": {
                reference: tuple(reversed(numbers))
                for reference, numbers in observed.component_pin_numbers.items()
            },
            "pin_functions": dict(reversed(tuple(observed.pin_functions.items()))),
        }
    )

    original = lint_report(roles, policy=policy, observed_override=observed)
    permuted = lint_report(roles, policy=policy, observed_override=reordered)
    assert original.status == "REVIEW"
    assert permuted.status == original.status
    assert "connector.return_distribution" in {finding.rule_id for finding in original.findings}
    assert tuple(
        (finding.rule_id, finding.fingerprint, finding.message, finding.evidence)
        for finding in original.findings
    ) == tuple(
        (finding.rule_id, finding.fingerprint, finding.message, finding.evidence)
        for finding in permuted.findings
    )

    original_entry = original.connector_return_distribution.entries[0]
    permuted_entry = permuted.connector_return_distribution.entries[0]
    assert original_entry.signal_pin_count == 8
    assert original_entry.return_pin_count == 2
    assert original_entry.signal_to_return_ratio == 4.0
    assert (
        permuted_entry.signal_pin_count,
        permuted_entry.return_pin_count,
        permuted_entry.signal_to_return_ratio,
    ) == (
        original_entry.signal_pin_count,
        original_entry.return_pin_count,
        original_entry.signal_to_return_ratio,
    )


def test_exact_boundary_passes_and_net_grouping_does_not_change_the_ratio() -> None:
    roles = ("signal",) * 6 + ("return", "return", "supply", "shield")
    policy = DesignLintPolicy(connector_return_distribution_map=distribution_map())
    shared = lint_report(roles, policy=policy, shared_returns=True)
    assert shared.status == "PASS"
    assert shared.connector_return_distribution.status == "COMPLETE"
    entry = shared.connector_return_distribution.entries[0]
    assert entry.signal_pin_count == 6
    assert entry.return_pin_count == 2
    assert entry.signal_to_return_ratio == 3.0
    assert entry.required_return_pin_count == 2
    assert entry.supply_pin_map == {"9": "J1.9"}
    assert entry.shield_pin_map == {"10": "J1.10"}

    split = lint_report(roles, policy=policy)
    assert split.connector_return_distribution.entries[0].status == "COMPLETE"
    assert split.connector_return_distribution.entries[0].signal_to_return_ratio == 3.0
    assert split.status == "REVIEW"
    assert "connector.repeated_pin_function" in {item.rule_id for item in split.findings}
    assert "connector.return_distribution" not in {item.rule_id for item in split.findings}
    assert (
        split.connector_return_distribution.entries[0].signal_to_return_ratio
        == shared.connector_return_distribution.entries[0].signal_to_return_ratio
    )


def test_below_scope_power_connector_does_not_trigger_the_signal_ratio() -> None:
    roles = ("supply", "shield")
    result = lint_report(
        roles,
        policy=DesignLintPolicy(
            connector_return_distribution_map=distribution_map(minimum_signal_pin_count=4)
        ),
    )
    assert result.status == "PASS"
    assert result.connector_return_distribution.entries[0].status == "BELOW_SCOPE"
    assert not (any(item.rule_id == "connector.return_distribution" for item in result.findings))


def test_missing_role_or_incomplete_pin_mapping_keeps_coverage_at_review() -> None:
    roles: tuple[ConnectorPinRole | None, ...] = ("signal",) * 5 + (
        "return",
        None,
        "shield",
    )
    missing_role = lint_report(
        roles,
        policy=DesignLintPolicy(connector_return_distribution_map=distribution_map()),
    )
    assert missing_role.status == "REVIEW"
    assert missing_role.connector_return_distribution.status == "INCOMPLETE"
    entry = missing_role.connector_return_distribution.entries[0]
    assert entry.unclassified_pin_map == {"7": "J1.7"}
    assert any(item.rule_id == "connector.return_distribution" for item in missing_role.findings)

    incomplete_map = lint_report(
        ("signal",) * 5 + ("return", "supply", "shield"),
        policy=DesignLintPolicy(connector_return_distribution_map=distribution_map()),
        omit_interface_pin="8",
    )
    assert incomplete_map.connector_return_distribution.status == "INCOMPLETE"
    assert incomplete_map.connector_return_distribution.entries[0].status == "INCOMPLETE"
    assert incomplete_map.status == "REVIEW"


def test_project_policy_can_review_block_disable_or_exactly_ignore() -> None:
    roles = ("signal",) * 6 + ("return", "supply", "shield")
    fault_map = distribution_map()
    reviewed = lint_report(
        roles,
        policy=DesignLintPolicy(connector_return_distribution_map=fault_map),
    )
    candidate = reviewed.findings[0]
    blocked = lint_report(
        roles,
        policy=DesignLintPolicy(
            connector_return_distribution_map=fault_map,
            rules=(
                DesignLintRuleOverride(
                    rule_id="connector.return_distribution",
                    mode="block",
                    reason="Synthetic authored return-contact requirement",
                ),
            ),
        ),
    )
    assert blocked.status == "FAIL"

    disabled = lint_report(
        roles,
        policy=DesignLintPolicy(
            connector_return_distribution_map=fault_map,
            rules=(
                DesignLintRuleOverride(
                    rule_id="connector.return_distribution",
                    mode="off",
                    reason="Synthetic interface is reviewed under another owner process",
                ),
            ),
        ),
    )
    assert disabled.status == "PASS"
    assert disabled.findings[0].disposition == "RULE_OFF"

    ignored = lint_report(
        roles,
        policy=DesignLintPolicy(
            connector_return_distribution_map=fault_map,
            ignores=(
                DesignLintIgnore(
                    rule_id=candidate.rule_id,
                    fingerprint=candidate.fingerprint,
                    reason="Synthetic ratio reviewed and accepted",
                ),
            ),
        ),
    )
    assert ignored.status == "PASS"
    assert ignored.findings[0].disposition == "IGNORED"


def test_no_threshold_is_not_requested() -> None:
    result = lint_report(("signal",) * 6 + ("return",))
    assert result.status == "PASS"
    assert result.connector_return_distribution.status == "NOT_REQUESTED"
    assert not (any(item.rule_id == "connector.return_distribution" for item in result.findings))


def test_return_distribution_map_rejects_duplicate_ids_and_interfaces() -> None:
    first = distribution_map().requirements[0]
    with pytest.raises(ValidationError, match="IDs must be unique"):
        ConnectorReturnDistributionMap(requirements=(first, first))
    duplicate_interface = first.model_copy(update={"id": "second"})
    with pytest.raises(ValidationError, match="interfaces must be unique"):
        ConnectorReturnDistributionMap(requirements=(first, duplicate_interface))
