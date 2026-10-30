"""Review complete connector alias maps that omit assignment-comparison scope."""

from __future__ import annotations

from pathlib import Path

import pytest
from mcp import Client

from kicad_tooling.hwrepo.connector_coverage_models import ConnectorCoverageReport
from kicad_tooling.hwrepo.contracts import read_model, repo_path, write_model
from kicad_tooling.hwrepo.discovery import load_registry
from kicad_tooling.hwrepo.mcp_server import create_server
from kicad_tooling.hwrepo.models import (
    ConnectorInterfaceReview,
    ConnectorInventoryReview,
    DesignLintIgnore,
    DesignLintPolicy,
    DesignLintRuleOverride,
    InterfacePin,
    InterfaceRecord,
    InterfacesCatalog,
    ProjectManifest,
)
from tests.connector_footprint_peer_support import peer_netlist
from tests.connector_peer_unanchored_scope_support import (
    PEER_GROUP,
    lint_report,
    reviewed_coverage,
)
from tests.design_lint_mcp_parity_report_support import DesignLintMcpParityReportHarness
from tests.mcp_parity_support import run_mcp_parity

RULE_ID = "connector.footprint_peer_unanchored_scope_unreviewed"

pytestmark = [pytest.mark.design_lint, pytest.mark.connector_lint]


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_complete_source_matched_maps_without_peer_scope_prompt_once_per_alias_group() -> None:
    observed = peer_netlist(assignments=(("PORT_A", "PORT_B"), ("DATA_A", "DATA_B")))
    coverage = reviewed_coverage(observed, (None, None))

    assert coverage.status == "COMPLETE"
    assert all(entry.status == "COVERED" for entry in coverage.entries)
    assert all(entry.peer_assignment_group is None for entry in coverage.entries)
    report = lint_report(observed, coverage)
    findings = [item for item in report.findings if item.rule_id == RULE_ID]

    assert report.status == "REVIEW"
    assert len(findings) == 1
    finding = findings[0]
    assert finding.evidence["references"] == ("J1", "J2")
    assert finding.evidence["unanchored_generic_pin_numbers"] == ("1", "2")
    assert finding.evidence["pin_assignments"] == (
        "pin 1: J1.1=PORT_A; J2.1=PORT_B",
        "pin 2: J1.2=DATA_A; J2.2=DATA_B",
    )
    assert finding.evidence["interface_catalog_sha256"] == ("f" * 64,)
    assert "does not require matching nets" in finding.message
    assert not any(
        item.rule_id == "connector.footprint_peer_pin_unanchored_assignment_divergence"
        for item in report.findings
    )
    assert report.connector_peer_pin_coverage is not None
    alias_coverage = report.connector_peer_pin_coverage.footprint_alias_coverage
    assert alias_coverage.unreviewed_peer_assignment_scope_finding_count == 1


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
@pytest.mark.parametrize(
    ("assignments", "groups", "inventory_reviewed", "pin_maps_complete"),
    (
        pytest.param(("COMMON", "COMMON"), (None, None), True, True, id="common-anchor"),
        pytest.param(
            ("PORT_A", "PORT_B"), (PEER_GROUP, PEER_GROUP), True, True, id="reviewed-peer-scope"
        ),
        pytest.param(("PORT_A", "PORT_B"), ("port-a", "port-b"), True, True, id="separate-scopes"),
        pytest.param(("PORT_A", "PORT_B"), (None, None), False, True, id="unreviewed-inventory"),
        pytest.param(("PORT_A", "PORT_B"), (None, None), True, False, id="incomplete-pin-maps"),
    ),
)
def test_no_prompt_for_common_anchor_or_noneligible_scope(
    assignments: tuple[str, str],
    groups: tuple[str | None, str | None],
    inventory_reviewed: bool,
    pin_maps_complete: bool,
) -> None:
    observed = peer_netlist(assignments=(assignments, ("DATA_A", "DATA_B")))
    coverage = reviewed_coverage(
        observed,
        groups,
        inventory_reviewed=inventory_reviewed,
        pin_maps_complete=pin_maps_complete,
    )

    report = lint_report(observed, coverage)

    assert not any(item.rule_id == RULE_ID for item in report.findings)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_missing_or_source_stale_connector_coverage_does_not_activate_scope_prompt() -> None:
    original = peer_netlist(assignments=(("PORT_A", "PORT_B"), ("DATA_A", "DATA_B")))
    coverage = reviewed_coverage(original, (None, None))
    changed = peer_netlist(assignments=(("PORT_A", "PORT_B"), ("DATA_A", "DATA_C")))

    assert not any(item.rule_id == RULE_ID for item in lint_report(original).findings)
    assert not any(item.rule_id == RULE_ID for item in lint_report(changed, coverage).findings)
    no_catalog_hash = coverage.model_copy(update={"interface_catalog_sha256": None})
    assert not any(
        item.rule_id == RULE_ID for item in lint_report(original, no_catalog_hash).findings
    )


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
@pytest.mark.parametrize(
    ("mode", "disposition"),
    (("review", "OPEN"), ("block", "OPEN"), ("off", "RULE_OFF")),
)
def test_scope_prompt_obeys_project_policy(mode: str, disposition: str) -> None:
    observed = peer_netlist(assignments=(("PORT_A", "PORT_B"), ("DATA_A", "DATA_B")))
    policy = DesignLintPolicy(
        rules=(
            DesignLintRuleOverride(
                rule_id=RULE_ID,
                mode=mode,
                reason="Synthetic test of project-owned lint policy",
            ),
        )
    )

    findings = [
        item
        for item in lint_report(
            observed, reviewed_coverage(observed, (None, None)), policy
        ).findings
        if item.rule_id == RULE_ID
    ]

    assert len(findings) == 1
    assert findings[0].mode == mode
    assert findings[0].disposition == disposition


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_scope_prompt_fingerprint_is_stable_under_native_mapping_reordering() -> None:
    observed = peer_netlist(assignments=(("PORT_A", "PORT_B"), ("DATA_A", "DATA_B")))
    reordered = observed.model_copy(
        update={
            "nets": dict(reversed(tuple(observed.nets.items()))),
            "component_symbols": dict(reversed(tuple(observed.component_symbols.items()))),
            "component_pin_numbers": dict(reversed(tuple(observed.component_pin_numbers.items()))),
            "pin_functions": dict(reversed(tuple(observed.pin_functions.items()))),
            "pin_electrical_types": dict(reversed(tuple(observed.pin_electrical_types.items()))),
        }
    )
    first = lint_report(observed, reviewed_coverage(observed, (None, None)))
    second = lint_report(reordered, reviewed_coverage(reordered, (None, None)))
    left = tuple(item for item in first.findings if item.rule_id == RULE_ID)
    right = tuple(item for item in second.findings if item.rule_id == RULE_ID)

    assert tuple((item.fingerprint, item.evidence) for item in left) == tuple(
        (item.fingerprint, item.evidence) for item in right
    )


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_scope_prompt_exact_ignore_matches_only_its_fingerprint() -> None:
    observed = peer_netlist(assignments=(("PORT_A", "PORT_B"), ("DATA_A", "DATA_B")))
    coverage: ConnectorCoverageReport = reviewed_coverage(observed, (None, None))
    initial = lint_report(observed, coverage)
    finding = next(item for item in initial.findings if item.rule_id == RULE_ID)
    policy = DesignLintPolicy(
        ignores=(
            DesignLintIgnore(
                rule_id=RULE_ID,
                fingerprint=finding.fingerprint,
                reason="Synthetic test of exact candidate disposition",
            ),
        )
    )

    result = lint_report(observed, coverage, policy)
    findings = [item for item in result.findings if item.rule_id == RULE_ID]

    assert len(findings) == 1
    assert findings[0].disposition == "IGNORED"


