"""Review open connector peer pins when native pin metadata is incomplete."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest
from mcp import Client

from kicad_tooling.hwrepo.contracts import read_model, write_model
from kicad_tooling.hwrepo.design_lint_report_models import DesignLintReport
from kicad_tooling.hwrepo.design_lint_rule_types import DesignLintRuleId
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
from tests.connector_footprint_peer_support import lint_report
from tests.design_lint_fixtures.connector_peer_missing_metadata_open import (
    missing_metadata_open_peer_netlist,
)
from tests.mcp_parity_support import semantic_design_lint_report
from tests.synthetic_design_lint_project import (
    run_design_lint_cli,
    synthetic_design_lint_project,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.connector_lint, pytest.mark.interface_lint]

RULE_ID: DesignLintRuleId = "connector.footprint_peer_pin_missing_metadata_open_outlier"


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_missing_metadata_open_peer_pin_is_reviewed() -> None:
    report = lint_report(missing_metadata_open_peer_netlist())
    findings = tuple(item for item in report.findings if item.rule_id == RULE_ID)

    assert len(findings) == 1
    finding = findings[0]
    assert finding.mode == "review"
    assert finding.subject == "Synthetic peer metadata connector [Synthetic:Package] pin 1"
    assert finding.evidence["missing_metadata"] == ("J2.1: pin_function",)
    assert finding.evidence["assignments"] == (
        "J1.1=UART_RX_NET",
        "J2.1=<unassigned>",
    )
    assert finding.evidence["common_anchor_pin_numbers"] == ("2",)
    assert "do not establish a shared role" in finding.message
    assert not any(
        item.rule_id == "connector.footprint_peer_pin_missing_metadata_assignment_divergence"
        for item in report.findings
    )


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
@pytest.mark.parametrize(
    (
        "target_assignments",
        "anchor_assignments",
        "dnp",
        "incomplete_inventory",
        "ambiguous_pin",
    ),
    (
        (("SHARED_PORT", "SHARED_PORT"), ("COMMON_REFERENCE", "COMMON_REFERENCE"), (), (), None),
        (("UART_RX_NET", None), ("ANCHOR_A", "ANCHOR_B"), (), (), None),
        ((None, None), ("COMMON_REFERENCE", "COMMON_REFERENCE"), (), (), None),
        (("UART_RX_NET", None), ("COMMON_REFERENCE", "COMMON_REFERENCE"), (), (), "J1.1"),
        (("UART_RX_NET", None), ("COMMON_REFERENCE", "COMMON_REFERENCE"), ("J2",), (), None),
        (("UART_RX_NET", None), ("COMMON_REFERENCE", "COMMON_REFERENCE"), (), ("J2",), None),
    ),
    ids=("common-target", "no-common-anchor", "all-open", "ambiguous", "dnp", "incomplete"),
)
def test_open_metadata_controls_require_matching_assignment_and_anchor(
    target_assignments: tuple[str | None, str | None],
    anchor_assignments: tuple[str | None, str | None],
    dnp: tuple[str, ...],
    incomplete_inventory: tuple[str, ...],
    ambiguous_pin: str | None,
) -> None:
    observed = missing_metadata_open_peer_netlist(
        target_assignments=target_assignments,
        anchor_assignments=anchor_assignments,
        dnp=dnp,
        incomplete_inventory=incomplete_inventory,
        ambiguous_pin=ambiguous_pin,
    )
    report = lint_report(observed)

    assert not any(item.rule_id == RULE_ID for item in report.findings)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_open_metadata_review_requires_available_roles_to_agree() -> None:
    observed = missing_metadata_open_peer_netlist()
    types = dict(observed.pin_electrical_types)
    types["J2.1"] = "output"

    report = lint_report(observed.model_copy(update={"pin_electrical_types": types}))

    assert not any(item.rule_id == RULE_ID for item in report.findings)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_open_metadata_review_does_not_compare_independently_scoped_peers() -> None:
    from kicad_tooling.hwrepo.connector_footprint_peer_missing_metadata_open import (
        connector_footprint_peer_pin_missing_metadata_open_outliers,
    )

    candidates = connector_footprint_peer_pin_missing_metadata_open_outliers(
        missing_metadata_open_peer_netlist(),
        peer_assignment_groups={
            "J1": ("port-a", "Synthetic independent port A"),
            "J2": ("port-b", "Synthetic independent port B"),
        },
    )

    assert candidates == ()


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_open_metadata_finding_is_stable_under_mapping_order() -> None:
    observed = missing_metadata_open_peer_netlist()
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
def test_open_metadata_review_obeys_project_mode_and_exact_ignore() -> None:
    observed = missing_metadata_open_peer_netlist()
    finding = next(item for item in lint_report(observed).findings if item.rule_id == RULE_ID)
    blocked = lint_report(
        observed,
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=RULE_ID,
                    mode="block",
                    reason="Synthetic policy exercises explicit blocking.",
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
                    reason="Synthetic policy exercises disabling the review prompt.",
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
                    reason="Synthetic policy records an intentional open peer pin.",
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
def test_missing_metadata_open_review_matches_cli_and_mcp(tmp_path: Path) -> None:
    off_rule_specs: tuple[tuple[DesignLintRuleId, str], ...] = (
        ("pcb.schematic_component_inventory", "Synthetic project has no PCB snapshot."),
        ("pcb.schematic_pcb_dnp_mismatch", "Synthetic project has no PCB snapshot."),
        ("pcb.schematic_pcb_value_mismatch", "Synthetic project has no PCB snapshot."),
        ("pcb.schematic_pcb_pad_net_mismatch", "Synthetic project has no PCB snapshot."),
        ("protection.unreviewed_interface_pin", "Synthetic test isolates peer review."),
    )
    off_rules = tuple(
        DesignLintRuleOverride(rule_id=rule_id, mode="off", reason=reason)
        for rule_id, reason in off_rule_specs
    )
    policy = DesignLintPolicy(
        rules=(
            *off_rules,
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
                        basis="Synthetic connector is only a lint fixture.",
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
        (missing_metadata_open_peer_netlist(), 1),
        (
            missing_metadata_open_peer_netlist(target_assignments=("SHARED_PORT", "SHARED_PORT")),
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
