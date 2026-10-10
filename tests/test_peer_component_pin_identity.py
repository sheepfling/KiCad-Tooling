"""Focused component peer-pin regression cases."""

from __future__ import annotations

from pathlib import Path

import pytest

from kicad_tooling.hwrepo.design_lint import text_report
from kicad_tooling.hwrepo.models import (
    DesignLintPolicy,
    DesignLintReport,
    NetlistContract,
)
from tests.component_peer_pin_support import (
    BIDIRECTIONAL_RULE_ID,
    INPUT_RULE_ID,
    RULE_ID,
    SIGNAL_RULE_ID,
    component_peer_coverage,
    lint_report,
    peer_component_pin_netlist,
    peer_power_output_netlist,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.component_lint]


@pytest.mark.parametrize(
    ("electrical_type", "function", "rule_id"),
    (
        ("power_out", "OUT", RULE_ID),
        ("output", "OUT", SIGNAL_RULE_ID),
        ("input", "IN", INPUT_RULE_ID),
        ("bidirectional", "DATA_IO", BIDIRECTIONAL_RULE_ID),
    ),
)
def test_shared_part_id_aliases_cover_each_typed_peer_rule(
    electrical_type: str, function: str, rule_id: str
) -> None:
    observed = peer_component_pin_netlist(
        symbols={"U1": "Synthetic:ModuleA", "U2": "Synthetic:ModuleB"},
        pin_electrical_types=(electrical_type, electrical_type),
        pin_function=function,
        part_ids={"U1": "SYNTHETIC-PEER-MODULE", "U2": "SYNTHETIC-PEER-MODULE"},
    )
    report = lint_report(observed)

    finding = next(item for item in report.findings if item.rule_id == rule_id)
    assert finding.evidence["peer_group_basis"] == ("part_id",)
    assert finding.evidence["peer_group_identity"] == ("SYNTHETIC-PEER-MODULE",)
    assert finding.evidence["unassigned_pins"] == ("U2.2",)
    coverage = component_peer_coverage(report, rule_id)
    assert coverage.part_id_peer_group_count == 1
    assert coverage.exact_symbol_peer_group_count == 0


