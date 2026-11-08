"""CLI/MCP parity for all-open generic connector peer-pin review."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest
from mcp import Client

pytestmark = [
    pytest.mark.parity_lint,
    pytest.mark.slow,
    pytest.mark.design_lint,
    pytest.mark.connector_lint,
    pytest.mark.interface_lint,
]

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
    ValidationSummary,
)
from tests.mcp_parity_support import semantic_design_lint_report
from tests.synthetic_design_lint_project import (
    run_design_lint_cli,
    synthetic_design_lint_project,
)

RULE_ID = "connector.generic_peer_pin_all_open"
FOOTPRINT_ALL_OPEN_RULE_ID = "connector.footprint_peer_pin_all_open"


def _netlist_xml(
    *,
    fault: bool,
    common_anchor: bool = True,
    part_id_aliases: bool = False,
    footprint_aliases: bool = False,
    split_anchor: bool = False,
    signal_pin_type: str = "passive",
) -> str:
    common_power_nodes = (
        "".join(f'<node ref="J{reference}" pin="1"/>' for reference in (1, 2))
        if common_anchor
        else ""
    )
    power_nets = (
        f'<net name="+5V">{common_power_nodes}</net>'
        if common_anchor
        else (
            '<net name="PORT_A"><node ref="J1" pin="1"/></net>'
            '<net name="PORT_B"><node ref="J2" pin="1"/></net>'
            if split_anchor
            else '<net name="+5V"></net>'
        )
    )
    return_nodes = (
        "" if fault else '<net name="GND"><node ref="J1" pin="2"/><node ref="J2" pin="2"/></net>'
    )
    symbol_names = (
        ("GenericPassivePortLeft", "GenericPassivePortRight")
        if part_id_aliases or footprint_aliases
        else ("GenericPassivePort", "GenericPassivePort")
    )
    components = "".join(
        f'<comp ref="J{reference}"><value>Synthetic peer port</value>'
        "<footprint>Synthetic:Port</footprint>"
        + (
            '<fields><field name="PART_ID">SYNTHETIC-PASSIVE-PORT-001</field></fields>'
            if part_id_aliases
            else ""
        )
        + f'<libsource lib="Synthetic" part="{symbol_name}"/></comp>'
        for reference, symbol_name in zip((1, 2), symbol_names, strict=True)
    )
    libparts = "".join(
        f'<libpart lib="Synthetic" part="{symbol_name}"><pins>'
        '<pin num="1" name="Pin_1" type="passive"/>'
        f'<pin num="2" name="Pin_2" type="{signal_pin_type}"/>'
        "</pins></libpart>"
        for symbol_name in sorted(set(symbol_names))
    )
    return (
        f"<export><components>{components}</components><libparts>{libparts}</libparts><nets>"
        f"{power_nets}{return_nodes}"
        "</nets></export>"
    )


def test_all_open_generic_peer_pin_lint_cli_mcp_parity(tmp_path: Path) -> None:
    policy = DesignLintPolicy(
        rules=(
            DesignLintRuleOverride(
                rule_id="pcb.schematic_component_inventory",
                mode="off",
                reason="Synthetic parity fixture has no native PCB snapshot",
            ),
            DesignLintRuleOverride(
                rule_id="pcb.schematic_pcb_dnp_mismatch",
                mode="off",
                reason="Synthetic parity fixture has no native PCB snapshot",
            ),
            DesignLintRuleOverride(
                rule_id="pcb.schematic_pcb_value_mismatch",
                mode="off",
                reason="Synthetic parity fixture has no native PCB snapshot",
            ),
            DesignLintRuleOverride(
                rule_id="pcb.schematic_pcb_pad_net_mismatch",
                mode="off",
                reason="Synthetic parity fixture has no native PCB pad snapshot",
            ),
            DesignLintRuleOverride(
                rule_id="protection.unreviewed_interface_pin",
                mode="off",
                reason="Synthetic parity fixture isolates generic peer-pin review",
            ),
            DesignLintRuleOverride(
                rule_id=RULE_ID,
                mode="review",
                reason="Synthetic parity fixture explicitly enables the opt-in heuristic",
            ),
        )
    )
    root, native = synthetic_design_lint_project(tmp_path, policy)
    manifest_path = root / "projects/controller/project.json"
    manifest = read_model(manifest_path, ProjectManifest)
    write_model(
        manifest_path,
        manifest.model_copy(
            update={
                "connector_inventory_review": ConnectorInventoryReview(
                    basis="Synthetic parity fixture reviews both generic connector peers"
                ),
                "connector_reviews": tuple(
                    ConnectorInterfaceReview(
                        reference=reference,
                        disposition="not_applicable",
                        basis="Synthetic regression symbol is not a project interface",
                    )
                    for reference in ("J1", "J2")
                ),
            }
        ),
    )
    netlist = native.parent / "netlist.xml"
    summary = read_model(native, ValidationSummary)

    def write_netlist(
        *,
        fault: bool,
        common_anchor: bool = True,
        part_id_aliases: bool = False,
        signal_pin_type: str = "passive",
    ) -> None:
        netlist.write_text(
            _netlist_xml(
                fault=fault,
                common_anchor=common_anchor,
                part_id_aliases=part_id_aliases,
                signal_pin_type=signal_pin_type,
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

    for part_id_aliases, signal_pin_type in (
        (False, "passive"),
        (True, "passive"),
        (False, "input"),
        (True, "input"),
    ):
        for fault, expected_status, expected_count in (
            (True, "REVIEW", 1),
            (False, "PASS", 0),
        ):
            write_netlist(
                fault=fault,
                part_id_aliases=part_id_aliases,
                signal_pin_type=signal_pin_type,
            )
            process = run_design_lint_cli(tmp_path, root, native)
            assert process.returncode in {0, 1}, process.stderr + process.stdout
            cli = DesignLintReport.model_validate_json(process.stdout)
            mcp = asyncio.run(inspect_mcp())

            assert semantic_design_lint_report(cli) == semantic_design_lint_report(mcp)
            assert cli.status == expected_status, (
                cli.issues,
                [
                    (item.rule_id, item.subject, item.mode, item.disposition)
                    for item in cli.findings
                ],
            )
            findings = tuple(item for item in cli.findings if item.rule_id == RULE_ID)
            assert len(findings) == expected_count
            assert cli.connector_peer_pin_coverage is not None
            assert cli.connector_peer_pin_coverage.generic_peer_pin_all_open_finding_count == (
                expected_count
            )
            if part_id_aliases and fault:
                assert findings[0].evidence["peer_identity_basis"] == ("part_id",)
                assert findings[0].evidence["peer_identity"] == ("SYNTHETIC-PASSIVE-PORT-001",)

    peer_interface = InterfaceRecord(
        id="synthetic-peer-port",
        revision="synthetic-1",
        pins=(
            InterfacePin(
                number="1",
                signal="GND",
                role="return",
                direction="passive",
                voltage_domain="signal-return",
                mating="GND",
                orientation="straight",
                mechanical_clearance="synthetic",
            ),
        ),
    )
    write_model(
        root / "catalog/interfaces.json",
        InterfacesCatalog(schema_version="1", interfaces=(peer_interface,)),
    )
    manifest = read_model(manifest_path, ProjectManifest)
    write_model(
        manifest_path,
        manifest.model_copy(
            update={
                "interfaces": (peer_interface.id,),
                "connector_reviews": tuple(
                    ConnectorInterfaceReview(
                        reference=reference,
                        disposition="interface",
                        basis=f"Synthetic reviewed pinout for {reference}",
                        interface_id=peer_interface.id,
                        pin_map={"1": "1"},
                        unlisted_pin_reasons={
                            "2": "Generic passive contact is outside this reviewed interface map"
                        },
                        peer_assignment_group="reviewed-serial-peers",
                        peer_assignment_basis=f"Reviewed {reference} in the same serial peer group",
                    )
                    for reference in ("J1", "J2")
                ),
                "connector_inventory_review": ConnectorInventoryReview(
                    basis="Synthetic parity fixture reviews both generic connector peers"
                ),
            }
        ),
    )
    write_netlist(fault=True, common_anchor=False)
    process = run_design_lint_cli(tmp_path, root, native)
    assert process.returncode in {0, 1}, process.stderr + process.stdout
    cli = DesignLintReport.model_validate_json(process.stdout)
    mcp = asyncio.run(inspect_mcp())
    assert semantic_design_lint_report(cli) == semantic_design_lint_report(mcp)
    findings = tuple(item for item in cli.findings if item.rule_id == RULE_ID)
    assert len(findings) == 1
    assert findings[0].evidence["peer_assignment_group"] == ("reviewed-serial-peers",)
    assert findings[0].evidence["shared_anchor_contacts"] == ()
    assert cli.connector_coverage is not None
    assert cli.connector_coverage.status == "COMPLETE"
    assert {
        entry.reference: entry.unlisted_pin_reasons for entry in cli.connector_coverage.entries
    } == {
        "J1": {"2": "Generic passive contact is outside this reviewed interface map"},
        "J2": {"2": "Generic passive contact is outside this reviewed interface map"},
    }
    assert not {
        "connector.mapped_interface_signal_unassigned",
        "connector.mapped_interface_other_unassigned",
    } & {item.rule_id for item in cli.findings}
    assert cli.connector_peer_pin_coverage is not None
    assert cli.connector_peer_pin_coverage.generic_peer_pin_all_open_finding_count == 1


@pytest.mark.design_lint_rule(rule_id=FOOTPRINT_ALL_OPEN_RULE_ID)
def test_unanchored_footprint_alias_prompt_matches_cli_and_mcp(tmp_path: Path) -> None:
    policy = DesignLintPolicy(
        rules=(
            *(
                DesignLintRuleOverride(
                    rule_id=rule_id,
                    mode="off",
                    reason="Synthetic project has no native PCB snapshot.",
                )
                for rule_id in (
                    "pcb.schematic_component_inventory",
                    "pcb.schematic_pcb_dnp_mismatch",
                    "pcb.schematic_pcb_value_mismatch",
                    "pcb.schematic_pcb_pad_net_mismatch",
                )
            ),
            DesignLintRuleOverride(
                rule_id="protection.unreviewed_interface_pin",
                mode="off",
                reason="Synthetic fixture isolates footprint peer review.",
            ),
            DesignLintRuleOverride(
                rule_id=FOOTPRINT_ALL_OPEN_RULE_ID,
                mode="review",
                reason="Synthetic project explicitly opts into this heuristic.",
            ),
        )
    )
    root, summary_path = synthetic_design_lint_project(tmp_path, policy)
    manifest_path = root / "projects/controller/project.json"
    manifest = read_model(manifest_path, ProjectManifest)
    interface = InterfaceRecord(
        id="synthetic-footprint-peer",
        revision="synthetic-1",
        pins=(
            InterfacePin(
                number="1",
                signal="PORT_RETURN",
                role="return",
                direction="passive",
                voltage_domain="signal-return",
                mating="PORT_RETURN",
                orientation="straight",
                mechanical_clearance="synthetic",
            ),
        ),
    )
    write_model(
        root / "catalog/interfaces.json",
        InterfacesCatalog(schema_version="1", interfaces=(interface,)),
    )
    write_model(
        manifest_path,
        manifest.model_copy(
            update={
                "interfaces": (interface.id,),
                "connector_inventory_review": ConnectorInventoryReview(
                    basis="Synthetic fixture reviews both connector aliases."
                ),
                "connector_reviews": tuple(
                    ConnectorInterfaceReview(
                        reference=reference,
                        disposition="interface",
                        basis=f"Synthetic current map for {reference}",
                        interface_id=interface.id,
                        pin_map={"1": "1"},
                        unlisted_pin_reasons={
                            "2": "Generic contact is outside this synthetic interface map"
                        },
                        peer_assignment_group="reviewed-serial-peers",
                        peer_assignment_basis=f"Reviewed {reference} in one peer group",
                    )
                    for reference in ("J1", "J2")
                ),
            }
        ),
    )
    summary = read_model(summary_path, ValidationSummary)
    netlist = summary_path.parent / "netlist.xml"
    netlist.write_text(
        _netlist_xml(
            fault=True,
            common_anchor=False,
            footprint_aliases=True,
            split_anchor=True,
        ),
        encoding="utf-8",
    )
    write_model(
        summary_path,
        summary.model_copy(
            update={
                "artifacts_sha256": {
                    **summary.artifacts_sha256,
                    "netlist.xml": digest(netlist),
                }
            }
        ),
    )

    process = run_design_lint_cli(tmp_path, root, summary_path)
    assert process.returncode in {0, 1}, process.stderr + process.stdout
    cli = DesignLintReport.model_validate_json(process.stdout)

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

    mcp = asyncio.run(inspect_mcp())
    assert semantic_design_lint_report(cli) == semantic_design_lint_report(mcp)
    (finding,) = tuple(item for item in cli.findings if item.rule_id == FOOTPRINT_ALL_OPEN_RULE_ID)
    assert finding.mode == "review"
    assert finding.evidence["common_anchor_pin_numbers"] == ()
    assert finding.evidence["peer_assignment_group"] == ("reviewed-serial-peers",)
    coverage = cli.connector_peer_pin_coverage
    assert coverage is not None
    alias = coverage.footprint_alias_coverage
    assert alias.all_open_peer_pin_group_count == 1
    assert alias.unanchored_all_open_peer_pin_group_count == 1
    assert alias.unanchored_all_open_finding_count == 1
