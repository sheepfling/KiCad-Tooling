"""Selection-page escaping and entry-point mode guards."""

from __future__ import annotations

import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from kicad_tooling.hwrepo.contracts import read_model
from kicad_tooling.hwrepo.models import (
    PartCadBinding,
    PartCadComponent,
    PartPickerItem,
    PartPickerReport,
    PartRecord,
    PartSelectionMap,
    PartSelectionReport,
    PartSourceEdit,
    PartStatus,
)
from kicad_tooling.hwrepo.part_picker_view import render_picker, render_selection, save_selection


class PickerViewTests(unittest.TestCase):
    def picker(self) -> PartPickerReport:
        part = PartRecord(
            id="reviewed-r",
            revision="A",
            description="Example <em>untrusted</em>",
            part_class="resistor",
            unit="each",
            manufacturer="Test & Co",
            mpn="FIXTURE-1K",
            datasheet_url="https://example.invalid",
            lifecycle="fixture",
            status=PartStatus.APPROVED,
            cad=PartCadBinding(
                symbol_id="Test:R",
                value="1k",
                footprint="Test:R",
                model="projects/pilot/kicad/body.step",
                digikey_sku="FIXTURE-SKU",
            ),
        )
        component = PartCadComponent(
            reference="R1",
            symbol_id="Test:R",
            value="1k",
            footprint="Test:R",
            source_path="projects/pilot/kicad/pilot.kicad_sch",
            uuid="fixture",
        )
        return PartPickerReport(
            status="READY",
            project_id="pilot",
            receipt_dir="/tmp/receipt",
            items=(PartPickerItem(component=component, choice_ids=(part.id,)),),
            choices=(part,),
            selection_template=PartSelectionMap(
                project_id="pilot",
                preconditions={
                    "projects/pilot/docs/purchasing.json": None,
                    "unsafe</script><script>fixture": "a" * 64,
                },
            ),
        )

    def test_untrusted_text_and_embedded_map_cannot_create_markup(self) -> None:
        page = render_picker(self.picker())
        self.assertIn("Example &lt;em&gt;untrusted&lt;/em&gt;", page)
        self.assertNotIn("Example <em>", page)
        self.assertNotIn("unsafe</script>", page)
        payload = re.search(r'id="selection-template">(.*?)</script>', page)
        self.assertIsNotNone(payload)
        assert payload is not None
        restored = PartSelectionMap.model_validate_json(payload.group(1))
        self.assertEqual(restored, self.picker().selection_template)
        self.assertIn('id="download-selection" type="submit" disabled', page)
        self.assertNotIn('<option value="reviewed-r" selected', page)
        for text in ("FIXTURE-SKU", "projects/pilot/kicad/body.step", "Test:R", "F8"):
            self.assertIn(text, page)

    def test_missing_catalog_has_action_and_no_invented_choice(self) -> None:
        report = self.picker().model_copy(
            update={
                "status": "NEEDS_CATALOG",
                "choices": (),
                "items": (self.picker().items[0].model_copy(update={"choice_ids": ()}),),
            }
        )
        page = render_picker(report)
        self.assertIn("Add reviewed parts to unlock the picker", page)
        self.assertNotIn("<select ", page)
        self.assertIn("Current footprint: Test:R", page)

    def test_blocked_picker_does_not_offer_download(self) -> None:
        report = self.picker().model_copy(
            update={
                "status": "BLOCKED",
                "selection_template": None,
                "issues": ("Source changed; create a fresh picker.",),
            }
        )
        page = render_picker(report)
        self.assertNotIn("<form", page)
        self.assertNotIn('id="download-selection"', page)
        self.assertIn("Source changed", page)

    def test_preview_escapes_diff_and_reports_placement_gap(self) -> None:
        report = PartSelectionReport(
            status="PLAN",
            project_id="pilot",
            receipt_dir="/tmp/receipt",
            edits=(
                PartSourceEdit(
                    path="projects/pilot/kicad/pilot.kicad_sch",
                    before='(property "Value" "<script>")\n',
                    after='(property "Value" "<em>")\n',
                ),
            ),
            pending_references=("R1",),
            next_commands=("python -B -m kicad_tooling.parts --sync-models",),
        )
        page = render_selection(report)
        self.assertNotIn("<script>", page)
        self.assertIn("&lt;script&gt;", page)
        self.assertIn("diff-remove", page)
        self.assertIn("diff-add", page)
        self.assertIn("Update PCB from Schematic (F8)", page)
        self.assertIn("--sync-models", page)

    def test_new_preferences_receipt_preserves_null_before_state(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            report = PartSelectionReport(
                status="PLAN",
                project_id="pilot",
                receipt_dir=temporary,
                edits=(
                    PartSourceEdit(
                        path="projects/pilot/docs/purchasing.json", before=None, after="{}\n"
                    ),
                ),
            )
            save_selection(output, report)
            self.assertEqual(read_model(output / "report.json", PartSelectionReport), report)

    def test_conflicting_cli_flags_fail_before_creating_receipt(self) -> None:
        root = Path(__file__).resolve().parents[1]
        cases = (
            ("--apply",),
            ("--picker", "--boards", "5"),
            ("--sync-models", "--apply"),
            ("--selection", "x.json", "--native-summary", "x"),
            ("--picker", "--init-preferences", "x.json"),
            ("--selection", "x.json", "--runner", "container"),
        )
        for arguments in cases:
            with self.subTest(arguments=arguments):
                result = subprocess.run(
                    (
                        sys.executable,
                        "-B",
                        "-m",
                        "kicad_tooling.parts",
                        "--project",
                        "invalid-no-discovery",
                        *arguments,
                    ),
                    cwd=root,
                    text=True,
                    capture_output=True,
                    check=False,
                )
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertIn("error:", result.stderr)


if __name__ == "__main__":
    unittest.main()
