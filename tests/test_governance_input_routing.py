"""Source identity and freshness boundaries for governance input routes."""

from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from kicad_tooling.hwrepo import governance_lint as governance_lint_service
from kicad_tooling.hwrepo import governance_lint_project_policy as project_policy_service
from kicad_tooling.hwrepo import product as product_service
from kicad_tooling.hwrepo.contracts import read_model, write_model
from kicad_tooling.hwrepo.discovery import load_registry_snapshot
from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.governance_lint_catalog_policy import (
    GovernanceLintCatalogPolicyRequest,
    evaluate_governance_lint_catalog_policy,
)
from kicad_tooling.hwrepo.governance_lint_filesystem_inputs import (
    capture_governance_lint_filesystem_inputs,
    governance_lint_filesystem_freshness_issues,
)
from kicad_tooling.hwrepo.governance_lint_inputs import read_governance_lint_shared_inputs
from kicad_tooling.hwrepo.governance_lint_project_policy import (
    GovernanceLintProjectPolicyRequest,
    evaluate_governance_lint_project_policy,
)
from kicad_tooling.hwrepo.governance_lint_scope import resolve_governance_lint_project_scope
from kicad_tooling.hwrepo.governance_records import (
    governance_record_review_freshness_issues,
    read_governance_team_policy,
    review_governance_record,
)
from kicad_tooling.hwrepo.models import (
    GovernanceRecord,
    InterfacesCatalog,
    LibraryRecord,
    TeamPolicy,
)
from kicad_tooling.hwrepo.product_models import ProductIndexEntry
from kicad_tooling.hwrepo.product_source_inputs import (
    capture_product_record,
    product_record_freshness_issues,
)
from kicad_tooling.hwrepo.project_models import ComponentIdentity, ProjectKind, ProjectRecord
from kicad_tooling.hwrepo.project_source_hashes import ProjectSourceInventoryInput
from kicad_tooling.hwrepo.release_contract_models import ReleasePoliciesCatalog
from tests.support import reference_root


class GovernanceInputRoutingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = reference_root()

    def test_selected_product_loader_uses_captured_catalog_and_index_values(self) -> None:
        snapshot = load_registry_snapshot(self.root)
        shared = read_governance_lint_shared_inputs(self.root, snapshot)

        with patch.object(
            product_service,
            "read_model",
            side_effect=AssertionError("product loader reread a captured catalog"),
        ):
            repository = product_service.load_repository(
                self.root,
                ("status-indicator-wiring",),
                registry_snapshot=snapshot,
                toolchains_catalog=shared.toolchains_document.value,
                product_index_document=shared.product_index,
                parts_catalog=shared.parts_document.value,
                interfaces_catalog=shared.interfaces_document.value,
            )

        self.assertEqual(shared.product_index.source.path, "catalog/products.json")
        self.assertEqual(len(repository.record_inputs), 1)
        self.assertEqual(repository.record_inputs[0].state, "EVALUATED")
        self.assertEqual(
            repository.record_inputs[0].source,
            repository.product_sources["status-indicator-system"],
        )

    def test_project_policy_result_keeps_captured_sources_with_project_identity(self) -> None:
        snapshot = load_registry_snapshot(self.root)
        shared = read_governance_lint_shared_inputs(self.root, snapshot)

        result = evaluate_governance_lint_project_policy(
            GovernanceLintProjectPolicyRequest(
                root=self.root,
                entry=snapshot.by_id["controller"],
                shared_inputs=shared,
            )
        )

        self.assertEqual(result.project_id, "controller")
        self.assertEqual(result.issues, ())
        self.assertIsNotNone(result.config_document)
        self.assertEqual(result.config_document.project_id, result.project_id)
        self.assertIsNotNone(result.source_review)
        self.assertEqual(result.source_review.issues, ())

    def test_catalog_policy_uses_captured_shared_inputs_and_selected_scope(self) -> None:
        snapshot = load_registry_snapshot(self.root)
        shared = read_governance_lint_shared_inputs(self.root, snapshot)
        selected = ("controller",)
        scope = resolve_governance_lint_project_scope(
            self.root,
            selected,
            selected,
            snapshot,
            shared,
        )

        result = evaluate_governance_lint_catalog_policy(
            GovernanceLintCatalogPolicyRequest(
                root=self.root,
                registry_snapshot=snapshot,
                shared_inputs=shared,
                project_scope=scope,
            )
        )

        self.assertEqual(result.issues, ())
        self.assertEqual(scope.project_ids, selected)

    def test_selected_product_source_changed_during_lint_fails_freshness(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            staged = Path(temporary) / "template"
            shutil.copytree(
                self.root,
                staged,
                ignore=shutil.ignore_patterns(".git", "build", ".evidence", "__pycache__"),
            )
            product_path = staged / "examples/products/status-indicator-system/product.json"
            original_capture = project_policy_service.capture_project_source_inventory
            mutated = False

            def mutate_after_capture(
                root: Path, source_roots: tuple[str, ...]
            ) -> ProjectSourceInventoryInput:
                nonlocal mutated
                result = original_capture(root, source_roots)
                if not mutated:
                    product_path.write_bytes(product_path.read_bytes() + b"\n")
                    mutated = True
                return result

            with patch.object(
                project_policy_service,
                "capture_project_source_inventory",
                side_effect=mutate_after_capture,
            ):
                result = governance_lint_service.lint(staged, ["status-indicator-wiring"])

            self.assertTrue(mutated)
            self.assertEqual(result.status, "FAIL")
            self.assertIn(
                "Product source examples/products/status-indicator-system/product.json changed during operation",
                result.issues,
            )

    def test_selected_catalog_policy_ignores_unselected_interface_contracts(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            staged = Path(temporary) / "template"
            shutil.copytree(
                self.root,
                staged,
                ignore=shutil.ignore_patterns(".git", "build", ".evidence", "__pycache__"),
            )
            catalog_path = staged / "catalog/interfaces.json"
            catalog = read_model(catalog_path, InterfacesCatalog)
            unused_interface = catalog.interfaces[0].model_copy(update={"pins": ()})
            write_model(
                catalog_path,
                catalog.model_copy(
                    update={"interfaces": (unused_interface, *catalog.interfaces[1:])}
                ),
            )

            result = governance_lint_service.lint(staged, ["controller"])

            self.assertEqual(result.status, "PASS", result.issues)
            self.assertFalse(
                any(f"interface {unused_interface.id}:" in issue for issue in result.issues)
            )

    def test_selected_catalog_policy_keeps_release_policy_completeness_global(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            staged = Path(temporary) / "template"
            shutil.copytree(
                self.root,
                staged,
                ignore=shutil.ignore_patterns(".git", "build", ".evidence", "__pycache__"),
            )
            catalog_path = staged / "catalog/release-policies.json"
            catalog = read_model(catalog_path, ReleasePoliciesCatalog)
            write_model(
                catalog_path, catalog.model_copy(update={"policies": catalog.policies[:-1]})
            )

            result = governance_lint_service.lint(staged, ["controller"])

            self.assertEqual(result.status, "FAIL")
            self.assertIn(
                "release policies: need exactly one minimum assurance for every release class",
                result.issues,
            )

    def test_product_record_capture_preserves_missing_and_unavailable_states(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            entry = ProductIndexEntry(
                id="sample-product", path="products/sample/product.json", project_ids=()
            )

            missing = capture_product_record(root, entry)
            self.assertEqual(missing.state, "MISSING")
            self.assertEqual(product_record_freshness_issues(root, (missing,)), ())

            product_path = root / entry.path
            product_path.mkdir(parents=True)
            self.assertIn(
                "changed state during operation",
                product_record_freshness_issues(root, (missing,))[0],
            )
            unavailable = capture_product_record(root, entry)
            self.assertEqual(unavailable.state, "UNAVAILABLE")
            self.assertEqual(product_record_freshness_issues(root, (unavailable,)), ())

            product_path.rmdir()
            product_path.write_text("{ invalid", encoding="utf-8")
            malformed = capture_product_record(root, entry)
            self.assertEqual(malformed.state, "UNAVAILABLE")
            self.assertIsNotNone(malformed.file_identity)
            self.assertEqual(product_record_freshness_issues(root, (malformed,)), ())
            product_path.write_bytes(product_path.read_bytes() + b" ")
            self.assertIn(
                "changed during operation",
                product_record_freshness_issues(root, (malformed,))[0],
            )

    def test_governance_record_absence_state_is_rechecked(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "catalog").mkdir()
            write_model(root / "catalog/team-policy.json", TeamPolicy(rationale="unit fixture"))
            team_policy = read_governance_team_policy(root)
            record_path = root / "records/governance.json"
            review = review_governance_record(
                root, team_policy, "records/governance.json", "sample-project"
            )

            self.assertEqual(review.state, "MISSING")
            self.assertEqual(
                governance_record_review_freshness_issues(root, "sample-project", review), ()
            )
            record_path.parent.mkdir()
            write_model(
                record_path,
                GovernanceRecord(
                    branch="main",
                    required_status_checks=("CI",),
                    authors=("author",),
                    reviewers=("reviewer",),
                    integrators=("integrator",),
                    release_authorities=("authority",),
                    branch_protection_evidence=("fixture",),
                    branch_protection_verified_at="2026-01-01",
                ),
            )
            self.assertIn(
                "changed state during operation",
                governance_record_review_freshness_issues(root, "sample-project", review)[0],
            )
            record_path.unlink()
            record_path.mkdir()
            unavailable = review_governance_record(
                root, team_policy, "records/governance.json", "sample-project"
            )
            self.assertEqual(unavailable.state, "UNAVAILABLE")
            self.assertEqual(
                governance_record_review_freshness_issues(root, "sample-project", unavailable),
                (),
            )
            record_path.rmdir()
            write_model(
                record_path,
                GovernanceRecord(
                    branch="main",
                    required_status_checks=("CI",),
                    authors=("author",),
                    reviewers=("reviewer",),
                    integrators=("integrator",),
                    release_authorities=("authority",),
                    branch_protection_evidence=("fixture",),
                    branch_protection_verified_at="2026-01-01",
                ),
            )
            self.assertIn(
                "changed state during operation",
                governance_record_review_freshness_issues(root, "sample-project", unavailable)[0],
            )

    def test_library_and_mechanical_sources_are_retained_and_rechecked(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            provenance = root / "libraries/sample/PROVENANCE.md"
            licensing = root / "libraries/sample/LICENSE.md"
            handoff = root / "projects/board/mechanical.md"
            for path in (provenance, licensing, handoff):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(f"source: {path.name}\n", encoding="utf-8")

            library = LibraryRecord(
                id="sample-library",
                version="1.0",
                path="libraries/sample",
                owner="fixture owner",
                status="approved",
                provenance_path="libraries/sample/PROVENANCE.md",
                provenance_sha256=digest(provenance),
                licensing_path="libraries/sample/LICENSE.md",
                licensing_sha256=digest(licensing),
            )
            project = ProjectRecord(
                id="board",
                kind=ProjectKind.PCB,
                status="engineering",
                assurance_profile="production",
                config="projects/board/project.json",
                project="projects/board/board.kicad_pro",
                component_identity=ComponentIdentity(required=False, part_ids=()),
                mechanical_handoff="projects/board/mechanical.md",
            )

            captured = capture_governance_lint_filesystem_inputs(root, (library,), (project,))

            self.assertEqual(captured.issues, ())
            provenance.write_text("changed provenance\n", encoding="utf-8")
            handoff.write_text("changed handoff\n", encoding="utf-8")
            freshness = governance_lint_filesystem_freshness_issues(root, captured)

            self.assertTrue(
                any("library sample-library: Governance source" in issue for issue in freshness),
                freshness,
            )
            self.assertTrue(
                any("project board: Governance source" in issue for issue in freshness),
                freshness,
            )


if __name__ == "__main__":
    unittest.main()
