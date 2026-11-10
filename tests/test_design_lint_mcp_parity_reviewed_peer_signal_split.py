"""CLI/MCP parity for reviewed connector peer signal splits."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest
from mcp import Client

from kicad_tooling.hwrepo.contracts import read_model, write_model
from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.mcp_server import create_server
from kicad_tooling.hwrepo.models import (
    ConnectorInterfaceReview,
    ConnectorInventoryReview,
    DesignLintPolicy,
    DesignLintReport,
    InterfacePin,
    InterfaceRecord,
    InterfacesCatalog,
    ProjectManifest,
)
from tests.mcp_parity_support import semantic_design_lint_report
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
]

RULE_ID = "connector.reviewed_peer_signal_assignment_split"
MAPPED_NAMED_RULE_ID = "connector.mapped_named_peer_signal_split_nets"
INTERFACE_ID = "synthetic-peer-serial-signal"


def _install_reviewed_peers(root: Path, island: Path) -> Path:
    interface = InterfaceRecord(
        id=INTERFACE_ID,
        revision="synthetic-1",
        pins=(
            InterfacePin(
                number="1",
                signal="UART_RX",
                role="signal",
                direction="input",
                voltage_domain="logic-3v3",
                mating="UART_TX",
                orientation="straight",
                mechanical_clearance="synthetic",
            ),
        ),
    )
    catalog_path = root / "catalog/interfaces.json"
    write_model(catalog_path, InterfacesCatalog(schema_version="1", interfaces=(interface,)))
    manifest_path = island / "project.json"
    manifest = read_model(manifest_path, ProjectManifest)
    reviews = tuple(
        ConnectorInterfaceReview(
            reference=reference,
            disposition="interface",
            basis=f"Synthetic reviewed connector pinout for {reference}",
            interface_id=INTERFACE_ID,
            pin_map={"1": pin_number},
            peer_assignment_group="serial-peer-ports",
            peer_assignment_basis="Both generic contacts expose the reviewed UART RX signal",
        )
        for reference, pin_number in (("J1", "2"), ("J2", "7"))
    )
    write_model(
        manifest_path,
        manifest.model_copy(
            update={
                "interfaces": (INTERFACE_ID,),
                "connector_reviews": reviews,
                "connector_inventory_review": ConnectorInventoryReview(
                    basis="Synthetic review covered every connector in this fixture"
                ),
            }
        ),
    )
    assert digest(catalog_path)
    return catalog_path


def _fault_netlist(functions: tuple[str, str] = ("2", "7")) -> str:
    return f"""<export><components>
      <comp ref="J1"><value>Synthetic USB port</value><footprint>Synthetic:USB</footprint><libsource lib="Lint" part="UsbPort"/></comp>
      <comp ref="J2"><value>Synthetic serial port</value><footprint>Synthetic:DB9</footprint><libsource lib="Lint" part="SerialPort"/></comp>
    </components><libparts>
      <libpart lib="Lint" part="UsbPort"><pins><pin num="2" name="{functions[0]}" type="passive"/></pins></libpart>
      <libpart lib="Lint" part="SerialPort"><pins><pin num="7" name="{functions[1]}" type="passive"/></pins></libpart>
    </libparts><nets>
      <net name="USB_RX_NET"><node ref="J1" pin="2"/></net>
      <net name="SERIAL_RX_NET"><node ref="J2" pin="7"/></net>
    </nets></export>"""


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_reviewed_peer_signal_split_matches_between_cli_and_mcp(tmp_path: Path) -> None:
    root, native = synthetic_design_lint_project(tmp_path, DesignLintPolicy())
    catalog_path = _install_reviewed_peers(root, root / "projects/controller")
    install_synthetic_netlist(native, _fault_netlist())

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

    cli = run_design_lint_cli(tmp_path, root, native)
    assert cli.returncode in {0, 1}, cli.stderr + cli.stdout
    cli_report = DesignLintReport.model_validate_json(cli.stdout)
    mcp_report = asyncio.run(inspect_mcp())

    assert semantic_design_lint_report(cli_report) == semantic_design_lint_report(mcp_report)
    assert cli_report.connector_coverage is not None
    assert cli_report.connector_coverage.status == "COMPLETE"
    assert cli_report.connector_coverage.interface_catalog_sha256 == digest(catalog_path)
    findings = tuple(item for item in cli_report.findings if item.rule_id == RULE_ID)
    assert len(findings) == 1
    assert findings[0].evidence["component_pin"] == ("J1.2", "J2.7")
    assert findings[0].evidence["assigned_nets"] == ("SERIAL_RX_NET", "USB_RX_NET")


@pytest.mark.design_lint_rule(rule_id=MAPPED_NAMED_RULE_ID)
def test_mapped_named_peer_signal_split_matches_between_cli_and_mcp(tmp_path: Path) -> None:
    root, native = synthetic_design_lint_project(tmp_path, DesignLintPolicy())
    catalog_path = _install_reviewed_peers(root, root / "projects/controller")
    install_synthetic_netlist(native, _fault_netlist(("CONTACT_A", "CONTACT_B")))

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

    cli = run_design_lint_cli(tmp_path, root, native)
    assert cli.returncode in {0, 1}, cli.stderr + cli.stdout
    cli_report = DesignLintReport.model_validate_json(cli.stdout)
    mcp_report = asyncio.run(inspect_mcp())

    assert semantic_design_lint_report(cli_report) == semantic_design_lint_report(mcp_report)
    assert cli_report.connector_coverage is not None
    assert cli_report.connector_coverage.status == "COMPLETE"
    assert cli_report.connector_coverage.interface_catalog_sha256 == digest(catalog_path)
    findings = tuple(item for item in cli_report.findings if item.rule_id == MAPPED_NAMED_RULE_ID)
    assert len(findings) == 1
    assert findings[0].evidence["component_pin"] == ("J1.2", "J2.7")
    assert findings[0].evidence["split_native_nets"] == ("SERIAL_RX_NET", "USB_RX_NET")
