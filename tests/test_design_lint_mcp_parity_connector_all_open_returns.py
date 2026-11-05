"""CLI/MCP parity for source-mapped returns open across mixed connector peers."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest
from mcp import Client

from kicad_tooling.hwrepo.contracts import read_model, write_model
from kicad_tooling.hwrepo.mcp_server import create_server
from kicad_tooling.hwrepo.models import (
    ComponentContract,
    ConnectorInterfaceReview,
    ConnectorInventoryReview,
    DesignLintPolicy,
    DesignLintReport,
    InterfacesCatalog,
    ProjectManifest,
)
from tests.design_lint_fixtures.connector_coverage import connector_return_role_catalog
from tests.design_lint_fixtures.connector_mixed_return import two_usb_one_serial_return_case
from tests.electrical_parity_support import contract_netlist_xml
from tests.mcp_parity_support import parity_design_lint_policy, semantic_design_lint_report
from tests.synthetic_design_lint_project import (
    install_synthetic_netlist,
    run_design_lint_cli,
    synthetic_design_lint_project,
)

pytestmark = [
    pytest.mark.parity_lint,
    pytest.mark.slow,
    pytest.mark.design_lint,
    pytest.mark.connector_lint,
    pytest.mark.interface_lint,
    pytest.mark.return_path_lint,
]

RULE_ID = "connector.repeated_pin_function"
RETURN_GROUP = "external-returns"


def _install_reviews(root: Path) -> None:
    interfaces = connector_return_role_catalog()
    write_model(
        root / "catalog/interfaces.json",
        InterfacesCatalog(
            schema_version="1",
            interfaces=tuple(sorted(interfaces.values(), key=lambda item: item.id)),
        ),
    )
    reviews = tuple(
        ConnectorInterfaceReview(
            reference=reference,
            disposition="interface",
            basis=f"Synthetic reviewed pinout for {interface_id}",
            interface_id=interface_id,
            pin_map=pin_map,
            peer_assignment_group=peer_group,
            peer_assignment_basis=f"Reviewed {reference} as {peer_group}",
            return_comparison_group=RETURN_GROUP,
            return_comparison_basis=f"Reviewed {reference} in {RETURN_GROUP}",
        )
        for reference, interface_id, pin_map, peer_group in (
            ("J1", "usb-interface", {"1": "1", "2": "2", "3": "3"}, "usb-port-1"),
            ("J2", "serial-interface", {"1": "1", "2": "2", "3": "3", "4": "4"}, "serial-port"),
            ("J3", "usb-interface", {"1": "1", "2": "2", "3": "3"}, "usb-port-2"),
        )
    )
    manifest_path = root / "projects/controller/project.json"
    manifest = read_model(manifest_path, ProjectManifest)
    write_model(
        manifest_path,
        manifest.model_copy(
            update={
                "interfaces": tuple(sorted(interfaces)),
                "connector_reviews": reviews,
                "connector_inventory_review": ConnectorInventoryReview(
                    basis="Synthetic review covers all three connector references"
                ),
            }
        ),
    )


async def _inspect_mcp(root: Path, native: Path) -> DesignLintReport:
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


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
@pytest.mark.parametrize(
    "all_returns_open", (True, False), ids=("all-open-review", "common-control")
)
def test_mixed_usb_serial_return_review_matches_between_cli_and_mcp(
    tmp_path: Path, all_returns_open: bool
) -> None:
    root, native = synthetic_design_lint_project(
        tmp_path,
        parity_design_lint_policy(DesignLintPolicy()),
    )
    _install_reviews(root)
    observed, _coverage = two_usb_one_serial_return_case(
        common_return=not all_returns_open,
        all_returns_open=all_returns_open,
        return_comparison_groups={reference: RETURN_GROUP for reference in ("J1", "J2", "J3")},
    )
    observed = observed.model_copy(
        update={
            "components": {
                reference: ComponentContract(
                    value=f"Synthetic {reference}", footprint="Synthetic:Port"
                )
                for reference in ("J1", "J2", "J3")
            }
        }
    )
    install_synthetic_netlist(native, contract_netlist_xml(observed))

    process = run_design_lint_cli(tmp_path, root, native)
    assert process.returncode in {0, 1}, process.stderr + process.stdout
    cli = DesignLintReport.model_validate_json(process.stdout)
    mcp = asyncio.run(_inspect_mcp(root, native))

    assert semantic_design_lint_report(cli) == semantic_design_lint_report(mcp)
    assert cli.connector_coverage is not None
    assert cli.connector_coverage.status == "COMPLETE"
    findings = tuple(item for item in cli.findings if item.rule_id == RULE_ID)
    if all_returns_open:
        assert len(findings) == 1
        finding = findings[0]
        assert finding.mode == "review"
        assert {pin: finding.evidence[pin] for pin in ("J1.3", "J2.3", "J3.3")} == {
            "J1.3": (),
            "J2.3": (),
            "J3.3": (),
        }
        assert finding.evidence["return_comparison_group"] == (RETURN_GROUP,)
        assert len(finding.evidence["return_comparison_basis"]) == 3
    else:
        assert findings == ()
