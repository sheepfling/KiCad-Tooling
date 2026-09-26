"""Purchasing review keeps exact identities and excludes ambiguous orders."""

from __future__ import annotations

import csv
import io
import tempfile
import unittest
from pathlib import Path

from pydantic import ValidationError

from kicad_tooling.hwrepo.models import (
    PartRecord,
    PartsCatalog,
    PartStatus,
    PurchasingComponent,
    PurchasingPlan,
    PurchasingPreferences,
    PurchasingReport,
)
from kicad_tooling.hwrepo.purchasing import plan, read_components, write_csvs


def part(
    identifier: str = "RES-1",
    mpn: str = "RC0603FR-071KL",
    manufacturer: str = "Yageo",
    status: PartStatus = PartStatus.APPROVED,
) -> PartRecord:
    return PartRecord(
        id=identifier,
        revision="A",
        description="Test resistor",
        part_class="resistor",
        unit="each",
        manufacturer=manufacturer,
        mpn=mpn,
        datasheet_url="https://example.test/datasheet",
        lifecycle="active",
        status=status,
    )


def component(
    reference: str = "R1",
    identifier: str | None = "RES-1",
    value: str = "1k",
    footprint: str = "Resistor_SMD:R_0603_1608Metric",
    dnp: bool = False,
    exclude: bool = False,
) -> PurchasingComponent:
    return PurchasingComponent(
        reference=reference,
        value=value,
        footprint=footprint,
        part_id=identifier,
        dnp=dnp,
        exclude_from_bom=exclude,
    )


def catalog(*parts: PartRecord) -> PartsCatalog:
    return PartsCatalog(schema_version="1", parts=parts or (part(),))


def codes(purchase_plan: PurchasingPlan) -> set[str]:
    return {finding.code for finding in purchase_plan.findings}


class PurchasingTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="purchasing-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def native(self, content: str) -> tuple[PurchasingComponent, ...]:
        path = self.root / "netlist.xml"
        path.write_text(content, encoding="utf-8")
        return read_components(path)

    def test_quantities_grouping_and_exact_digikey_override(self) -> None:
        preferences = PurchasingPreferences(
            boards=3, spare_percent=20, spare_minimum=1, digikey_skus={"RES-1": "311-1.00KHRCT-ND"}
        )
        result = plan((component("R2"), component()), catalog(), preferences, ("RES-1",))
        self.assertEqual(result.status, "READY_FOR_ORDER_REVIEW")
        self.assertEqual(len(result.lines), 1)
        line = result.lines[0]
        self.assertEqual(
            (line.references, line.per_board, line.required, line.spares, line.quantity),
            (("R1", "R2"), 2, 6, 2, 8),
        )
        self.assertEqual(
            (line.order_number, line.order_number_kind), ("311-1.00KHRCT-ND", "DigiKey")
        )
        self.assertFalse(result.purchase_authorized)
        self.assertFalse(result.build_authorized)
        minimum = plan(
            (component(),), catalog(), PurchasingPreferences(spare_minimum=3), ("RES-1",)
        )
        self.assertEqual(minimum.lines[0].quantity, 4)

    def test_native_properties_and_nested_variants_are_distinct(self) -> None:
        components = self.native("""<export><components>
          <comp ref="R3"><value>1k</value><footprint>R:F</footprint>
            <fields><field name="PART_ID">RES-1</field></fields>
            <variants><variant name="other"><property name="dnp" value="yes"/></variant></variants>
          </comp>
          <comp ref="R2"><property name="exclude_from_bom"/></comp>
          <comp ref="R1"><property name="dnp"/></comp>
        </components></export>""")
        self.assertTrue(components[0].dnp)
        self.assertTrue(components[1].exclude_from_bom)
        self.assertFalse(components[2].dnp)
        result = plan(components, catalog(), PurchasingPreferences(), ("RES-1",))
        self.assertEqual(result.excluded_references, ("R1", "R2"))
        self.assertEqual(result.lines[0].references, ("R3",))
        self.assertEqual(result.status, "READY_FOR_ORDER_REVIEW")

    def test_native_explicit_true_and_false_ambiguity(self) -> None:
        for value in ("true", "yes", "1", ""):
            with self.subTest(value=value):
                result = self.native(
                    f'<export><components><comp ref="R1"><property name="dnp" value="{value}"/></comp></components></export>'
                )
                self.assertTrue(result[0].dnp)
        for value in ("false", "0", "no", "maybe"):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "Ambiguous"):
                self.native(
                    f'<export><components><comp ref="R1"><property name="dnp" value="{value}"/></comp></components></export>'
                )

    def test_native_rejects_malformed_empty_missing_and_duplicate_records(self) -> None:
        for source in (
            "",
            "<bad>",
            "<export/>",
            "<export><components/></export>",
            '<export><components><comp ref="R1"/><comp ref="R1"/></components></export>',
            '<export><components><comp ref="R1"/></components><components/></export>',
            "<export><components><comp/></components></export>",
            '<export><components><comp ref="R1"><fields><field name="PART_ID">A</field><field name="PART_ID">B</field></fields></comp></components></export>',
            '<export><components><comp ref="R1"><property name="dnp"/><property name="dnp"/></comp></components></export>',
            '<export><components><comp ref="R1"><value>A</value><value>B</value></comp></components></export>',
            '<export><components><comp ref="R1"><fields/><fields/></comp></components></export>',
            '<export><components><comp ref="R1"><fields><field>A</field></fields></comp></components></export>',
            '<export><components><comp ref="R1"><footprint><bad/></footprint></comp></components></export>',
        ):
            with self.subTest(source=source), self.assertRaises(ValueError):
                self.native(source)

    def test_preferences_strict_boundary_and_round_trip(self) -> None:
        preferences = PurchasingPreferences(
            boards=4, spare_percent=25, spare_minimum=2, digikey_skus={"RES-1": "ABC-01-ND"}
        )
        self.assertEqual(
            PurchasingPreferences.model_validate_json(preferences.model_dump_json()), preferences
        )
        for source in (
            "[]",
            "null",
            "5",
            '"bad"',
            '{"schema_version":"2"}',
            '{"schema_version":1}',
            '{"schema_version":true}',
            '{"boards":"2"}',
            '{"boards":true}',
            '{"boards":0}',
            '{"spare_percent":101}',
            '{"spare_percent":-1}',
            '{"spare_minimum":-1}',
            '{"surprise":1}',
            '{"digikey_skus":{"RES-1":""}}',
            '{"digikey_skus":{"RES-1":" X-ND "}}',
            '{"digikey_skus":{"RES-1":"X\\nND"}}',
            '{"digikey_skus":{"RES-1":123}}',
            '{"digikey_skus":[]}',
        ):
            with self.subTest(source=source), self.assertRaises(ValidationError):
                PurchasingPreferences.model_validate_json(source)

    def test_component_plan_report_roundtrip_and_strictness(self) -> None:
        result = plan((component(),), catalog(), PurchasingPreferences(), ("RES-1",))
        report = PurchasingReport(
            project_id="example",
            status=result.status,
            plan=result,
            receipt_dir="build/parts/example",
        )
        self.assertEqual(PurchasingPlan.model_validate_json(result.model_dump_json()), result)
        self.assertEqual(PurchasingReport.model_validate_json(report.model_dump_json()), report)
        self.assertEqual(
            PurchasingComponent.model_validate_json(component().model_dump_json()), component()
        )
        for model, source in (
            (
                PurchasingPlan,
                result.model_dump_json().replace('"schema_version":"1"', '"schema_version":"2"', 1),
            ),
            (
                PurchasingReport,
                report.model_dump_json().replace(
                    '"schema_version":"1"', '"schema_version":true', 1
                ),
            ),
            (PurchasingComponent, '{"reference":"R1","value":"x","footprint":"x","dnp":"true"}'),
            (PurchasingComponent, '{"reference":"R1","value":"x","footprint":"x","unexpected":1}'),
        ):
            with self.subTest(source=source), self.assertRaises(ValidationError):
                model.model_validate_json(source)

    def test_missing_unknown_and_undeclared_identity(self) -> None:
        for item, allowed, expected in (
            (component(identifier=None), ("RES-1",), "MISSING_PART_ID"),
            (component(identifier="missing"), ("RES-1",), "UNKNOWN_PART_ID"),
            (component(), (), "UNDECLARED_PART_ID"),
            (component(footprint=""), ("RES-1",), "MISSING_FOOTPRINT"),
            (component(value=""), ("RES-1",), "MISSING_VALUE"),
        ):
            with self.subTest(expected=expected):
                result = plan((item,), catalog(), PurchasingPreferences(), allowed)
                self.assertIn(expected, codes(result))
                self.assertEqual(result.status, "NEEDS_PARTS")

    def test_training_and_placeholder_parts_cannot_be_ordered(self) -> None:
        for record, expected in (
            (part(status=PartStatus.TRAINING), "UNAPPROVED_PART"),
            (part(mpn="TBD"), "PLACEHOLDER_PART"),
            (part(manufacturer="UNSPECIFIED — training fixture"), "PLACEHOLDER_PART"),
        ):
            with self.subTest(expected=expected):
                result = plan((component(),), catalog(record), PurchasingPreferences(), ("RES-1",))
                self.assertIn(expected, codes(result))
                self.assertEqual(result.lines, ())

    def test_all_excluded_and_empty_components_block_order(self) -> None:
        for components in ((), (component(dnp=True),), (component(exclude=True),)):
            with self.subTest(components=components):
                result = plan(components, catalog(), PurchasingPreferences(), ("RES-1",))
                self.assertIn("NO_FITTED_COMPONENTS", codes(result))
                self.assertEqual(result.lines, ())

    def test_duplicate_catalog_ids_and_commercial_identities_block(self) -> None:
        for parts, expected in (
            (catalog(part(), part(mpn="different")), "DUPLICATE_PART_ID"),
            (catalog(part(), part(identifier="RES-2")), "DUPLICATE_PART_IDENTITY"),
        ):
            with self.subTest(expected=expected):
                result = plan(
                    (component(), component("R2", "RES-2")),
                    parts,
                    PurchasingPreferences(),
                    ("RES-1", "RES-2"),
                )
                self.assertIn(expected, codes(result))

    def test_duplicate_component_reference_blocks(self) -> None:
        result = plan((component(), component()), catalog(), PurchasingPreferences(), ("RES-1",))
        self.assertIn("DUPLICATE_REFERENCE", codes(result))

    def test_conflicting_part_usage_blocks_without_choosing_alternate(self) -> None:
        for other in (component("R2", value="10k"), component("R2", footprint="R:0805")):
            with self.subTest(other=other):
                result = plan((component(), other), catalog(), PurchasingPreferences(), ("RES-1",))
                self.assertIn("INCONSISTENT_PART_USE", codes(result))
                self.assertEqual(result.lines, ())

    def test_unknown_conflicting_and_placeholder_sku_override(self) -> None:
        parts = catalog(part(), part(identifier="RES-2", mpn="OTHER"))
        for overrides, allowed, expected in (
            ({"absent": "ABC-ND"}, ("RES-1", "RES-2"), "UNKNOWN_SKU_OVERRIDE"),
            ({"RES-2": "ABC-ND"}, ("RES-1",), "UNKNOWN_SKU_OVERRIDE"),
            ({"RES-1": "ABC-ND", "RES-2": "ABC-ND"}, ("RES-1", "RES-2"), "CONFLICTING_SKU"),
            ({"RES-1": "TBD"}, ("RES-1", "RES-2"), "PLACEHOLDER_SKU"),
        ):
            with self.subTest(expected=expected):
                result = plan(
                    (component(),), parts, PurchasingPreferences(digikey_skus=overrides), allowed
                )
                self.assertIn(expected, codes(result))

    def test_csv_groups_once_preserves_identifiers_and_has_stable_bytes(self) -> None:
        result = plan(
            (component("R2"), component(), component("R3", dnp=True)),
            catalog(),
            PurchasingPreferences(boards=5, spare_minimum=1),
            ("RES-1",),
        )
        names = write_csvs(self.root / "first", result)
        reordered = plan(
            tuple(reversed(result.components)), catalog(), result.preferences, ("RES-1",)
        )
        self.assertEqual(names, ("bom.csv", "digikey.csv"))
        write_csvs(self.root / "second", reordered)
        for name in names:
            self.assertEqual(
                (self.root / "first" / name).read_bytes(),
                (self.root / "second" / name).read_bytes(),
            )
        review = list(csv.DictReader(io.StringIO((self.root / "first/bom.csv").read_text())))
        self.assertEqual(len(review), 2)
        self.assertEqual(review[0]["Reference"], "R1; R2")
        self.assertEqual(review[0]["Order Quantity"], "11")
        self.assertEqual(review[1]["Order Quantity"], "")
        order = list(csv.reader(io.StringIO((self.root / "first/digikey.csv").read_text())))
        self.assertEqual(
            order, [["Part Number", "Quantity", "Customer Reference"], [part().mpn, "11", "RES-1"]]
        )
        self.assertIn("Yageo%20RC0603FR-071KL", result.lines[0].search_url)

    def test_blocked_plan_emits_review_only(self) -> None:
        result = plan((component(identifier=None),), catalog(), PurchasingPreferences(), ("RES-1",))
        self.assertEqual(write_csvs(self.root, result), ("bom.csv",))
        self.assertFalse((self.root / "digikey.csv").exists())
        self.assertIn("MISSING_PART_ID", (self.root / "bom.csv").read_text())

    def test_unsafe_cells_reject_all_outputs_without_mutating_ids(self) -> None:
        for index, unsafe in enumerate(
            ("=1+2", "+123", "-123", "@SUM(A1)", "MPN\nNEXT", "MPN\tNEXT")
        ):
            with self.subTest(unsafe=unsafe):
                result = plan(
                    (component(),), catalog(part(mpn=unsafe)), PurchasingPreferences(), ("RES-1",)
                )
                output = self.root / str(index)
                with self.assertRaisesRegex(ValueError, "CSV text"):
                    write_csvs(output, result)
                self.assertFalse(output.exists())
                self.assertEqual(result.lines[0].order_number, unsafe)
        result = plan(
            (component(),),
            catalog(),
            PurchasingPreferences(digikey_skus={"RES-1": "=1+2"}),
            ("RES-1",),
        )
        with self.assertRaisesRegex(ValueError, "formula"):
            write_csvs(self.root / "sku", result)
        self.assertFalse((self.root / "sku").exists())

    def test_stale_files_are_never_overwritten_and_no_partial_order(self) -> None:
        result = plan((component(),), catalog(), PurchasingPreferences(), ("RES-1",))
        stale = self.root / "digikey.csv"
        stale.write_text("old order", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "replace existing"):
            write_csvs(self.root, result)
        self.assertEqual(stale.read_text(), "old order")
        self.assertFalse((self.root / "bom.csv").exists())

    def test_forged_ready_plan_with_findings_cannot_export_order(self) -> None:
        result = plan((component(identifier=None),), catalog(), PurchasingPreferences(), ("RES-1",))
        forged = result.model_copy(update={"status": "READY_FOR_ORDER_REVIEW"})
        with self.assertRaisesRegex(ValueError, "Ready purchasing plan"):
            write_csvs(self.root, forged)
        self.assertFalse((self.root / "digikey.csv").exists())
        self.assertFalse((self.root / "bom.csv").exists())

    def test_unused_commercial_duplicates_do_not_block_selected_board(self) -> None:
        parts = catalog(
            part(),
            part(identifier="UNUSED-A", mpn="OTHER"),
            part(identifier="UNUSED-B", mpn="OTHER"),
        )
        result = plan((component(),), parts, PurchasingPreferences(), ("RES-1",))
        self.assertEqual(result.status, "READY_FOR_ORDER_REVIEW")

    def test_same_mpn_different_manufacturers_requires_distinct_supplier_ids(self) -> None:
        parts = catalog(part(), part(identifier="RES-2", manufacturer="Vishay"))
        components = (component(), component("R2", "RES-2"))
        allowed = ("RES-1", "RES-2")
        result = plan(components, parts, PurchasingPreferences(), allowed)
        self.assertIn("ORDER_NUMBER_COLLISION", codes(result))
        self.assertNotIn("DUPLICATE_PART_IDENTITY", codes(result))
        write_csvs(self.root, result)
        self.assertFalse((self.root / "digikey.csv").exists())
        preferences = PurchasingPreferences(digikey_skus={"RES-1": "A-ND", "RES-2": "B-ND"})
        resolved = plan(components, parts, preferences, allowed)
        self.assertEqual(resolved.status, "READY_FOR_ORDER_REVIEW")

    def test_excluded_from_board_still_purchases_if_in_bom(self) -> None:
        components = self.native("""<export><components><comp ref="R1">
          <value>1k</value><footprint>R:F</footprint>
          <fields><field name="PART_ID">RES-1</field></fields>
          <property name="exclude_from_board"/>
        </comp></components></export>""")
        result = plan(components, catalog(), PurchasingPreferences(), ("RES-1",))
        self.assertEqual(result.status, "READY_FOR_ORDER_REVIEW")
        self.assertEqual(result.lines[0].quantity, 1)
