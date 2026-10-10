"""Synthetic coverage for likely UART endpoints omitted from the peer map."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from kicad_tooling.hwrepo.contracts import read_model, write_model
from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.design_lint_project_contexts import serial_peer_roster_context
from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.models import (
    AnalysisPending,
    ComponentIdentity,
    DesignLintIgnore,
    DesignLintPolicy,
    DesignLintRuleOverride,
    ElectricalAnalysisContract,
    IgnoredChecks,
    ProjectConfig,
    ProjectKind,
    SchematicValidationContract,
    SerialPeerAnalysis,
)
from kicad_tooling.hwrepo.serial_participants import (
    SerialPeerRosterContext,
    unmapped_serial_peers,
)
from tests.serial_participant_support import coach, serial_netlist, serial_peers

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.interface_lint,
]


def test_unmapped_endpoints_are_deterministic_and_exact_mapped_pairs_clear() -> None:
    source = serial_netlist(dnp=("J4",))
    rule_id = "bus.serial_unmapped_peer"
    analysis = serial_peers()
    analysis_hash = hashlib.sha256(analysis.model_dump_json().encode("utf-8")).hexdigest()
    context = SerialPeerRosterContext(
        state="required",
        analysis=analysis,
        source_path="projects/synthetic-serial-roster/electrical.json",
        source_sha256=analysis_hash,
    )
    report = evaluate(
        "synthetic-serial-roster", coach(source), DesignLintPolicy(), serial_peer_roster=context
    )
    findings = [item for item in report.findings if item.rule_id == rule_id]
    assert tuple(item.subject for item in findings) == (
        "J3: serial-peer map coverage (UART)",
        "U1: serial-peer map coverage (UART2)",
        "U1: serial-peer map coverage (USART1)",
    )
    assert findings[0].evidence["TX_pins"] == ("J3.1",)
    assert findings[0].evidence["RX_pins"] == ("J3.2",)
    assert findings[0].evidence["serial_peer_map_state"] == ("required",)
    assert findings[0].evidence["electrical_contract_sha256"] == (analysis_hash,)

    reordered = source.model_copy(
        update={
            "components": dict(reversed(tuple(source.components.items()))),
            "nets": dict(reversed(tuple(source.nets.items()))),
            "component_symbols": dict(reversed(tuple(source.component_symbols.items()))),
            "pin_functions": dict(reversed(tuple(source.pin_functions.items()))),
            "component_pin_numbers": dict(reversed(tuple(source.component_pin_numbers.items()))),
        }
    )
    reordered_report = evaluate(
        "synthetic-serial-roster",
        coach(reordered),
        DesignLintPolicy(),
        serial_peer_roster=context,
    )
    reordered_findings = [item for item in reordered_report.findings if item.rule_id == rule_id]
    assert tuple((item.fingerprint, item.evidence) for item in reordered_findings) == tuple(
        (item.fingerprint, item.evidence) for item in findings
    )


@pytest.mark.parametrize(
    ("state", "expected_text"),
    (
        ("not_configured", "no configured project serial-peer map"),
        ("pending", "review remains pending"),
        ("not_applicable", "marked not applicable"),
    ),
)
def test_missing_map_and_pending_states_prompt_without_asserting_intent(
    state: str, expected_text: str
) -> None:
    source = serial_netlist(dnp=("J4",))
    context = SerialPeerRosterContext(state=state)
    report = evaluate(
        "synthetic-serial-roster",
        coach(source),
        DesignLintPolicy(),
        serial_peer_roster=context,
    )
    finding = next(
        item
        for item in report.findings
        if item.rule_id == "bus.serial_unmapped_peer" and item.subject.startswith("J1:")
    )
    assert expected_text in finding.message
    assert "does not assert that a peer or connection is required" in finding.message


def test_authored_external_peers_clear_singleton_uart_coverage_prompts() -> None:
    source = serial_netlist()
    map_path = (
        Path(__file__).parent
        / "fixtures/design_lint/serial-peer-native/peer-map-with-offboard-endpoints.json"
    )
    analysis = read_model(map_path, SerialPeerAnalysis)
    context = SerialPeerRosterContext(
        state="required",
        analysis=analysis,
        source_path=map_path.as_posix(),
        source_sha256=hashlib.sha256(map_path.read_bytes()).hexdigest(),
    )

    report = evaluate(
        "synthetic-serial-roster",
        coach(source),
        DesignLintPolicy(),
        serial_peer_roster=context,
    )

    findings = tuple(item for item in report.findings if item.rule_id == "bus.serial_unmapped_peer")
    assert findings
    assert not any(item.subject.startswith(("J1:", "J2:", "J3:", "J4:")) for item in findings)
    assert {item.subject for item in findings} == {
        "U1: serial-peer map coverage (UART2)",
        "U1: serial-peer map coverage (USART1)",
    }


def test_rule_mode_and_exact_ignore_remain_project_configurable() -> None:
    source = serial_netlist(dnp=("J4",))
    review = evaluate("synthetic-serial-roster", coach(source), DesignLintPolicy())
    finding = next(item for item in review.findings if item.rule_id == "bus.serial_unmapped_peer")
    assert finding.mode == "review"

    blocked = evaluate(
        "synthetic-serial-roster",
        coach(source),
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=finding.rule_id,
                    mode="block",
                    reason="Synthetic project requires each logic-level UART endpoint to be mapped",
                ),
            )
        ),
    )
    assert blocked.status == "FAIL"

    ignored = evaluate(
        "synthetic-serial-roster",
        coach(source),
        DesignLintPolicy(
            ignores=(
                DesignLintIgnore(
                    rule_id=finding.rule_id,
                    fingerprint=finding.fingerprint,
                    reason="Synthetic endpoint is intentionally unused",
                ),
            )
        ),
    )
    ignored_finding = next(
        item
        for item in ignored.findings
        if item.rule_id == finding.rule_id and item.fingerprint == finding.fingerprint
    )
    assert ignored_finding.disposition == "IGNORED"


def test_contract_loader_hash_binds_serial_peer_roster(tmp_path: Path) -> None:
    root = tmp_path.resolve()
    contract_path = root / "projects/synthetic-serial-roster/electrical.json"
    contract = ElectricalAnalysisContract(
        project_id="synthetic-serial-roster",
        ngspice_version="synthetic",
        grounding=AnalysisPending(reason="Synthetic grounding review pending."),
        power=AnalysisPending(reason="Synthetic power review pending."),
        high_frequency=AnalysisPending(reason="Synthetic frequency review pending."),
        serial_peers=serial_peers(),
    )
    contract_path.parent.mkdir(parents=True)
    write_model(contract_path, contract)
    source_sha256 = digest(contract_path)
    config = ProjectConfig(
        schema_version="1",
        kind=ProjectKind.SCHEMATIC,
        assurance_profile="development",
        not_for_manufacture=True,
        project_id="synthetic-serial-roster",
        component_identity=ComponentIdentity(required=False, part_ids=()),
        toolchain_id="synthetic-kicad-10",
        kicad_version="10.0.6",
        image="example.invalid/kicad@sha256:" + "c" * 64,
        project="projects/synthetic-serial-roster/design.kicad_pro",
        source_roots=(),
        required_inputs=(),
        validation=SchematicValidationContract(
            kind=ProjectKind.SCHEMATIC,
            expected_ignored_checks=IgnoredChecks(erc=(), drc=()),
        ),
        electrical="projects/synthetic-serial-roster/electrical.json",
    )
    context = serial_peer_roster_context(root, config)

    assert context.state == "required"
    assert context.analysis == contract.serial_peers
    assert context.source_path == "projects/synthetic-serial-roster/electrical.json"
    assert context.source_sha256 == source_sha256


def test_dnp_ambiguous_and_differential_function_pairs_are_excluded() -> None:
    observed = serial_netlist(dnp=("J4",)).model_copy(
        update={
            "nets": {
                **serial_netlist(dnp=("J4",)).nets,
                "AMBIGUOUS": ("J3.1",),
            }
        }
    )
    candidates = unmapped_serial_peers(observed, SerialPeerRosterContext(state="not_configured"))
    found = {(item.reference, item.channel) for item in candidates}
    assert ("J4", "TX/RX") not in found
    assert ("U1", "channel 1") not in found
    assert found == {("J1", "TX/RX"), ("J2", "TX/RX"), ("U1", "USART1"), ("U1", "UART2")}
