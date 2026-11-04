"""Guard capability grouping for authored USB data-path evidence."""

from __future__ import annotations

import ast
from dataclasses import fields
from typing import get_type_hints

import pytest

from kicad_tooling.hwrepo import (
    design_lint_candidate_aggregation,
    design_lint_candidate_inputs,
    design_lint_evaluation_preparation,
    design_lint_mapped_coverage_candidates,
    design_lint_mapped_topology_coverage,
    design_lint_peer_candidates,
    design_lint_peer_inputs,
    design_lint_usb_data_path_candidates,
    design_lint_usb_data_path_inputs,
    design_lint_usb_peer_candidates,
    usb_peer_reference_coverage,
)
from kicad_tooling.hwrepo.design_lint_candidate_inputs import (
    DesignLintCandidateInputs,
    UsbDataPathCandidateInputs,
)
from kicad_tooling.hwrepo.design_lint_mapped_coverage_candidates import (
    MappedCoverageCandidateInputs,
)
from kicad_tooling.hwrepo.design_lint_peer_inputs import PeerCandidateScanInputs
from kicad_tooling.hwrepo.design_lint_usb_data_path_inputs import (
    UsbDataPathCandidateInputs as OwnedUsbDataPathCandidateInputs,
)
from kicad_tooling.hwrepo.usb_data_path_models import (
    UsbDataPathMap,
    usb_data_path_map_sha256,
)
from tests.lint_architecture_support import IMPLEMENTATION_MAX_LINES, REPO_ROOT, line_count
from tests.usb_data_path_support import usb_data_map

pytestmark = [pytest.mark.architecture, pytest.mark.design_lint, pytest.mark.interface_lint]


def test_usb_data_path_map_is_owned_by_a_named_candidate_group() -> None:
    names = {item.name for item in fields(DesignLintCandidateInputs)}

    assert get_type_hints(DesignLintCandidateInputs)["usb_data_path"] is (
        UsbDataPathCandidateInputs
    )
    assert "usb_data_path_map" not in names
    assert get_type_hints(UsbDataPathCandidateInputs)["authored_map"] == UsbDataPathMap | None
    assert UsbDataPathCandidateInputs is OwnedUsbDataPathCandidateInputs
    assert get_type_hints(PeerCandidateScanInputs)["usb_data_path"] is (
        OwnedUsbDataPathCandidateInputs
    )
    assert get_type_hints(MappedCoverageCandidateInputs)["usb_data_path"] is (
        OwnedUsbDataPathCandidateInputs
    )


def test_usb_candidate_input_keeps_map_and_canonical_digest_bound() -> None:
    path_map = usb_data_map()
    inputs = OwnedUsbDataPathCandidateInputs(authored_map=path_map)

    assert inputs.map_sha256 == usb_data_path_map_sha256(path_map)
    with pytest.raises(ValueError, match="digest must match"):
        OwnedUsbDataPathCandidateInputs(authored_map=path_map, map_sha256="0" * 64)


def test_usb_map_digest_uses_one_domain_owner() -> None:
    owner_path = REPO_ROOT / "kicad_tooling/hwrepo/usb_data_path_models.py"
    consumers = (
        design_lint_usb_data_path_inputs,
        design_lint_mapped_topology_coverage,
        design_lint_usb_peer_candidates,
        usb_peer_reference_coverage,
    )

    assert line_count(owner_path) < IMPLEMENTATION_MAX_LINES
    assert all(module.usb_data_path_map_sha256 is usb_data_path_map_sha256 for module in consumers)


def test_internal_usb_candidates_import_the_theme_owned_input() -> None:
    owner = "design_lint_usb_data_path_inputs"
    modules = (
        design_lint_candidate_aggregation,
        design_lint_evaluation_preparation,
        design_lint_mapped_coverage_candidates,
        design_lint_peer_candidates,
        design_lint_peer_inputs,
        design_lint_usb_data_path_candidates,
        design_lint_usb_peer_candidates,
    )

    for module in modules:
        source = REPO_ROOT / f"kicad_tooling/hwrepo/{module.__name__.rsplit('.', 1)[-1]}.py"
        tree = ast.parse(source.read_text(encoding="utf-8"))
        assert any(
            isinstance(node, ast.ImportFrom)
            and node.module == owner
            and "UsbDataPathCandidateInputs" in {alias.name for alias in node.names}
            for node in tree.body
        ), module.__name__

    assert (
        design_lint_candidate_inputs.UsbDataPathCandidateInputs
        is design_lint_usb_data_path_inputs.UsbDataPathCandidateInputs
    )
