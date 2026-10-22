"""Synthetic connector peer-pin checks across guarded native PART_ID aliases."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest
from mcp import Client

from kicad_tooling.hwrepo.connector_pins import (
    connector_peer_pin_assignment_divergences,
    connector_peer_pin_assignment_outliers,
)
from kicad_tooling.hwrepo.contracts import read_model, write_model
from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.mcp_server import create_server
from kicad_tooling.hwrepo.models import (
    DesignLintIgnore,
    DesignLintPolicy,
    DesignLintReport,
    DesignLintRuleOverride,
    ValidationSummary,
)
from tests.connector_part_id_peer_support import (
    PART_ID_PEER_PIN_DIVERGENCE_RULE_ID as DIVERGENCE_RULE_ID,
)
from tests.connector_part_id_peer_support import (
    PART_ID_PEER_PIN_OUTLIER_RULE_ID as RULE_ID,
)
from tests.connector_part_id_peer_support import (
    connector_netlist,
    lint_report,
)
from tests.mcp_parity_support import semantic_design_lint_report
from tests.synthetic_design_lint_project import (
    run_design_lint_cli,
    synthetic_design_lint_project,
)

pytestmark = [
    pytest.mark.connector_lint,
    pytest.mark.design_lint,
]


def test_shared_part_id_symbol_aliases_surface_open_generic_pin_with_coverage() -> None:
    observed = connector_netlist(
        symbols={"J1": "Synthetic:PortLeft", "J2": "Synthetic:PortRight"},
        part_ids={"J1": "SYNTHETIC-PORT-001", "J2": "synthetic-port-001"},
    )
    report = lint_report(observed)
    findings = [item for item in report.findings if item.rule_id == RULE_ID]

    assert report.status == "REVIEW"
    assert len(findings) == 1
    finding = findings[0]
    assert finding.evidence["peer_identity_basis"] == ("part_id",)
    assert finding.evidence["peer_identity"] == ("SYNTHETIC-PORT-001",)
    assert finding.evidence["peer_symbols"] == (
        "Synthetic:PortLeft",
        "Synthetic:PortRight",
    )
    assert finding.evidence["outlier_pins"] == ("J2.2",)
    assert finding.evidence["J1.2"] == ("GND",)
    assert finding.evidence["J2.2"] == ()

    coverage = report.connector_peer_pin_coverage
    assert coverage is not None
    assert coverage.exact_symbol_peer_group_count == 0
    alias_coverage = coverage.part_id_alias_coverage
    assert alias_coverage.status == "EVALUATED"
    assert alias_coverage.candidate_group_count == 1
    assert alias_coverage.eligible_peer_group_count == 1
    assert alias_coverage.compared_pin_group_count == 2
    assert alias_coverage.common_assignment_pin_group_count == 1
    assert alias_coverage.different_assignment_pin_group_count == 1
    assert alias_coverage.open_assignment_pin_group_count == 1
    assert alias_coverage.outlier_finding_count == 1
    assert alias_coverage.divergence_finding_count == 0


def test_common_part_id_aliases_are_a_quiet_control_and_split_groups_allow_isolation() -> None:
    common = connector_netlist(
        symbols={"J1": "Synthetic:PortLeft", "J2": "Synthetic:PortRight"},
        pin_two_nets=("GND", "GND"),
    )
    assert lint_report(common).findings == ()

    split = connector_netlist(
        symbols={"J1": "Synthetic:PortLeft", "J2": "Synthetic:PortRight"},
        pin_two_nets=("RETURN_A", "RETURN_B"),
    )
    report = lint_report(split)
    divergence = [item for item in report.findings if item.rule_id == DIVERGENCE_RULE_ID]
    assert len(divergence) == 1
    assert divergence[0].evidence["peer_identity_basis"] == ("part_id",)

    reviewed_groups = {
        "J1": ("isolated-port-a", "Reviewed independent interface A"),
        "J2": ("isolated-port-b", "Reviewed independent interface B"),
    }
    assert (
        connector_peer_pin_assignment_outliers(split, peer_assignment_groups=reviewed_groups) == ()
    )
    assert (
        connector_peer_pin_assignment_divergences(split, peer_assignment_groups=reviewed_groups)
        == ()
    )


def test_dnp_and_ambiguous_pin_assignments_do_not_trigger_alias_findings() -> None:
    dnp_report = lint_report(
        connector_netlist(
            symbols={"J1": "Synthetic:PortLeft", "J2": "Synthetic:PortRight"},
            dnp=("J2",),
        )
    )
    assert not any(item.rule_id in {RULE_ID, DIVERGENCE_RULE_ID} for item in dnp_report.findings)

    ambiguous_report = lint_report(
        connector_netlist(
            symbols={"J1": "Synthetic:PortLeft", "J2": "Synthetic:PortRight"},
            ambiguous_pin="J1.2",
        )
    )
    assert not any(
        item.rule_id in {RULE_ID, DIVERGENCE_RULE_ID} for item in ambiguous_report.findings
    )
    coverage = ambiguous_report.connector_peer_pin_coverage
    assert coverage is not None
    assert coverage.part_id_alias_coverage.ambiguous_assignment_pin_group_count == 1


@pytest.mark.parametrize(
    ("pin_two_nets", "rule_id"),
    (
        (("GND", None), RULE_ID),
        (("RETURN_A", "RETURN_B"), DIVERGENCE_RULE_ID),
    ),
    ids=("outlier", "divergence"),
)
def test_part_id_alias_findings_are_stable_under_mapping_order(
    pin_two_nets: tuple[str | None, ...], rule_id: str
) -> None:
    source = connector_netlist(
        symbols={"J1": "Synthetic:PortLeft", "J2": "Synthetic:PortRight"},
        pin_two_nets=pin_two_nets,
    )
    reordered = source.model_copy(
        update={
            "components": dict(reversed(tuple(source.components.items()))),
            "nets": dict(reversed(tuple(source.nets.items()))),
            "component_symbols": dict(reversed(tuple(source.component_symbols.items()))),
            "component_pin_numbers": dict(reversed(tuple(source.component_pin_numbers.items()))),
            "pin_functions": dict(reversed(tuple(source.pin_functions.items()))),
            "pin_electrical_types": dict(reversed(tuple(source.pin_electrical_types.items()))),
        }
    )

    initial = next(item for item in lint_report(source).findings if item.rule_id == rule_id)
    reordered_finding = next(
        item for item in lint_report(reordered).findings if item.rule_id == rule_id
    )
    assert (reordered_finding.fingerprint, reordered_finding.evidence) == (
        initial.fingerprint,
        initial.evidence,
    )


def test_part_id_alias_findings_obey_project_policy_and_ignore_lifecycle() -> None:
    source = connector_netlist(
        symbols={"J1": "Synthetic:PortLeft", "J2": "Synthetic:PortRight"},
        pin_two_nets=("GND", None),
    )
    initial = lint_report(source)
    finding = next(item for item in initial.findings if item.rule_id == RULE_ID)

    blocked = lint_report(
        source,
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=RULE_ID,
                    mode="block",
                    reason="Synthetic fixture requires review of peer connector contacts",
                ),
            )
        ),
    )
    assert blocked.status == "FAIL"
    assert blocked.findings[0].mode == "block"

    off = lint_report(
        source,
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=RULE_ID,
                    mode="off",
                    reason="Synthetic fixture records an intentionally unchecked alias",
                ),
            )
        ),
    )
    off_finding = next(item for item in off.findings if item.rule_id == RULE_ID)
    assert off_finding.disposition == "RULE_OFF"

    ignore_policy = DesignLintPolicy(
        ignores=(
            DesignLintIgnore(
                rule_id=RULE_ID,
                fingerprint=finding.fingerprint,
                reason="Synthetic fixture records this open alias contact as intentional",
            ),
        )
    )
    ignored = lint_report(source, ignore_policy)
    ignored_finding = next(item for item in ignored.findings if item.rule_id == RULE_ID)
    assert ignored_finding.disposition == "IGNORED"

    changed_source = connector_netlist(
        symbols={"J1": "Synthetic:PortLeft", "J2": "Synthetic:PortRight"},
        pin_two_nets=("RETURN_MAIN", None),
    )
    stale = lint_report(changed_source, ignore_policy)
    assert stale.status == "REVIEW"
    assert stale.stale_ignores == ignore_policy.ignores


def test_part_id_connector_alias_assignment_matches_between_cli_and_mcp(
    tmp_path: Path,
) -> None:
    from tests.component_peer_power_assignment_support import peer_pin_netlist_xml

    root, summary_path = synthetic_design_lint_project(
        tmp_path,
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id="pcb.schematic_component_inventory",
                    mode="off",
                    reason="Synthetic parity fixture has no native PCB snapshot evidence.",
                ),
                DesignLintRuleOverride(
                    rule_id="pcb.schematic_pcb_dnp_mismatch",
                    mode="off",
                    reason="Synthetic parity fixture has no native PCB snapshot evidence.",
                ),
                DesignLintRuleOverride(
                    rule_id="pcb.schematic_pcb_value_mismatch",
                    mode="off",
                    reason="Synthetic parity fixture has no native PCB value snapshot evidence.",
                ),
                DesignLintRuleOverride(
                    rule_id="pcb.schematic_pcb_pad_net_mismatch",
                    mode="off",
                    reason="Synthetic parity fixture has no native PCB pad-net snapshot evidence.",
                ),
            )
        ),
    )
    netlist_path = summary_path.parent / "netlist.xml"
    summary = read_model(summary_path, ValidationSummary)

    async def inspect_mcp() -> tuple[DesignLintReport, ...]:
        async with Client(create_server(root), mode="legacy") as client:
            reports: list[DesignLintReport] = []
            for assignments, expected_rule_id in (
                (("GND", None), RULE_ID),
                (("GND", "GND"), None),
                (("RETURN_A", "RETURN_B"), DIVERGENCE_RULE_ID),
            ):
                observed = connector_netlist(
                    symbols={"J1": "Synthetic:PortLeft", "J2": "Synthetic:PortRight"},
                    part_ids={"J1": "SYNTHETIC-PORT-001", "J2": "synthetic-port-001"},
                    pin_two_nets=assignments,
                )
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
                assert process.returncode == 1, process.stderr + process.stdout
                cli_report = DesignLintReport.model_validate_json(process.stdout)
                result = await client.call_tool(
                    "inspect_design_lint",
                    {
                        "project_id": "controller",
                        "native_summary": summary_path.relative_to(root).as_posix(),
                    },
                )
                assert not result.is_error, result.content
                assert result.structured_content is not None
                mcp_report = DesignLintReport.model_validate_json(
                    json.dumps(result.structured_content)
                )

                assert semantic_design_lint_report(cli_report) == semantic_design_lint_report(
                    mcp_report
                )
                assert mcp_report.status == "REVIEW", mcp_report.issues
                peer_rule_ids = {
                    item.rule_id
                    for item in mcp_report.findings
                    if item.rule_id in {RULE_ID, DIVERGENCE_RULE_ID}
                }
                assert peer_rule_ids == ({expected_rule_id} if expected_rule_id else set())
                reports.append(mcp_report)
            return tuple(reports)

    fault, control, divergence = asyncio.run(inspect_mcp())
    finding = next(item for item in fault.findings if item.rule_id == RULE_ID)
    assert finding.evidence["peer_identity_basis"] == ("part_id",)
    assert finding.evidence["outlier_pins"] == ("J2.2",)
    assert not any(item.rule_id in {RULE_ID, DIVERGENCE_RULE_ID} for item in control.findings)
    divergence_finding = next(
        item for item in divergence.findings if item.rule_id == DIVERGENCE_RULE_ID
    )
    assert divergence_finding.evidence["peer_identity_basis"] == ("part_id",)
    assert divergence_finding.evidence["missing_pin_function_pins"] == ("J1.2", "J2.2")
