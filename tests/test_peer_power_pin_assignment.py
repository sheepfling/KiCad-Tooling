"""Pytest regressions for source-bound peer power-pin assignment review."""

from __future__ import annotations

import hashlib
import os
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.models import (
    ComponentContract,
    ContractCoachReport,
    DesignLintIgnore,
    DesignLintPolicy,
    DesignLintReport,
    DesignLintRuleOverride,
    NetlistContract,
)

RULE_ID = "component.peer_power_pin_assignment_divergence"


def peer_power_netlist(
    *,
    references: tuple[str, ...] = ("U1", "U2"),
    symbols: dict[str, str] | None = None,
    part_ids: dict[str, str] | None = None,
    values: dict[str, str] | None = None,
    footprints: dict[str, str] | None = None,
    supply_nets: tuple[str | None, ...] = ("+3V3", "+5V"),
    return_nets: tuple[str | None, ...] = ("GND", "AGND"),
    pin_functions: dict[str, tuple[str, str]] | None = None,
    pin_types: dict[str, tuple[str, str]] | None = None,
    incomplete_inventory: tuple[str, ...] = (),
    ambiguous_pins: tuple[str, ...] = (),
    dnp: tuple[str, ...] = (),
) -> NetlistContract:
    if len(references) != len(supply_nets) or len(references) != len(return_nets):
        raise ValueError("Each component needs one supply and return assignment")
    symbols = symbols or {
        reference: f"Synthetic:PowerModuleAlias{index}"
        for index, reference in enumerate(references, start=1)
    }
    part_ids = part_ids or {}
    values = values or {}
    footprints = footprints or {}
    pin_functions = pin_functions or {reference: ("VDD", "GND") for reference in references}
    pin_types = pin_types or {reference: ("power_in", "power_in") for reference in references}
    components = {
        reference: ComponentContract(
            value=values.get(reference, "Synthetic power module"),
            footprint=footprints.get(reference, "Package:SyntheticPower"),
            part_id=part_ids.get(reference),
        )
        for reference in references
    }
    nets: dict[str, tuple[str, ...]] = {}
    for reference, supply_net, return_net in zip(references, supply_nets, return_nets, strict=True):
        for pin_number, net in (("1", supply_net), ("2", return_net)):
            pin = f"{reference}.{pin_number}"
            if net is not None:
                nets[net] = (*nets.get(net, ()), pin)
            if pin in ambiguous_pins:
                nets[f"ALSO_{pin}"] = (pin,)
    return NetlistContract(
        components=components,
        nets=nets,
        dnp_components=dnp,
        component_symbols=symbols,
        component_pin_numbers={
            reference: ("1", "2")
            for reference in references
            if reference not in incomplete_inventory
        },
        pin_functions={
            f"{reference}.{pin_number}": function
            for reference in references
            for pin_number, function in enumerate(pin_functions[reference], start=1)
        },
        pin_electrical_types={
            f"{reference}.{pin_number}": electrical_type
            for reference in references
            for pin_number, electrical_type in enumerate(pin_types[reference], start=1)
        },
    )


def lint_report(
    observed: NetlistContract, policy: DesignLintPolicy | None = None
) -> DesignLintReport:
    netlist_sha256 = hashlib.sha256(observed.model_dump_json().encode("utf-8")).hexdigest()
    coach = ContractCoachReport(
        status="READY_FOR_REVIEW",
        project_id="synthetic-peer-power-pin-assignment",
        observed=observed,
        netlist_sha256=netlist_sha256,
    )
    return evaluate(coach.project_id, coach, policy or DesignLintPolicy())


