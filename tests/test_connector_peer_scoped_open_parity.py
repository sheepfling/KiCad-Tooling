"""Check source-scoped partial-open peer lint parity across CLI and MCP."""

from __future__ import annotations

from pathlib import Path

import pytest
from mcp import Client

from kicad_tooling.hwrepo.contracts import read_model, repo_path, write_model
from kicad_tooling.hwrepo.discovery import load_config, load_registry
from kicad_tooling.hwrepo.mcp_server import create_server
from kicad_tooling.hwrepo.models import (
    ConnectorInterfaceReview,
    ConnectorInventoryReview,
    InterfacePin,
    InterfaceRecord,
    InterfacesCatalog,
    ProjectManifest,
)
from tests.design_lint_mcp_parity_report_support import DesignLintMcpParityReportHarness
from tests.mcp_parity_support import run_mcp_parity
from tests.pcb_drc_parity_support import install_source_bound_drc_receipt

RULE_ID = "connector.footprint_peer_pin_open_outlier"
PEER_GROUP = "synthetic-peer-connectors"
PEER_BASIS = "Synthetic connector pinouts were reviewed as one peer set"

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.connector_lint,
    pytest.mark.parity_lint,
    pytest.mark.slow,
    pytest.mark.template_checkout,
]


class _ScopedPartialOpenParityCases(DesignLintMcpParityReportHarness):
    async def _case_scoped_partial_open_review_matches_cli_and_mcp(self) -> None:
        native = self.native_evidence()
        config = load_config(self.root, self.island / "project.json")
        install_source_bound_drc_receipt(
            self.root,
            native,
            board_path=repo_path(self.root, config.project).with_suffix(".kicad_pcb"),
            kicad_version=config.kicad_version,
        )
        fixture = (
            Path(__file__).parent
            / "fixtures/design_lint/connector-peer-unanchored-scope/partial-open-netlist.xml"
        )
        netlist = native.parent / "netlist.xml"
        netlist.write_text(fixture.read_text(encoding="utf-8"), encoding="utf-8")
        self.rehash_native_netlist(native)

        interface_id = "synthetic-scoped-partial-open"
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
                            basis=f"Synthetic current pin map for {reference}",
                            interface_id=interface_id,
                            pin_map={"1": "1", "2": "2"},
                            peer_assignment_group=PEER_GROUP,
                            peer_assignment_basis=PEER_BASIS,
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

        open_findings = [item for item in report.findings if item.rule_id == RULE_ID]
        self.assertEqual(len(open_findings), 1)
        self.assertEqual(open_findings[0].evidence["open_pins"], ("J2.1",))
        self.assertEqual(open_findings[0].evidence["peer_assignment_group"], (PEER_GROUP,))


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_scoped_partial_open_review_cli_mcp_parity() -> None:
    run_mcp_parity(
        _ScopedPartialOpenParityCases,
        "_case_scoped_partial_open_review_matches_cli_and_mcp",
    )
