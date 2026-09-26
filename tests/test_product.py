"""Mutation tests for product policy. Synthetic fixtures are not engineering proof."""

from __future__ import annotations

import copy
import csv
import hashlib
import json
import shutil
import subprocess
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import patch

from pydantic import ValidationError

from kicad_tooling.hwrepo.contracts import read_model, repo_path, write_model
from kicad_tooling.hwrepo.discovery import load_config
from kicad_tooling.hwrepo.exports import purchasing_bom
from kicad_tooling.hwrepo.generation import (
    bom_rows,
    csv_bytes,
    drift,
    electrical_view,
    expected_outputs,
    generate,
    harness_schedule,
    harness_schedule_csv_bytes,
    snapshot,
    verify_snapshot,
)
from kicad_tooling.hwrepo.models import (
    LibrariesCatalog,
    PartsCatalog,
    ProductRecord,
    ProjectManifest,
    ReleaseManifest,
    ReleasePoliciesCatalog,
    TemplateContract,
)
from kicad_tooling.hwrepo.product import (
    check,
    check_harness_interface_contract,
    check_project_netlist,
    check_system_wiring_contract,
    load_repository,
    validate_product,
)
from kicad_tooling.hwrepo.repository import (
    cad_dependencies,
    check_repository,
    ephemeral,
    unmanaged_artifact,
)
from kicad_tooling.lint_registry import lint, reviewed_value
from tests.support import reference_root

ROOT = reference_root()


class ProductTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repository = load_repository(ROOT)
        self.product = self.repository.products[0]
        self.data = self.product.model_dump(mode="json", by_alias=True)
        self.parts = self.repository.parts
        self.interfaces = self.repository.interfaces
        self.projects = self.repository.projects
        self.temporary = tempfile.TemporaryDirectory(prefix="product-policy-")
        self.addCleanup(self.temporary.cleanup)
        self.temp = Path(self.temporary.name)

    def model(self, data=None) -> ProductRecord:
        raw = self.data if data is None else data
        return ProductRecord.model_validate_json(json.dumps(raw))

    def codes(self, data=None, root=ROOT, parts=None):
        raw = self.data if data is None else data
        try:
            product = self.model(raw)
        except ValidationError:
            return {"SCHEMA"}
        active_parts = self.parts if parts is None else parts
        return {
            issue.code
            for issue in validate_product(
                root,
                product,
                active_parts,
                self.interfaces,
                self.projects,
            )
        }

    def stage(self):
        for directory in (
            "catalog",
            "examples",
            "docs",
        ):
            shutil.copytree(ROOT / directory, self.temp / directory)
        return self.temp

    def test_valid_training_product(self):
        self.assertEqual(self.codes(), set())
        result = check(ROOT)
        self.assertEqual(result.status, "PASS")
        self.assertFalse(result.build_authorized)
        self.assertTrue(result.open_items[self.product.id])

    def test_system_wiring_contract_requires_complete_typed_coverage(self):
        config = load_config(ROOT, ROOT / "examples/projects/status-indicator-wiring/project.json")
        check_system_wiring_contract(ROOT, config)
        bad = config.model_copy(
            update={
                "validation": config.validation.model_copy(update={"harness_ids": ("H-MISSING",)})
            }
        )
        with self.assertRaisesRegex(ValueError, "harness coverage"):
            check_system_wiring_contract(ROOT, bad)

    def test_harness_interface_contract_and_schedule_are_typed(self):
        config = load_config(
            ROOT, ROOT / "examples/projects/status-indicator-harness-interface/project.json"
        )
        check_harness_interface_contract(ROOT, config)
        schedule = harness_schedule(self.product, self.product.variants[0])
        self.assertEqual(schedule.rows[0].harness_id, "H-STATUS")
        self.assertEqual(schedule.rows[0].electrical_connection_ids, ("C-RETURN", "C-SIGNAL"))
        self.assertIn(b"conductor_area_mm2", harness_schedule_csv_bytes(schedule))
        bad = config.model_copy(
            update={
                "validation": config.validation.model_copy(
                    update={"connection_ids": ("C-STATUS-ROLE",)}
                )
            }
        )
        with self.assertRaisesRegex(ValueError, "conductor coverage"):
            check_harness_interface_contract(ROOT, bad)

    def test_strict_schema_rejects_unknown_fields_types_and_versions(self):
        for key, value in (
            ("schema_version", "2"),
            ("revision", 2),
            ("maturity", "uncontrolled"),
            ("invented_field", True),
        ):
            with self.subTest(key=key):
                data = {**self.data, key: value}
                self.assertIn("SCHEMA", self.codes(data))
        for quantity in (True, 0, -1, 1.5, "2"):
            with self.subTest(quantity=quantity):
                self.data["assemblies"][0]["members"][0]["quantity"] = quantity
                self.assertIn("SCHEMA", self.codes())

    def test_json_duplicate_keys_and_nonfinite_numbers_fail(self):
        for text in ('{"id":1,"id":2}', '{"value":NaN}', '{"value":Infinity}'):
            with self.subTest(text=text):
                path = self.temp / "bad.json"
                path.write_text(text, encoding="utf-8")
                with self.assertRaises(ValueError):
                    read_model(path, ProductRecord)

    def test_unknown_part(self):
        self.data["assemblies"][1]["members"][0]["item"] = "missing-part"
        self.assertIn("PART_REF", self.codes())

    def test_duplicate_assembly_and_case_collision(self):
        duplicate = copy.deepcopy(self.data["assemblies"][0])
        duplicate["id"] = duplicate["id"].upper()
        self.data["assemblies"].append(duplicate)
        self.assertIn("DUPLICATE_ID", self.codes())

    def test_duplicate_instance(self):
        self.data["assemblies"][0]["members"].append(
            copy.deepcopy(self.data["assemblies"][0]["members"][0])
        )
        self.assertIn("DUPLICATE_INSTANCE", self.codes())

    def test_cycle_even_when_unreachable(self):
        self.data["assemblies"].append(
            {
                "id": "unreachable",
                "revision": "A",
                "kind": "built",
                "members": [{"ref": "SELF", "item": "unreachable", "quantity": 1}],
            }
        )
        self.assertIn("ASSEMBLY_GRAPH", self.codes())

    def test_missing_root(self):
        self.data["root_assembly"] = "missing"
        self.assertIn("ASSEMBLY_REF", self.codes())

    def test_purchased_assembly_cannot_double_count_children(self):
        self.data["assemblies"][3]["members"] = [
            {"ref": "EXTRA", "item": "training-generic-cable", "quantity": 1}
        ]
        self.assertIn("PURCHASED_ASSEMBLY", self.codes())

    def test_part_revision_and_units_required(self):
        cable = self.parts["training-generic-cable"].model_copy(update={"revision": ""})
        self.assertIn(
            "PART_METADATA",
            self.codes(parts={**self.parts, cable.id: cable}),
        )

    def test_missing_endpoint(self):
        self.data["connections"][0]["to"] = "missing"
        self.assertIn("ENDPOINT_REF", self.codes())

    def test_nonexistent_kicad_pin(self):
        self.data["terminals"][0]["pin"] = "999"
        self.assertIn("KICAD_TERMINAL", self.codes())

    def test_interface_terminal_and_harness_binding_fail_closed(self):
        self.data["terminals"][0]["interface_pin"] = "UNKNOWN"
        self.assertIn("INTERFACE_PIN", self.codes())
        self.data["terminals"][0]["interface_pin"] = "D13"
        self.data["terminals"][0].pop("interface_id")
        self.assertIn("INTERFACE_BINDING", self.codes())
        self.data["terminals"][0]["interface_id"] = "iface-arduino-uno-r3-d13-status-v1"
        self.data["terminals"][0].pop("interface_pin")
        self.data["terminals"][1].pop("interface_id")
        self.data["terminals"][1].pop("interface_pin")
        self.assertIn("HARNESS_INTERFACE", self.codes())

    def test_duplicate_terminal_pair(self):
        terminal = {**self.data["terminals"][0], "id": "alias"}
        self.data["terminals"].append(terminal)
        self.assertIn("DUPLICATE_TERMINAL", self.codes())

    def test_nonunique_physical_occurrence(self):
        self.data["assemblies"][0]["members"][0]["quantity"] = 2
        self.assertIn("TERMINAL_REF", self.codes())

    def test_exclusive_terminal_double_allocation(self):
        self.data["connections"].append({**self.data["connections"][0], "id": "extra-wire"})
        self.assertIn("TERMINAL_ALLOCATION", self.codes())

    def test_electrical_relation_cannot_use_mechanical_endpoint(self):
        self.data["connections"][0]["to"] = "T-ENC-MOUNT"
        self.assertIn("RELATION_KIND", self.codes())

    def test_functional_relation_never_exported_as_continuity(self):
        product = self.model()
        view = electrical_view(product, product.variants[0])
        self.assertEqual([row.id for row in view.connections], ["C-RETURN", "C-SIGNAL"])
        self.data["connections"][2]["harness"] = "H-STATUS"
        self.assertIn("HARNESS_REF", self.codes())

    def test_excluded_instance_cannot_have_active_connection(self):
        self.data["variants"][0]["exclude"] = ["UNO"]
        self.assertIn("VARIANT_ENDPOINT", self.codes())

    def test_unknown_variant_and_exclusion(self):
        self.data["variants"][0]["exclude"] = ["missing"]
        self.data["connections"][0]["variants"] = ["missing"]
        self.assertIn("VARIANT_REF", self.codes())

    def test_verified_requires_scoped_test_evidence(self):
        for assurance in ("verified", "observed", "manufacturer_documented"):
            with self.subTest(assurance=assurance):
                self.data["connections"][0]["assurance"] = assurance
                self.assertIn("ASSURANCE_EVIDENCE", self.codes())

    def test_evidence_type_scope_and_hash(self):
        root = self.stage()
        evidence_path = root / "docs/unit-test-evidence.txt"
        evidence_path.write_text("SYNTHETIC UNIT TEST ONLY\n", encoding="utf-8")
        claim = self.data["connections"][0]
        claim.update(assurance="verified", evidence=["EV-TEST"])
        evidence = {
            "id": "EV-TEST",
            "kind": "test_report",
            "path": "docs/unit-test-evidence.txt",
            "sha256": hashlib.sha256(evidence_path.read_bytes()).hexdigest(),
            "claims": [claim["id"]],
        }
        self.data["evidence"] = [evidence]
        self.assertEqual(self.codes(root=root), set())
        evidence["kind"] = "design_note"
        self.assertIn("ASSURANCE_EVIDENCE", self.codes(root=root))
        evidence["kind"] = "test_report"
        evidence["claims"] = ["C-RETURN"]
        self.assertIn("EVIDENCE_REF", self.codes(root=root))
        evidence["claims"] = [claim["id"]]
        evidence_path.write_text("changed", encoding="utf-8")
        self.assertIn("EVIDENCE_HASH", self.codes(root=root))

    def test_missing_harness_and_instance(self):
        self.data["connections"][0]["harness"] = "missing"
        self.data["harnesses"][0]["instance"] = "missing"
        self.assertTrue({"HARNESS_REF", "HARNESS_INSTANCE"}.issubset(self.codes()))

    def test_excluded_harness(self):
        self.data["variants"][0]["exclude"] = ["CABLE"]
        self.assertIn("VARIANT_HARNESS", self.codes())

    def test_units_and_positive_harness_measurements(self):
        self.data["mechanical"][0]["units"] = "inch"
        self.data["harnesses"][0]["length_mm"] = 0
        self.assertIn("SCHEMA", self.codes())

    def test_missing_mechanical_drawing_and_instance(self):
        self.data["mechanical"][0]["drawing"] = "docs/missing.step"
        self.data["mechanical"][0]["instances"] = ["missing"]
        self.assertTrue({"MECHANICAL_DRAWING", "MECHANICAL_INSTANCE"}.issubset(self.codes()))

    def test_release_cannot_be_authorized_by_training_pass(self):
        result = check(ROOT, release=True)
        self.assertEqual(result.status, "FAIL")
        self.assertIn("RELEASE_NOT_IMPLEMENTED", {row.code for row in result.issues})

    def test_bom_purchased_built_phantom_and_variant(self):
        product = self.model()
        standard = {row.part_id: row for row in bom_rows(product, self.parts, product.variants[0])}
        uno = {row.part_id: row for row in bom_rows(product, self.parts, product.variants[1])}
        self.assertEqual(standard["training-generic-led-red-5mm"].quantity, 2)
        self.assertEqual(uno["training-generic-led-red-5mm"].quantity, 1)
        self.assertEqual(standard["training-generic-cable"].quantity, 1)
        self.assertNotIn("training-status-system", standard)
        self.assertNotIn("training-uno-indicator", standard)
        self.assertEqual(sum(row.quantity for row in standard.values()), 8)

    def test_nested_quantities_multiply(self):
        self.data["assemblies"][0]["members"][0]["quantity"] = 3
        product = self.model()
        rows = {row.part_id: row for row in bom_rows(product, self.parts, product.variants[0])}
        self.assertEqual(rows["training-generic-led-red-5mm"].quantity, 4)

    def test_bom_order_is_deterministic(self):
        product = self.model()
        before = csv_bytes(bom_rows(product, self.parts, product.variants[0]))
        self.data["assemblies"].reverse()
        for assembly in self.data["assemblies"]:
            assembly["members"].reverse()
        product = self.model()
        self.assertEqual(before, csv_bytes(bom_rows(product, self.parts, product.variants[0])))

    def test_bom_escapes_spreadsheet_formulas(self):
        cable = self.parts["training-generic-cable"].model_copy(
            update={"manufacturer": "=supplier", "mpn": "+1+1"}
        )
        product = self.model()
        content = csv_bytes(bom_rows(product, {**self.parts, cable.id: cable}, product.variants[0]))
        row = next(csv.DictReader(content.decode(encoding="utf-8").splitlines()))
        cable_row = next(
            item
            for item in csv.DictReader(content.decode(encoding="utf-8").splitlines())
            if item["part_id"] == cable.id
        )
        self.assertIn("part_id", row)
        self.assertEqual(cable_row["manufacturer"], "'=supplier")
        self.assertEqual(cable_row["mpn"], "'+1+1")

    def test_purchasing_bom_escapes_catalog_and_native_text_fields(self):
        root = self.stage()
        catalog_path = root / "catalog/parts.json"
        catalog = read_model(catalog_path, PartsCatalog)
        part = catalog.parts[0].model_copy(
            update={"manufacturer": "=supplier", "mpn": "+part-number"}
        )
        write_model(catalog_path, catalog.model_copy(update={"parts": (part, *catalog.parts[1:])}))
        native = root / "native-bom.csv"
        native.write_text(
            "Reference,Value,Footprint,PartID,DNP\n@R1,-value,=footprint," + part.id + ",DNP\n",
            encoding="utf-8",
        )
        output = root / "purchasing-bom.csv"
        purchasing_bom(root, native, output)
        with output.open(newline="", encoding="utf-8") as stream:
            row = next(csv.DictReader(stream))
        for column in ("Reference", "Value", "Footprint", "Manufacturer", "MPN"):
            self.assertTrue(row[column].startswith("'"), column)

    def test_stale_and_missing_generated_outputs(self):
        root = self.stage()
        generate(root)
        self.assertEqual(drift(root), ())
        target = root / "examples/products/status-indicator-system/build/STANDARD.bom.csv"
        target.write_text("stale", encoding="utf-8")
        self.assertTrue(any("STANDARD.bom.csv" in issue for issue in drift(root)))
        (target.parent / "OLD.bom.csv").write_text("old", encoding="utf-8")
        self.assertTrue(any("STALE_OUTPUT" in issue for issue in drift(root)))

    def test_published_schema_matches_implementation(self):
        outputs = expected_outputs(ROOT)
        for name, model in (
            ("product-v1", ProductRecord),
            ("project-manifest-v1", ProjectManifest),
            ("release-manifest-v1", ReleaseManifest),
            ("release-policies-v1", ReleasePoliciesCatalog),
            ("template-contract-v1", TemplateContract),
        ):
            with self.subTest(schema=name):
                self.assertEqual(
                    json.loads(outputs[f"schemas/{name}.schema.json"]), model.model_json_schema()
                )

    def test_unregistered_product_discovered(self):
        root = self.stage()
        (root / "examples/products/forgotten").mkdir()
        (root / "examples/products/forgotten/product.json").write_text("{}", encoding="utf-8")
        self.assertIn("PRODUCT_DISCOVERY", {issue.code for issue in load_repository(root).issues})

    def test_project_scope_checks_only_products_that_declare_the_project(self):
        controller = check(ROOT, selected_project_ids=("controller",))
        status_led = check(ROOT, selected_project_ids=("arduino-uno-status-led",))
        self.assertEqual(controller.products, ())
        self.assertEqual(status_led.products, ("status-indicator-system",))

    def test_full_product_check_rejects_an_incorrect_project_index(self):
        root = self.stage()
        index_path = root / "catalog/products.json"
        index = json.loads(index_path.read_text(encoding="utf-8"))
        index["products"][0]["project_ids"] = ["controller"]
        index_path.write_text(json.dumps(index), encoding="utf-8")
        self.assertIn("PRODUCT_PROJECTS", {issue.code for issue in check(root).issues})

    def test_selected_discovery_checks_its_island_and_full_discovers_unrelated_files(self):
        root = self.stage()
        (root / "examples/projects/forgotten.kicad_pro").write_text("{}", encoding="utf-8")
        self.assertTrue(any("project discovery" in issue for issue in lint(root).issues))
        self.assertFalse(
            any("project discovery" in issue for issue in lint(root, ["controller"]).issues)
        )
        (root / "examples/projects/controller/kicad/forgotten.kicad_pro").write_text(
            "{}",
            encoding="utf-8",
        )
        self.assertTrue(
            any("project discovery" in issue for issue in lint(root, ["controller"]).issues)
        )

    def test_selected_lint_retains_global_catalog_path_safety(self):
        root = self.stage()
        path = root / "catalog/libraries.json"
        catalog = read_model(path, LibrariesCatalog)
        bad = catalog.libraries[0].model_copy(update={"provenance_path": "../outside.md"})
        write_model(path, catalog.model_copy(update={"libraries": (bad,)}))
        issues = lint(root, ["controller"]).issues
        self.assertTrue(any("unsafe provenance" in issue for issue in issues), issues)

    def test_native_netlist_identity_adapter(self):
        root = ET.Element("export")
        components = ET.SubElement(root, "components")
        for member in self.data["assemblies"][1]["members"]:
            component = ET.SubElement(components, "comp", ref=member["ref"])
            fields = ET.SubElement(component, "fields")
            ET.SubElement(fields, "field", name="PART_ID").text = member["item"]
        path = self.temp / "unit-only-netlist.xml"
        ET.ElementTree(root).write(path)
        self.assertEqual(check_project_netlist(ROOT, "arduino-uno-status-led", path).status, "PASS")
        root.find("./components/comp/fields/field").text = "wrong-part"
        ET.ElementTree(root).write(path)
        with self.assertRaisesRegex(ValueError, "PART_ID mismatch"):
            check_project_netlist(ROOT, "arduino-uno-status-led", path)

    def test_standalone_board_identity_catches_swapped_part_ids_without_a_product(self):
        repository = self.stage()
        directory = repository / "projects/standalone-led"
        shutil.copytree(repository / "examples/projects/arduino-uno-status-led", directory)
        manifest = json.loads((directory / "project.json").read_text())
        manifest["id"] = "standalone-led"
        (directory / "project.json").write_text(json.dumps(manifest), encoding="utf-8")
        discovery_path = repository / "catalog/projects.json"
        discovery = json.loads(discovery_path.read_text())
        discovery["project_roots"] = ["projects"]
        discovery_path.write_text(json.dumps(discovery), encoding="utf-8")
        (repository / "catalog/products.json").write_text(
            json.dumps({"schema_version": "1", "products": []}), encoding="utf-8"
        )
        root = ET.Element("export")
        components = ET.SubElement(root, "components")
        fields_by_ref = {}
        for member in self.data["assemblies"][1]["members"]:
            component = ET.SubElement(components, "comp", ref=member["ref"])
            fields = ET.SubElement(component, "fields")
            field = ET.SubElement(fields, "field", name="PART_ID")
            field.text = member["item"]
            fields_by_ref[member["ref"]] = field
        path = self.temp / "unit-only-netlist.xml"
        ET.ElementTree(root).write(path)
        self.assertEqual(check_project_netlist(repository, "standalone-led", path).status, "PASS")
        fields_by_ref["D1"].text, fields_by_ref["R1"].text = (
            fields_by_ref["R1"].text,
            fields_by_ref["D1"].text,
        )
        ET.ElementTree(root).write(path)
        with self.assertRaisesRegex(ValueError, "PART_ID mismatch"):
            check_project_netlist(repository, "standalone-led", path)

    def test_windows_posix_traversal_and_case_paths(self):
        for value in (
            "C:/private/model.step",
            "C:relative.step",
            "//server/share",
            "/tmp/file",
            "../escape",
            "a/../b",
            "a\\b",
            "a//b",
            "NUL.txt",
            "a./file",
            "a?b",
            "a|b",
            ".",
        ):
            with self.subTest(value=value), self.assertRaises(ValueError):
                repo_path(self.temp, value)
        (self.temp / "Case.txt").write_text("test", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "case mismatch"):
            repo_path(self.temp, "case.txt")

    def test_linked_source_root_rejected(self):
        directory = self.temp / "real"
        directory.mkdir()
        try:
            (self.temp / "linked").symlink_to(directory, target_is_directory=True)
        except OSError:
            self.skipTest("Host does not allow creating symlinks")
        with self.assertRaisesRegex(ValueError, "Linked"):
            repo_path(self.temp, "linked/file")

    def test_machine_local_cad_paths_and_unknown_variables(self):
        path = self.temp / "fp-lib-table"
        for value in (
            "C:/parts/private.pretty",
            "/home/parts/local.pretty",
            "${MY_LIBRARY}/part.pretty",
        ):
            with self.subTest(value=value):
                path.write_text(f'(uri "{value}")', encoding="utf-8")
                self.assertTrue(
                    cad_dependencies(self.temp, path, self.temp, "10", frozenset(), frozenset())
                )
        path.write_text('(uri "${KICAD10_FOOTPRINT_DIR}/Connector.pretty")', encoding="utf-8")
        self.assertEqual(
            cad_dependencies(self.temp, path, self.temp, "10", frozenset(), frozenset()), []
        )

    def test_tracked_local_state_classification(self):
        for value in (
            "examples/projects/a.kicad_prl",
            "examples/projects/~a.lck",
            "examples/projects/a-backups/a.zip",
            "build/bom.csv",
            "tools/__pycache__/a.pyc",
            "Desktop.ini",
            ".vscode/settings.json",
        ):
            self.assertTrue(ephemeral(value), value)
        for value in (
            "examples/projects/a.kicad_pro",
            "libraries/a.kicad_sym",
            "generated/product/a/STANDARD.bom.csv",
        ):
            self.assertFalse(ephemeral(value), value)

    def test_unmanaged_artifacts_are_rejected_but_engineering_records_remain_available(self):
        for value in (
            "handoff/review-notes.docx",
            "capture/schematic.png",
            "meeting/demo.mp4",
            "downloads/vendor.zip",
            "install/kicad.msi",
        ):
            self.assertTrue(unmanaged_artifact(value), value)
        for value in (
            "docs/released-drawing.pdf",
            "mechanical/enclosure.step",
            "mechanical/outline.dxf",
            "catalog/parts.json",
        ):
            self.assertFalse(unmanaged_artifact(value), value)

    def test_repository_gate_rejects_force_added_unmanaged_artifact(self):
        completed = subprocess.CompletedProcess(
            args=("git", "ls-files"),
            returncode=0,
            stdout="docs/meeting-notes.docx\0references/planning-packet.zip\0",
            stderr="",
        )
        with patch("kicad_tooling.hwrepo.repository.subprocess.run", return_value=completed):
            report = check_repository(ROOT)
        self.assertEqual(report.status, "FAIL")
        self.assertIn("TRACKED_UNMANAGED_ARTIFACT: docs/meeting-notes.docx", report.issues)
        self.assertIn("TRACKED_UNMANAGED_ARTIFACT: references/planning-packet.zip", report.issues)

    def test_gitignore_matches_the_repository_hygiene_boundary(self):
        for ignored in (
            "Thumbs.db",
            "Desktop.ini",
            ".DS_Store",
            ".vscode/settings.json",
            "~$budget.xlsx",
            "handoff/review-notes.docx",
            "capture/schematic.png",
            "meeting/demo.mp4",
            "downloads/vendor.zip",
            "install/kicad.msi",
            "generated/product/a/STANDARD.bom.csv",
            "schemas/product-v1.schema.json",
        ):
            with self.subTest(ignored=ignored):
                result = subprocess.run(
                    ["git", "check-ignore", "--no-index", "-q", "--", ignored],
                    cwd=ROOT,
                    check=False,
                )
                self.assertEqual(result.returncode, 0)
        for source in (
            "examples/projects/controller/kicad/controller.kicad_pro",
            "docs/released-drawing.pdf",
            "mechanical/enclosure.step",
            "mechanical/outline.dxf",
        ):
            with self.subTest(source=source):
                result = subprocess.run(
                    ["git", "check-ignore", "--no-index", "-q", "--", source],
                    cwd=ROOT,
                    check=False,
                )
                self.assertEqual(result.returncode, 1)

    def test_governance_placeholders_do_not_count_as_review(self):
        for value in (
            "replace-with-reviewer",
            "replace_with_reviewer",
            "https://example.invalid/evidence",
            "unknown",
        ):
            self.assertFalse(reviewed_value(value))

    def test_review_snapshot_hashes_and_write_once(self):
        root = self.stage()
        output = root / "build/review"

        def fake_git(argv, **kwargs):
            return subprocess.CompletedProcess(
                argv,
                0,
                "a" * 40
                if "rev-parse" in argv
                else " M examples/products/status-indicator-system/product.json\n",
                "",
            )

        with patch("kicad_tooling.hwrepo.generation.subprocess.run", side_effect=fake_git):
            manifest = snapshot(root, output)
            self.assertFalse(manifest.working_tree_clean)
            self.assertEqual(manifest.checks["kicad"], "NOT_RUN")
            self.assertFalse(manifest.build_authorized)
            self.assertEqual(verify_snapshot(output).status, "PASS")
            with self.assertRaises(FileExistsError):
                snapshot(root, output)
        (output / "examples/products/status-indicator-system/build/STANDARD.bom.csv").write_text(
            "tampered", encoding="utf-8"
        )
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            verify_snapshot(output)

    def test_generation_does_not_write_invalid_product(self):
        root = self.stage()
        self.data["connections"][0]["to"] = "missing"
        (root / "examples/products/status-indicator-system/product.json").write_text(
            json.dumps(self.data), encoding="utf-8"
        )
        with self.assertRaises(ValueError):
            generate(root)
        self.assertFalse((root / "generated").exists())

    def test_direct_kicad_validator_cannot_bypass_product_policy(self):
        from kicad_tooling.validate import validate

        root = self.stage()
        self.data["connections"][0]["to"] = "missing"
        (root / "examples/products/status-indicator-system/product.json").write_text(
            json.dumps(self.data), encoding="utf-8"
        )
        with patch("kicad_tooling.validate.execute") as execute:
            result = validate(
                root,
                root / "output",
                "must-not-run",
                Path("examples/projects/arduino-uno-status-led/project.json"),
            )
        self.assertEqual(result.status, "FAIL")
        self.assertEqual(result.checks["product_policy"].status, "FAIL")
        execute.assert_not_called()


if __name__ == "__main__":
    unittest.main()