def test_exact_symbol_power_assignment_fault_and_valid_controls() -> None:
    same_symbol = {
        "U1": "Synthetic:PowerPeer",
        "U2": "Synthetic:PowerPeer",
    }
    fault = peer_power_netlist(symbols=same_symbol)

    report = lint_report(fault)
    findings = [item for item in report.findings if item.rule_id == RULE_ID]

    assert len(findings) == 2
    assert {item.evidence["peer_role"][0] for item in findings} == {
        "ground/return",
        "supply",
    }
    return_finding = next(
        item for item in findings if item.evidence["peer_role"] == ("ground/return",)
    )
    assert return_finding.evidence["U1.2"] == ("GND",)
    assert return_finding.evidence["U2.2"] == ("AGND",)
    assert "intentionally separate" in return_finding.message

    controls = (
        peer_power_netlist(
            symbols=same_symbol,
            supply_nets=("+3V3", "+3V3"),
            return_nets=("GND", "GND"),
        ),
        peer_power_netlist(symbols=same_symbol, dnp=("U2",)),
        peer_power_netlist(symbols={"U1": "Synthetic:PowerPeer", "U2": "Synthetic:OtherPowerPeer"}),
    )
    for control in controls:
        assert RULE_ID not in {item.rule_id for item in lint_report(control).findings}

    open_return = peer_power_netlist(
        symbols=same_symbol,
        supply_nets=("+3V3", "+3V3"),
        return_nets=("GND", None),
    )
    open_findings = {item.rule_id for item in lint_report(open_return).findings}
    assert RULE_ID not in open_findings
    assert "component.unconnected_return_pin" in open_findings


def test_exact_symbol_power_assignment_obeys_policy_and_ignore_lifecycle() -> None:
    source = peer_power_netlist(
        symbols={"U1": "Synthetic:PowerPeer", "U2": "Synthetic:PowerPeer"},
        supply_nets=("+3V3", "+3V3"),
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
                    reason="Synthetic project requires reviewed peer return domains",
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
                    reason="Synthetic isolation control is explicitly reviewed",
                ),
            )
        ),
    )
    off_finding = next(item for item in off.findings if item.rule_id == RULE_ID)
    assert off_finding.disposition == "RULE_OFF"

    ignored_policy = DesignLintPolicy(
        ignores=(
            DesignLintIgnore(
                rule_id=RULE_ID,
                fingerprint=finding.fingerprint,
                reason="Synthetic return-domain isolation is intentional",
            ),
        )
    )
    ignored = lint_report(source, ignored_policy)
    ignored_finding = next(item for item in ignored.findings if item.rule_id == RULE_ID)
    assert ignored_finding.disposition == "IGNORED"

    changed_source = source.model_copy(
        update={"nets": {"+3V3": ("U1.1", "U2.1"), "GND": ("U1.2",), "CHASSIS": ("U2.2",)}}
    )
    stale = lint_report(changed_source, ignored_policy)
    assert stale.status == "REVIEW"
    assert stale.stale_ignores == ignored_policy.ignores


def test_exact_symbol_power_assignment_is_stable_under_mapping_order() -> None:
    source = peer_power_netlist(symbols={"U1": "Synthetic:PowerPeer", "U2": "Synthetic:PowerPeer"})
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
    findings = [item for item in lint_report(source).findings if item.rule_id == RULE_ID]
    reordered_findings = [
        item for item in lint_report(reordered).findings if item.rule_id == RULE_ID
    ]

    assert [(item.evidence, item.fingerprint) for item in reordered_findings] == [
        (item.evidence, item.fingerprint) for item in findings
    ]

    commoned = peer_power_netlist(
        symbols={"U1": "Synthetic:PowerPeer", "U2": "Synthetic:PowerPeer"},
        supply_nets=("+3V3", "+3V3"),
        return_nets=("GND", "GND"),
    )
    assert RULE_ID not in {item.rule_id for item in lint_report(commoned).findings}


def test_shared_part_id_symbol_aliases_prompt_for_split_power_and_return_assignments() -> None:
    observed = peer_power_netlist(
        part_ids={"U1": "SYNTHETIC-POWER-001", "U2": "synthetic-power-001"}
    )

    report = lint_report(observed)
    findings = [item for item in report.findings if item.rule_id == RULE_ID]

    assert report.status == "REVIEW"
    assert len(findings) == 2
    assert {item.evidence["peer_role"] for item in findings} == {
        ("ground/return",),
        ("supply",),
    }
    for finding in findings:
        assert finding.mode == "review"
        assert finding.evidence["peer_identity_basis"] == ("part_id",)
        assert finding.evidence["peer_identity"] == ("SYNTHETIC-POWER-001",)
        assert finding.evidence["peer_symbols"] == (
            "Synthetic:PowerModuleAlias1",
            "Synthetic:PowerModuleAlias2",
        )
        assert "do not prove the nets should be common" in finding.message


