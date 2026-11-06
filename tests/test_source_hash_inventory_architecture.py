"""Keep repository source inventories typed across evidence and review routes."""

from __future__ import annotations

import ast
from collections.abc import MutableMapping
from pathlib import Path
from typing import get_type_hints

import pytest

from kicad_tooling.hwrepo import (
    cross_probe_schematic,
    design_lint_stm32_coverage,
    electrical_view_evidence,
    findings_view,
    findings_view_mapping,
    findings_view_native,
    findings_view_sheets,
    native_netlist_evidence,
    native_summary_binding,
    parts_workflow,
    pcb_variant_population_capture,
    product_visual,
    project_source_hashes,
    repository,
    review_overview_evidence,
    review_overview_result,
    schematic_geometry_source,
    schematic_source_tree,
    verification_history_evidence,
)
from kicad_tooling.hwrepo.model_primitives import Digest, RepositoryPath
from kicad_tooling.hwrepo.purchasing_models import PurchasingReport
from kicad_tooling.hwrepo.schematic_geometry_models import VerifiedSchematicSourceTree
from kicad_tooling.hwrepo.source_state_models import PathDigestInventory, SourceHashInventory
from kicad_tooling.hwrepo.stm32_pin_map_models import Stm32PinMapCoverageReport
from kicad_tooling.hwrepo.supplier_analysis_models import SupplierAnalysisReport

pytestmark = [pytest.mark.architecture, pytest.mark.evidence_lint]

_ROOT = Path(__file__).parents[1]
_FUNCTIONS = {
    "native_summary_binding.py": native_summary_binding.validate_native_summary_binding,
    "native_netlist_evidence.py": native_netlist_evidence.read_bound_native_netlist,
    "schematic_geometry_source.py": schematic_geometry_source.source_tree_sha256,
    "schematic_source_tree.py": schematic_source_tree.verified_schematic_sources,
    "cross_probe_schematic.py": cross_probe_schematic.schematic_drawing_bindings,
    "findings_view.py": findings_view._lint_snapshot,  # pyright: ignore[reportPrivateUsage]
    "findings_view_mapping.py": findings_view_mapping.design_lint_finding,
    "findings_view_mapping.py:erc": findings_view_mapping.erc_finding,
    "findings_view_native.py": findings_view_native.native_findings,
    "findings_view_sheets.py:root": findings_view_sheets._bind_single_root_drawing,  # pyright: ignore[reportPrivateUsage]
    "findings_view_sheets.py": findings_view_sheets.bind_schematic_drawings,
    "review_overview_result.py": review_overview_result.receipt_result,
    "review_overview_evidence.py": review_overview_evidence.source_mismatch,
    "pcb_variant_population_capture.py": pcb_variant_population_capture.capture_variant_population,
    "verification_history_evidence.py": verification_history_evidence.load_snapshot,
}


def test_native_and_schematic_inventory_handoffs_use_the_shared_type() -> None:
    package = _ROOT / "kicad_tooling/hwrepo"
    for name, function in _FUNCTIONS.items():
        filename = name.split(":", maxsplit=1)[0]
        path = package / filename
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=path.as_posix())
        assert any(
            isinstance(node, ast.ImportFrom)
            and node.module == "source_state_models"
            and any(alias.name == "SourceHashInventory" for alias in node.names)
            for node in tree.body
        ), f"{filename} must import the shared repository inventory type"
        parameter = (
            "expected"
            if filename == "review_overview_evidence.py"
            else "current_source_hashes"
            if filename == "verification_history_evidence.py"
            else "expected_source_hashes"
            if filename == "pcb_variant_population_capture.py"
            else "source_hashes"
        )
        expected_type = (
            SourceHashInventory | None
            if filename == "review_overview_result.py"
            else SourceHashInventory
        )
        assert get_type_hints(function, include_extras=True)[parameter] == expected_type


def test_project_inventory_producers_and_review_context_use_shared_type() -> None:
    assert (
        get_type_hints(schematic_source_tree.verified_schematic_sources, include_extras=True)[
            "return"
        ]
        == VerifiedSchematicSourceTree
    )
    assert (
        get_type_hints(project_source_hashes.hash_project_sources, include_extras=True)["return"]
        == SourceHashInventory
    )
    assert (
        get_type_hints(repository.checkout_input_hashes, include_extras=True)["return"]
        == SourceHashInventory
    )
    assert (
        get_type_hints(review_overview_evidence.ReviewContext, include_extras=True)["source_hashes"]
        == SourceHashInventory
    )
    assert (
        get_type_hints(
            design_lint_stm32_coverage.resolve_stm32_pin_map_coverage,
            include_extras=True,
        )["return"]
        == tuple[Stm32PinMapCoverageReport, SourceHashInventory]
    )
    assert (
        get_type_hints(
            product_visual._project_identities,  # pyright: ignore[reportPrivateUsage]
            include_extras=True,
        )["source_hashes"]
        == MutableMapping[RepositoryPath, Digest]
    )
    assert (
        get_type_hints(electrical_view_evidence.ElectricalViewEvidence, include_extras=True)[
            "current_source_sha256"
        ]
        == SourceHashInventory | None
    )
    assert (
        get_type_hints(verification_history_evidence.current_source, include_extras=True)["return"]
        == tuple[SourceHashInventory, str]
    )


def test_parts_policy_input_hashes_use_the_shared_path_digest_contract() -> None:
    assert (
        get_type_hints(parts_workflow.input_hashes, include_extras=True)["return"]
        == PathDigestInventory
    )
    assert (
        get_type_hints(PurchasingReport, include_extras=True)["input_hashes"] == PathDigestInventory
    )
    assert (
        get_type_hints(PurchasingReport, include_extras=True)["source_hashes"]
        == SourceHashInventory
    )
    assert (
        get_type_hints(SupplierAnalysisReport, include_extras=True)["parts_input_hashes"]
        == PathDigestInventory
    )
    assert (
        get_type_hints(SupplierAnalysisReport, include_extras=True)["parts_source_hashes"]
        == SourceHashInventory
    )


def test_schematic_source_tree_fingerprint_is_order_independent() -> None:
    first: SourceHashInventory = {
        "projects/controller/main.kicad_sch": "a" * 64,
        "projects/controller/child.kicad_sch": "b" * 64,
    }
    second: SourceHashInventory = dict(reversed(tuple(first.items())))

    assert schematic_geometry_source.source_tree_sha256(first) == (
        schematic_geometry_source.source_tree_sha256(second)
    )
