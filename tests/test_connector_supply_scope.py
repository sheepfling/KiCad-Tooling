"""Source-matched project scopes for connector supply-pin heuristics."""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType

import pytest
from pydantic import ValidationError

from kicad_tooling.hwrepo.connector_coverage import (
    evaluate as evaluate_connector_coverage,
)
from kicad_tooling.hwrepo.connector_coverage import (
    source_matched_connector_supply_comparison_groups,
)
from kicad_tooling.hwrepo.connector_coverage_models import ConnectorInterfaceReview
from kicad_tooling.hwrepo.contracts import model_json_bytes
from kicad_tooling.hwrepo.design_lint import evaluate as evaluate_design_lint
from kicad_tooling.hwrepo.design_lint import text_report
from kicad_tooling.hwrepo.models import (
    ContractCoachReport,
    DesignLintPolicy,
    InterfaceRecord,
    NetlistContract,
)
from tests.design_lint_fixtures.connector_coverage import (
    inventory_review,
    three_connector_supply_role_catalog,
    three_connector_supply_role_netlist,
    three_connector_supply_role_reviews,
)

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.connector_lint,
    pytest.mark.design_lint_rule(rule_id="connector.repeated_pin_function"),
]

_GROUPS = MappingProxyType({"J1": "host-5v", "J2": "host-5v", "J3": "sensor-5v"})


def _split_supply_netlist() -> NetlistContract:
    observed = three_connector_supply_role_netlist()
    return observed.model_copy(
        update={
            "nets": {
                "SUPPLY_USB": ("J1.2",),
                "SUPPLY_SERIAL": ("J2.5",),
                "SUPPLY_SENSOR": ("J3.9",),
            }
        }
    )


def _coverage(
    observed: NetlistContract,
    groups: Mapping[str, str] | None = None,
    *,
    catalog: Mapping[str, InterfaceRecord] | None = None,
):
    groups = groups or {}
    reviews = tuple(
        review.model_copy(
            update={
                "supply_comparison_group": groups.get(review.reference),
                "supply_comparison_basis": (
                    f"Reviewed {review.reference} in supply-comparison group "
                    f"{groups[review.reference]}"
                    if review.reference in groups
                    else None
                ),
            }
        )
        for review in three_connector_supply_role_reviews()
    )
    interfaces = three_connector_supply_role_catalog() if catalog is None else catalog
    return evaluate_connector_coverage(
        observed,
        tuple(sorted(interfaces)),
        reviews,
        interfaces=interfaces,
        interface_catalog_path="catalog/interfaces.json",
        interface_catalog_sha256="c" * 64,
        inventory_review=inventory_review(),
    )


def _report(netlist: NetlistContract, coverage):
    return evaluate_design_lint(
        "synthetic-connector-supply-scope",
        ContractCoachReport(
            status="READY_FOR_REVIEW",
            project_id="synthetic-connector-supply-scope",
            observed=netlist,
            netlist_sha256="a" * 64,
        ),
        DesignLintPolicy(),
        connector_coverage=coverage,
    )


def _supply_findings(report):
    return tuple(
        finding
        for finding in report.findings
        if finding.rule_id == "connector.repeated_pin_function"
        and finding.subject.endswith("supply in voltage domain external-5v")
    )


def test_split_supply_in_one_reviewed_group_prompts_and_separate_group_is_scoped() -> None:
    netlist = _split_supply_netlist()
    coverage = _coverage(netlist, _GROUPS)

    assert source_matched_connector_supply_comparison_groups(netlist, coverage) == {
        reference: (
            group,
            f"Reviewed {reference} in supply-comparison group {group}",
        )
        for reference, group in _GROUPS.items()
    }
    findings = _supply_findings(_report(netlist, coverage))
    assert len(findings) == 1
    finding = findings[0]
    assert {"J1.2", "J2.5"} <= set(finding.evidence)
    assert "J3.9" not in finding.evidence
    assert finding.evidence["supply_comparison_group"] == ("host-5v",)
    assert len(finding.evidence["supply_comparison_basis"]) == 2
    assert "peer_assignment_group" not in finding.evidence
    assert "peer_assignment_basis" not in finding.evidence
    assert "does not require common power nets" in finding.message
    assert "supply-comparison group host-5v" in finding.message
    rendered = text_report(_report(netlist, coverage))
    assert "Supply-comparison group: host-5v" in rendered
    assert "Supply-comparison basis: Reviewed J1" in rendered