@pytest.mark.parity_lint
@pytest.mark.parametrize(
    ("electrical_type", "pin_function", "pin_net", "rule_id"),
    (
        ("power_out", "OUT", "VOUT", RULE_ID),
        ("output", "OUT", "SIGNAL", SIGNAL_RULE_ID),
        ("input", "IN", "SIGNAL", INPUT_RULE_ID),
        ("bidirectional", "DATA_IO", "DATA", BIDIRECTIONAL_RULE_ID),
    ),
    ids=("power-output", "signal-output", "signal-input", "bidirectional"),
)
def test_shared_part_id_peer_pin_assignment_matches_between_cli_and_mcp(
    tmp_path: Path, electrical_type: str, pin_function: str, pin_net: str, rule_id: str
) -> None:
    import asyncio
    import json

    from mcp import Client

    from kicad_tooling.hwrepo.contracts import read_model, write_model
    from kicad_tooling.hwrepo.evidence import digest
    from kicad_tooling.hwrepo.mcp_server import create_server
    from kicad_tooling.hwrepo.models import (
        ConnectorInventoryReview,
        ProjectManifest,
        ValidationSummary,
    )
    from tests.component_peer_power_assignment_support import peer_pin_netlist_xml
    from tests.synthetic_design_lint_project import (
        run_design_lint_cli,
        synthetic_design_lint_project,
    )

    root, summary_path = synthetic_design_lint_project(tmp_path, DesignLintPolicy())
    netlist_path = summary_path.parent / "netlist.xml"
    summary = read_model(summary_path, ValidationSummary)
    manifest_path = root / "projects/controller/project.json"
    manifest = read_model(manifest_path, ProjectManifest)
    write_model(
        manifest_path,
        manifest.model_copy(
            update={
                "connector_inventory_review": ConnectorInventoryReview(
                    basis=(
                        "Synthetic parity fixture reviewed its complete schematic inventory; "
                        "no connector candidates are present"
                    )
                )
            }
        ),
    )
    symbols = {"U1": "Synthetic:ModuleA", "U2": "Synthetic:ModuleB"}
    part_ids = {"U1": "SYNTHETIC-PEER-MODULE", "U2": "synthetic-peer-module"}

    async def exercise() -> None:
        async with Client(create_server(root), mode="legacy") as client:
            for fault in (True, False):
                observed = peer_component_pin_netlist(
                    pin_nets=(pin_net, None if fault else f"{pin_net}_PEER"),
                    symbols=symbols,
                    pin_electrical_types=(electrical_type, electrical_type),
                    pin_function=pin_function,
                    part_ids=part_ids,
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
                assert process.returncode == int(fault), process.stderr + process.stdout
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

                assert cli_report == mcp_report
                assert mcp_report.status == ("REVIEW" if fault else "PASS")
                findings = tuple(item for item in mcp_report.findings if item.rule_id == rule_id)
                coverage = component_peer_coverage(mcp_report, rule_id)
                assert coverage.status == "EVALUATED"
                assert coverage.netlist_sha256 == mcp_report.netlist_sha256
                assert coverage.exact_symbol_peer_group_count == 0
                assert coverage.part_id_peer_group_count == 1
                assert coverage.candidate_group_count == int(fault)
                assert coverage.finding_count == len(findings) == int(fault)
                assert coverage.suppressed_candidate_count == 0
                if fault:
                    assert findings[0].evidence["peer_group_basis"] == ("part_id",)
                    assert findings[0].evidence["peer_group_identity"] == ("SYNTHETIC-PEER-MODULE",)
                    assert findings[0].evidence["unassigned_pins"] == ("U2.2",)

            ineligible_aliases = peer_component_pin_netlist(
                symbols={"U1": "Synthetic:ModuleA", "U2": "Synthetic:ModuleB"},
                pin_electrical_types=(electrical_type, electrical_type),
                pin_function=pin_function,
                part_ids={"U1": "SYNTHETIC-PEER-MODULE", "U2": "synthetic-peer-module"},
                values={"U1": "Synthetic module", "U2": "Other module"},
            )
            netlist_path.write_text(peer_pin_netlist_xml(ineligible_aliases), encoding="utf-8")
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
            assert process.returncode == 0, process.stderr + process.stdout
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
            mcp_report = DesignLintReport.model_validate_json(json.dumps(result.structured_content))
            assert cli_report == mcp_report
            assert mcp_report.status == "PASS"
            assert not any(item.rule_id == rule_id for item in mcp_report.findings)
            coverage = component_peer_coverage(mcp_report, rule_id)
            assert coverage.status == "INCOMPLETE_COMPONENT_IDENTITY"
            assert coverage.netlist_sha256 == mcp_report.netlist_sha256
            assert coverage.part_id_candidate_group_count == 1
            assert coverage.part_id_peer_group_count == 0
            assert coverage.part_id_incomplete_component_identity_group_count == 1
            assert coverage.part_id_incomplete_component_identity_references == ("U1", "U2")
            assert "PART_ID identity mismatch references: U1, U2" in text_report(mcp_report)

    asyncio.run(exercise())


@pytest.mark.parametrize(
    ("electrical_type", "rule_id"),
    (
        ("power_out", RULE_ID),
        ("output", SIGNAL_RULE_ID),
        ("input", INPUT_RULE_ID),
        ("bidirectional", BIDIRECTIONAL_RULE_ID),
    ),
)
def test_shared_part_id_aliases_accept_identical_generic_pin_metadata(
    electrical_type: str, rule_id: str
) -> None:
    observed = peer_component_pin_netlist(
        symbols={"U1": "Synthetic:ModuleA", "U2": "Synthetic:ModuleB"},
        pin_electrical_types=(electrical_type, electrical_type),
        pin_function="Pin_2",
        part_ids={"U1": "SYNTHETIC-PEER-MODULE", "U2": "SYNTHETIC-PEER-MODULE"},
    )
    report = lint_report(observed)

    finding = next(item for item in report.findings if item.rule_id == rule_id)
    assert finding.evidence["peer_group_basis"] == ("part_id",)
    assert finding.evidence["pin_function"] == ("Pin_2",)
    assert finding.evidence["unassigned_pins"] == ("U2.2",)
    coverage = component_peer_coverage(report, rule_id)
    assert coverage.part_id_peer_group_count == 1
    assert coverage.compatible_function_pin_group_count == 1


@pytest.mark.parametrize(
    ("electrical_type", "function", "rule_id"),
    (
        ("power_out", "OUT", RULE_ID),
        ("output", "OUT", SIGNAL_RULE_ID),
        ("input", "IN", INPUT_RULE_ID),
        ("bidirectional", "DATA_IO", BIDIRECTIONAL_RULE_ID),
    ),
)
def test_shared_part_id_aliases_skip_mismatched_pin_functions(
    electrical_type: str, function: str, rule_id: str
) -> None:
    observed = peer_component_pin_netlist(
        symbols={"U1": "Synthetic:ModuleA", "U2": "Synthetic:ModuleB"},
        pin_electrical_types=(electrical_type, electrical_type),
        pin_functions=(function, f"OTHER_{function}"),
        part_ids={"U1": "SYNTHETIC-PEER-MODULE", "U2": "SYNTHETIC-PEER-MODULE"},
    )
    report = lint_report(observed)

    assert rule_id not in {item.rule_id for item in report.findings}
    assert component_peer_coverage(report, rule_id).status == "NO_COMPATIBLE_PIN_FUNCTIONS"


@pytest.mark.parametrize(
    ("observed", "expected_status"),
    (
        pytest.param(
            peer_power_output_netlist(
                symbols={"U1": "Synthetic:PowerModule", "U2": "Synthetic:PowerModuleAlias"},
                part_ids={"U1": "SYNTHETIC-A", "U2": "SYNTHETIC-B"},
            ),
            "NO_COMPARABLE_PEERS",
            id="different-part-ids",
        ),
        pytest.param(
            peer_power_output_netlist(
                symbols={"U1": "Synthetic:PowerModule", "U2": "Synthetic:PowerModuleAlias"},
                part_ids={"U1": "SYNTHETIC-A", "U2": "SYNTHETIC-A"},
                values={"U1": "Synthetic module", "U2": "Other module"},
            ),
            "INCOMPLETE_COMPONENT_IDENTITY",
            id="different-values",
        ),
        pytest.param(
            peer_power_output_netlist(
                symbols={"U1": "Synthetic:PowerModule", "U2": "Synthetic:PowerModuleAlias"},
                part_ids={"U1": "SYNTHETIC-A", "U2": "SYNTHETIC-A"},
                footprints={"U1": "Synthetic:Module", "U2": "Synthetic:OtherModule"},
            ),
            "INCOMPLETE_COMPONENT_IDENTITY",
            id="different-footprints",
        ),
        pytest.param(
            peer_power_output_netlist(
                symbols={"U1": "Synthetic:PowerModule", "U2": "Synthetic:PowerModuleAlias"},
                part_ids={"U1": "SYNTHETIC-A", "U2": "SYNTHETIC-A"},
                missing_inventory=("U2",),
            ),
            "INCOMPLETE_PIN_INVENTORY",
            id="incomplete-inventory",
        ),
        pytest.param(
            peer_power_output_netlist(
                symbols={"U1": "Synthetic:PowerModule", "U2": "Synthetic:PowerModuleAlias"},
                part_ids={"U1": "SYNTHETIC-A", "U2": "SYNTHETIC-A"},
                dnp=("U2",),
            ),
            "NO_COMPARABLE_PEERS",
            id="dnp-peer",
        ),
    ),
)
def test_part_id_peer_scan_requires_consistent_fitted_component_identity(
    observed: NetlistContract, expected_status: str
) -> None:
    report = lint_report(observed)
    coverage = component_peer_coverage(report, RULE_ID)

    assert RULE_ID not in {item.rule_id for item in report.findings}
    assert coverage.status == expected_status
    if expected_status == "INCOMPLETE_COMPONENT_IDENTITY":
        assert coverage.part_id_candidate_group_count == 1
        assert coverage.part_id_peer_group_count == 0
        assert coverage.part_id_incomplete_component_identity_group_count == 1
        assert coverage.part_id_incomplete_component_identity_references == ("U1", "U2")


@pytest.mark.parametrize(
    "pin_functions",
    (("OUT_A", "OUT_B"), ("Pin_1", "Pin_2")),
    ids=("different-meaningful-functions", "different-generic-placeholders"),
)
def test_part_id_peer_scan_requires_matching_native_pin_functions(
    pin_functions: tuple[str, str],
) -> None:
    observed = peer_component_pin_netlist(
        symbols={"U1": "Synthetic:ModuleA", "U2": "Synthetic:ModuleB"},
        pin_electrical_types=("output", "output"),
        pin_functions=pin_functions,
        part_ids={"U1": "SYNTHETIC-A", "U2": "SYNTHETIC-A"},
    )
    report = lint_report(observed)

    assert SIGNAL_RULE_ID not in {item.rule_id for item in report.findings}
    assert component_peer_coverage(report, SIGNAL_RULE_ID).status == "NO_COMPATIBLE_PIN_FUNCTIONS"


def test_part_id_peer_scan_skips_missing_pin_function_metadata() -> None:
    observed = peer_power_output_netlist(
        symbols={"U1": "Synthetic:ModuleA", "U2": "Synthetic:ModuleB"},
        output_function="OUT",
        part_ids={"U1": "SYNTHETIC-A", "U2": "SYNTHETIC-A"},
    )
    observed = observed.model_copy(
        update={
            "pin_functions": {
                key: value for key, value in observed.pin_functions.items() if key != "U2.2"
            }
        }
    )
    report = lint_report(observed)

    assert RULE_ID not in {item.rule_id for item in report.findings}
    assert component_peer_coverage(report, RULE_ID).status == "NO_COMPATIBLE_PIN_FUNCTIONS"


def test_part_id_peer_scan_deduplicates_same_pin_candidate_from_exact_symbol_group() -> None:
    observed = peer_power_output_netlist(
        references=("U1", "U2", "U3"),
        output_nets=("VOUT", None, "VOUT"),
        symbols={
            "U1": "Synthetic:PowerModule",
            "U2": "Synthetic:PowerModule",
            "U3": "Synthetic:PowerModuleAlias",
        },
        part_ids={
            "U1": "SYNTHETIC-POWER-MODULE-001",
            "U2": "SYNTHETIC-POWER-MODULE-001",
            "U3": "SYNTHETIC-POWER-MODULE-001",
        },
    )
    report = lint_report(observed)
    findings = [item for item in report.findings if item.rule_id == RULE_ID]
    coverage = component_peer_coverage(report, RULE_ID)

    assert len(findings) == 1
    assert findings[0].evidence["peer_group_basis"] == ("exact_symbol",)
    assert coverage.exact_symbol_peer_group_count == 1
    assert coverage.part_id_peer_group_count == 1
    assert coverage.deduplicated_candidate_group_count == 1
