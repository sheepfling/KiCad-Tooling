"""Synthetic regressions for peer-pin assignment completeness."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

import pytest

from kicad_tooling.hwrepo.design_lint import evaluate, text_report
from kicad_tooling.hwrepo.models import (
    ComponentContract,
    ContractCoachReport,
    DesignLintIgnore,
    DesignLintPolicy,
    DesignLintReport,
    DesignLintRuleOverride,
    NetlistContract,
)

RULE_ID = "component.peer_power_output_unconnected"
SIGNAL_RULE_ID = "component.peer_signal_output_unconnected"
INPUT_RULE_ID = "component.peer_signal_input_unconnected"
BIDIRECTIONAL_RULE_ID = "component.peer_bidirectional_pin_unconnected"


def peer_component_pin_netlist(
    *,
    references: tuple[str, ...] = ("U1", "U2"),
    pin_nets: tuple[str | None, ...] = ("VOUT", None),
    dnp: tuple[str, ...] = (),
    symbols: dict[str, str] | None = None,
    default_symbol: str = "Synthetic:PowerModule",
    pin_electrical_types: tuple[str, ...] | None = None,
    pin_function: str = "OUT",
    pin_functions: tuple[str | None, ...] | None = None,
    missing_inventory: tuple[str, ...] = (),
    ambiguous_pins: tuple[str, ...] = (),
    part_ids: dict[str, str] | None = None,
    values: dict[str, str] | None = None,
    footprints: dict[str, str] | None = None,
) -> NetlistContract:
    if len(references) != len(pin_nets):
        raise ValueError("Each peer needs one pin-net case")
    symbols = symbols or {reference: default_symbol for reference in references}
    pin_electrical_types = pin_electrical_types or tuple("power_out" for _ in references)
    pin_functions = pin_functions or tuple(pin_function for _ in references)
    if len(pin_electrical_types) != len(references) or len(pin_functions) != len(references):
        raise ValueError("Each peer needs one pin type and function case")
    part_ids = part_ids or {}
    values = values or {}
    footprints = footprints or {}
    components = {
        reference: ComponentContract(
            value=values.get(reference, "Synthetic module"),
            footprint=footprints.get(reference, "Synthetic:Module"),
            part_id=part_ids.get(reference),
        )
        for reference in references
    }
    nets: dict[str, tuple[str, ...]] = {"DATA": tuple(f"{reference}.1" for reference in references)}
    for reference, net in zip(references, pin_nets, strict=True):
        if net is not None:
            nets[net] = (*nets.get(net, ()), f"{reference}.2")
        if reference in ambiguous_pins:
            nets[f"ALSO_{reference}"] = (f"{reference}.2",)
    peer_pin_functions = {
        f"{reference}.2": function
        for reference, function in zip(references, pin_functions, strict=True)
        if function is not None
    }
    return NetlistContract(
        components=components,
        nets=nets,
        dnp_components=dnp,
        component_symbols=symbols,
        pin_functions={
            **{f"{reference}.1": "IO" for reference in references},
            **peer_pin_functions,
        },
        pin_electrical_types={
            f"{reference}.2": electrical_type
            for reference, electrical_type in zip(references, pin_electrical_types, strict=True)
        },
        component_pin_numbers={
            reference: ("1", "2") for reference in references if reference not in missing_inventory
        },
    )


def peer_power_output_netlist(
    *,
    references: tuple[str, ...] = ("U1", "U2"),
    output_nets: tuple[str | None, ...] = ("VOUT", None),
    dnp: tuple[str, ...] = (),
    symbols: dict[str, str] | None = None,
    output_electrical_types: tuple[str, ...] | None = None,
    output_function: str = "OUT",
    missing_inventory: tuple[str, ...] = (),
    ambiguous_outputs: tuple[str, ...] = (),
    part_ids: dict[str, str] | None = None,
    values: dict[str, str] | None = None,
    footprints: dict[str, str] | None = None,
) -> NetlistContract:
    return peer_component_pin_netlist(
        references=references,
        pin_nets=output_nets,
        dnp=dnp,
        symbols=symbols,
        pin_electrical_types=output_electrical_types,
        pin_function=output_function,
        missing_inventory=missing_inventory,
        ambiguous_pins=ambiguous_outputs,
        part_ids=part_ids,
        values=values,
        footprints=footprints,
    )


def peer_signal_input_netlist(
    *,
    references: tuple[str, ...] = ("U1", "U2"),
    input_nets: tuple[str | None, ...] = ("SIGNAL_A", None),
    dnp: tuple[str, ...] = (),
    symbols: dict[str, str] | None = None,
    input_electrical_types: tuple[str, ...] | None = None,
    input_function: str = "IN",
    input_functions: tuple[str | None, ...] | None = None,
    missing_inventory: tuple[str, ...] = (),
    ambiguous_inputs: tuple[str, ...] = (),
) -> NetlistContract:
    return peer_component_pin_netlist(
        references=references,
        pin_nets=input_nets,
        dnp=dnp,
        symbols=symbols,
        default_symbol="Synthetic:SignalInputModule",
        pin_electrical_types=input_electrical_types or tuple("input" for _ in references),
        pin_function=input_function,
        pin_functions=input_functions,
        missing_inventory=missing_inventory,
        ambiguous_pins=ambiguous_inputs,
    )


def peer_bidirectional_netlist(
    *,
    references: tuple[str, ...] = ("U1", "U2"),
    pin_nets: tuple[str | None, ...] = ("DATA_A", None),
    dnp: tuple[str, ...] = (),
    symbols: dict[str, str] | None = None,
    electrical_types: tuple[str, ...] | None = None,
    pin_function: str = "DATA_IO",
    pin_functions: tuple[str | None, ...] | None = None,
    missing_inventory: tuple[str, ...] = (),
    ambiguous_pins: tuple[str, ...] = (),
) -> NetlistContract:
    return peer_component_pin_netlist(
        references=references,
        pin_nets=pin_nets,
        dnp=dnp,
        symbols=symbols,
        default_symbol="Synthetic:BidirectionalModule",
        pin_electrical_types=electrical_types or tuple("bidirectional" for _ in references),
        pin_function=pin_function,
        pin_functions=pin_functions,
        missing_inventory=missing_inventory,
        ambiguous_pins=ambiguous_pins,
    )


def lint_report(
    observed: NetlistContract,
    policy: DesignLintPolicy | None = None,
) -> DesignLintReport:
    serialized = observed.model_dump_json().encode("utf-8")
    coach = ContractCoachReport(
        status="READY_FOR_REVIEW",
        project_id="synthetic-peer-power-output",
        netlist_sha256=hashlib.sha256(serialized).hexdigest(),
        observed=observed,
    )
    return evaluate(coach.project_id, coach, policy or DesignLintPolicy())


def component_peer_coverage(report: DesignLintReport, rule_id: str):
    return next(item for item in report.component_peer_pin_coverage if item.rule_id == rule_id)


def test_reports_an_open_native_power_output_pin_when_an_exact_peer_is_connected() -> None:
    report = lint_report(peer_power_output_netlist())
    findings = [item for item in report.findings if item.rule_id == RULE_ID]

    assert report.status == "REVIEW"
    assert len(findings) == 1
    finding = findings[0]
    assert finding.mode == "review"
    assert finding.evidence["symbol"] == ("Synthetic:PowerModule",)
    assert finding.evidence["pin_number"] == ("2",)
    assert finding.evidence["pin_electrical_type"] == ("power_out",)
    assert finding.evidence["unassigned_pins"] == ("U2.2",)
    assert finding.evidence["U1.2"] == ("VOUT",)
    assert finding.evidence["U2.2"] == ()
    assert "do not require peer pins to share a net" in finding.message
    assert "component.unconnected_power_input" not in {item.rule_id for item in report.findings}
    coverage = component_peer_coverage(report, RULE_ID)
    assert coverage.status == "EVALUATED"
    assert coverage.netlist_sha256 == report.netlist_sha256
    assert coverage.exact_symbol_peer_group_count == 1
    assert coverage.complete_pin_inventory_group_count == 1
    assert coverage.comparable_pin_group_count == 2
    assert coverage.matching_electrical_type_pin_group_count == 1
    assert coverage.compatible_function_pin_group_count == 1
    assert coverage.unambiguous_assignment_pin_group_count == 1
    assert coverage.candidate_group_count == coverage.finding_count == 1
    assert coverage.suppressed_candidate_count == 0


def test_reports_open_pin_across_native_symbol_aliases_with_the_same_part_id() -> None:
    observed = peer_power_output_netlist(
        symbols={"U1": "Synthetic:PowerModule", "U2": "Synthetic:PowerModuleAlias"},
        part_ids={"U1": "synthetic-power-module-001", "U2": "SYNTHETIC-POWER-MODULE-001"},
    )
    report = lint_report(observed)
    findings = [item for item in report.findings if item.rule_id == RULE_ID]

    assert len(findings) == 1
    finding = findings[0]
    assert finding.evidence["peer_group_basis"] == ("part_id",)
    assert finding.evidence["peer_group_identity"] == ("SYNTHETIC-POWER-MODULE-001",)
    assert finding.evidence["peer_group_symbols"] == (
        "Synthetic:PowerModule",
        "Synthetic:PowerModuleAlias",
    )
    assert finding.evidence["unassigned_pins"] == ("U2.2",)
    assert "same native PART_ID" in finding.message
    coverage = component_peer_coverage(report, RULE_ID)
    assert coverage.status == "EVALUATED"
    assert coverage.exact_symbol_peer_group_count == 0
    assert coverage.part_id_peer_group_count == 1
    assert coverage.candidate_group_count == coverage.finding_count == 1
    assert coverage.deduplicated_candidate_group_count == 0
    reordered = lint_report(
        observed.model_copy(
            update={
                "components": dict(reversed(tuple(observed.components.items()))),
                "nets": dict(reversed(tuple(observed.nets.items()))),
                "component_symbols": dict(reversed(tuple(observed.component_symbols.items()))),
                "pin_functions": dict(reversed(tuple(observed.pin_functions.items()))),
                "pin_electrical_types": dict(
                    reversed(tuple(observed.pin_electrical_types.items()))
                ),
                "component_pin_numbers": dict(
                    reversed(tuple(observed.component_pin_numbers.items()))
                ),
            }
        )
    )
    reordered_finding = next(item for item in reordered.findings if item.rule_id == RULE_ID)
    assert (reordered_finding.fingerprint, reordered_finding.evidence) == (
        finding.fingerprint,
        finding.evidence,
    )


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
    from tests.synthetic_design_lint_project import (
        run_design_lint_cli,
        synthetic_design_lint_project,
    )
    from tests.test_peer_power_pin_assignment import peer_pin_netlist_xml

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


def test_reports_an_open_native_signal_output_pin_when_an_exact_peer_is_connected() -> None:
    report = lint_report(peer_power_output_netlist(output_electrical_types=("output", "output")))
    findings = [item for item in report.findings if item.rule_id == SIGNAL_RULE_ID]

    assert report.status == "REVIEW"
    assert len(findings) == 1
    finding = findings[0]
    assert finding.mode == "review"
    assert finding.evidence["symbol"] == ("Synthetic:PowerModule",)
    assert finding.evidence["pin_number"] == ("2",)
    assert finding.evidence["pin_electrical_type"] == ("output",)
    assert finding.evidence["unassigned_pins"] == ("U2.2",)
    assert finding.evidence["U1.2"] == ("VOUT",)
    assert finding.evidence["U2.2"] == ()
    assert "do not require peer pins to share a net" in finding.message
    assert RULE_ID not in {item.rule_id for item in report.findings}


def test_reports_an_open_native_signal_input_pin_when_an_exact_peer_is_connected() -> None:
    report = lint_report(peer_signal_input_netlist())
    findings = [item for item in report.findings if item.rule_id == INPUT_RULE_ID]

    assert report.status == "REVIEW"
    assert len(findings) == 1
    finding = findings[0]
    assert finding.mode == "review"
    assert finding.evidence["symbol"] == ("Synthetic:SignalInputModule",)
    assert finding.evidence["pin_number"] == ("2",)
    assert finding.evidence["pin_electrical_type"] == ("input",)
    assert finding.evidence["pin_function"] == ("IN",)
    assert finding.evidence["unassigned_pins"] == ("U2.2",)
    assert finding.evidence["U1.2"] == ("SIGNAL_A",)
    assert finding.evidence["U2.2"] == ()
    assert "do not require peer pins to share a net" in finding.message
    assert "control.unconnected_control_input" not in {item.rule_id for item in report.findings}


def test_reports_an_open_native_bidirectional_pin_when_an_exact_peer_is_connected() -> None:
    report = lint_report(
        peer_bidirectional_netlist(
            references=("U1", "U2", "U3"), pin_nets=("DATA_IO", "DATA_IO", None)
        )
    )
    findings = [item for item in report.findings if item.rule_id == BIDIRECTIONAL_RULE_ID]

    assert report.status == "REVIEW"
    assert len(findings) == 1
    finding = findings[0]
    assert finding.mode == "review"
    assert finding.evidence["symbol"] == ("Synthetic:BidirectionalModule",)
    assert finding.evidence["pin_number"] == ("2",)
    assert finding.evidence["pin_electrical_type"] == ("bidirectional",)
    assert finding.evidence["pin_function"] == ("DATA_IO",)
    assert finding.evidence["unassigned_pins"] == ("U3.2",)
    assert finding.evidence["U1.2"] == ("DATA_IO",)
    assert finding.evidence["U2.2"] == ("DATA_IO",)
    assert finding.evidence["U3.2"] == ()
    assert "do not require peer pins to share a net" in finding.message


@pytest.mark.parametrize(
    "output_nets",
    (("VOUT", "VOUT"), ("VOUT_A", "VOUT_B")),
)
def test_assigned_peer_outputs_are_valid_same_or_separate_net_controls(
    output_nets: tuple[str, str],
) -> None:
    report = lint_report(peer_power_output_netlist(output_nets=output_nets))

    assert RULE_ID not in {item.rule_id for item in report.findings}
    assert report.status == "PASS"


@pytest.mark.parametrize(
    "output_nets",
    (("VOUT", "VOUT"), ("VOUT_A", "VOUT_B")),
)
def test_assigned_signal_peer_outputs_are_valid_same_or_separate_net_controls(
    output_nets: tuple[str, str],
) -> None:
    report = lint_report(
        peer_power_output_netlist(
            output_nets=output_nets,
            output_electrical_types=("output", "output"),
        )
    )

    assert SIGNAL_RULE_ID not in {item.rule_id for item in report.findings}
    assert report.status == "PASS"


@pytest.mark.parametrize(
    "input_nets",
    (("SIGNAL", "SIGNAL"), ("SIGNAL_A", "SIGNAL_B")),
)
def test_assigned_signal_peer_inputs_are_valid_same_or_separate_net_controls(
    input_nets: tuple[str, str],
) -> None:
    report = lint_report(peer_signal_input_netlist(input_nets=input_nets))

    assert INPUT_RULE_ID not in {item.rule_id for item in report.findings}
    assert report.status == "PASS"


@pytest.mark.parametrize(
    "pin_nets",
    (("DATA_IO", "DATA_IO"), ("DATA_IO_A", "DATA_IO_B")),
)
def test_assigned_bidirectional_peers_are_valid_same_or_separate_net_controls(
    pin_nets: tuple[str, str],
) -> None:
    report = lint_report(peer_bidirectional_netlist(pin_nets=pin_nets))

    assert BIDIRECTIONAL_RULE_ID not in {item.rule_id for item in report.findings}
    assert report.status == "PASS"


@pytest.mark.parametrize(
    "observed",
    (
        peer_signal_input_netlist(input_nets=(None, None)),
        peer_signal_input_netlist(input_nets=("SIGNAL", None), dnp=("U2",)),
        peer_signal_input_netlist(
            input_nets=("SIGNAL", None),
            symbols={"U1": "Synthetic:SourceA", "U2": "Synthetic:SourceB"},
        ),
        peer_signal_input_netlist(input_nets=("SIGNAL", None), missing_inventory=("U2",)),
        peer_signal_input_netlist(input_nets=("SIGNAL", None), ambiguous_inputs=("U1",)),
        peer_signal_input_netlist(input_electrical_types=("input", "output")),
        peer_signal_input_netlist(input_functions=("DATA_IN", "DATA_OUT")),
        peer_signal_input_netlist(input_functions=(None, None)),
        peer_signal_input_netlist(input_functions=("IN", None)),
        peer_signal_input_netlist(input_electrical_types=("passive", "passive")),
        peer_signal_input_netlist(references=("J1", "J2")),
    ),
)
def test_signal_input_prompt_skips_open_or_incomplete_peer_evidence(
    observed: NetlistContract,
) -> None:
    assert INPUT_RULE_ID not in {item.rule_id for item in lint_report(observed).findings}


@pytest.mark.parametrize(
    "observed",
    (
        peer_bidirectional_netlist(pin_nets=(None, None)),
        peer_bidirectional_netlist(pin_nets=("DATA_IO", None), dnp=("U2",)),
        peer_bidirectional_netlist(
            pin_nets=("DATA_IO", None),
            symbols={"U1": "Synthetic:PeripheralA", "U2": "Synthetic:PeripheralB"},
        ),
        peer_bidirectional_netlist(pin_nets=("DATA_IO", None), missing_inventory=("U2",)),
        peer_bidirectional_netlist(pin_nets=("DATA_IO", None), ambiguous_pins=("U1",)),
        peer_bidirectional_netlist(electrical_types=("bidirectional", "input")),
        peer_bidirectional_netlist(electrical_types=("tri_state", "tri_state")),
        peer_bidirectional_netlist(pin_functions=(None, None)),
        peer_bidirectional_netlist(pin_functions=("DATA_IO", None)),
        peer_bidirectional_netlist(pin_functions=("DATA_IN", "DATA_OUT")),
        peer_bidirectional_netlist(references=("J1", "J2")),
    ),
)
def test_bidirectional_prompt_skips_open_or_incomplete_peer_evidence(
    observed: NetlistContract,
) -> None:
    assert BIDIRECTIONAL_RULE_ID not in {item.rule_id for item in lint_report(observed).findings}


@pytest.mark.parametrize(
    ("observed", "rule_id", "expected_status"),
    (
        pytest.param(
            peer_component_pin_netlist(symbols={"U1": "Synthetic:A", "U2": "Synthetic:B"}),
            RULE_ID,
            "NO_COMPARABLE_PEERS",
            id="different-symbols",
        ),
        pytest.param(
            peer_component_pin_netlist(missing_inventory=("U2",)),
            RULE_ID,
            "INCOMPLETE_PIN_INVENTORY",
            id="missing-inventory",
        ),
        pytest.param(
            peer_component_pin_netlist(pin_electrical_types=("input", "output")),
            RULE_ID,
            "NO_MATCHING_PIN_TYPES",
            id="nonmatching-native-types",
        ),
        pytest.param(
            peer_component_pin_netlist(
                pin_electrical_types=("input", "input"),
                pin_functions=(None, "IN"),
            ),
            INPUT_RULE_ID,
            "NO_COMPATIBLE_PIN_FUNCTIONS",
            id="missing-required-functions",
        ),
        pytest.param(
            peer_component_pin_netlist(ambiguous_pins=("U1",)),
            RULE_ID,
            "NO_UNAMBIGUOUS_ASSIGNMENTS",
            id="ambiguous-assignment",
        ),
        pytest.param(
            peer_component_pin_netlist(
                references=("U1", "U2", "U3", "U4"),
                pin_nets=("VOUT", None, "VOUT", None),
                symbols={
                    "U1": "Synthetic:Complete",
                    "U2": "Synthetic:Complete",
                    "U3": "Synthetic:Incomplete",
                    "U4": "Synthetic:Incomplete",
                },
                missing_inventory=("U4",),
            ),
            RULE_ID,
            "PARTIALLY_EVALUATED",
            id="mixed-complete-and-incomplete-groups",
        ),
        pytest.param(
            peer_component_pin_netlist(
                references=("U1", "U2", "U3", "U4"),
                pin_nets=("VOUT", None, "VOUT", None),
                symbols={
                    "U1": "Synthetic:Complete",
                    "U2": "Synthetic:Complete",
                    "U3": "Synthetic:AliasA",
                    "U4": "Synthetic:AliasB",
                },
                part_ids={"U3": "SYNTHETIC-PART", "U4": "synthetic-part"},
                footprints={"U3": "Synthetic:Module", "U4": "Synthetic:OtherModule"},
            ),
            RULE_ID,
            "PARTIALLY_EVALUATED",
            id="valid-exact-peer-group-with-ineligible-part-id-alias-group",
        ),
    ),
)
def test_component_peer_coverage_explains_applicability_and_skips(
    observed: NetlistContract, rule_id: str, expected_status: str
) -> None:
    report = lint_report(observed)
    coverage = component_peer_coverage(report, rule_id)

    assert coverage.status == expected_status
    assert coverage.netlist_sha256 == report.netlist_sha256
    assert coverage.finding_count == sum(item.rule_id == rule_id for item in report.findings)
    if expected_status == "PARTIALLY_EVALUATED":
        if coverage.part_id_candidate_group_count:
            assert coverage.exact_symbol_peer_group_count == 1
            assert coverage.complete_pin_inventory_group_count == 1
            assert coverage.incomplete_pin_inventory_group_count == 0
            assert coverage.part_id_incomplete_component_identity_references == ("U3", "U4")
        else:
            assert coverage.exact_symbol_peer_group_count == 2
            assert coverage.complete_pin_inventory_group_count == 1
            assert coverage.incomplete_pin_inventory_group_count == 1
            assert coverage.incomplete_pin_inventory_references == ("U3", "U4")
        assert coverage.candidate_group_count == coverage.finding_count == 1


def test_component_peer_coverage_records_control_input_suppression() -> None:
    report = lint_report(
        peer_component_pin_netlist(
            pin_electrical_types=("input", "input"),
            pin_function="RESET_B",
        )
    )
    coverage = component_peer_coverage(report, INPUT_RULE_ID)

    assert coverage.status == "EVALUATED"
    assert coverage.candidate_group_count == 1
    assert coverage.finding_count == 0
    assert coverage.suppressed_candidate_count == 1


def test_active_low_input_is_eligible_for_peer_review() -> None:
    report = lint_report(
        peer_signal_input_netlist(input_electrical_types=("input_low", "input_low"))
    )

    finding = next(item for item in report.findings if item.rule_id == INPUT_RULE_ID)
    assert finding.evidence["pin_electrical_type"] == ("input_low",)
    assert finding.evidence["unassigned_pins"] == ("U2.2",)


@pytest.mark.parametrize(
    ("input_function", "specific_rule"),
    (
        ("VDD", "component.unconnected_supply_pin"),
        ("GND", "component.unconnected_return_pin"),
        ("RESET_B", "control.unconnected_control_input"),
    ),
)
def test_specific_supply_return_and_control_inputs_keep_their_own_findings(
    input_function: str, specific_rule: str
) -> None:
    report = lint_report(peer_signal_input_netlist(input_function=input_function))
    findings = {item.rule_id: item for item in report.findings}

    assert INPUT_RULE_ID not in findings
    assert specific_rule in findings


@pytest.mark.parametrize(
    "observed",
    (
        peer_power_output_netlist(
            output_nets=(None, None), output_electrical_types=("output", "output")
        ),
        peer_power_output_netlist(
            output_nets=("VOUT", None),
            dnp=("U2",),
            output_electrical_types=("output", "output"),
        ),
        peer_power_output_netlist(
            output_nets=("VOUT", None),
            symbols={"U1": "Synthetic:SourceA", "U2": "Synthetic:SourceB"},
            output_electrical_types=("output", "output"),
        ),
        peer_power_output_netlist(
            output_nets=("VOUT", None),
            missing_inventory=("U2",),
            output_electrical_types=("output", "output"),
        ),
        peer_power_output_netlist(
            output_nets=("VOUT", None),
            ambiguous_outputs=("U1",),
            output_electrical_types=("output", "output"),
        ),
        peer_power_output_netlist(output_nets=("VOUT", None)),
    ),
)
def test_signal_output_prompt_skips_incomplete_or_non_signal_peer_evidence(
    observed: NetlistContract,
) -> None:
    assert SIGNAL_RULE_ID not in {item.rule_id for item in lint_report(observed).findings}


@pytest.mark.parametrize(
    "observed",
    (
        peer_power_output_netlist(output_nets=(None, None)),
        peer_power_output_netlist(output_nets=("VOUT", None), dnp=("U2",)),
        peer_power_output_netlist(
            output_nets=("VOUT", None),
            symbols={"U1": "Synthetic:SourceA", "U2": "Synthetic:SourceB"},
        ),
        peer_power_output_netlist(output_nets=("VOUT", None), missing_inventory=("U2",)),
        peer_power_output_netlist(output_nets=("VOUT", None), ambiguous_outputs=("U1",)),
        peer_power_output_netlist(
            output_nets=("VOUT", None), output_electrical_types=("power_in", "power_in")
        ),
    ),
)
def test_skips_open_all_dnp_different_symbol_incomplete_ambiguous_and_non_output_cases(
    observed: NetlistContract,
) -> None:
    assert RULE_ID not in {item.rule_id for item in lint_report(observed).findings}


@pytest.mark.parametrize("output_function", ("VDD", "GND"))
def test_named_supply_and_return_outputs_keep_their_specific_findings(
    output_function: str,
) -> None:
    report = lint_report(peer_power_output_netlist(output_function=output_function))
    findings = {item.rule_id: item for item in report.findings}

    assert RULE_ID not in findings
    specific_rule = (
        "component.unconnected_return_pin"
        if output_function == "GND"
        else "component.unconnected_supply_pin"
    )
    assert specific_rule in findings
    assert findings[specific_rule].evidence["U2.2"] == ()


def test_shield_named_power_output_remains_eligible_without_a_component_shield_rule() -> None:
    report = lint_report(peer_power_output_netlist(output_function="SHIELD"))
    findings = {item.rule_id: item for item in report.findings}

    assert RULE_ID in findings
    assert "component.unconnected_return_pin" not in findings
    assert findings[RULE_ID].evidence["unassigned_pins"] == ("U2.2",)


def test_rule_policy_and_exact_ignore_are_project_configurable() -> None:
    observed = peer_power_output_netlist()
    original = lint_report(observed)
    finding = next(item for item in original.findings if item.rule_id == RULE_ID)

    blocked = lint_report(
        observed,
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=RULE_ID,
                    mode="block",
                    reason="Synthetic project requires every peer output to be disposed",
                ),
            )
        ),
    )
    assert blocked.status == "FAIL"

    disabled = lint_report(
        observed,
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=RULE_ID,
                    mode="off",
                    reason="Synthetic project disables this peer-output prompt",
                ),
            )
        ),
    )
    assert disabled.status == "PASS"
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
                    reason="Synthetic project accepts the intentionally open peer output",
                ),
            )
        ),
    )
    ignored_finding = next(
        item for item in ignored.findings if item.fingerprint == finding.fingerprint
    )
    assert ignored_finding.disposition == "IGNORED"


def test_signal_output_review_supports_project_policy_and_exact_ignore() -> None:
    observed = peer_power_output_netlist(output_electrical_types=("output", "output"))
    original = lint_report(observed)
    finding = next(item for item in original.findings if item.rule_id == SIGNAL_RULE_ID)

    blocked = lint_report(
        observed,
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=SIGNAL_RULE_ID,
                    mode="block",
                    reason="Synthetic project requires a disposition for peer outputs",
                ),
            )
        ),
    )
    assert blocked.status == "FAIL"

    disabled = lint_report(
        observed,
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=SIGNAL_RULE_ID,
                    mode="off",
                    reason="Synthetic project disables the signal-output prompt",
                ),
            )
        ),
    )
    assert disabled.status == "PASS"

    ignored = lint_report(
        observed,
        DesignLintPolicy(
            ignores=(
                DesignLintIgnore(
                    rule_id=SIGNAL_RULE_ID,
                    fingerprint=finding.fingerprint,
                    reason="Synthetic project records this output as intentionally unused",
                ),
            )
        ),
    )
    ignored_finding = next(
        item for item in ignored.findings if item.fingerprint == finding.fingerprint
    )
    assert ignored_finding.disposition == "IGNORED"


def test_signal_input_review_supports_project_policy_and_exact_ignore() -> None:
    observed = peer_signal_input_netlist()
    original = lint_report(observed)
    finding = next(item for item in original.findings if item.rule_id == INPUT_RULE_ID)

    blocked = lint_report(
        observed,
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=INPUT_RULE_ID,
                    mode="block",
                    reason="Synthetic project requires a disposition for peer inputs",
                ),
            )
        ),
    )
    assert blocked.status == "FAIL"

    disabled = lint_report(
        observed,
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=INPUT_RULE_ID,
                    mode="off",
                    reason="Synthetic project disables the signal-input prompt",
                ),
            )
        ),
    )
    assert disabled.status == "PASS"

    ignored = lint_report(
        observed,
        DesignLintPolicy(
            ignores=(
                DesignLintIgnore(
                    rule_id=INPUT_RULE_ID,
                    fingerprint=finding.fingerprint,
                    reason="Synthetic project records this input as intentionally unused",
                ),
            )
        ),
    )
    ignored_finding = next(
        item for item in ignored.findings if item.fingerprint == finding.fingerprint
    )
    assert ignored_finding.disposition == "IGNORED"


def test_bidirectional_review_supports_project_policy_and_exact_ignore() -> None:
    observed = peer_bidirectional_netlist()
    original = lint_report(observed)
    finding = next(item for item in original.findings if item.rule_id == BIDIRECTIONAL_RULE_ID)

    blocked = lint_report(
        observed,
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=BIDIRECTIONAL_RULE_ID,
                    mode="block",
                    reason="Synthetic project requires review of open bidirectional peers",
                ),
            )
        ),
    )
    assert blocked.status == "FAIL"

    disabled = lint_report(
        observed,
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=BIDIRECTIONAL_RULE_ID,
                    mode="off",
                    reason="Synthetic project disables the peer bidirectional prompt",
                ),
            )
        ),
    )
    assert disabled.status == "PASS"

    ignored = lint_report(
        observed,
        DesignLintPolicy(
            ignores=(
                DesignLintIgnore(
                    rule_id=BIDIRECTIONAL_RULE_ID,
                    fingerprint=finding.fingerprint,
                    reason="Synthetic project records this peripheral pin as unused",
                ),
            )
        ),
    )
    ignored_finding = next(
        item for item in ignored.findings if item.fingerprint == finding.fingerprint
    )
    assert ignored_finding.disposition == "IGNORED"


def test_finding_is_stable_under_map_order_changes() -> None:
    source = peer_power_output_netlist()
    original = lint_report(source)
    reordered_source = source.model_copy(
        update={
            "components": dict(reversed(tuple(source.components.items()))),
            "nets": dict(reversed(tuple(source.nets.items()))),
            "component_symbols": dict(reversed(tuple(source.component_symbols.items()))),
            "pin_functions": dict(reversed(tuple(source.pin_functions.items()))),
            "pin_electrical_types": dict(reversed(tuple(source.pin_electrical_types.items()))),
            "component_pin_numbers": dict(reversed(tuple(source.component_pin_numbers.items()))),
        }
    )
    reordered = lint_report(reordered_source)
    original_findings = {
        item.subject: (item.fingerprint, item.evidence)
        for item in original.findings
        if item.rule_id == RULE_ID
    }
    reordered_findings = {
        item.subject: (item.fingerprint, item.evidence)
        for item in reordered.findings
        if item.rule_id == RULE_ID
    }

    assert reordered_findings == original_findings


def test_signal_output_finding_is_stable_under_map_order_changes() -> None:
    source = peer_power_output_netlist(output_electrical_types=("output", "output"))
    original = lint_report(source)
    reordered_source = source.model_copy(
        update={
            "components": dict(reversed(tuple(source.components.items()))),
            "nets": dict(reversed(tuple(source.nets.items()))),
            "component_symbols": dict(reversed(tuple(source.component_symbols.items()))),
            "pin_functions": dict(reversed(tuple(source.pin_functions.items()))),
            "pin_electrical_types": dict(reversed(tuple(source.pin_electrical_types.items()))),
            "component_pin_numbers": dict(reversed(tuple(source.component_pin_numbers.items()))),
        }
    )
    reordered = lint_report(reordered_source)

    def get_findings(report: DesignLintReport) -> dict[str, tuple[str, dict[str, tuple[str, ...]]]]:
        return {
            item.subject: (item.fingerprint, item.evidence)
            for item in report.findings
            if item.rule_id == SIGNAL_RULE_ID
        }

    assert get_findings(reordered) == get_findings(original)


def test_signal_input_finding_is_stable_under_map_order_changes() -> None:
    source = peer_signal_input_netlist()
    original = lint_report(source)
    reordered_source = source.model_copy(
        update={
            "components": dict(reversed(tuple(source.components.items()))),
            "nets": dict(reversed(tuple(source.nets.items()))),
            "component_symbols": dict(reversed(tuple(source.component_symbols.items()))),
            "pin_functions": dict(reversed(tuple(source.pin_functions.items()))),
            "pin_electrical_types": dict(reversed(tuple(source.pin_electrical_types.items()))),
            "component_pin_numbers": dict(reversed(tuple(source.component_pin_numbers.items()))),
        }
    )
    reordered = lint_report(reordered_source)

    def get_findings(report: DesignLintReport) -> dict[str, tuple[str, dict[str, tuple[str, ...]]]]:
        return {
            item.subject: (item.fingerprint, item.evidence)
            for item in report.findings
            if item.rule_id == INPUT_RULE_ID
        }

    assert get_findings(reordered) == get_findings(original)


def test_bidirectional_finding_is_stable_under_map_order_changes() -> None:
    source = peer_bidirectional_netlist()
    original = lint_report(source)
    reordered_source = source.model_copy(
        update={
            "components": dict(reversed(tuple(source.components.items()))),
            "nets": dict(reversed(tuple(source.nets.items()))),
            "component_symbols": dict(reversed(tuple(source.component_symbols.items()))),
            "pin_functions": dict(reversed(tuple(source.pin_functions.items()))),
            "pin_electrical_types": dict(reversed(tuple(source.pin_electrical_types.items()))),
            "component_pin_numbers": dict(reversed(tuple(source.component_pin_numbers.items()))),
        }
    )
    reordered = lint_report(reordered_source)

    def get_findings(report: DesignLintReport) -> dict[str, tuple[str, dict[str, tuple[str, ...]]]]:
        return {
            item.subject: (item.fingerprint, item.evidence)
            for item in report.findings
            if item.rule_id == BIDIRECTIONAL_RULE_ID
        }

    assert get_findings(reordered) == get_findings(original)


def test_native_fixture_sources_match_reviewed_digests() -> None:
    fixture_root = Path(__file__).resolve().parent / "fixtures/design_lint"
    expected = {
        "component-peer-power-output-native/control.kicad_sch": "3b41f81891115ae3e324694f46e41fbe44fb737c86555aa873333aa225b6f34b",
        "component-peer-power-output-native/fault.kicad_sch": "76cd57afa2e87980e9914a6508066e7197812bacd68241fe9e29ffd618bb9ff4",
        "component-peer-signal-output-native/control.kicad_sch": "bc5d93308322cd66b404bf058afde73b7b538e5590d84160d26b65af2e53f355",
        "component-peer-signal-output-native/fault.kicad_sch": "0d45eef6e2fc66da65781bb0e06d5c7601788aeb37489e60bf1302bfdad6a04a",
        "component-peer-signal-input-native/control.kicad_sch": "961527991bc45a4545bbf980a7540e81207c0012fa3fbe20772589970b507e15",
        "component-peer-signal-input-native/fault.kicad_sch": "9d3293d4c7d536549decad392096f118ad0f8cab6e62926572c9784f46f45275",
        "component-peer-bidirectional-native/control.kicad_sch": "1ea8f0a5b92fab8fafd0170adbe6b374f8bc9c24f38b00c00a0ceaafa70e2aa0",
        "component-peer-bidirectional-native/fault.kicad_sch": "5811d43e0298fb4bd8443bf849e8e75665e693561b4981786e768c0c895f4ea3",
    }

    assert {
        name: hashlib.sha256((fixture_root / name).read_bytes()).hexdigest() for name in expected
    } == expected


def test_power_output_native_fixture_readme_hashes_match_sources() -> None:
    fixture_dir = (
        Path(__file__).resolve().parent / "fixtures/design_lint/component-peer-power-output-native"
    )
    readme = (fixture_dir / "README.md").read_text(encoding="utf-8")
    for name in ("control.kicad_sch", "fault.kicad_sch"):
        digest = hashlib.sha256((fixture_dir / name).read_bytes()).hexdigest()
        assert f"- `{name}`: `{digest}`" in readme


def _run_native_peer_pin_assignment_lane(kind: str, base: Path) -> None:
    import json

    from kicad_tooling.ci_hosted import (
        HostedLog,
        component_peer_bidirectional_fixture_lane,
        component_peer_power_output_fixture_lane,
        component_peer_signal_input_fixture_lane,
        component_peer_signal_output_fixture_lane,
    )
    from kicad_tooling.hwrepo.electrical import selected_config
    from kicad_tooling.hwrepo.models import DesignLintPolicy
    from tests.synthetic_design_lint_project import (
        PINNED_NATIVE_KICAD_IMAGES,
        synthetic_design_lint_project,
    )

    expected_versions = {"controller": "10.0.0", "raspberry-pi-status-led": "10.0.5"}
    expected_images = {
        project: PINNED_NATIVE_KICAD_IMAGES[version]
        for project, version in expected_versions.items()
    }
    lanes = {
        "power": ("power-output", component_peer_power_output_fixture_lane),
        "signal": ("signal-output", component_peer_signal_output_fixture_lane),
        "signal-input": ("signal-input", component_peer_signal_input_fixture_lane),
        "bidirectional": ("bidirectional", component_peer_bidirectional_fixture_lane),
    }
    lane_kind, lane = lanes[kind]
    expected_peer_basis_counts = (0, 1) if kind == "power" else (1, 0)
    fixture_lane = f"component-peer-{lane_kind}-fixture"
    source_hashes = {
        "power": {
            "fault": "76cd57afa2e87980e9914a6508066e7197812bacd68241fe9e29ffd618bb9ff4",
            "control": "3b41f81891115ae3e324694f46e41fbe44fb737c86555aa873333aa225b6f34b",
        },
        "signal": {
            "fault": "0d45eef6e2fc66da65781bb0e06d5c7601788aeb37489e60bf1302bfdad6a04a",
            "control": "bc5d93308322cd66b404bf058afde73b7b538e5590d84160d26b65af2e53f355",
        },
        "signal-input": {
            "fault": "9d3293d4c7d536549decad392096f118ad0f8cab6e62926572c9784f46f45275",
            "control": "961527991bc45a4545bbf980a7540e81207c0012fa3fbe20772589970b507e15",
        },
        "bidirectional": {
            "fault": "5811d43e0298fb4bd8443bf849e8e75665e693561b4981786e768c0c895f4ea3",
            "control": "1ea8f0a5b92fab8fafd0170adbe6b374f8bc9c24f38b00c00a0ceaafa70e2aa0",
        },
    }[kind]
    for project, version in expected_versions.items():
        root, _ = synthetic_design_lint_project(
            base / project,
            DesignLintPolicy(),
            project_id=project,
            kicad_version=version,
            image=expected_images[project],
        )
        config = selected_config(root, project)
        assert config.kicad_version == version
        assert config.image == expected_images[project]
        log = HostedLog(root, f"native-peer-{kind}-{project}")
        lane(root, project=project, image=config.image, log=log)
        events = tuple(json.loads(line) for line in log.events.read_text().splitlines())
        results = {
            item["stage"]: item
            for item in events
            if item.get("stage", "").startswith(fixture_lane + "/")
        }
        assert set(results) == {
            f"{fixture_lane}/native-export",
            f"{fixture_lane}/fault",
            f"{fixture_lane}/control",
        }
        native = results[f"{fixture_lane}/native-export"]
        assert native["status"] == "PASS"
        assert native["kicad_version"] == version
        assert native["image"] == expected_images[project]
        for case, expected_pins, expected_status in (
            ("fault", "U2.2", "REVIEW"),
            ("control", "none", "PASS"),
        ):
            result = results[f"{fixture_lane}/{case}"]
            assert result["status"] == "PASS"
            assert result["source_sha256"] == source_hashes[case]
            assert result["lint_status"] == expected_status
            assert result["unassigned_pins"] == expected_pins
            assert result["repeatable"] == "true"
            assert result["normalized_netlist_sha256"] == result["repeat_normalized_netlist_sha256"]
            assert result["peer_coverage_status"] == "EVALUATED"
            assert result["peer_coverage_netlist_sha256"] == result["netlist_sha256"]
            assert result["peer_coverage_exact_symbol_group_count"] == expected_peer_basis_counts[0]
            assert result["peer_coverage_part_id_group_count"] == expected_peer_basis_counts[1]
            expected_count = int(case == "fault")
            assert result["peer_coverage_candidate_count"] == expected_count
            assert result["peer_coverage_deduplicated_candidate_count"] == 0
            assert result["peer_coverage_finding_count"] == expected_count
            assert result["peer_coverage_suppressed_count"] == 0


@pytest.mark.skipif(
    os.environ.get("KICAD_RUN_NATIVE_COMPONENT_PEER_PIN_FIXTURES") != "1",
    reason="pinned native fixtures run in package acceptance",
)
def test_peer_power_output_fault_and_control_on_pinned_native_versions(tmp_path: Path) -> None:
    _run_native_peer_pin_assignment_lane("power", tmp_path)


@pytest.mark.skipif(
    os.environ.get("KICAD_RUN_NATIVE_COMPONENT_PEER_PIN_FIXTURES") != "1",
    reason="pinned native fixtures run in package acceptance",
)
def test_peer_signal_output_fault_and_control_on_pinned_native_versions(tmp_path: Path) -> None:
    _run_native_peer_pin_assignment_lane("signal", tmp_path)


@pytest.mark.skipif(
    os.environ.get("KICAD_RUN_NATIVE_COMPONENT_PEER_PIN_FIXTURES") != "1",
    reason="pinned native fixtures run in package acceptance",
)
def test_peer_signal_input_fault_and_control_on_pinned_native_versions(tmp_path: Path) -> None:
    _run_native_peer_pin_assignment_lane("signal-input", tmp_path)


@pytest.mark.skipif(
    os.environ.get("KICAD_RUN_NATIVE_COMPONENT_PEER_PIN_FIXTURES") != "1",
    reason="pinned native fixtures run in package acceptance",
)
def test_peer_bidirectional_fault_and_control_on_pinned_native_versions(tmp_path: Path) -> None:
    _run_native_peer_pin_assignment_lane("bidirectional", tmp_path)