def test_distinct_supply_groups_and_common_supply_are_quiet() -> None:
    split = _split_supply_netlist()
    separate_groups = {reference: reference for reference in ("J1", "J2", "J3")}
    separate_coverage = _coverage(split, separate_groups)
    assert not _supply_findings(_report(split, separate_coverage))

    common = three_connector_supply_role_netlist(all_common=True)
    common_coverage = _coverage(common, {reference: "board-5v" for reference in _GROUPS})
    assert not _supply_findings(_report(common, common_coverage))


def test_missing_or_stale_scope_restores_broad_supply_comparison() -> None:
    netlist = _split_supply_netlist()
    missing_scope = _coverage(netlist, {"J1": "host-5v", "J2": "host-5v"})
    missing_finding = _supply_findings(_report(netlist, missing_scope))[0]
    assert {"J1.2", "J2.5", "J3.9"} <= set(missing_finding.evidence)
    assert "supply_comparison_group" not in missing_finding.evidence

    mapped = _coverage(netlist, _GROUPS)
    changed = netlist.model_copy(
        update={
            "nets": {
                "SUPPLY_USB": ("J1.2",),
                "SUPPLY_SERIAL": ("J2.5",),
                "SUPPLY_SENSOR_REVISED": ("J3.9",),
            }
        }
    )
    assert source_matched_connector_supply_comparison_groups(changed, mapped) == {}
    stale_finding = _supply_findings(_report(changed, mapped))[0]
    assert {"J1.2", "J2.5"} <= set(stale_finding.evidence)
    assert "J3.9" not in stale_finding.evidence
    assert "supply_comparison_group" not in stale_finding.evidence


def test_supply_scope_without_mapped_voltage_domain_role_makes_coverage_incomplete() -> None:
    netlist = three_connector_supply_role_netlist()
    catalog = three_connector_supply_role_catalog()
    catalog["usb-power"] = catalog["usb-power"].model_copy(
        update={
            "pins": tuple(
                pin.model_copy(update={"role": "signal"}) for pin in catalog["usb-power"].pins
            )
        }
    )
    coverage = _coverage(netlist, {"J1": "host-5v"}, catalog=catalog)
    j1 = next(entry for entry in coverage.entries if entry.reference == "J1")
    assert j1.status == "INCOMPLETE"
    assert "no voltage-domain supply-role pin" in j1.issues[0]
    assert "J1" not in source_matched_connector_supply_comparison_groups(netlist, coverage)


def test_supply_scope_group_requires_a_review_basis() -> None:
    review = three_connector_supply_role_reviews()[0]
    with pytest.raises(ValidationError):
        ConnectorInterfaceReview.model_validate(
            review.model_dump() | {"supply_comparison_group": "host-5v"}
        )


def test_supply_group_fingerprint_is_order_stable_and_repair_clears_the_candidate() -> None:
    fault = _split_supply_netlist()
    coverage = _coverage(fault, _GROUPS)
    report = _report(fault, coverage)

    reversed_fault = NetlistContract(
        components=dict(reversed(tuple(fault.components.items()))),
        nets=dict(reversed(tuple(fault.nets.items()))),
        component_symbols=dict(reversed(tuple(fault.component_symbols.items()))),
        component_pin_numbers=dict(reversed(tuple(fault.component_pin_numbers.items()))),
        pin_functions=dict(reversed(tuple(fault.pin_functions.items()))),
    )
    reversed_coverage = _coverage(reversed_fault, dict(reversed(tuple(_GROUPS.items()))))
    assert model_json_bytes(report) == model_json_bytes(_report(reversed_fault, reversed_coverage))

    repaired = fault.model_copy(
        update={
            "nets": {
                "SUPPLY_HOST": ("J1.2", "J2.5"),
                "SUPPLY_SENSOR": ("J3.9",),
            }
        }
    )
    assert not _supply_findings(_report(repaired, _coverage(repaired, _GROUPS)))
