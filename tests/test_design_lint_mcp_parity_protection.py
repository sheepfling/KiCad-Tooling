"""Design-lint CLI/MCP parity cases: design lint mcp parity protection."""

from __future__ import annotations

import pytest

pytestmark = [
    pytest.mark.parity_lint,
    pytest.mark.slow,
    pytest.mark.template_checkout,
    pytest.mark.design_lint,
]

from mcp import Client

from kicad_tooling.hwrepo.contracts import (
    read_model,
    write_model,
)
from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.mcp_server import create_server
from kicad_tooling.hwrepo.models import (
    ComponentIdentity,
    ConnectorInterfaceReview,
    ConnectorInventoryReview,
    DesignLintPolicy,
    DesignLintReport,
    ExternalProtectionInterfaceRequirement,
    InterfacePin,
    InterfaceRecord,
    InterfacesCatalog,
    ProjectManifest,
    ProjectTestContract,
    ValidationSummary,
)
from tests.external_protection_support import protection_map as synthetic_protection_map
from tests.mcp_parity_support import (
    McpParityHarness,
    run_mcp_parity,
)


class _DesignLintMcpParityProtectionCases(McpParityHarness):
    async def _case_test_external_protection_map_parity(self) -> None:
        """Compare exact external-protection coverage through CLI and MCP."""
        native = self.native_evidence()
        netlist = native.parent / "netlist.xml"
        netlist.write_text(
            "<export><components>"
            '<comp ref="J1"><value>Synthetic USB connector</value>'
            "<footprint>Synthetic:USB-C</footprint>"
            '<libsource lib="Synthetic" part="UsbPort"/></comp>'
            '<comp ref="D1"><value>Synthetic TVS</value>'
            "<footprint>Synthetic:SOD323</footprint>"
            '<libsource lib="Synthetic" part="TVS"/></comp>'
            "</components><libparts>"
            '<libpart lib="Synthetic" part="UsbPort"><pins>'
            '<pin num="1" name="D+" type="passive"/>'
            '<pin num="2" name="D-" type="passive"/>'
            "</pins></libpart>"
            '<libpart lib="Synthetic" part="TVS"><pins>'
            '<pin num="1" name="IO" type="passive"/>'
            '<pin num="2" name="GND" type="passive"/>'
            "</pins></libpart></libparts><nets>"
            '<net name="USB_DP"><node ref="J1" pin="1"/>'
            '<node ref="D1" pin="1"/></net>'
            '<net name="USB_DM"><node ref="J1" pin="2"/></net>'
            '<net name="GND"><node ref="D1" pin="2"/></net>'
            "</nets></export>",
            encoding="utf-8",
        )
        summary = read_model(native, ValidationSummary)
        write_model(
            native,
            summary.model_copy(
                update={
                    "artifacts_sha256": {
                        **summary.artifacts_sha256,
                        "netlist.xml": digest(netlist),
                    }
                }
            ),
        )

        manifest_path = self.island / "project.json"
        manifest = read_model(manifest_path, ProjectManifest)
        write_model(
            manifest_path,
            manifest.model_copy(
                update={
                    "component_identity": ComponentIdentity(required=False, part_ids=()),
                    "interfaces": ("usb-data",),
                    "connector_reviews": (
                        ConnectorInterfaceReview(
                            reference="J1",
                            disposition="interface",
                            interface_id="usb-data",
                            basis="Synthetic reviewed USB connector pinout",
                            pin_map={"1": "1", "2": "2"},
                        ),
                    ),
                    "connector_inventory_review": ConnectorInventoryReview(
                        basis="Synthetic review covered all connector candidates in the schematic"
                    ),
                }
            ),
        )
        write_model(
            self.root / "catalog/interfaces.json",
            InterfacesCatalog(
                schema_version="1",
                interfaces=(
                    InterfaceRecord(
                        id="usb-data",
                        revision="synthetic-1",
                        pins=(
                            InterfacePin(
                                number="1",
                                signal="USB_D+",
                                direction="bidirectional",
                                voltage_domain="synthetic-low-voltage",
                                mating="synthetic host",
                                orientation="not applicable",
                                mechanical_clearance="not applicable",
                            ),
                            InterfacePin(
                                number="2",
                                signal="USB_D-",
                                direction="bidirectional",
                                voltage_domain="synthetic-low-voltage",
                                mating="synthetic host",
                                orientation="not applicable",
                                mechanical_clearance="not applicable",
                            ),
                        ),
                    ),
                ),
            ),
        )
        contract_path = self.island / "tests/contract.json"
        contract = read_model(contract_path, ProjectTestContract)
        protection = synthetic_protection_map()
        protection = protection.model_copy(
            update={
                "interfaces": (
                    *protection.interfaces,
                    ExternalProtectionInterfaceRequirement(
                        connector_reference="J1",
                        expected_connector_symbol="Synthetic:UsbPort",
                        expected_connector_footprint="Synthetic:USB-C",
                        connector_pin="J1.2",
                        signal_net="USB_DM",
                        disposition="not_required",
                        basis="Synthetic reviewed data-line protection decision",
                    ),
                )
            }
        )
        write_model(
            contract_path,
            contract.model_copy(
                update={"design_lint": DesignLintPolicy(external_protection_map=protection)}
            ),
        )

        async with Client(create_server(self.root), mode="legacy") as client:

            async def compare(expected_status: str, exit_code: int) -> DesignLintReport:
                cli = await self.cli(
                    "kicad_tooling.design_lint",
                    DesignLintReport,
                    "--project",
                    "controller",
                    "--native-summary",
                    str(native),
                    expected_exit=exit_code,
                )
                mcp = await self.call(
                    client,
                    "inspect_design_lint",
                    DesignLintReport,
                    {
                        "project_id": "controller",
                        "native_summary": native.relative_to(self.root).as_posix(),
                    },
                )
                self.assertEqual(cli, mcp)
                self.assertEqual(mcp.status, expected_status, mcp.issues)
                return mcp

            matched = await compare("REVIEW", 1)
            assert matched.external_protection_coverage is not None
            self.assertEqual(matched.external_protection_coverage.status, "COMPLETE")
            self.assertEqual(
                matched.external_protection_coverage.entries[0].status,
                "PROTECTED",
            )
            self.assertEqual(matched.external_protection_coverage.netlist_sha256, digest(netlist))
            assert matched.connector_coverage is not None
            self.assertEqual(
                matched.connector_coverage.interface_catalog_path,
                "catalog/interfaces.json",
            )
            pair_review = next(
                finding
                for finding in matched.findings
                if finding.rule_id == "signal.named_pair_without_reviewed_requirement"
            )
            self.assertEqual(pair_review.subject, "USB_DP / USB_DM")

            netlist.write_text(
                netlist.read_text(encoding="utf-8").replace(
                    '<net name="USB_DP"><node ref="J1" pin="1"/>'
                    '<node ref="D1" pin="1"/></net>'
                    '<net name="USB_DM"><node ref="J1" pin="2"/></net>',
                    '<net name="USB_DP"><node ref="J1" pin="1"/></net>'
                    '<net name="USB_DM"><node ref="J1" pin="2"/>'
                    '<node ref="D1" pin="1"/></net>',
                ),
                encoding="utf-8",
            )
            summary = read_model(native, ValidationSummary)
            write_model(
                native,
                summary.model_copy(
                    update={
                        "artifacts_sha256": {
                            **summary.artifacts_sha256,
                            "netlist.xml": digest(netlist),
                        }
                    }
                ),
            )
            mismatched = await compare("REVIEW", 1)
            assert mismatched.external_protection_coverage is not None
            self.assertEqual(
                mismatched.external_protection_coverage.entries[0].status,
                "INCOMPLETE",
            )
            self.assertTrue(
                any(
                    finding.rule_id == "protection.mapped_device_mismatch"
                    for finding in mismatched.findings
                )
            )


def test_external_protection_map_parity() -> None:
    run_mcp_parity(_DesignLintMcpParityProtectionCases, "_case_test_external_protection_map_parity")
