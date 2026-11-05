"""Guard typed source evidence for the distinct MOSFET gate reviews."""

from __future__ import annotations

import ast
from dataclasses import replace

import pytest

from kicad_tooling.hwrepo.component_mosfet_gate_drive import (
    mosfets_with_direct_output_gate_drive,
)
from kicad_tooling.hwrepo.design_lint_mosfet_gate_candidate_evidence import (
    MosfetGateCandidate,
    MosfetGateDirectDriveEvidence,
    MosfetGateWithoutPeerEvidence,
    MosfetGateWithoutSourceBiasEvidence,
    project_mosfet_gate_candidate_evidence,
)
from kicad_tooling.hwrepo.mosfet_gate_connectivity import (
    mosfet_gates_without_peer,
    mosfet_gates_without_visible_source_bias,
)
from tests.design_lint_fixtures.mosfet_gate_direct_drive import netlist as direct_drive_netlist
from tests.design_lint_fixtures.mosfet_gate_source_bias import netlist as source_bias_netlist
from tests.lint_architecture_support import HWREPO, IMPLEMENTATION_MAX_LINES, line_count
from tests.test_mosfet_gate_connectivity import mosfet_netlist

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.component_lint,
    pytest.mark.architecture,
    pytest.mark.evidence_lint,
]


def test_no_peer_candidate_retains_current_gate_evidence() -> None:
    observed = mosfet_netlist()
    (candidate,) = mosfet_gates_without_peer(observed)

    assert isinstance(candidate, MosfetGateCandidate)
    assert isinstance(candidate.source_evidence, MosfetGateWithoutPeerEvidence)
    assert candidate.source_evidence.device.observed is observed
    assert (
        candidate.evidence
        == project_mosfet_gate_candidate_evidence(candidate.source_evidence).evidence
    )


def test_source_bias_candidate_retains_current_peer_and_resistor_evidence() -> None:
    observed = source_bias_netlist()
    (candidate,) = mosfet_gates_without_visible_source_bias(observed)

    assert isinstance(candidate, MosfetGateCandidate)
    assert isinstance(candidate.source_evidence, MosfetGateWithoutSourceBiasEvidence)
    assert candidate.source_evidence.device.observed is observed
    assert candidate.source_evidence.fitted_gate_peers == ("U1.1",)
    assert candidate.source_evidence.visible_source_bias_resistors == ()
    assert (
        candidate.evidence
        == project_mosfet_gate_candidate_evidence(candidate.source_evidence).evidence
    )


def test_direct_drive_candidate_retains_current_output_peer_evidence() -> None:
    observed = direct_drive_netlist()
    (candidate,) = mosfets_with_direct_output_gate_drive(observed)

    assert isinstance(candidate, MosfetGateCandidate)
    assert isinstance(candidate.source_evidence, MosfetGateDirectDriveEvidence)
    assert candidate.source_evidence.device.observed is observed
    assert candidate.source_evidence.output_pins == ("U1.1",)
    assert candidate.source_evidence.output_pin_types == ("U1.1=output",)
    assert (
        candidate.evidence
        == project_mosfet_gate_candidate_evidence(candidate.source_evidence).evidence
    )


def test_no_peer_source_rejects_a_new_fitted_gate_peer() -> None:
    (candidate,) = mosfet_gates_without_peer(mosfet_netlist())
    assert isinstance(candidate, MosfetGateCandidate)
    assert isinstance(candidate.source_evidence, MosfetGateWithoutPeerEvidence)
    source = candidate.source_evidence
    peer_added = mosfet_netlist(gate_net_members=("U1.1",))
    updated_device = replace(source.device, observed=peer_added)

    with pytest.raises(ValueError, match="assignment must match"):
        replace(source, device=updated_device)


def test_source_bias_evidence_rejects_a_new_direct_resistor() -> None:
    (candidate,) = mosfet_gates_without_visible_source_bias(source_bias_netlist())
    assert isinstance(candidate, MosfetGateCandidate)
    assert isinstance(candidate.source_evidence, MosfetGateWithoutSourceBiasEvidence)
    source = candidate.source_evidence
    biased = source_bias_netlist(resistor_value="100k")
    updated_device = replace(source.device, observed=biased)

    with pytest.raises(ValueError, match="no direct visible resistor"):
        replace(source, device=updated_device, fitted_gate_peers=("R1.1", "U1.1"))


def test_direct_drive_evidence_rejects_an_output_peer_that_is_no_longer_capable() -> None:
    (candidate,) = mosfets_with_direct_output_gate_drive(direct_drive_netlist())
    assert isinstance(candidate, MosfetGateCandidate)
    assert isinstance(candidate.source_evidence, MosfetGateDirectDriveEvidence)
    source = candidate.source_evidence
    changed = direct_drive_netlist(driver_type="input")
    updated_device = replace(source.device, observed=changed)

    with pytest.raises(ValueError, match="output-capable fitted peer"):
        replace(source, device=updated_device)


def test_mosfet_gate_routes_use_one_theme_evidence_projector() -> None:
    route = HWREPO / "mosfet_gate_connectivity.py"
    direct_drive_route = HWREPO / "component_mosfet_gate_drive.py"
    owner = HWREPO / "design_lint_mosfet_gate_candidate_evidence.py"
    tree = ast.parse(route.read_text(encoding="utf-8"), filename=route.name)
    functions = {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}
    direct_drive_tree = ast.parse(
        direct_drive_route.read_text(encoding="utf-8"), filename=direct_drive_route.name
    )
    direct_drive_function = next(
        node
        for node in direct_drive_tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "mosfets_with_direct_output_gate_drive"
    )

    assert line_count(route) < IMPLEMENTATION_MAX_LINES
    assert line_count(direct_drive_route) < IMPLEMENTATION_MAX_LINES
    assert line_count(owner) < IMPLEMENTATION_MAX_LINES
    for name in (
        "mosfet_gates_without_peer",
        "mosfet_gates_without_visible_source_bias",
    ):
        function = functions[name]
        assert any(
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "from_source_evidence"
            for node in ast.walk(function)
        )
        assert not any(
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "Candidate"
            for node in ast.walk(function)
        )
    assert any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "from_source_evidence"
        for node in ast.walk(direct_drive_function)
    )
    assert not any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "Candidate"
        for node in ast.walk(direct_drive_function)
    )


def test_all_mosfet_gate_rules_catalog_the_shared_projector() -> None:
    from kicad_tooling.hwrepo.design_lint import rule_catalog

    rules = {
        rule.rule_id: rule
        for rule in rule_catalog().rules
        if rule.rule_id
        in {
            "component.mosfet_gate_without_peer",
            "component.mosfet_gate_without_visible_source_bias",
            "component.mosfet_gate_direct_drive",
        }
    }

    assert len(rules) == 3
    for rule in rules.values():
        assert rule.implementation_owner in rule.implementation_refs
        assert (
            "kicad_tooling/hwrepo/design_lint_mosfet_gate_candidate_evidence.py#"
            "project_mosfet_gate_candidate_evidence"
        ) in rule.implementation_refs
        assert "kicad_tooling/hwrepo/component_mosfet_symbols.py#mosfet_terminal_role" in (
            rule.implementation_refs
        )
