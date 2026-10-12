"""Component peer power assignment parity across CLI and MCP."""

from __future__ import annotations

from pathlib import Path

import pytest

from kicad_tooling.hwrepo.models import (
    DesignLintPolicy,
    DesignLintReport,
    DesignLintRuleOverride,
)
from tests.component_peer_power_assignment_support import (
    RULE_ID,
    peer_pin_netlist_xml,
    peer_power_netlist,
)
from tests.component_peer_power_input_support import (
    NAMED_PEER_POWER_INPUT_DIVERGENCE_RULE_ID,
    NAMED_PEER_POWER_INPUT_OPEN_RULE_ID,
    named_peer_power_input_netlist,
)
from tests.mcp_parity_support import semantic_design_lint_report

pytestmark = [
    pytest.mark.component_lint,
    pytest.mark.design_lint,
    pytest.mark.parity_lint,
    pytest.mark.power_lint,
]


def _synthetic_parity_project(tmp_path: Path) -> tuple[Path, Path]:
    from tests.synthetic_design_lint_project import synthetic_design_lint_project

    return synthetic_design_lint_project(
        tmp_path,
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id="pcb.schematic_component_inventory",
                    mode="off",
                    reason="Synthetic parity case has no native PCB snapshot",
                ),
                DesignLintRuleOverride(
                    rule_id="pcb.schematic_pcb_dnp_mismatch",
                    mode="off",
                    reason="Synthetic parity case has no native PCB snapshot",
                ),
                DesignLintRuleOverride(
                    rule_id="pcb.schematic_pcb_value_mismatch",
                    mode="off",
                    reason="Synthetic parity case has no native PCB snapshot",
                ),
                DesignLintRuleOverride(
                    rule_id="pcb.schematic_pcb_pad_net_mismatch",
                    mode="off",
                    reason="Synthetic parity case has no native PCB snapshot",
                ),
            )
        ),
    )


def _run_cli_and_mcp(tmp_path: Path, root: Path, summary_path: Path, observed) -> DesignLintReport:
    import asyncio
    import json

    from mcp import Client

    from kicad_tooling.hwrepo.contracts import read_model, write_model
    from kicad_tooling.hwrepo.evidence import digest
    from kicad_tooling.hwrepo.mcp_server import create_server
    from kicad_tooling.hwrepo.models import ValidationSummary
    from tests.synthetic_design_lint_project import run_design_lint_cli

    netlist_path = summary_path.parent / "netlist.xml"
    netlist_path.write_text(peer_pin_netlist_xml(observed), encoding="utf-8")
    summary = read_model(summary_path, ValidationSummary)
    write_model(
        summary_path,
        summary.model_copy(
            update={
                "artifacts_sha256": {
                    **summary.artifacts_sha256,
                    "netlist.xml": digest(netlist_path),
                }
            }
        ),
    )

    process = run_design_lint_cli(tmp_path, root, summary_path)
    assert process.returncode == 1, process.stderr + process.stdout
    cli_report = DesignLintReport.model_validate_json(process.stdout)

    async def inspect_mcp() -> DesignLintReport:
        async with Client(create_server(root), mode="legacy") as client:
            result = await client.call_tool(
                "inspect_design_lint",
                {
                    "project_id": "controller",
                    "native_summary": summary_path.relative_to(root).as_posix(),
                },
            )
            assert not result.is_error, result.content
            assert result.structured_content is not None
            return DesignLintReport.model_validate_json(json.dumps(result.structured_content))

    mcp_report = asyncio.run(inspect_mcp())
    assert semantic_design_lint_report(cli_report) == semantic_design_lint_report(mcp_report)
    return cli_report


