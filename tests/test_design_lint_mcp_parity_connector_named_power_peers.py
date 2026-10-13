"""CLI/MCP parity for named connector power-pin alias review."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Literal

import pytest
from mcp import Client

pytestmark = [
    pytest.mark.parity_lint,
    pytest.mark.slow,
    pytest.mark.design_lint,
    pytest.mark.connector_lint,
    pytest.mark.power_lint,
]

from kicad_tooling.hwrepo.contracts import read_model, write_model
from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.mcp_server import create_server
from kicad_tooling.hwrepo.models import (
    DesignLintPolicy,
    DesignLintReport,
    DesignLintRuleOverride,
    ValidationSummary,
)
from tests.mcp_parity_support import semantic_design_lint_report
from tests.synthetic_design_lint_project import (
    run_design_lint_cli,
    synthetic_design_lint_project,
)

RULE_ID = "connector.peer_power_input_open_assignment"
ALL_OPEN_RULE_ID = "connector.peer_power_input_named_all_open"
OUTPUT_RULE_ID = "connector.peer_power_output_open_assignment"
OUTPUT_ALL_OPEN_RULE_ID = "connector.peer_power_output_named_all_open"
OUTPUT_DIVERGENCE_RULE_ID = "connector.peer_power_output_named_assignment_divergence"


def _netlist_xml(
    *,
    power_mode: Literal["split", "common", "all_open", "divergent"],
    pin_function: str,
    pin_electrical_type: Literal["power_in", "power_out"],
) -> str:
    components = "".join(
        f'<comp ref="J{index}"><value>Synthetic peer</value>'
        "<footprint>Synthetic:2Pin</footprint>"
        '<fields><field name="PART_ID">SYNTHETIC-NAMED-POWER-001</field></fields>'
        f'<libsource lib="Synthetic" part="Port{alias}"/></comp>'
        for index, alias in ((1, "A"), (2, "B"))
    )
    pins = "".join(
        f'<libpart lib="Synthetic" part="Port{alias}"><pins>'
        f'<pin num="1" name="{pin_function}" type="{pin_electrical_type}"/>'
        '<pin num="2" name="Pin_2" type="passive"/>'
        "</pins></libpart>"
        for alias in ("A", "B")
    )
    power_nets = {
        "split": '<net name="SYNTHETIC_BIAS"><node ref="J1" pin="1"/></net>',
        "common": (
            '<net name="SYNTHETIC_BIAS"><node ref="J1" pin="1"/><node ref="J2" pin="1"/></net>'
        ),
        "all_open": "",
        "divergent": (
            '<net name="SYNTHETIC_RAIL_A"><node ref="J1" pin="1"/></net>'
            '<net name="SYNTHETIC_RAIL_B"><node ref="J2" pin="1"/></net>'
        ),
    }[power_mode]
    return (
        f"<export><components>{components}</components><libparts>{pins}</libparts><nets>"
        '<net name="SYNTHETIC_SIGNAL"><node ref="J1" pin="2"/>'
        f'<node ref="J2" pin="2"/></net>{power_nets}'
        "</nets></export>"
    )


def _assert_named_connector_power_peer_parity(
    tmp_path: Path,
    cases: tuple[tuple[Literal["split", "common", "all_open", "divergent"], int, int, int], ...],
    *,
    pin_function: str,
    pin_electrical_type: Literal["power_in", "power_out"],
    rule_id: str,
    all_open_rule_id: str | None,
    divergence_rule_id: str | None,
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
                reason="Synthetic parity fixture omits native PCB snapshots",
            )
            for rule_id in unrelated_rules
        )
    )
    root, native = synthetic_design_lint_project(tmp_path, policy)
    netlist = native.parent / "netlist.xml"
    summary = read_model(native, ValidationSummary)

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

    for (
        power_mode,
        expected_mixed_count,
        expected_all_open_count,
        expected_divergence_count,
    ) in cases:
        netlist.write_text(
            _netlist_xml(
                power_mode=power_mode,
                pin_function=pin_function,
                pin_electrical_type=pin_electrical_type,
            ),
            encoding="utf-8",
        )
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
        process = run_design_lint_cli(tmp_path, root, native)
        assert process.returncode in {0, 1}, process.stderr + process.stdout
        cli = DesignLintReport.model_validate_json(process.stdout)
        mcp = asyncio.run(inspect_mcp())

        assert semantic_design_lint_report(cli) == semantic_design_lint_report(mcp)
        assert cli.status in {"PASS", "REVIEW"}
        assert sum(item.rule_id == rule_id for item in cli.findings) == expected_mixed_count
        if all_open_rule_id is not None:
            assert (
                sum(item.rule_id == all_open_rule_id for item in cli.findings)
                == expected_all_open_count
            )
        if divergence_rule_id is not None:
            assert (
                sum(item.rule_id == divergence_rule_id for item in cli.findings)
                == expected_divergence_count
            )


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_named_connector_power_input_open_assignment_matches_between_cli_and_mcp(
    tmp_path: Path,
) -> None:
    _assert_named_connector_power_peer_parity(
        tmp_path,
        (("split", 1, 0, 0), ("common", 0, 0, 0)),
        pin_function="BIAS_IN",
        pin_electrical_type="power_in",
        rule_id=RULE_ID,
        all_open_rule_id=ALL_OPEN_RULE_ID,
        divergence_rule_id=None,
    )


@pytest.mark.design_lint_rule(rule_id=ALL_OPEN_RULE_ID)
def test_named_connector_power_input_all_open_aliases_match_between_cli_and_mcp(
    tmp_path: Path,
) -> None:
    _assert_named_connector_power_peer_parity(
        tmp_path,
        (("all_open", 0, 1, 0), ("common", 0, 0, 0)),
        pin_function="BIAS_IN",
        pin_electrical_type="power_in",
        rule_id=RULE_ID,
        all_open_rule_id=ALL_OPEN_RULE_ID,
        divergence_rule_id=None,
    )


@pytest.mark.design_lint_rule(rule_id=OUTPUT_RULE_ID)
def test_named_connector_power_output_open_assignment_matches_between_cli_and_mcp(
    tmp_path: Path,
) -> None:
    _assert_named_connector_power_peer_parity(
        tmp_path,
        (
            ("split", 1, 0, 0),
            ("common", 0, 0, 0),
            ("divergent", 0, 0, 1),
            ("all_open", 0, 1, 0),
        ),
        pin_function="BIAS_OUT",
        pin_electrical_type="power_out",
        rule_id=OUTPUT_RULE_ID,
        all_open_rule_id=OUTPUT_ALL_OPEN_RULE_ID,
        divergence_rule_id=OUTPUT_DIVERGENCE_RULE_ID,
    )


@pytest.mark.design_lint_rule(rule_id=OUTPUT_ALL_OPEN_RULE_ID)
def test_named_connector_power_output_all_open_aliases_match_between_cli_and_mcp(
    tmp_path: Path,
) -> None:
    _assert_named_connector_power_peer_parity(
        tmp_path,
        (("all_open", 0, 1, 0), ("common", 0, 0, 0)),
        pin_function="BIAS_OUT",
        pin_electrical_type="power_out",
        rule_id=OUTPUT_RULE_ID,
        all_open_rule_id=OUTPUT_ALL_OPEN_RULE_ID,
        divergence_rule_id=OUTPUT_DIVERGENCE_RULE_ID,
    )


@pytest.mark.design_lint_rule(rule_id=OUTPUT_DIVERGENCE_RULE_ID)
def test_named_connector_power_output_assignment_divergence_matches_between_cli_and_mcp(
    tmp_path: Path,
) -> None:
    _assert_named_connector_power_peer_parity(
        tmp_path,
        (("divergent", 0, 0, 1), ("common", 0, 0, 0)),
        pin_function="BIAS_OUT",
        pin_electrical_type="power_out",
        rule_id=OUTPUT_RULE_ID,
        all_open_rule_id=OUTPUT_ALL_OPEN_RULE_ID,
        divergence_rule_id=OUTPUT_DIVERGENCE_RULE_ID,
    )