def test_common_power_and_return_assignments_clear_part_id_peer_prompts() -> None:
    observed = peer_power_netlist(
        part_ids={"U1": "SYNTHETIC-POWER-001", "U2": "SYNTHETIC-POWER-001"},
        supply_nets=("+3V3", "+3V3"),
        return_nets=("GND", "GND"),
    )

    report = lint_report(observed)

    assert RULE_ID not in {item.rule_id for item in report.findings}


def test_shared_part_id_group_covers_exact_symbol_subgroups_once() -> None:
    observed = peer_power_netlist(
        references=("U1", "U2", "U3"),
        symbols={
            "U1": "Synthetic:PowerModuleA",
            "U2": "Synthetic:PowerModuleA",
            "U3": "Synthetic:PowerModuleB",
        },
        part_ids={
            "U1": "SYNTHETIC-POWER-001",
            "U2": "SYNTHETIC-POWER-001",
            "U3": "SYNTHETIC-POWER-001",
        },
        supply_nets=("+3V3", "+3V3", "+5V"),
        return_nets=("GND", "GND", "AGND"),
    )

    report = lint_report(observed)
    findings = [item for item in report.findings if item.rule_id == RULE_ID]

    assert len(findings) == 2
    assert {item.evidence["peer_role"] for item in findings} == {
        ("ground/return",),
        ("supply",),
    }
    for finding in findings:
        pin_number = "1" if finding.evidence["peer_role"] == ("supply",) else "2"
        assert all(f"U{reference}.{pin_number}" in finding.evidence for reference in range(1, 4))
    assert all(item.evidence["peer_identity_basis"] == ("part_id",) for item in findings)


def test_part_id_peer_findings_are_stable_under_input_mapping_order() -> None:
    observed = peer_power_netlist(
        part_ids={"U1": "SYNTHETIC-POWER-001", "U2": "SYNTHETIC-POWER-001"}
    )
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

    original_findings = [item for item in lint_report(observed).findings if item.rule_id == RULE_ID]
    reordered_findings = [
        item for item in lint_report(reordered).findings if item.rule_id == RULE_ID
    ]

    assert [(item.evidence, item.fingerprint) for item in reordered_findings] == [
        (item.evidence, item.fingerprint) for item in original_findings
    ]


@pytest.mark.parametrize(
    "changes",
    (
        pytest.param({"part_ids": {}}, id="missing-part-id"),
        pytest.param(
            {"part_ids": {"U1": "SYNTHETIC-1", "U2": "SYNTHETIC-2"}},
            id="different-part-ids",
        ),
        pytest.param(
            {
                "part_ids": {"U1": "SYNTHETIC-1", "U2": "SYNTHETIC-1"},
                "values": {"U2": "Different value"},
            },
            id="different-values",
        ),
        pytest.param(
            {
                "part_ids": {"U1": "SYNTHETIC-1", "U2": "SYNTHETIC-1"},
                "footprints": {"U2": "Package:Different"},
            },
            id="different-footprints",
        ),
        pytest.param(
            {
                "part_ids": {"U1": "SYNTHETIC-1", "U2": "SYNTHETIC-1"},
                "incomplete_inventory": ("U2",),
            },
            id="incomplete-inventory",
        ),
        pytest.param(
            {
                "part_ids": {"U1": "SYNTHETIC-1", "U2": "SYNTHETIC-1"},
                "pin_functions": {"U1": ("VDD", "GND"), "U2": ("AVDD", "GND")},
            },
            id="different-pin-function",
        ),
        pytest.param(
            {
                "part_ids": {"U1": "SYNTHETIC-1", "U2": "SYNTHETIC-1"},
                "pin_types": {
                    "U1": ("power_in", "power_in"),
                    "U2": ("power_in", "passive"),
                },
            },
            id="different-pin-type",
        ),
        pytest.param(
            {
                "part_ids": {"U1": "SYNTHETIC-1", "U2": "SYNTHETIC-1"},
                "dnp": ("U2",),
            },
            id="dnp-peer",
        ),
        pytest.param(
            {
                "part_ids": {"U1": "SYNTHETIC-1", "U2": "SYNTHETIC-1"},
                "supply_nets": ("+3V3", None),
                "return_nets": ("GND", "GND"),
            },
            id="open-power-pin",
        ),
    ),
)
def test_part_id_alias_comparison_requires_complete_matching_peer_identity(
    changes: dict[str, object],
) -> None:
    defaults: dict[str, object] = {"part_ids": {"U1": "SYNTHETIC-1", "U2": "SYNTHETIC-1"}}
    defaults.update(changes)

    report = lint_report(peer_power_netlist(**defaults))

    assert RULE_ID not in {item.rule_id for item in report.findings}


