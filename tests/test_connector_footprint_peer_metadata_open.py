"""Review partial-open connector peers whose known pin roles differ."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest
from mcp import Client

from kicad_tooling.hwrepo.connector_footprint_peer_metadata_open import (
    connector_footprint_peer_pin_metadata_open_outliers,
)
from kicad_tooling.hwrepo.contracts import read_model, write_model
from kicad_tooling.hwrepo.design_lint_report_models import DesignLintReport
from kicad_tooling.hwrepo.design_lint_rule_types import DesignLintRuleId
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
from tests.connector_footprint_peer_support import lint_report, peer_metadata_divergence_netlist
from tests.mcp_parity_support import semantic_design_lint_report
from tests.synthetic_design_lint_project import (
    run_design_lint_cli,
    synthetic_design_lint_project,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.connector_lint, pytest.mark.interface_lint]

RULE_ID: DesignLintRuleId = "connector.footprint_peer_pin_metadata_open_outlier"


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_known_metadata_open_peer_is_reviewed() -> None:
    observed = peer_metadata_divergence_netlist(target_assignments=("UART_RX_NET", None))
    report = lint_report(observed)
    findings = tuple(item for item in report.findings if item.rule_id == RULE_ID)

    assert len(findings) == 1
    finding = findings[0]
    assert finding.mode == "review"
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
        "J2.2=<unassigned>",
    )
    assert finding.evidence["common_anchor_pin_numbers"] == ("1",)
    assert "does not require a connection" in finding.message
    assert not any(
        item.rule_id == "connector.footprint_peer_pin_metadata_assignment_divergence"
        for item in report.findings
    )
    coverage = report.connector_peer_pin_coverage
    assert coverage is not None
    alias = coverage.footprint_alias_coverage
    assert alias.status == "PARTIALLY_EVALUATED"
    assert alias.incomplete_pin_metadata_group_count == 0
    assert alias.differing_pin_metadata_group_count == 1


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
@pytest.mark.parametrize("different_field", ("pin_function", "pin_electrical_type"))
def test_one_known_metadata_difference_is_enough(different_field: str) -> None:
    observed = peer_metadata_divergence_netlist(target_assignments=("UART_RX_NET", None))
    update = (
        {
            "pin_electrical_types": {
                **observed.pin_electrical_types,
                "J2.2": observed.pin_electrical_types["J1.2"],
            }
        }
        if different_field == "pin_function"
        else {
            "pin_functions": {
                **observed.pin_functions,
                "J2.2": observed.pin_functions["J1.2"],
            }
        }
    )

    finding = next(
        item
        for item in lint_report(observed.model_copy(update=update)).findings
        if item.rule_id == RULE_ID
    )

    assert finding.evidence["metadata_mismatch_fields"] == (different_field,)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
@pytest.mark.parametrize(
    "kwargs",
    (
        {"target_assignments": ("SHARED_PORT", "SHARED_PORT")},
        {"target_assignments": (None, None)},
        {"target_assignments": ("UART_RX_NET", "UART_TX_NET")},
        {"anchor_assignments": ("ANCHOR_A", "ANCHOR_B")},
        {"ambiguous_pin": "J1.2"},
        {"dnp": ("J2",)},
        {"incomplete_inventory": True},
        {"part_id": "SYNTHETIC-PART-001"},
    ),
    ids=(
        "common-target",
        "all-open",
        "split-assigned-nets",
        "no-common-anchor",
        "ambiguous-target",
        "dnp-peer",
        "incomplete-inventory",
        "part-id-group",
    ),
)
def test_open_metadata_controls_require_partial_assignment_and_anchor(
    kwargs: dict[str, object],
) -> None:
    report = lint_report(
        peer_metadata_divergence_netlist(**{"target_assignments": ("UART_RX_NET", None), **kwargs})
    )

    assert not any(item.rule_id == RULE_ID for item in report.findings)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_equal_or_missing_role_metadata_remains_outside_this_rule() -> None:
    observed = peer_metadata_divergence_netlist(target_assignments=("UART_RX_NET", None))
    equal_metadata = observed.model_copy(
        update={
            "pin_functions": {**observed.pin_functions, "J2.2": observed.pin_functions["J1.2"]},
            "pin_electrical_types": {
                **observed.pin_electrical_types,
                "J2.2": observed.pin_electrical_types["J1.2"],
            },
        }
    )
    missing_metadata = peer_metadata_divergence_netlist(
        target_assignments=("UART_RX_NET", None),
        missing_metadata_pin="J2.2",
    )

    assert not any(item.rule_id == RULE_ID for item in lint_report(equal_metadata).findings)
    missing_report = lint_report(missing_metadata)
    assert not any(item.rule_id == RULE_ID for item in missing_report.findings)
    coverage = missing_report.connector_peer_pin_coverage
    assert coverage is not None
    alias = coverage.footprint_alias_coverage
    assert alias.status == "INCOMPLETE_EVIDENCE"
    assert alias.incomplete_pin_metadata_group_count == 1
    assert alias.differing_pin_metadata_group_count == 0


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_peer_assignment_groups_prevent_cross_port_comparison() -> None:
    observed = peer_metadata_divergence_netlist(target_assignments=("UART_RX_NET", None))

    candidates = connector_footprint_peer_pin_metadata_open_outliers(
        observed,
        peer_assignment_groups={
            "J1": ("port-a", "Synthetic independent port A"),
            "J2": ("port-b", "Synthetic independent port B"),
        },
    )

    assert candidates == ()


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_incomplete_metadata_in_another_reviewed_scope_does_not_suppress_candidate() -> None:
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
            "PORT_A_ANCHOR": ("J1.1", "J2.1"),
            "PORT_A_SIGNAL": ("J1.2",),
            "PORT_B_ANCHOR": ("J3.1", "J4.1"),
            "PORT_B_SIGNAL": ("J3.2", "J4.2"),
        },
        component_symbols={
            reference: f"Synthetic:Alias{index}" for index, reference in enumerate(references)
        },
        component_pin_numbers={reference: ("1", "2") for reference in references},
        pin_functions={
            "J1.1": "2",
            "J2.1": "2",
            "J3.1": "2",
            "J4.1": "2",
            "J1.2": "UART_RX",
            "J2.2": "UART_TX",
            "J3.2": "UART_TX",
            "J4.2": "~",
        },
        pin_electrical_types={
            "J1.1": "passive",
            "J2.1": "passive",
            "J3.1": "passive",
            "J4.1": "passive",
            "J1.2": "input",
            "J2.2": "output",
            "J3.2": "output",
            "J4.2": "output",
        },
    )

    candidates = connector_footprint_peer_pin_metadata_open_outliers(
        observed,
        peer_assignment_groups={
            "J1": ("port-a", "Synthetic independent port A"),
            "J2": ("port-a", "Synthetic independent port A"),
            "J3": ("port-b", "Synthetic independent port B"),
            "J4": ("port-b", "Synthetic independent port B"),
        },
    )

    assert tuple(item.subject for item in candidates) == (
        "Synthetic two-contact connector [Synthetic:Connector_2x1] pin 2",
    )
    assert candidates[0].evidence["peer_assignment_group"] == ("port-a",)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_metadata_open_finding_is_stable_under_mapping_order() -> None:
    observed = peer_metadata_divergence_netlist(target_assignments=("UART_RX_NET", None))
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
    original = next(item for item in lint_report(observed).findings if item.rule_id == RULE_ID)
    shuffled = next(item for item in lint_report(reordered).findings if item.rule_id == RULE_ID)

    assert (shuffled.fingerprint, shuffled.evidence) == (original.fingerprint, original.evidence)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_metadata_open_review_obeys_mode_and_exact_ignore() -> None:
    observed = peer_metadata_divergence_netlist(target_assignments=("UART_RX_NET", None))
    finding = next(item for item in lint_report(observed).findings if item.rule_id == RULE_ID)
    blocked = lint_report(
        observed,
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=RULE_ID,
                    mode="block",
                    reason="Synthetic test explicitly selects a blocking policy.",
                ),
            )
        ),
    )
    disabled = lint_report(
        observed,
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=RULE_ID,
                    mode="off",
                    reason="Synthetic test explicitly disables this review heuristic.",
                ),
            )
        ),
    )
    ignored = lint_report(
        observed,
        DesignLintPolicy(
            ignores=(
                DesignLintIgnore(
                    rule_id=RULE_ID,
                    fingerprint=finding.fingerprint,
                    reason="Synthetic project records an intentional open connector contact.",
                ),
            )
        ),
    )

    assert blocked.status == "FAIL"
    assert next(item for item in blocked.findings if item.rule_id == RULE_ID).mode == "block"
    assert next(item for item in disabled.findings if item.rule_id == RULE_ID).disposition == (
        "RULE_OFF"
    )
    assert next(item for item in ignored.findings if item.rule_id == RULE_ID).disposition == (
        "IGNORED"
    )


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
@pytest.mark.parity_lint
@pytest.mark.slow
def test_metadata_open_review_matches_cli_and_mcp(tmp_path: Path) -> None:
    off_rule_specs: tuple[tuple[DesignLintRuleId, str], ...] = (
        ("pcb.schematic_component_inventory", "Synthetic project has no PCB snapshot."),
        ("pcb.schematic_pcb_dnp_mismatch", "Synthetic project has no PCB snapshot."),
        ("pcb.schematic_pcb_value_mismatch", "Synthetic project has no PCB snapshot."),
        ("pcb.schematic_pcb_pad_net_mismatch", "Synthetic project has no PCB snapshot."),
        ("protection.unreviewed_interface_pin", "Synthetic parity fixture isolates peer review."),
    )
    policy = DesignLintPolicy(
        rules=(
            *(
                DesignLintRuleOverride(rule_id=rule, mode="off", reason=reason)
                for rule, reason in off_rule_specs
            ),
            DesignLintRuleOverride(
                rule_id=RULE_ID,
                mode="review",
                reason="Synthetic parity test enables this bounded review heuristic.",
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

    for observed, expected_count in (
        (peer_metadata_divergence_netlist(target_assignments=("UART_RX_NET", None)), 1),
        (
            peer_metadata_divergence_netlist(
                target_assignments=("UART_RX_NET", None),
                anchor_assignments=("ANCHOR_A", "ANCHOR_B"),
            ),
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
        assert sum(item.rule_id == RULE_ID for item in cli_report.findings) == expected_count
