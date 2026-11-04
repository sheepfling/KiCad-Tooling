"""Keep protocol peer scan records in their theme-owned input module."""

from __future__ import annotations

import ast
import inspect
from dataclasses import dataclass, replace
from typing import get_type_hints

import pytest

from kicad_tooling.hwrepo import (
    design_lint_candidate_aggregation,
    design_lint_candidate_inputs,
    design_lint_peer_candidates,
    design_lint_peer_inputs,
)
from kicad_tooling.hwrepo.design_lint_candidate_aggregation import candidates, scan_candidates
from kicad_tooling.hwrepo.design_lint_peer_inputs import (
    PeerCandidateInputs,
    PeerCandidateScanInputs,
)
from kicad_tooling.hwrepo.design_lint_types import Candidate
from kicad_tooling.hwrepo.spi_participants import SpiRosterContext
from tests.design_lint_candidate_inputs_support import candidate_inputs
from tests.design_lint_fixtures import i2c_netlist
from tests.lint_architecture_support import IMPLEMENTATION_MAX_LINES, REPO_ROOT, line_count
from tests.usb_data_path_support import usb_data_map

pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint, pytest.mark.architecture]


def _class_definitions(tree: ast.Module) -> set[str]:
    return {node.name for node in tree.body if isinstance(node, ast.ClassDef)}


def _imports_from(tree: ast.Module, module: str) -> set[str]:
    return {
        alias.name
        for node in tree.body
        if isinstance(node, ast.ImportFrom) and node.module == module
        for alias in node.names
    }


def test_peer_candidate_records_live_in_a_theme_owned_module() -> None:
    owner_path = REPO_ROOT / "kicad_tooling/hwrepo/design_lint_peer_inputs.py"
    owner_tree = ast.parse(owner_path.read_text(encoding="utf-8"))

    assert line_count(owner_path) < IMPLEMENTATION_MAX_LINES
    assert {"PeerCandidateInputs", "PeerCandidateScanInputs"} <= _class_definitions(owner_tree)


def test_peer_services_import_the_owner_and_legacy_bundle_keeps_identity() -> None:
    owner = "design_lint_peer_inputs"
    modules = {
        "design_lint_candidate_inputs": {"PeerCandidateInputs"},
        "design_lint_candidate_aggregation": {
            "PeerCandidateInputs",
            "PeerCandidateScanInputs",
        },
        "design_lint_evaluation_preparation": {"PeerCandidateInputs"},
        "design_lint_peer_candidates": {"PeerCandidateInputs", "PeerCandidateScanInputs"},
    }

    for module_name, expected_imports in modules.items():
        path = REPO_ROOT / f"kicad_tooling/hwrepo/{module_name}.py"
        tree = ast.parse(path.read_text(encoding="utf-8"))
        assert expected_imports <= _imports_from(tree, owner), module_name

    assert (
        design_lint_candidate_inputs.PeerCandidateInputs
        is design_lint_peer_inputs.PeerCandidateInputs
    )
    assert (
        design_lint_peer_candidates.PeerCandidateInputs
        is design_lint_peer_inputs.PeerCandidateInputs
    )
    assert (
        design_lint_peer_candidates.PeerCandidateScanInputs
        is design_lint_peer_inputs.PeerCandidateScanInputs
    )


def test_peer_candidate_service_accepts_one_typed_scan_request() -> None:
    signature = inspect.signature(design_lint_peer_candidates.scan_peer_candidates)

    assert tuple(signature.parameters) == ("inputs",)
    assert (
        get_type_hints(design_lint_peer_candidates.scan_peer_candidates)["inputs"]
        is design_lint_peer_inputs.PeerCandidateScanInputs
    )


def test_candidate_aggregation_forwards_one_complete_peer_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    @dataclass(frozen=True, slots=True)
    class ExtendedPeerInputs(PeerCandidateInputs):
        extension_marker: str = "new peer evidence"

    inputs = candidate_inputs(i2c_netlist(pullups=()), usb_map=usb_data_map())
    peer = ExtendedPeerInputs(
        digital_voltage_context=None,
        digital_voltage_scan=None,
        usb_reference_scan=None,
        serial_reference_scan=None,
        serial_roster=None,
        usb_c_port_roster=None,
    )
    reviewed = ("J1", "J2")
    spi_roster = SpiRosterContext(state="not_configured")
    inputs = replace(
        inputs,
        reviewed_connector_references=reviewed,
        bus=replace(
            inputs.bus,
            reviewed_connector_references=reviewed,
            spi_roster=spi_roster,
        ),
        peer=peer,
    )
    expected = candidates(
        inputs.observed,
        reviewed_connector_references=reviewed,
        spi_roster=spi_roster,
        usb_data_path_map=inputs.usb_data_path.authored_map,
    )
    received: list[PeerCandidateScanInputs] = []
    original = design_lint_candidate_aggregation.scan_peer_candidates

    def capture(request: PeerCandidateScanInputs) -> tuple[Candidate, ...]:
        received.append(request)
        return original(request)

    monkeypatch.setattr(design_lint_candidate_aggregation, "scan_peer_candidates", capture)
    assert scan_candidates(inputs) == expected
    assert len(received) == 1
    request = received[0]
    assert request.observed is inputs.observed
    assert request.peer is peer
    assert request.peer.extension_marker == "new peer evidence"
    assert request.reviewed_connector_references == reviewed
    assert request.spi_roster is spi_roster
    assert request.usb_data_path_map is inputs.usb_data_path.authored_map
    assert request.usb_data_map_sha256 is not None