def test_ambiguous_net_assignment_is_not_compared_as_peer_divergence() -> None:
    observed = peer_power_netlist(
        part_ids={"U1": "SYNTHETIC-1", "U2": "SYNTHETIC-1"},
        supply_nets=("+3V3", "+3V3"),
        return_nets=("GND", "GND"),
        ambiguous_pins=("U2.2",),
    )

    report = lint_report(observed)

    assert RULE_ID not in {item.rule_id for item in report.findings}


def peer_pin_netlist_xml(observed: NetlistContract) -> str:
    root = ET.Element("export")
    components = ET.SubElement(root, "components")
    libparts: dict[tuple[str, str], dict[str, tuple[str, str]]] = {}
    for reference, component in sorted(observed.components.items()):
        library, part = observed.component_symbols[reference].split(":", maxsplit=1)
        entry = ET.SubElement(components, "comp", ref=reference)
        ET.SubElement(entry, "value").text = component.value
        ET.SubElement(entry, "footprint").text = component.footprint
        if component.part_id is not None:
            fields = ET.SubElement(entry, "fields")
            ET.SubElement(fields, "field", name="PART_ID").text = component.part_id
        ET.SubElement(entry, "libsource", lib=library, part=part)
        pins = ET.SubElement(ET.SubElement(ET.SubElement(entry, "units"), "unit", name="A"), "pins")
        libpart = libparts.setdefault((library, part), {})
        for number in observed.component_pin_numbers[reference]:
            ET.SubElement(pins, "pin", num=number)
            pin = f"{reference}.{number}"
            libpart[number] = (
                observed.pin_functions.get(pin, number),
                observed.pin_electrical_types.get(pin, "passive"),
            )

    libparts_element = ET.SubElement(root, "libparts")
    for (library, part), pins in sorted(libparts.items()):
        libpart = ET.SubElement(libparts_element, "libpart", lib=library, part=part)
        pin_elements = ET.SubElement(libpart, "pins")
        for number, (function, electrical_type) in sorted(pins.items()):
            ET.SubElement(
                pin_elements,
                "pin",
                num=number,
                name=function,
                type=electrical_type,
            )

    nets = ET.SubElement(root, "nets")
    for net_name, assignments in sorted(observed.nets.items()):
        net = ET.SubElement(nets, "net", name=net_name)
        for pin in assignments:
            reference, number = pin.rsplit(".", maxsplit=1)
            ET.SubElement(net, "node", ref=reference, pin=number)
    return ET.tostring(root, encoding="unicode")


