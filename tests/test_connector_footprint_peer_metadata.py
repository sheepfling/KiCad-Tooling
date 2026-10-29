"""Review connector-alias pin-role mismatches when their assigned nets split."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest
from mcp import Client

from kicad_tooling.hwrepo.connector_footprint_peer_metadata import (
    connector_footprint_peer_pin_metadata_assignment_divergences,
)
from kicad_tooling.hwrepo.contracts import read_model, write_model
from kicad_tooling.hwrepo.design_lint_report_models import DesignLintReport
from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.mcp_server import create_server
from kicad_tooling.hwrepo.models import (
    ComponentContract,
    ConnectorInterfaceReview,
    ConnectorInventoryReview,
    DesignLintIgnore,
    DesignLintPolicy,
    DesignLintRuleOverride,
    NetlistContract,
    ProjectManifest,
    ValidationSummary,
)
from tests.component_peer_power_assignment_support import peer_pin_netlist_xml
from tests.connector_footprint_peer_support import (
    PeerMetadataDivergenceOverrides,
    lint_report,
    peer_metadata_divergence_netlist,
)
from tests.mcp_parity_support import semantic_design_lint_report
from tests.synthetic_design_lint_project import (
    run_design_lint_cli,
    synthetic_design_lint_project,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.connector_lint, pytest.mark.interface_lint]

RULE_ID = "connector.footprint_peer_pin_metadata_assignment_divergence"


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_mismatched_pin_metadata_with_split_assignment_is_reviewed() -> None:
    report = lint_report(peer_metadata_divergence_netlist())
    findings = [item for item in report.findings if item.rule_id == RULE_ID]

    assert report.status == "REVIEW"
    assert len(findings) == 1
    finding = findings[0]
    assert finding.subject == "Synthetic two-contact connector [Synthetic:Connector_2x1] pin 2"
    assert finding.evidence["metadata_mismatch_fields"] == (
        "pin_function",
        "pin_electrical_type",
    )
    assert finding.evidence["peer_pin_metadata"] == (
        "J1.2: function=UART_RX; electrical_type=input",
        "J2.2: function=UART_TX; electrical_type=output",
    )
    assert finding.evidence["assignments"] == (
        "J1.2=UART_RX_NET",
        "J2.2=UART_TX_NET",
    )
    assert finding.evidence["common_anchor_pin_numbers"] == ("1",)
    assert "does not infer that the nets should connect" in finding.message

    assert report.schema_version == "7"
    coverage = report.connector_peer_pin_coverage
    assert coverage is not None
    alias = coverage.footprint_alias_coverage
    assert alias.status == "PARTIALLY_EVALUATED"
    assert alias.incomplete_pin_metadata_group_count == 0
    assert alias.differing_pin_metadata_group_count == 1
    assert alias.eligible_peer_group_count == 0


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_different_metadata_with_common_target_assignment_is_quiet() -> None:
    report = lint_report(
        peer_metadata_divergence_netlist(target_assignments=("SHARED_PORT", "SHARED_PORT"))
    )

    assert not any(item.rule_id == RULE_ID for item in report.findings)
    coverage = report.connector_peer_pin_coverage
    assert coverage is not None
    alias = coverage.footprint_alias_coverage
    assert alias.status == "PARTIALLY_EVALUATED"
    assert alias.incomplete_pin_metadata_group_count == 0
    assert alias.differing_pin_metadata_group_count == 1


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
@pytest.mark.parametrize(
    "kwargs",
    (
        {"anchor_assignments": ("ANCHOR_A", "ANCHOR_B")},
        {"target_assignments": ("UART_RX_NET", None)},
        {"ambiguous_pin": "J1.2"},
        {"incomplete_inventory": True},
        {"missing_metadata_pin": "J2.2"},
        {"part_id": "SYNTHETIC-PART-001"},
        {"dnp": ("J2",)},
    ),
    ids=(
        "no-common-anchor",
        "target-open",
        "target-ambiguous",
        "incomplete-inventory",
        "incomplete-target-metadata",
        "part-id-group",
        "dnp-peer",
    ),
)
def test_metadata_divergence_requires_complete_anchored_assignments(
    kwargs: PeerMetadataDivergenceOverrides,
) -> None:
    report = lint_report(peer_metadata_divergence_netlist(**kwargs))

    assert not any(item.rule_id == RULE_ID for item in report.findings)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_matching_metadata_does_not_enter_the_metadata_divergence_rule() -> None:
    observed = peer_metadata_divergence_netlist()
    report = lint_report(
        observed.model_copy(
            update={
                "pin_functions": {
                    **observed.pin_functions,
                    "J2.2": observed.pin_functions["J1.2"],
                },
                "pin_electrical_types": {
                    **observed.pin_electrical_types,
                    "J2.2": observed.pin_electrical_types["J1.2"],
                },
            }
        )
    )

    assert not any(item.rule_id == RULE_ID for item in report.findings)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_unnamed_native_pin_function_is_missing_metadata_not_a_role_difference() -> None:
    observed = peer_metadata_divergence_netlist()
    report = lint_report(
        observed.model_copy(
            update={
                "pin_functions": {**observed.pin_functions, "J2.2": "~"},
            }
        )
    )

    assert not any(item.rule_id == RULE_ID for item in report.findings)
    coverage = report.connector_peer_pin_coverage
    assert coverage is not None
    alias = coverage.footprint_alias_coverage
    assert alias.status == "INCOMPLETE_EVIDENCE"
    assert alias.incomplete_pin_metadata_group_count == 1
    assert alias.differing_pin_metadata_group_count == 0


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_current_peer_groups_prevent_cross_port_metadata_comparison() -> None:
    observed = peer_metadata_divergence_netlist()
    candidates = connector_footprint_peer_pin_metadata_assignment_divergences(
        observed,
        peer_assignment_groups={
            "J1": ("port-a", "Synthetic independent port A"),
            "J2": ("port-b", "Synthetic independent port B"),
        },
    )

    assert candidates == ()


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_metadata_difference_must_exist_inside_each_peer_scope() -> None:
    references = ("J1", "J2", "J3", "J4")
    observed = NetlistContract(
        components={
            reference: ComponentContract(
                value="Synthetic two-contact connector",
                footprint="Synthetic:Connector_2x1",
            )
            for reference in references
        },
        nets={
            "COMMON_A": ("J1.1", "J2.1"),
            "COMMON_B": ("J3.1", "J4.1"),
            "A_NET_1": ("J1.2",),
            "A_NET_2": ("J2.2",),
            "B_NET_1": ("J3.2",),
            "B_NET_2": ("J4.2",),
        },
        component_symbols={
            reference: f"Synthetic:ConnectorAlias{index}"
            for index, reference in enumerate(references, start=1)
        },
        component_pin_numbers={reference: ("1", "2") for reference in references},
        pin_functions={
            **{f"{reference}.1": "Pin_1" for reference in references},
            "J1.2": "UART_RX",
            "J2.2": "UART_RX",
            "J3.2": "UART_TX",
            "J4.2": "UART_TX",
        },
        pin_electrical_types={
            **{f"{reference}.1": "passive" for reference in references},
            "J1.2": "input",
            "J2.2": "input",
            "J3.2": "output",
            "J4.2": "output",
        },
    )
    candidates = connector_footprint_peer_pin_metadata_assignment_divergences(
        observed,
        peer_assignment_groups={
            "J1": ("port-a", "Synthetic port A"),
            "J2": ("port-a", "Synthetic port A"),
            "J3": ("port-b", "Synthetic port B"),
            "J4": ("port-b", "Synthetic port B"),
        },
    )

    assert candidates == ()


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_metadata_divergence_finding_is_stable_under_mapping_order() -> None:
    observed = peer_metadata_divergence_netlist()
    reordered = observed.model_copy(
        update={
            "components": dict(reversed(tuple(observed.components.items()))),
            "nets": dict(reversed(tuple(observed.nets.items()))),
            "component_symbols": dict(reversed(tuple(observed.component_symbols.items()))),
            "component_pin_numbers": dict(reversed(tuple(observed.component_pin_numbers.items()))),
            "pin_functions": dict(reversed(tuple(observed.pin_functions.items()))),
            "pin_electrical_types": dict(reversed(tuple(observed.pin_electrical_types.items()))),
        }
    )
    initial = next(item for item in lint_report(observed).findings if item.rule_id == RULE_ID)
    shuffled = next(item for item in lint_report(reordered).findings if item.rule_id == RULE_ID)

    assert (shuffled.fingerprint, shuffled.evidence) == (initial.fingerprint, initial.evidence)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_metadata_divergence_obeys_project_mode_and_exact_ignore() -> None:
    observed = peer_metadata_divergence_netlist()
    default = lint_report(observed)
    finding = next(item for item in default.findings if item.rule_id == RULE_ID)

    blocked = lint_report(
        observed,
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=RULE_ID,
                    mode="block",
                    reason="Synthetic test selects blocking policy explicitly.",
                ),
            )
        ),
    )
    assert blocked.status == "FAIL"
    assert next(item for item in blocked.findings if item.rule_id == RULE_ID).mode == "block"

    disabled = lint_report(
        observed,
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=RULE_ID,
                    mode="off",
                    reason="Synthetic test records a disabled review heuristic.",
                ),
            )
        ),
    )
    assert next(item for item in disabled.findings if item.rule_id == RULE_ID).disposition == (
        "RULE_OFF"
    )

    ignored = lint_report(
        observed,
        DesignLintPolicy(
            ignores=(
                DesignLintIgnore(
                    rule_id=RULE_ID,
                    fingerprint=finding.fingerprint,
                    reason="Synthetic test records an intentional peer assignment difference.",
                ),
            )
        ),
    )
    assert next(item for item in ignored.findings if item.rule_id == RULE_ID).disposition == (
        "IGNORED"
    )


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
@pytest.mark.parity_lint
@pytest.mark.slow
def test_metadata_divergence_matches_cli_and_mcp(tmp_path: Path) -> None:
    disabled_rules = (
        ("pcb.schematic_component_inventory", "Synthetic parity project has no PCB snapshot."),
        ("pcb.schematic_pcb_dnp_mismatch", "Synthetic parity project has no PCB snapshot."),
        ("pcb.schematic_pcb_value_mismatch", "Synthetic parity project has no PCB snapshot."),
        ("pcb.schematic_pcb_pad_net_mismatch", "Synthetic parity project has no PCB snapshot."),
        ("protection.unreviewed_interface_pin", "Synthetic fixture isolates peer review."),
    )
    policy = DesignLintPolicy(
        rules=(
            *(
                DesignLintRuleOverride(rule_id=rule_id, mode="off", reason=reason)
                for rule_id, reason in disabled_rules
            ),
            DesignLintRuleOverride(
                rule_id=RULE_ID,
                mode="review",
                reason="Synthetic parity case explicitly enables this heuristic.",
            ),
        )
    )
    root, summary_path = synthetic_design_lint_project(tmp_path, policy)
    manifest_path = root / "projects/controller/project.json"
    manifest = read_model(manifest_path, ProjectManifest)
    write_model(
        manifest_path,
        manifest.model_copy(
            update={
                "connector_inventory_review": ConnectorInventoryReview(
                    basis="Synthetic parity fixture reviews both connector symbols."
                ),
                "connector_reviews": tuple(
                    ConnectorInterfaceReview(
                        reference=reference,
                        disposition="not_applicable",
                        basis="Synthetic symbols are not board interfaces.",
                    )
                    for reference in ("J1", "J2")
                ),
            }
        ),
    )
    summary = read_model(summary_path, ValidationSummary)
    netlist_path = summary_path.parent / "netlist.xml"

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

    for observed, expected_status, expected_count in (
        (peer_metadata_divergence_netlist(), "REVIEW", 1),
        (
            peer_metadata_divergence_netlist(target_assignments=("SHARED_PORT", "SHARED_PORT")),
            "PASS",
            0,
        ),
    ):
        netlist_path.write_text(peer_pin_netlist_xml(observed), encoding="utf-8")
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
        assert process.returncode in {0, 1}, process.stderr + process.stdout
        cli_report = DesignLintReport.model_validate_json(process.stdout)
        mcp_report = asyncio.run(inspect_mcp())

        assert semantic_design_lint_report(cli_report) == semantic_design_lint_report(mcp_report)
        assert cli_report.status == expected_status
        assert sum(item.rule_id == RULE_ID for item in cli_report.findings) == expected_count
