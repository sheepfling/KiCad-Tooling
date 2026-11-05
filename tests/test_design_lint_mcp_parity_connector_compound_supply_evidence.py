"""CLI/MCP parity for evidence explaining compound connector-supply matches."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest
from mcp import Client

from kicad_tooling.hwrepo.mcp_server import create_server
from kicad_tooling.hwrepo.models import (
    DesignLintPolicy,
    DesignLintReport,
    DesignLintRuleOverride,
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
    pytest.mark.evidence_lint,
]

RULE_ID = "connector.repeated_pin_function"


def _compound_supply_netlist(usb_function: str, serial_function: str) -> str:
    return (
        "<export><components>"
        '<comp ref="J1"><value>USB port</value><footprint>Synthetic:Port</footprint>'
        '<libsource lib="Synthetic" part="UsbPort"/></comp>'
        '<comp ref="J2"><value>Serial port</value><footprint>Synthetic:Port</footprint>'
        '<libsource lib="Synthetic" part="SerialPort"/></comp>'
        "</components><libparts>"
        '<libpart lib="Synthetic" part="UsbPort"><pins>'
        f'<pin num="1" name="{usb_function}" type="passive"/>'
        '<pin num="2" name="GND" type="passive"/>'
        "</pins></libpart>"
        '<libpart lib="Synthetic" part="SerialPort"><pins>'
        f'<pin num="1" name="{serial_function}" type="passive"/>'
        '<pin num="2" name="GND" type="passive"/>'
        "</pins></libpart></libparts><nets>"
        '<net name="USB_SUPPLY"><node ref="J1" pin="1"/></net>'
        '<net name="SERIAL_SUPPLY"><node ref="J2" pin="1"/></net>'
        '<net name="GND"><node ref="J1" pin="2"/><node ref="J2" pin="2"/></net>'
        "</nets></export>"
    )


def _policy() -> DesignLintPolicy:
    return DesignLintPolicy(
        rules=tuple(
            DesignLintRuleOverride(
                rule_id=rule_id,
                mode="off",
                reason="Synthetic CLI/MCP parity fixture isolates connector supply evidence",
            )
            for rule_id in (
                "pcb.schematic_component_inventory",
                "pcb.schematic_pcb_dnp_mismatch",
                "pcb.schematic_pcb_value_mismatch",
                "pcb.schematic_pcb_pad_net_mismatch",
                "protection.unreviewed_interface_pin",
            )
        )
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
    ("usb_function", "serial_function"),
    (("USB_VBUS", "SERIAL_VBUS"), ("USB_VBUS", "VBUS")),
    ids=("compound-peers", "compound-and-exact-alias"),
)
def test_compound_supply_category_evidence_matches_between_cli_and_mcp(
    tmp_path: Path,
    usb_function: str,
    serial_function: str,
) -> None:
    case = tmp_path / f"{usb_function.lower()}-{serial_function.lower()}"
    root, native = synthetic_design_lint_project(case, _policy())
    install_synthetic_netlist(native, _compound_supply_netlist(usb_function, serial_function))

    cli_process = run_design_lint_cli(tmp_path, root, native)
    assert cli_process.returncode in {0, 1}, cli_process.stderr + cli_process.stdout
    cli = DesignLintReport.model_validate_json(cli_process.stdout)
    mcp = asyncio.run(_inspect_mcp(root, native))

    assert semantic_design_lint_report(cli) == semantic_design_lint_report(mcp)
    finding = next(item for item in cli.findings if item.rule_id == RULE_ID)
    assert finding.evidence["normalized_supply_category"] == ("vbus",)
    assert finding.evidence["normalized_supply_category_sources"] == (
        f"J1.1: native symbol function={usb_function}; normalized supply category=vbus",
        f"J2.1: native symbol function={serial_function}; normalized supply category=vbus",
    )