class _UnanchoredScopeParityCases(DesignLintMcpParityReportHarness):
    async def _case_unanchored_scope_review_matches_cli_and_mcp(self) -> None:
        native = self.native_evidence()
        netlist = native.parent / "netlist.xml"
        fixture = (
            Path(__file__).parent
            / "fixtures/design_lint/connector-peer-unanchored-scope/netlist.xml"
        )
        netlist.write_text(fixture.read_text(encoding="utf-8"), encoding="utf-8")
        self.rehash_native_netlist(native)

        interface_id = "synthetic-unanchored-peer-scope"
        interface = InterfaceRecord(
            id=interface_id,
            revision="synthetic-1",
            pins=tuple(
                InterfacePin(
                    number=str(number),
                    signal=f"contact-{number}",
                    direction="bidirectional",
                    voltage_domain="synthetic-domain",
                    mating="synthetic peer",
                    orientation="straight",
                    mechanical_clearance="synthetic",
                )
                for number in (1, 2)
            ),
        )
        registry = load_registry(self.root)
        catalog_path = repo_path(self.root, registry.catalogs.interfaces)
        catalog = read_model(catalog_path, InterfacesCatalog)
        write_model(
            catalog_path,
            catalog.model_copy(update={"interfaces": (*catalog.interfaces, interface)}),
        )
        manifest_path = self.island / "project.json"
        manifest = read_model(manifest_path, ProjectManifest)
        write_model(
            manifest_path,
            manifest.model_copy(
                update={
                    "interfaces": (*manifest.interfaces, interface_id),
                    "connector_reviews": tuple(
                        ConnectorInterfaceReview(
                            reference=reference,
                            disposition="interface",
                            basis=f"Synthetic source-matched interface map for {reference}",
                            interface_id=interface_id,
                            pin_map={"1": "1", "2": "2"},
                        )
                        for reference in ("J1", "J2")
                    ),
                    "connector_inventory_review": ConnectorInventoryReview(
                        basis="Synthetic connector inventory was reviewed"
                    ),
                }
            ),
        )

        async with Client(create_server(self.root), mode="legacy") as client:
            report = await self.compare_lint_report(client, native, "REVIEW", 1)
        findings = [item for item in report.findings if item.rule_id == RULE_ID]
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].evidence["references"], ("J1", "J2"))
        self.assertIsNotNone(report.connector_peer_pin_coverage)
        self.assertEqual(
            report.connector_peer_pin_coverage.footprint_alias_coverage.unreviewed_peer_assignment_scope_finding_count,
            1,
        )


@pytest.mark.parity_lint
@pytest.mark.slow
@pytest.mark.template_checkout
@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_unanchored_scope_review_cli_mcp_parity() -> None:
    run_mcp_parity(_UnanchoredScopeParityCases, "_case_unanchored_scope_review_matches_cli_and_mcp")
