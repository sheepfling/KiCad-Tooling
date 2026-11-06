"""CLI/MCP parity for source-mapped connector supply-domain review."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest
from mcp import Client

from kicad_tooling.hwrepo.contracts import read_model, write_model
from kicad_tooling.hwrepo.design_lint_reconciliation_models import (
    DesignLintReconciliationReport,
)
from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.mcp_server import create_server
from kicad_tooling.hwrepo.models import (
    ComponentContract,
    ConnectorInventoryReview,
    DesignLintPolicy,
    DesignLintReport,
    InterfacesCatalog,
    NetlistContract,
    ProjectManifest,
)
from tests.design_lint_fixtures.connector_coverage import (
    connector_supply_role_catalog,
    connector_supply_role_netlist,
    connector_supply_role_reviews,
)
from tests.electrical_parity_support import contract_netlist_xml
from tests.mcp_parity_support import parity_design_lint_policy, semantic_design_lint_report
from tests.synthetic_design_lint_project import (
    install_synthetic_netlist,
    run_design_lint_cli,
    synthetic_design_lint_project,
)

RULE_ID = "connector.mapped_supply_domains_share_net"
IMPLEMENTATION_OWNER = (
    "kicad_tooling/hwrepo/design_lint_connectors_supply_domains.py#"
    "mapped_supply_domains_shared_net_candidates"
)

pytestmark = [
    pytest.mark.parity_lint,
    pytest.mark.slow,
    pytest.mark.design_lint,
    pytest.mark.connector_lint,
    pytest.mark.evidence_lint,
]


def _observed_netlist(*, common_supply: bool) -> NetlistContract:
    """Add component records needed to serialize the shared synthetic netlist."""
    base = connector_supply_role_netlist(common_supply=common_supply)
    return base.model_copy(
        update={
            "components": {
                "J1": ComponentContract(
                    value="Synthetic USB power connector",
                    footprint="Synthetic:UsbPort",
                ),
                "J2": ComponentContract(
                    value="Synthetic serial power connector",
                    footprint="Synthetic:SerialPort",
                ),
            }
        }
    )


def _install_connector_reviews(root: Path, *, serial_voltage_domain: str) -> Path:
    """Write exact source-matched interface records for the two fixture pins."""
    interfaces = connector_supply_role_catalog(serial_voltage_domain=serial_voltage_domain)
    catalog_path = root / "catalog/interfaces.json"
    write_model(
        catalog_path,
        InterfacesCatalog(
            schema_version="1",
            interfaces=tuple(sorted(interfaces.values(), key=lambda item: item.id)),
        ),
    )

    manifest_path = root / "projects/controller/project.json"
    manifest = read_model(manifest_path, ProjectManifest)
    write_model(
        manifest_path,
        manifest.model_copy(
            update={
                "interfaces": tuple(sorted(interfaces)),
                "connector_reviews": connector_supply_role_reviews(),
                "connector_inventory_review": ConnectorInventoryReview(
                    basis="Synthetic review accounts for both connector supply contacts"
                ),
            }
        ),
    )
    return catalog_path


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
@pytest.mark.parametrize(
    ("common_supply", "serial_voltage_domain", "expected_domains"),
    (
        pytest.param(
            True,
            "serial-vbus",
            ("external-5v", "serial-vbus"),
            id="distinct-domains-share-net-review",
        ),
        pytest.param(
            True,
            "external-5v",
            None,
            id="same-domain-shared-net-control",
        ),
        pytest.param(
            False,
            "serial-vbus",
            None,
            id="distinct-domains-separate-nets-control",
        ),
    ),
)
def test_mapped_supply_domain_rule_matches_between_cli_and_mcp(
    tmp_path: Path,
    common_supply: bool,
    serial_voltage_domain: str,
    expected_domains: tuple[str, ...] | None,
) -> None:
    """Keep catalog ownership, review policy, evidence, and both surfaces aligned."""
    root, native = synthetic_design_lint_project(
        tmp_path,
        parity_design_lint_policy(DesignLintPolicy()),
    )
    interface_catalog = _install_connector_reviews(
        root,
        serial_voltage_domain=serial_voltage_domain,
    )
    observed = _observed_netlist(common_supply=common_supply)
    install_synthetic_netlist(native, contract_netlist_xml(observed))

    process = run_design_lint_cli(tmp_path, root, native)
    assert process.returncode in {0, 1}, process.stderr + process.stdout
    cli_report = DesignLintReport.model_validate_json(process.stdout)

    async def inspect_mcp() -> DesignLintReport:
        async with Client(create_server(root), mode="legacy") as client:
            result = await client.call_tool(
                "inspect_design_lint",
                {
                    "project_id": "controller",
                    "native_summary": native.relative_to(root).as_posix(),
                },
            )
            assert not result.is_error, result.content
            assert result.structured_content is not None
            return DesignLintReport.model_validate_json(json.dumps(result.structured_content))

    mcp_report = asyncio.run(inspect_mcp())

    assert semantic_design_lint_report(cli_report) == semantic_design_lint_report(mcp_report)
    assert process.returncode == (0 if cli_report.status == "PASS" else 1)
    assert cli_report.rule_catalog is not None
    catalog_rule = next(rule for rule in cli_report.rule_catalog.rules if rule.rule_id == RULE_ID)
    assert catalog_rule.implementation_owner == IMPLEMENTATION_OWNER

    coverage = cli_report.connector_coverage
    assert coverage is not None
    assert coverage.status == "COMPLETE"
    assert coverage.interface_catalog_sha256 == digest(interface_catalog)
    findings = tuple(item for item in cli_report.findings if item.rule_id == RULE_ID)
    if expected_domains is None:
        assert findings == ()
        return

    (finding,) = findings
    assert finding.mode == "review"
    assert finding.disposition == "OPEN"
    assert finding.evidence["native_shared_net"] == ("SHARED_SUPPLY",)
    assert finding.evidence["reviewed_voltage_domains"] == expected_domains
    assert finding.evidence["mapped_supply_assignments"] == (
        "J1.2=SHARED_SUPPLY; voltage_domain=external-5v",
        "J2.5=SHARED_SUPPLY; voltage_domain=serial-vbus",
    )
    assert finding.evidence["interface_catalog_sha256"] == (digest(interface_catalog),)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_mapped_supply_domain_finding_transition_matches_between_cli_and_mcp(
    tmp_path: Path,
) -> None:
    """Retain the exact rule's quiet-to-review transition on both surfaces."""
    root, native = synthetic_design_lint_project(
        tmp_path,
        parity_design_lint_policy(DesignLintPolicy()),
    )
    _install_connector_reviews(root, serial_voltage_domain="external-5v")
    install_synthetic_netlist(native, contract_netlist_xml(_observed_netlist(common_supply=True)))

    baseline_process = run_design_lint_cli(tmp_path, root, native)
    assert baseline_process.returncode in {0, 1}, baseline_process.stderr + baseline_process.stdout
    baseline = DesignLintReport.model_validate_json(baseline_process.stdout)
    assert not any(item.rule_id == RULE_ID for item in baseline.findings)
    baseline_path = root / "lint-baseline.json"
    baseline_path.write_text(baseline.model_dump_json(), encoding="utf-8")

    _install_connector_reviews(root, serial_voltage_domain="serial-vbus")
    cli_process = run_design_lint_cli(
        tmp_path,
        root,
        native,
        baseline_report=Path(baseline_path.name),
    )
    assert cli_process.returncode == 1, cli_process.stderr + cli_process.stdout
    cli_report = DesignLintReconciliationReport.model_validate_json(cli_process.stdout)

    async def reconcile_mcp() -> DesignLintReconciliationReport:
        async with Client(create_server(root), mode="legacy") as client:
            result = await client.call_tool(
                "reconcile_design_lint",
                {
                    "project_id": "controller",
                    "native_summary": native.relative_to(root).as_posix(),
                    "baseline_report_json": baseline.model_dump_json(),
                },
            )
        assert not result.is_error, result.content
        assert result.structured_content is not None
        return DesignLintReconciliationReport.model_validate_json(
            json.dumps(result.structured_content)
        )

    mcp_report = asyncio.run(reconcile_mcp())
    assert cli_report == mcp_report
    assert cli_report.status == "REVIEW"
    assert cli_report.baseline_status == baseline.status
    assert cli_report.current_status == "REVIEW"
    (transition,) = tuple(
        item
        for item in cli_report.transitions
        if item.current is not None and item.current.rule_id == RULE_ID
    )
    assert transition.kind == "NEW"
    assert transition.baseline is None
    assert transition.current is not None
    assert transition.current.mode == "review"
    assert transition.current.disposition == "OPEN"
    assert transition.current.evidence["native_shared_net"] == ("SHARED_SUPPLY",)
