"""CAD CLI keeps source/import separate and prints executable checkout-bound commands."""
from __future__ import annotations

import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from shlex import split
from unittest.mock import patch

from kicad_tooling.hwrepo.contracts import read_model
from kicad_tooling.hwrepo.models import (
    CadBundleCheck,
    CadImportReport,
    CadSourceBundle,
    CadSourceFile,
    CadSourceReport,
    CadSourcingReview,
    CadStepReport,
)
from kicad_tooling.parts import main


class CadCliTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="cad-cli-test-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve() / "CAD repo's files $(literal)"
        self.root.mkdir()
        self.receipt = self.root / "build/source review"
        self.receipt.mkdir(parents=True)
        self.plan_receipt = self.root / "build/import review"
        self.plan_receipt.mkdir()
        self.plan_path = self.plan_receipt / "review's plan.json"
        self.bundle_directory = self.root / "build/source bundle"
        self.bundle = CadSourceBundle(
            supplier_id="C2040", manufacturer="Raspberry Pi", mpn="RP2040", package="QFN",
            symbol_file="library/part.kicad_sym", symbol_name="RP2040",
            footprint_file="library/part.pretty/QFN.kicad_mod", footprint_name="QFN",
            model_file="library/part.3dshapes/QFN.wrl",
            files=(CadSourceFile(path="library/part.kicad_sym", sha256="a" * 64),
                   CadSourceFile(path="library/part.pretty/QFN.kicad_mod", sha256="b" * 64),
                   CadSourceFile(path="library/part.3dshapes/QFN.wrl", sha256="c" * 64)),
            source_url="https://easyeda.com/api/products/C2040/components",
            source_sha256="d" * 64, retrieved_at="2026-09-25T00:00:00+00:00",
        )
        self.source = CadSourceReport(
            status="READY", supplier_id="C2040", bundle_directory=str(self.bundle_directory),
            bundle=self.bundle, receipt_directory=str(self.receipt),
        )
        self.planned = CadImportReport(
            status="PLAN", project_id="controller", symbol_id="CAD_C2040:RP2040",
            footprint_id="CAD_C2040:QFN", plan_path=str(self.plan_path),
            receipt_directory=str(self.plan_receipt),
            check=CadBundleCheck(status="READY", symbol_pins=("1", "2"),
                                 footprint_pads=("1", "2")),
        )

    def invoke(self, arguments: list[str]) -> tuple[int, str]:
        stdout = StringIO()
        with (patch.object(sys, "argv", ["kicad_tooling.parts", "--root", str(self.root),
                                          "--project", "controller", *arguments]),
              redirect_stdout(stdout)):
            status = main()
        return status, stdout.getvalue()

    def test_source_json_passes_exact_identity_refresh_and_receipts_without_applying(self) -> None:
        with (patch("kicad_tooling.parts.new_receipt", side_effect=[self.receipt, self.plan_receipt]) as receipts,
              patch("kicad_tooling.hwrepo.cad_source.fetch", return_value=self.source) as fetch,
              patch("kicad_tooling.hwrepo.cad_library.plan", return_value=self.planned) as plan,
              patch("kicad_tooling.hwrepo.cad_library.apply") as apply):
            status, stdout = self.invoke([
                "--source-cad", "C2040", "--expected-mpn", "RP2040", "--refresh-cad",
                "--output", "build/chosen", "--format", "json",
            ])
        self.assertEqual(status, 0)
        fetch.assert_called_once_with(self.root, "C2040", self.receipt,
                                      expected_mpn="RP2040", refresh=True)
        plan.assert_called_once_with(self.root, "controller", self.bundle_directory, self.plan_receipt)
        self.assertEqual(receipts.call_args_list[0].args, (self.root, "controller", Path("build/chosen")))
        self.assertEqual(receipts.call_args_list[1].args, (self.root, "controller", None))
        apply.assert_not_called()
        review = CadSourcingReview.model_validate_json(stdout)
        self.assertEqual(review.source, self.source)
        self.assertEqual(review.import_plan, self.planned)
        self.assertEqual(read_model(self.receipt / "cad-review.json", CadSourcingReview), review)

    def test_text_followup_preserves_custom_root_and_quotes_every_argument(self) -> None:
        with (patch("kicad_tooling.parts.new_receipt", side_effect=[self.receipt, self.plan_receipt]),
              patch("kicad_tooling.hwrepo.cad_source.fetch", return_value=self.source),
              patch("kicad_tooling.hwrepo.cad_library.plan", return_value=self.planned)):
            status, stdout = self.invoke(["--source-cad", "C2040"])
        self.assertEqual(status, 0)
        self.assertIn("Provider reports: Raspberry Pi RP2040", stdout)
        command = next(line.removeprefix("Then: ") for line in stdout.splitlines()
                       if line.startswith("Then: "))
        self.assertEqual(split(command), [
            "python", "-B", "-m", "kicad_tooling.parts", "--root", str(self.root),
            "--project", "controller", "--import-cad", str(self.plan_path), "--apply",
        ])

    def test_blocked_source_never_previews_or_applies_and_has_nonzero_exit(self) -> None:
        blocked = CadSourceReport(status="BLOCKED", supplier_id="C2040",
            issues=("Provider unavailable",), receipt_directory=str(self.receipt))
        with (patch("kicad_tooling.parts.new_receipt", return_value=self.receipt),
              patch("kicad_tooling.hwrepo.cad_source.fetch", return_value=blocked),
              patch("kicad_tooling.hwrepo.cad_library.plan") as plan,
              patch("kicad_tooling.hwrepo.cad_library.apply") as apply):
            status, stdout = self.invoke(["--source-cad", "C2040", "--format", "json"])
        self.assertEqual(status, 1)
        review = CadSourcingReview.model_validate_json(stdout)
        self.assertIsNone(review.import_plan)
        self.assertEqual(review.source.issues, ("Provider unavailable",))
        plan.assert_not_called()
        apply.assert_not_called()

    def test_usable_download_with_blocked_import_is_not_cli_success(self) -> None:
        blocked = CadImportReport(status="BLOCKED", project_id="controller",
            issues=("Symbol pins differ from footprint pads",),
            receipt_directory=str(self.plan_receipt))
        with (patch("kicad_tooling.parts.new_receipt", side_effect=[self.receipt, self.plan_receipt]),
              patch("kicad_tooling.hwrepo.cad_source.fetch", return_value=self.source),
              patch("kicad_tooling.hwrepo.cad_library.plan", return_value=blocked),
              patch("kicad_tooling.hwrepo.cad_library.apply") as apply):
            status, stdout = self.invoke(["--source-cad", "C2040", "--format", "json"])
        self.assertEqual(status, 1)
        self.assertEqual(CadSourcingReview.model_validate_json(stdout).import_plan, blocked)
        apply.assert_not_called()

    def test_check_step_uses_exact_source_and_reports_review_or_block(self) -> None:
        for ready in (True, False):
            result = CadStepReport(status="REVIEW" if ready else "BLOCKED",
                project_id="controller", supplier_id="C2040", receipt_directory=str(self.receipt),
                issues=("Inspect paired views",) if ready else ("No source STEP",))
            with (self.subTest(ready=ready),
                  patch("kicad_tooling.parts.new_receipt", side_effect=[self.receipt, self.plan_receipt]),
                  patch("kicad_tooling.hwrepo.cad_source.fetch", return_value=self.source) as fetch,
                  patch("kicad_tooling.hwrepo.cad_step.review", return_value=result) as compare,
                  patch("kicad_tooling.hwrepo.cad_library.apply") as apply):
                status, stdout = self.invoke(["--check-step", "C2040", "--expected-mpn", "RP2040",
                                              "--format", "json"])
            self.assertEqual(status, 0 if ready else 1)
            self.assertEqual(CadStepReport.model_validate_json(stdout), result)
            fetch.assert_called_once_with(self.root, "C2040", self.plan_receipt,
                                          expected_mpn="RP2040", refresh=False)
            compare.assert_called_once_with(self.root, "controller", self.source, self.receipt)
            apply.assert_not_called()

    def test_import_uses_only_locked_plan_and_reports_applied_or_blocked_status(self) -> None:
        for applied in (True, False):
            report = CadImportReport(status="APPLIED" if applied else "BLOCKED",
                project_id="controller", symbol_id="CAD_C2040:RP2040",
                receipt_directory=str(self.receipt), issues=() if applied else ("Source changed",))
            with (self.subTest(applied=applied),
                  patch("kicad_tooling.parts.new_receipt", return_value=self.receipt),
                  patch("kicad_tooling.hwrepo.cad_library.apply", return_value=report) as apply,
                  patch("kicad_tooling.hwrepo.cad_library.plan") as plan,
                  patch("kicad_tooling.hwrepo.cad_source.fetch") as fetch):
                status, stdout = self.invoke(["--import-cad", str(self.plan_path),
                                              "--apply", "--format", "json"])
            self.assertEqual(status, 0 if applied else 1)
            self.assertEqual(CadImportReport.model_validate_json(stdout), report)
            apply.assert_called_once_with(self.root, "controller", self.plan_path, self.receipt)
            plan.assert_not_called()
            fetch.assert_not_called()

    def test_invalid_flags_fail_before_receipts_network_or_source_changes(self) -> None:
        invalid = (
            ["--expected-mpn", "RP2040"],
            ["--refresh-cad"],
            ["--source-cad", "C2040", "--apply"],
            ["--check-step", "C2040", "--apply"],
            ["--import-cad", str(self.plan_path)],
            ["--source-cad", "C2040", "--boards", "2"],
            ["--source-cad", "C2040", "--assist"],
            ["--source-cad", "C2040", "--runner", "container"],
            ["--import-cad", str(self.plan_path), "--apply", "--refresh-cad"],
            ["--import-cad", str(self.plan_path), "--apply", "--expected-mpn", "RP2040"],
        )
        for flags in invalid:
            with (self.subTest(flags=flags),
                  patch("kicad_tooling.parts.new_receipt") as receipt,
                  patch("kicad_tooling.hwrepo.cad_source.fetch") as fetch,
                  patch("kicad_tooling.hwrepo.cad_library.apply") as apply,
                  redirect_stderr(StringIO()), self.assertRaises(SystemExit) as raised):
                self.invoke(flags)
            self.assertEqual(raised.exception.code, 2)
            receipt.assert_not_called()
            fetch.assert_not_called()
            apply.assert_not_called()


if __name__ == "__main__":
    unittest.main()