def test_shared_part_id_power_assignment_matches_between_cli_and_mcp(tmp_path: Path) -> None:
    root, summary_path = _synthetic_parity_project(tmp_path)
    part_ids = {"U1": "SYNTHETIC-POWER-001", "U2": "synthetic-power-001"}

    for split_domains, expected_roles in (
        (True, {"ground/return", "supply"}),
        (False, set()),
    ):
        observed = peer_power_netlist(
            part_ids=part_ids,
            supply_nets=("+3V3", "+5V") if split_domains else ("+3V3", "+3V3"),
            return_nets=("GND", "AGND") if split_domains else ("GND", "GND"),
        )
        cli_report = _run_cli_and_mcp(tmp_path, root, summary_path, observed)
        assert cli_report.status == "REVIEW", cli_report.model_dump_json(indent=2)
        findings = [item for item in cli_report.findings if item.rule_id == RULE_ID]
        assert {item.evidence["peer_role"][0] for item in findings} == expected_roles


def test_generic_power_input_peer_assignment_matches_between_cli_and_mcp(
    tmp_path: Path,
) -> None:
    root, summary_path = _synthetic_parity_project(tmp_path)
    symbols = {"U1": "Synthetic:GenericPowerInputPeer", "U2": "Synthetic:GenericPowerInputPeer"}
    pin_functions = {reference: ("1", "2") for reference in symbols}
    pin_types = {reference: ("power_in", "passive") for reference in symbols}
    for supplies, expected, expected_coverage in (
        (("+5V", "+3V3"), True, "EVALUATED"),
        (("+3V3", "+3V3"), False, "EVALUATED"),
        (("+5V", None), False, "NO_COMPLETE_ASSIGNMENTS"),
    ):
        observed = peer_power_netlist(
            symbols=symbols,
            supply_nets=supplies,
            return_nets=("SIGNAL", "SIGNAL"),
            pin_functions=pin_functions,
            pin_types=pin_types,
        )
        report = _run_cli_and_mcp(
            tmp_path,
            root,
            summary_path,
            observed,
        )
        findings = [
            item
            for item in report.findings
            if item.rule_id == "component.peer_power_input_assignment_divergence"
        ]
        assert bool(findings) is expected
        coverage = next(
            item
            for item in report.component_peer_pin_coverage
            if item.rule_id == "component.peer_power_input_assignment_divergence"
        )
        assert coverage.status == expected_coverage
        if supplies[1] is None:
            assert coverage.open_assignment_pin_group_count == 1
        assert report.status == "REVIEW", report.model_dump_json(indent=2)


def test_non_generic_peer_power_input_open_assignment_matches_between_cli_and_mcp(
    tmp_path: Path,
) -> None:
    root, summary_path = _synthetic_parity_project(tmp_path)
    report = _run_cli_and_mcp(
        tmp_path,
        root,
        summary_path,
        named_peer_power_input_netlist(),
    )
    findings = [
        item for item in report.findings if item.rule_id == NAMED_PEER_POWER_INPUT_OPEN_RULE_ID
    ]

    assert report.status == "REVIEW"
    assert len(findings) == 1
    assert findings[0].evidence["open_peer_pins"] == ("U2.1",)
    coverage = next(
        item
        for item in report.component_peer_pin_coverage
        if item.rule_id == NAMED_PEER_POWER_INPUT_OPEN_RULE_ID
    )
    assert coverage.status == "EVALUATED"
    assert coverage.finding_count == 1


def test_named_peer_power_input_divergence_matches_between_cli_and_mcp(
    tmp_path: Path,
) -> None:
    root, summary_path = _synthetic_parity_project(tmp_path)
    for assignments, expected in (
        (("SYNTHETIC_RAIL_A", "SYNTHETIC_RAIL_B"), True),
        (("+3V3", "+3V3"), False),
    ):
        report = _run_cli_and_mcp(
            tmp_path,
            root,
            summary_path,
            named_peer_power_input_netlist(assignments=assignments),
        )
        findings = [
            item
            for item in report.findings
            if item.rule_id == NAMED_PEER_POWER_INPUT_DIVERGENCE_RULE_ID
        ]
        assert bool(findings) is expected
        assert report.status == "REVIEW"
        coverage = next(
            item
            for item in report.component_peer_pin_coverage
            if item.rule_id == NAMED_PEER_POWER_INPUT_DIVERGENCE_RULE_ID
        )
        assert coverage.status == "EVALUATED"
        assert coverage.finding_count == int(expected)
        assert coverage.netlist_sha256 == report.netlist_sha256