def test_shared_part_id_power_assignment_matches_between_cli_and_mcp(tmp_path: Path) -> None:
    import asyncio
    import json

    from mcp import Client

    from kicad_tooling.hwrepo.contracts import read_model, write_model
    from kicad_tooling.hwrepo.evidence import digest
    from kicad_tooling.hwrepo.mcp_server import create_server
    from kicad_tooling.hwrepo.models import ValidationSummary
    from tests.synthetic_design_lint_project import (
        run_design_lint_cli,
        synthetic_design_lint_project,
    )

    root, summary_path = synthetic_design_lint_project(tmp_path, DesignLintPolicy())
    netlist_path = summary_path.parent / "netlist.xml"
    summary = read_model(summary_path, ValidationSummary)
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
        assert cli_report == mcp_report
        assert cli_report.status == "REVIEW"
        findings = [item for item in cli_report.findings if item.rule_id == RULE_ID]
        assert {item.evidence["peer_role"][0] for item in findings} == expected_roles


def test_native_fixture_sources_match_reviewed_digests() -> None:
    fixture_root = (
        Path(__file__).resolve().parent
        / "fixtures/design_lint/component-peer-power-assignment-native"
    )
    expected = {
        "fault.kicad_sch": "2e4bc0c9f883e948660b1982a7ccae888c18c3b52b9ae285b878666a7353c4c6",
        "control.kicad_sch": "23fec400e1e0a0581abc650a7d108512948d5d0b14744a276ebabc75a94be67d",
    }

    assert {
        filename: hashlib.sha256((fixture_root / filename).read_bytes()).hexdigest()
        for filename in expected
    } == expected


def _run_native_part_id_peer_power_assignment_lane(base: Path) -> None:
    import json

    from kicad_tooling.ci_hosted import HostedLog, component_peer_power_assignment_fixture_lane
    from kicad_tooling.hwrepo.electrical import selected_config
    from tests.synthetic_design_lint_project import synthetic_design_lint_project

    expected_projects = {
        "controller": (
            "10.0.0",
            (
                "ghcr.io/kicad/kicad:10.0.0@sha256:"
                "9549d3a08e0822f9434a9eda0782c812451ab4a733c73535f9e8beed42039bc3"
            ),
        ),
        "raspberry-pi-status-led": (
            "10.0.5",
            (
                "ghcr.io/kicad/kicad:10.0.5@sha256:"
                "fdcfa0e8d41f640d16edfb28e027fe8862ab31af9e45dcacbc662cec5c916e4c"
            ),
        ),
    }
    source_hashes = {
        "fault": "2e4bc0c9f883e948660b1982a7ccae888c18c3b52b9ae285b878666a7353c4c6",
        "control": "23fec400e1e0a0581abc650a7d108512948d5d0b14744a276ebabc75a94be67d",
    }
    fixture_lane = "component-peer-power-assignment-fixture"

    for project, (version, image) in expected_projects.items():
        root, _ = synthetic_design_lint_project(
            base / project,
            DesignLintPolicy(),
            project_id=project,
            kicad_version=version,
            image=image,
        )
        config = selected_config(root, project)
        assert config.kicad_version == version
        assert config.image == image
        log = HostedLog(root, f"native-peer-power-assignment-{project}")
        component_peer_power_assignment_fixture_lane(
            root, project=project, image=config.image, log=log
        )
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
        assert native["image"] == image

        for case, expected_findings, expected_status, decoupling_nets in (
            ("fault", "ground/return;supply", "REVIEW", "SYNTHETIC_NET_A;SYNTHETIC_NET_B"),
            ("control", "none", "REVIEW", "SYNTHETIC_NET_1"),
        ):
            result = results[f"{fixture_lane}/{case}"]
            assert result["status"] == "PASS"
            assert result["source_sha256"] == source_hashes[case]
            assert result["lint_status"] == expected_status
            assert result["peer_power_findings"] == expected_findings
            assert result["independent_decoupling_findings"] == decoupling_nets
            assert result["repeatable"] == "true"
            assert result["normalized_netlist_sha256"] == result["repeat_normalized_netlist_sha256"]


@pytest.mark.skipif(
    os.environ.get("KICAD_RUN_NATIVE_COMPONENT_PEER_PIN_FIXTURES") != "1",
    reason="pinned native fixtures run in package acceptance",
)
def test_part_id_peer_power_assignment_fault_and_control_on_pinned_native_versions(
    tmp_path: Path,
) -> None:
    _run_native_part_id_peer_power_assignment_lane(tmp_path)
