"""CLI/MCP parity for unanchored named power-input peer review."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest
from mcp import Client

from kicad_tooling.hwrepo.contracts import read_model, write_model
from kicad_tooling.hwrepo.design_lint_report_models import DesignLintReport
from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.mcp_server import create_server
from kicad_tooling.hwrepo.models import (
    ConnectorInterfaceReview,
    ConnectorInventoryReview,
    DesignLintPolicy,
    DesignLintRuleOverride,
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
    pytest.mark.power_lint,
    pytest.mark.interface_lint,
]

RULE_ID = "connector.footprint_named_power_input_assignment_divergence"
INTERFACE_ID = "synthetic-peer-power-input"
PEER_GROUP = "reviewed-power-input-ports"


def _unanchored_netlist_xml(assignments: tuple[str, str]) -> str:
    """Return a one-pin split or common control with no possible anchor."""
    nets = (
        f'<net name="{assignments[0]}"><node ref="J1" pin="1"/><node ref="J2" pin="1"/></net>'
        if assignments[0] == assignments[1]
        else f'<net name="{assignments[0]}"><node ref="J1" pin="1"/></net>'
        f'<net name="{assignments[1]}"><node ref="J2" pin="1"/></net>'
    )
    return f"""<export><components>
      <comp ref="J1"><value>Synthetic named power-input peer</value><footprint>Synthetic:Package</footprint><libsource lib="Lint" part="NamedPowerInputA"/></comp>
      <comp ref="J2"><value>Synthetic named power-input peer</value><footprint>Synthetic:Package</footprint><libsource lib="Lint" part="NamedPowerInputB"/></comp>
    </components><libparts>
      <libpart lib="Lint" part="NamedPowerInputA"><pins><pin num="1" name="BIAS_IN" type="power_in"/></pins></libpart>
      <libpart lib="Lint" part="NamedPowerInputB"><pins><pin num="1" name="BIAS_IN" type="power_in"/></pins></libpart>
    </libparts><nets>{nets}</nets></export>"""


def _install_source_matched_peer_map(root: Path, project: Path) -> Path:
    interface = InterfaceRecord(
        id=INTERFACE_ID,
        revision="synthetic-1",
        pins=(
            InterfacePin(
                number="1",
                signal="BIAS_IN",
                direction="input",
                voltage_domain="external-5v",
                mating="synthetic fixture",
                orientation="straight",
                mechanical_clearance="synthetic",
            ),
        ),
    )
    catalog_path = root / "catalog/interfaces.json"
    write_model(catalog_path, InterfacesCatalog(schema_version="1", interfaces=(interface,)))
    manifest_path = project / "project.json"
    manifest = read_model(manifest_path, ProjectManifest)
    reviews = tuple(
        ConnectorInterfaceReview(
            reference=reference,
            disposition="interface",
            basis=f"Synthetic current one-pin map for {reference}",
            interface_id=INTERFACE_ID,
            pin_map={"1": "1"},
            peer_assignment_group=PEER_GROUP,
            peer_assignment_basis="Synthetic USB and serial connectors are review peers",
        )
        for reference in ("J1", "J2")
    )
    write_model(
        manifest_path,
        manifest.model_copy(
            update={
                "interfaces": (INTERFACE_ID,),
                "connector_reviews": reviews,
                "connector_inventory_review": ConnectorInventoryReview(
                    basis="Synthetic map covers both connector instances"
                ),
            }
        ),
    )
    return catalog_path


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_unanchored_named_power_input_scope_matches_between_cli_and_mcp(
    tmp_path: Path,
) -> None:
    unrelated_rules = (
        "pcb.schematic_component_inventory",
        "pcb.schematic_pcb_dnp_mismatch",
        "pcb.schematic_pcb_value_mismatch",
        "pcb.schematic_pcb_pad_net_mismatch",
        "protection.unreviewed_interface_pin",
    )
    policy = DesignLintPolicy(
        rules=tuple(
            DesignLintRuleOverride(
                rule_id=rule_id,
                mode="off",
                reason="Synthetic parity fixture isolates unanchored connector review",
            )
            for rule_id in unrelated_rules
        )
    )
    root, native = synthetic_design_lint_project(tmp_path, policy)
    catalog_path = _install_source_matched_peer_map(root, root / "projects/controller")

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

    for assignments, expected_status, expected_count in (
        (("BIAS_INPUT_A", "BIAS_INPUT_B"), "REVIEW", 1),
        (("BIAS_INPUT", "BIAS_INPUT"), "PASS", 0),
    ):
        install_synthetic_netlist(native, _unanchored_netlist_xml(assignments))
        process = run_design_lint_cli(tmp_path, root, native)
        assert process.returncode in {0, 1}, process.stderr + process.stdout
        cli_report = DesignLintReport.model_validate_json(process.stdout)
        mcp_report = asyncio.run(inspect_mcp())

        assert semantic_design_lint_report(cli_report) == semantic_design_lint_report(mcp_report)
        assert cli_report.status == expected_status, (
            tuple((item.rule_id, item.disposition) for item in cli_report.findings),
            cli_report.issues,
        )
        assert cli_report.connector_coverage is not None
        assert cli_report.connector_coverage.status == "COMPLETE"
        assert cli_report.connector_coverage.interface_catalog_sha256 == digest(catalog_path)
        findings = tuple(item for item in cli_report.findings if item.rule_id == RULE_ID)
        assert len(findings) == expected_count
        if findings:
            assert findings[0].evidence["assignments"] == (
                "J1.1=BIAS_INPUT_A",
                "J2.1=BIAS_INPUT_B",
            )
            assert findings[0].evidence["common_anchor_pin_numbers"] == ()
            assert findings[0].evidence["peer_assignment_group"] == (PEER_GROUP,)
