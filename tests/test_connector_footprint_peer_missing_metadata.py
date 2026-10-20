"""Review split connector aliases when a pin's native role metadata is missing."""

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
    DesignLintIgnore,
    DesignLintPolicy,
    DesignLintRuleOverride,
    ProjectManifest,
    ValidationSummary,
)
from tests.component_peer_power_assignment_support import peer_pin_netlist_xml
from tests.connector_footprint_peer_support import (
    lint_report,
    peer_metadata_divergence_netlist,
    peer_missing_metadata_netlist,
)
from tests.mcp_parity_support import semantic_design_lint_report
from tests.synthetic_design_lint_project import (
    run_design_lint_cli,
    synthetic_design_lint_project,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.connector_lint, pytest.mark.interface_lint]

RULE_ID = "connector.footprint_peer_pin_missing_metadata_assignment_divergence"


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_unnamed_peer_pin_with_split_assignment_is_reviewed() -> None:
    report = lint_report(peer_missing_metadata_netlist())
    findings = [item for item in report.findings if item.rule_id == RULE_ID]

    assert report.status == "REVIEW"
    assert len(findings) == 1
    finding = findings[0]
    assert finding.subject == "Synthetic two-contact connector [Synthetic:Connector_2x1] pin 2"
    assert finding.evidence["missing_metadata"] == ("J2.2: pin_function",)
    assert finding.evidence["peer_pin_metadata"] == (
        "J1.2: function=UART_RX; electrical_type=input",
        "J2.2: function=<missing>; electrical_type=output",
    )
    assert finding.evidence["assignments"] == (
        "J1.2=UART_RX_NET",
        "J2.2=UART_TX_NET",
    )
    assert finding.evidence["common_anchor_pin_numbers"] == ("1",)
    assert "does not establish a shared electrical role" in finding.message
    assert not any(
        item.rule_id == "connector.footprint_peer_pin_metadata_assignment_divergence"
        for item in report.findings
    )


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
@pytest.mark.parametrize(
    ("kwargs", "missing_fields"),
    (
        ({}, ("pin_function",)),
        ({"missing_fields": ("pin_electrical_type",)}, ("pin_electrical_type",)),
        (
            {"missing_fields": ("pin_function", "pin_electrical_type")},
            ("pin_function", "pin_electrical_type"),
        ),
        ({"placeholder_function": None}, ("pin_function",)),
    ),
    ids=("unnamed-function", "missing-electrical-type", "both-fields", "absent-function"),
)
def test_supported_missing_metadata_values_are_reported(
    kwargs: dict[str, object], missing_fields: tuple[str, ...]
) -> None:
    report = lint_report(peer_missing_metadata_netlist(**kwargs))

    finding = next(item for item in report.findings if item.rule_id == RULE_ID)
    assert finding.evidence["missing_metadata"] == tuple(
        f"J2.2: {field}" for field in missing_fields
    )


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
@pytest.mark.parametrize(
    "kwargs",
    (
        {"target_assignments": ("SHARED_PORT", "SHARED_PORT")},
        {"anchor_assignments": ("ANCHOR_A", "ANCHOR_B")},
        {"target_assignments": ("UART_RX_NET", None)},
        {"ambiguous_pin": "J1.2"},
        {"incomplete_inventory": True},
        {"part_id": "SYNTHETIC-PART-001"},
        {"dnp": ("J2",)},
    ),
    ids=(
        "common-target-control",
        "no-common-anchor",
        "open-target",
        "ambiguous-anchor",
        "incomplete-inventory",
        "part-id-group",
        "dnp-peer",
    ),
)
def test_missing_metadata_needs_complete_split_and_anchor_evidence(
    kwargs: dict[str, object],
) -> None:
    report = lint_report(peer_missing_metadata_netlist(**kwargs))

    assert not any(item.rule_id == RULE_ID for item in report.findings)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_current_peer_assignment_scopes_prevent_cross_port_comparison() -> None:
    from kicad_tooling.hwrepo.connector_footprint_peer_missing_metadata import (
        connector_footprint_peer_pin_missing_metadata_assignment_divergences,
    )

    candidates = connector_footprint_peer_pin_missing_metadata_assignment_divergences(
        peer_missing_metadata_netlist(),
        peer_assignment_groups={
            "J1": ("port-a", "Synthetic independent port A"),
            "J2": ("port-b", "Synthetic independent port B"),
        },
    )

    assert candidates == ()


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_complete_metadata_differences_remain_with_lint_164() -> None:
    report = lint_report(peer_metadata_divergence_netlist())

    assert not any(item.rule_id == RULE_ID for item in report.findings)
    assert any(
        item.rule_id == "connector.footprint_peer_pin_metadata_assignment_divergence"
        for item in report.findings
    )


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_missing_metadata_finding_is_stable_under_mapping_order() -> None:
    observed = peer_missing_metadata_netlist()
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
def test_missing_metadata_review_obeys_project_mode_and_exact_ignore() -> None:
    observed = peer_missing_metadata_netlist()
    review = lint_report(observed)
    finding = next(item for item in review.findings if item.rule_id == RULE_ID)
    assert finding.mode == "review"

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
                    reason="Synthetic test disables this review heuristic.",
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
                    reason="Synthetic test records intentional connector isolation.",
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
def test_missing_metadata_review_matches_cli_and_mcp(tmp_path: Path) -> None:
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

    for observed, expected_count in (
        (peer_missing_metadata_netlist(), 1),
        (peer_missing_metadata_netlist(target_assignments=("SHARED_PORT", "SHARED_PORT")), 0),
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
