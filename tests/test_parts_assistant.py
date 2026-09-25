"""Local browser actions keep source-bound plans, safe inputs and private routes."""
from __future__ import annotations

import http.client
import json
import shutil
import tempfile
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlencode

from kicad_tooling.hwrepo.contract_coach import NetlistRunner, project_context
from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.models import (
    AutoCadItem,
    AutoCadReport,
    CadBundleCheck,
    CadImportReport,
    CadSourceBundle,
    CadSourceFile,
    CadSourceReport,
    CadStepReport,
    DigiKeyHandoffPayload,
    DigiKeyHandoffReply,
    PartCadComponent,
    PartPickerItem,
    PartPickerReport,
    PartSelectionAssignment,
    PartSelectionMap,
    PartSelectionReport,
    PurchasingLine,
    PurchasingPlan,
    PurchasingPreferences,
    PurchasingReport,
)
from kicad_tooling.hwrepo.parts_assistant import Assistant, Form, create_server, render_html
from kicad_tooling.hwrepo.parts_workflow import input_hashes
from tests.support import reference_root


class FormTests(unittest.TestCase):
    def test_form_rejects_duplicate_unknown_and_invalid_quantities(self) -> None:
        with self.assertRaisesRegex(ValueError, "more than once"):
            Form.decode(b"boards=1&boards=2")
        for body in (b"boards=1", b"boards=1&spare_percent=0&spare_minimum=0&path=x",
                     b"boards=-1&spare_percent=0&spare_minimum=0",
                     b"boards=0&spare_percent=0&spare_minimum=0",
                     b"boards=1&spare_percent=101&spare_minimum=0"):
            with self.subTest(body=body), self.assertRaises(ValueError):
                Form.decode(body).quantities()
        with self.assertRaises(ValueError):
            Form.decode(b"path=/private/secret").assignments()
        with self.assertRaises(ValueError):
            Form.decode(b"part...%2FR1=identity").assignments()
        with self.assertRaises(ValueError):
            Form.decode(b"plan=anything").empty()

    def test_form_converts_to_immutable_typed_values(self) -> None:
        self.assertEqual(Form.decode(b"part.R1=resistor-1k").assignments(),
                         (PartSelectionAssignment(reference="R1", part_id="resistor-1k"),))
        self.assertEqual(Form.decode(b"boards=4&spare_percent=10&spare_minimum=2").quantities(),
                         PurchasingPreferences(boards=4, spare_percent=10, spare_minimum=2))

    def test_cad_source_form_accepts_only_exact_ids_and_bounded_expected_mpn(self) -> None:
        self.assertEqual(Form.decode(b"id=C2040&expected_mpn=").cad_source(), ("C2040", None))
        self.assertEqual(Form.decode(b"id=C2040&expected_mpn=NE555P").cad_source(), ("C2040", "NE555P"))
        for body in (
            "id=C2040", "id=C2040&expected_mpn=&path=/tmp/model", "id=C2040&expected_mpn=&refresh=true",
            "id=&expected_mpn=", "id=c2040&expected_mpn=", "id=C0&expected_mpn=",
            "id=C02040&expected_mpn=", "id=C../2040&expected_mpn=", "id=../C2040&expected_mpn=",
            "id=https://example.test/C2040&expected_mpn=", "id=C2040%0A&expected_mpn=",
            "id=" + "C" + "1" * 32 + "&expected_mpn=", "id=C2040&expected_mpn=%20NE555P",
            "id=C2040&expected_mpn=NE555P%0A", "id=C2040&expected_mpn=%7F",
            "id=C2040&expected_mpn=" + "a" * 201,
        ):
            with self.subTest(body=body), self.assertRaises(ValueError):
                Form.decode(body.encode()).cad_source()

    def test_page_has_no_source_html_injection_or_download_json_workflow(self) -> None:
        html = render_html('board<script>alert(1)</script>', PurchasingPreferences(), "nonce-safe")
        self.assertNotIn('<script>alert(1)</script>', html)
        self.assertIn('board&lt;script&gt;', html)
        self.assertNotIn('innerHTML', html)
        self.assertNotIn('Download selection', html)
        self.assertIn("element('pre',report.diff)", html)
        self.assertIn("$('scan').click()", html)
        self.assertIn('Add matched models', html)
        self.assertIn('filter(issue=>!shownIssues.has(issue))', html)
        self.assertIn('CAD matching checks pads and preserves library model settings', html)
        self.assertNotIn('confirms its library alignment', html)
        self.assertIn("element('button','Send BOM to DigiKey')", html)
        self.assertIn("action('digikey','handoff-status'", html)
        self.assertIn('No API key is needed', html)
        self.assertIn("link.rel='noopener noreferrer'", html)
        self.assertIn("['boards','spare_percent','spare_minimum'].forEach", html)
        self.assertIn('clearOrderView();', html)
        self.assertIn('new URLSearchParams({review:report.receipt_dir})', html)
        self.assertIn('Find CAD for a part', html)
        self.assertIn('Add CAD to this project', html)
        self.assertIn('Check STEP alignment', html)
        self.assertIn('renderStepViews(parent)', html)
        self.assertIn("['top','turned','bottom','angled']", html)
        self.assertIn('Expected manufacturer part number (optional)', html)
        self.assertIn("action('source-cad','source-status'", html)
        self.assertIn("action('import-cad','source-status'", html)
        self.assertIn('Checks compare files and pin numbers.', html)
        self.assertIn('WRL model included', html)
        self.assertIn('STEP export is not verified; review actual fit, dimensions and polarity.', html)
        self.assertIn('Source and review limits', html)
        self.assertIn('Update PCB from Schematic (F8)', html)
        self.assertIn("element('p','KiCad symbol: '+report.symbol_id)", html)
        self.assertLess(html.index('id="source-heading"'), html.index('id="cad-heading"'))


class AssistantHttpTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="parts-assistant-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve() / "source"
        shutil.copytree(reference_root(), self.root, ignore=shutil.ignore_patterns(".git"))
        self.server = create_server(self.root, "controller")
        self.addCleanup(self.server.server_close)
        self.thread = threading.Thread(target=self.server.serve_forever, kwargs={"poll_interval": 0.01})
        self.thread.start()
        self.addCleanup(self.thread.join)
        self.addCleanup(self.server.shutdown)
        self.state = self.server.assistant
        self.base = "/" + self.state.token + "/"

    def request(self, method: str, action: str = "", body: str = "", *,
                origin: str | None = "auto", host: str | None = None,
                path: str | None = None, content_type: str = "application/x-www-form-urlencoded"):
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=5)
        headers = {"Content-Type": content_type}
        if origin is not None:
            headers["Origin"] = self.server.origin if origin == "auto" else origin
        if host is not None:
            headers["Host"] = host
        connection.request(method, path or self.base + action, body, headers)
        response = connection.getresponse()
        result = (response.status, dict(response.getheaders()), response.read())
        connection.close()
        return result

    def test_loopback_page_is_private_and_sets_browser_boundaries(self) -> None:
        self.assertEqual(self.server.server_address[0], "127.0.0.1")
        status, headers, content = self.request("GET")
        self.assertEqual(status, 200)
        self.assertIn(b"Finish your board", content)
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertEqual(headers["Referrer-Policy"], "no-referrer")
        self.assertIn("frame-ancestors 'none'", headers["Content-Security-Policy"])
        self.assertIn("script-src 'nonce-", headers["Content-Security-Policy"])
        self.assertEqual(self.request("GET", path="/wrong-token/")[0], 404)
        self.assertEqual(self.request("GET", host="attacker.invalid")[0], 403)
        self.assertEqual(self.request("GET", "../../catalog/parts.json")[0], 404)
        self.assertEqual(self.request("GET", "download/report.json")[0], 404)

    def test_cross_origin_and_non_form_writes_are_rejected_before_backend(self) -> None:
        with patch.object(Assistant, "execute") as execute:
            self.assertEqual(self.request("POST", "scan", origin=None)[0], 403)
            self.assertEqual(self.request("POST", "scan", origin="https://attacker.invalid")[0], 403)
            self.assertEqual(self.request("POST", "scan", content_type="application/json")[0], 415)
            self.assertEqual(self.request("POST", "scan", host="attacker.invalid")[0], 403)
            self.assertEqual(self.request("POST", "scan", path="/wrong-token/scan")[0], 404)
            self.assertEqual(self.request("POST", "scan", body="x=" + "a" * 65536)[0], 413)
            execute.assert_not_called()

    def test_busy_action_refuses_a_second_write(self) -> None:
        self.state.lock.acquire()
        try:
            with patch.object(Assistant, "execute") as execute:
                self.assertEqual(self.request("POST", "scan")[0], 409)
                execute.assert_not_called()
        finally:
            self.state.lock.release()

    def cad_source_report(self) -> CadSourceReport:
        directory = self.root / "build/provider-bundle"
        bundle = CadSourceBundle(supplier_id="C2040", manufacturer="Test manufacturer", mpn="TEST-1",
            package="Test package", symbol_file="parts.kicad_sym", symbol_name="TEST_1",
            footprint_file="parts.pretty/TEST_1.kicad_mod", footprint_name="TEST_1",
            model_file="parts.3dshapes/test.wrl",
            files=(CadSourceFile(path="parts.kicad_sym", sha256="1" * 64),),
            source_url="https://easyeda.com/api/products/C2040/components", source_sha256="2" * 64,
            retrieved_at="2026-09-25T12:00:00Z", issues=("Only a WRL model is available for this test part",))
        return CadSourceReport(status="READY", supplier_id="C2040", bundle_directory=str(directory),
                               bundle=bundle, receipt_directory=str(self.root / "build/provider-review"))

    def cad_import_report(self, *, status: str = "PLAN") -> CadImportReport:
        return CadImportReport(status=status, project_id="controller", symbol_id="Imported:TEST_1",
            footprint_id="Imported:TEST_1", files=("examples/projects/controller/kicad/sym-lib-table",),
            check=CadBundleCheck(status="READY", symbol_pins=("1", "2"), footprint_pads=("1", "2"),
                                 model_references=("${KIPRJMOD}/parts.3dshapes/test.wrl",)),
            plan_path=str(self.root / "build/library-plan.json"), receipt_directory=str(self.root / "build/library-review"),
            diff="+ reviewed library registration\n")

    def source_cad(self, *, source: CadSourceReport | None = None,
                   report: CadImportReport | None = None) -> tuple[int, dict[str, str], bytes]:
        with patch("kicad_tooling.hwrepo.cad_source.fetch", return_value=source or self.cad_source_report()), patch(
                "kicad_tooling.hwrepo.cad_library.plan", return_value=report or self.cad_import_report()):
            return self.request("POST", "source-cad", "id=C2040&expected_mpn=TEST-1")

    def test_cad_source_validates_form_before_any_provider_request(self) -> None:
        with patch("kicad_tooling.hwrepo.cad_source.fetch") as fetch, patch("kicad_tooling.hwrepo.cad_library.plan") as plan:
            self.request("GET")
            for body in ("", "id=C2040", "id=../C2040&expected_mpn=", "id=c2040&expected_mpn=",
                         "id=C2040&expected_mpn=&path=/private/secret", "id=C2040&expected_mpn=%0A"):
                with self.subTest(body=body):
                    self.assertEqual(self.request("POST", "source-cad", body)[0], 400)
            fetch.assert_not_called()
            plan.assert_not_called()

    def test_cad_source_creates_fresh_typed_review_without_importing(self) -> None:
        source, planned = self.cad_source_report(), self.cad_import_report()
        with patch("kicad_tooling.hwrepo.cad_source.fetch", return_value=source) as fetch, patch(
                "kicad_tooling.hwrepo.cad_library.plan", return_value=planned) as plan, patch(
                "kicad_tooling.hwrepo.cad_library.apply") as apply:
            status, _, body = self.request("POST", "source-cad", "id=C2040&expected_mpn=TEST-1")
        self.assertEqual(status, 200)
        review = json.loads(body)
        self.assertEqual(review["source"]["bundle"]["mpn"], "TEST-1")
        self.assertEqual(review["import_plan"]["check"]["symbol_pins"], ["1", "2"])
        self.assertFalse(review["import_plan"]["check"]["physical_fit_verified"])
        self.assertEqual(review["import_plan"]["diff"], planned.diff)
        self.assertEqual(fetch.call_args.args[:2], (self.root, "C2040"))
        self.assertEqual(fetch.call_args.kwargs, {"expected_mpn": "TEST-1"})
        self.assertEqual(plan.call_args.args[:3], (self.root, "controller", Path(source.bundle_directory)))
        self.assertNotEqual(fetch.call_args.args[2], plan.call_args.args[3])
        self.assertTrue(fetch.call_args.args[2].is_relative_to(self.root / "build/parts"))
        self.assertTrue(plan.call_args.args[3].is_relative_to(self.root / "build/parts"))
        self.assertEqual(self.state.sourced_plan, Path(planned.plan_path))
        self.assertEqual(self.state.sourcing_review_id, review["review_id"])
        self.assertNotEqual(review["review_id"], planned.plan_path)
        apply.assert_not_called()

    def test_step_review_serves_only_current_hash_checked_views(self) -> None:
        self.assertEqual(self.request("POST", "check-step", "review=guessed")[0], 400)
        current = json.loads(self.source_cad()[2])["review_id"]
        output = self.root / "build/step-review"
        output.mkdir()
        files = {"index.html": b"<h1>Paired views</h1>", "index.css": b"body{color:black}",
                 "wrl-top.png": b"WRL image", "step-top.png": b"STEP image",
                 "assembly.step": b"ISO-10303-21;"}
        hashes: dict[str, str] = {}
        for name, content in files.items():
            (output / name).write_bytes(content)
            hashes[name] = digest(output / name)
        result = CadStepReport(status="REVIEW", project_id="controller", supplier_id="C2040",
                               receipt_directory=str(output), artifacts_sha256=hashes)
        with patch("kicad_tooling.hwrepo.cad_step.review", return_value=result) as compare:
            self.assertEqual(self.request("POST", "check-step", "review=wrong")[0], 400)
            status, _, body = self.request("POST", "check-step", urlencode({"review": current}))
            self.assertEqual(status, 200)
            self.assertEqual(json.loads(body)["status"], "REVIEW")
            compare.assert_called_once()
            self.assertEqual(compare.call_args.args[:3], (self.root, "controller", self.state.sourced_source))
        status, headers, content = self.request("GET", "step/index.html")
        self.assertEqual((status, content), (200, files["index.html"]))
        self.assertIn("img-src 'self'", headers["Content-Security-Policy"])
        self.assertIn("style-src 'self'", headers["Content-Security-Policy"])
        self.assertEqual(self.request("GET", "step/index.css")[2], files["index.css"])
        self.assertEqual(self.request("GET", "step/step-top.png")[2], files["step-top.png"])
        self.assertEqual(self.request("GET", "step/unknown.png")[0], 409)
        (output / "step-top.png").write_bytes(b"changed")
        self.assertEqual(self.request("GET", "step/step-top.png")[0], 409)
        self.assertEqual(self.request("GET", "step/index.html")[0], 409)

    def test_gallery_reads_wait_for_each_other_instead_of_dropping_images(self) -> None:
        output = self.root / "build/parallel-step"
        output.mkdir(parents=True)
        for name in ("wrl-top.png", "step-top.png"):
            path = output / name
            path.write_bytes(name.encode())
            self.state.step_assets[name] = (path, digest(path))
        entered, release = threading.Event(), threading.Event()
        original = self.state.step_asset

        def slow_read(name: str) -> bytes:
            entered.set()
            if not release.wait(2):
                raise TimeoutError("Timed out waiting for the second image request")
            return original(name)

        with patch.object(Assistant, "step_asset", side_effect=slow_read), ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(self.request, "GET", "step/wrl-top.png")
            self.assertTrue(entered.wait(2))
            second = pool.submit(self.request, "GET", "step/step-top.png")
            time.sleep(0.05)
            release.set()
            self.assertEqual(first.result()[0], 200)
            self.assertEqual(second.result()[0], 200)

    def test_cad_source_can_omit_expected_mpn(self) -> None:
        with patch("kicad_tooling.hwrepo.cad_source.fetch", return_value=self.cad_source_report()) as fetch, patch(
                "kicad_tooling.hwrepo.cad_library.plan", return_value=self.cad_import_report()):
            self.assertEqual(self.request("POST", "source-cad", "id=C2040&expected_mpn=")[0], 200)
        self.assertIsNone(fetch.call_args.kwargs["expected_mpn"])

    def test_failed_cad_lookup_exposes_setup_guidance_and_clears_older_import(self) -> None:
        self.source_cad()
        old_review = self.state.sourcing_review_id
        blocked = CadSourceReport(status="BLOCKED", supplier_id="C2040", receipt_directory="build/provider-review",
                                  issues=("Install the pinned converter: python -m pip install easyeda2kicad==1.0.1",))
        with patch("kicad_tooling.hwrepo.cad_source.fetch", return_value=blocked), patch(
                "kicad_tooling.hwrepo.cad_library.plan") as plan, patch("kicad_tooling.hwrepo.cad_library.apply") as apply:
            status, _, body = self.request("POST", "source-cad", "id=C2040&expected_mpn=")
            self.assertEqual(status, 200)
            review = json.loads(body)
            self.assertEqual(review["source"]["status"], "BLOCKED")
            self.assertIn("pinned converter", review["source"]["issues"][0])
            self.assertIsNone(review["import_plan"])
            self.assertEqual(self.request("POST", "import-cad", urlencode({"review": old_review}))[0], 400)
            plan.assert_not_called()
            apply.assert_not_called()
        self.assertIsNone(self.state.sourced_plan)
        self.assertIsNone(self.state.sourcing_review_id)

    def test_blocked_cad_plan_cannot_be_imported(self) -> None:
        planned = self.cad_import_report(status="BLOCKED").model_copy(update={"issues": ("Pin numbers differ",)})
        status, _, body = self.source_cad(report=planned)
        self.assertEqual(status, 200)
        review = json.loads(body)
        self.assertEqual(review["import_plan"]["issues"], ["Pin numbers differ"])
        with patch("kicad_tooling.hwrepo.cad_library.apply") as apply:
            self.assertEqual(self.request("POST", "import-cad", urlencode({"review": review["review_id"]}))[0], 400)
            apply.assert_not_called()

    def test_cad_import_requires_this_tabs_review_and_server_held_path(self) -> None:
        first = json.loads(self.source_cad()[2])
        second = json.loads(self.source_cad()[2])
        self.assertNotEqual(first["review_id"], second["review_id"])
        planned_path = self.state.sourced_plan
        with patch("kicad_tooling.hwrepo.cad_library.apply", return_value=self.cad_import_report(status="APPLIED")) as apply:
            for form in ({}, {"review": first["review_id"]}, {"review": "/private/secret"},
                         {"path": str(planned_path)}, {"review": second["review_id"], "path": "/private/secret"}):
                with self.subTest(form=form):
                    self.assertEqual(self.request("POST", "import-cad", urlencode(form))[0], 400)
            apply.assert_not_called()
            status, _, body = self.request("POST", "import-cad", urlencode({"review": second["review_id"]}))
            self.assertEqual(status, 200)
            self.assertEqual(json.loads(body)["status"], "APPLIED")
            self.assertEqual(apply.call_args.args[:3], (self.root, "controller", planned_path))
            self.assertEqual(self.request("POST", "import-cad", urlencode({"review": second["review_id"]}))[0], 400)
            apply.assert_called_once()

    def test_cad_import_invalidates_cad_selection_and_order_state(self) -> None:
        self.ready_order()
        self.state.cad_plan = self.root / "build/old-cad.json"
        self.state.selection_plan = self.root / "build/old-selection.json"
        self.state.selection_diff = self.root / "build/old-selection.diff"
        self.state.handoff_result = None
        review = json.loads(self.source_cad()[2])
        with patch("kicad_tooling.hwrepo.cad_library.apply", return_value=self.cad_import_report(status="APPLIED")):
            self.assertEqual(self.request("POST", "import-cad", urlencode({"review": review["review_id"]}))[0], 200)
        self.assertIsNone(self.state.sourced_plan)
        self.assertIsNone(self.state.sourcing_review_id)
        self.assertIsNone(self.state.cad_plan)
        self.assertIsNone(self.state.selection_plan)
        self.assertIsNone(self.state.selection_diff)
        self.assertIsNone(self.state.order)
        self.assertEqual(self.state.downloads, {})

    def test_failed_import_consumes_plan_and_does_not_retry_on_repeat(self) -> None:
        review = json.loads(self.source_cad()[2])
        with patch("kicad_tooling.hwrepo.cad_library.apply", side_effect=ValueError("Source changed since review")) as apply:
            first = self.request("POST", "import-cad", urlencode({"review": review["review_id"]}))
            self.assertEqual(first[0], 400)
            self.assertIn(b"Source changed", first[2])
            self.assertEqual(self.request("POST", "import-cad", urlencode({"review": review["review_id"]}))[0], 400)
            apply.assert_called_once()
        self.assertIsNone(self.state.sourced_plan)

    def test_other_source_apply_invalidates_pending_cad_import(self) -> None:
        review = json.loads(self.source_cad()[2])
        self.state.cad_plan = self.root / "build/old-cad.json"
        applied = AutoCadReport(project_id="controller", status="APPLIED", receipt_directory="build/applied")
        with patch("kicad_tooling.hwrepo.auto_cad.apply", return_value=applied), patch("kicad_tooling.hwrepo.cad_library.apply") as apply:
            self.assertEqual(self.request("POST", "apply")[0], 200)
            self.assertEqual(self.request("POST", "import-cad", urlencode({"review": review["review_id"]}))[0], 400)
            apply.assert_not_called()

    def test_cad_scan_and_apply_use_only_the_server_held_plan(self) -> None:
        plan_path = self.root / "build/cad-plan.json"
        report = AutoCadReport(project_id="controller", status="PLAN", plan_path=str(plan_path),
            receipt_directory=str(self.root / "build"), files=("examples/projects/controller/kicad/model.step",),
            items=(AutoCadItem(reference="R1", footprint="Device:R", status="READY", detail="Matched pair"),))
        applied = report.model_copy(update={"status": "APPLIED"})
        with patch("kicad_tooling.hwrepo.auto_cad.plan", return_value=report) as planning:
            status, _, body = self.request("POST", "scan")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["plan_path"], str(plan_path))
        planning.assert_called_once()
        with patch("kicad_tooling.hwrepo.auto_cad.apply", return_value=applied) as apply:
            self.assertEqual(self.request("POST", "apply", "path=/private/secret")[0], 400)
            apply.assert_not_called()
            status, _, _ = self.request("POST", "apply")
        self.assertEqual(status, 200)
        self.assertEqual(apply.call_args.args[2], plan_path)
        self.assertIsNone(self.state.cad_plan)
        self.assertEqual(self.request("POST", "apply")[0], 400)

    def test_partial_cad_review_still_has_exact_diff_and_per_reference_details(self) -> None:
        report = AutoCadReport(project_id="controller", status="PLAN", plan_path="build/plan.json",
            receipt_directory="build/review", diff='- old\n+ <script>untrusted</script>\n',
            items=(AutoCadItem(reference="D1", footprint="LED:Custom", status="NEEDS_REVIEW",
                               detail="Pad spacing differs from the source footprint"),))
        with patch.object(Assistant, "scan", return_value=report):
            status, _, body = self.request("POST", "scan")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["items"][0]["status"], "NEEDS_REVIEW")
        self.assertEqual(json.loads(body)["diff"], report.diff)

    def test_picker_selection_cannot_submit_unoffered_identity_or_source_hashes(self) -> None:
        component = PartCadComponent(reference="R1", value="1k", footprint="Device:R", symbol_id="Device:R",
                                     source_path="examples/projects/controller/kicad/controller.kicad_sch", uuid="uuid")
        self.state.picker = PartPickerReport(project_id="controller", status="READY", receipt_dir="build/picker",
            items=(PartPickerItem(component=component, choice_ids=("resistor-1k",)),),
            selection_template=PartSelectionMap(project_id="controller", preconditions={"catalog/parts.json": "1" * 64}))
        locked = self.root / "build/locked.json"
        report = PartSelectionReport(project_id="controller", status="PLAN", receipt_dir="build/review", locked_map=str(locked))
        with patch("kicad_tooling.hwrepo.parts_assistant.selection", return_value=report) as selecting:
            self.assertEqual(self.request("POST", "select", "part.R1=unoffered")[0], 400)
            self.assertEqual(self.request("POST", "select", "part.R1=resistor-1k&preconditions=fake")[0], 400)
            selecting.assert_not_called()
            status, _, _ = self.request("POST", "select", "part.R1=resistor-1k")
            spec_path = selecting.call_args.args[2]
        self.assertEqual(status, 200)
        spec = PartSelectionMap.model_validate_json(spec_path.read_text())
        self.assertEqual(spec.preconditions, {"catalog/parts.json": "1" * 64})
        self.assertEqual(self.state.selection_plan, locked)
        with patch("kicad_tooling.hwrepo.parts_assistant.selection", return_value=report) as applying:
            self.assertEqual(self.request("POST", "apply-selection")[0], 200)
        self.assertEqual(applying.call_args.args[2], locked)
        self.assertTrue(applying.call_args.kwargs["apply"])
        self.assertIsNone(self.state.selection_plan)

    def test_order_download_cannot_leak_other_files_and_rejects_stale_sources(self) -> None:
        receipt = self.root / "build/order"
        receipt.mkdir(parents=True)
        csv = receipt / "bom.csv"
        csv.write_text("Reference,Quantity\nR1,2\n", encoding="utf-8")
        _, _, source_hashes = project_context(self.root, "controller")
        report = PurchasingReport(project_id="controller", status="NEEDS_PARTS", receipt_dir=str(receipt),
            source_hashes=source_hashes, input_hashes=input_hashes(self.root, "controller", None), artifacts=("bom.csv",))
        self.state.order = report
        self.state.downloads["bom.csv"] = digest(csv)
        status, headers, content = self.request("GET", "download/bom.csv")
        self.assertEqual(status, 200)
        self.assertIn('filename="bom.csv"', headers["Content-Disposition"])
        self.assertEqual(content, csv.read_bytes())
        self.assertEqual(self.request("GET", "download/digikey.csv")[0], 409)
        self.assertEqual(self.request("GET", "download/../../catalog/parts.json")[0], 404)
        manifest = self.root / "examples/projects/controller/project.json"
        manifest.write_text(manifest.read_text() + "\n")
        self.assertEqual(self.request("GET", "download/bom.csv")[0], 409)
        self.assertIsNone(self.state.order)

    def test_tampered_download_is_rejected(self) -> None:
        receipt = self.root / "build/order"
        receipt.mkdir(parents=True)
        csv = receipt / "bom.csv"
        csv.write_text("original", encoding="utf-8")
        _, _, source_hashes = project_context(self.root, "controller")
        self.state.order = PurchasingReport(project_id="controller", status="NEEDS_PARTS", receipt_dir=str(receipt),
            source_hashes=source_hashes, input_hashes=input_hashes(self.root, "controller", None), artifacts=("bom.csv",))
        self.state.downloads["bom.csv"] = digest(csv)
        csv.write_text("changed", encoding="utf-8")
        self.assertEqual(self.request("GET", "download/bom.csv")[0], 409)

    def ready_order(self) -> PurchasingReport:
        receipt = self.root / "build/order"
        receipt.mkdir(parents=True, exist_ok=True)
        csv = receipt / "digikey.csv"
        csv.write_text("PartNumber,Quantity,CustomerReference\nRC0603FR-071KL,8,RES-1\n", encoding="utf-8")
        _, _, source_hashes = project_context(self.root, "controller")
        plan = PurchasingPlan(status="READY_FOR_ORDER_REVIEW",
            preferences=PurchasingPreferences(boards=3), components=(), findings=(),
            lines=(PurchasingLine(part_id="RES-1", revision="A", manufacturer="Yageo",
                mpn="RC0603FR-071KL", footprint="Resistor_SMD:R_0603_1608Metric", references=("R1", "R2"),
                per_board=2, required=6, spares=2, quantity=8, order_number="RC0603FR-071KL",
                order_number_kind="MPN", search_url="https://www.digikey.com/en/products"),))
        report = PurchasingReport(project_id="controller", status="READY_FOR_ORDER_REVIEW",
            receipt_dir=str(receipt), source_hashes=source_hashes,
            input_hashes=input_hashes(self.root, "controller", None), plan=plan, artifacts=("digikey.csv",))
        self.state.order = report
        self.state.downloads["digikey.csv"] = digest(csv)
        return report

    def handoff(self, review: str | None = None):
        return self.request("POST", "digikey", urlencode({"review": review or str(self.root / "build/order")}))

    def test_handoff_requires_ready_server_plan_and_exact_review_field(self) -> None:
        with patch("kicad_tooling.hwrepo.digikey_handoff.send") as send:
            status, _, body = self.handoff()
            self.assertEqual(status, 200)
            self.assertEqual(json.loads(body)["status"], "BLOCKED")
            report = self.ready_order()
            for body in ("", "review=", "review=%20", "quantity=999&part=arbitrary", "review=old&quantity=999"):
                self.assertEqual(self.request("POST", "digikey", body)[0], 400)
            self.state.order = report.model_copy(update={"status": "NEEDS_PARTS"})
            self.assertEqual(json.loads(self.handoff()[2])["status"], "BLOCKED")
            self.state.order = report.model_copy(update={"plan": None})
            self.assertEqual(json.loads(self.handoff()[2])["status"], "BLOCKED")
            send.assert_not_called()

    def test_handoff_submits_server_order_once_and_caches_review_link(self) -> None:
        self.ready_order()
        reply = DigiKeyHandoffReply(single_use_url="https://www.digikey.com/short/abc1234")
        with patch("kicad_tooling.hwrepo.digikey_handoff.send", return_value=reply) as send:
            self.request("GET")
            send.assert_not_called()
            status, _, body = self.handoff()
            self.assertEqual(status, 200)
            self.assertEqual(json.loads(body)["single_use_url"], reply.single_use_url)
            self.assertFalse(json.loads(body)["purchase_authorized"])
            self.assertEqual(self.handoff()[2], body)
            send.assert_called_once()
            payload = send.call_args.args[0]
            self.assertEqual(payload.root[0].requested_part_number, "RC0603FR-071KL")
            self.assertEqual(payload.root[0].quantities[0].quantity, 8)
            self.assertEqual(send.call_args.kwargs["list_name"], "controller")

    def test_new_preparation_rejects_other_tabs_old_review_before_send_or_cache(self) -> None:
        template = self.ready_order()
        assert template.plan is not None
        plan = template.plan
        def projected(root: Path, project_id: str, output: Path, runner: NetlistRunner, *,
                      boards: int, spare_percent: int, spare_minimum: int) -> PurchasingReport:
            updated = plan.model_copy(update={
                "preferences": PurchasingPreferences(boards=boards, spare_percent=spare_percent,
                                                     spare_minimum=spare_minimum),
                "lines": (plan.lines[0].model_copy(update={"required": boards * 2, "spares": 0,
                                                         "quantity": boards * 2}),),
            })
            return template.model_copy(update={"receipt_dir": str(output), "plan": updated})
        with patch("kicad_tooling.hwrepo.parts_assistant.prepare", side_effect=projected):
            first = json.loads(self.request("POST", "order", "boards=1&spare_percent=0&spare_minimum=0")[2])
            second = json.loads(self.request("POST", "order", "boards=10&spare_percent=0&spare_minimum=0")[2])
        self.assertNotEqual(first["receipt_dir"], second["receipt_dir"])
        self.assertEqual(first["plan"]["lines"][0]["quantity"], 2)
        self.assertEqual(second["plan"]["lines"][0]["quantity"], 20)
        reply = DigiKeyHandoffReply(single_use_url="https://www.digikey.com/short/abc1234")
        with patch("kicad_tooling.hwrepo.digikey_handoff.send", return_value=reply) as send:
            result = json.loads(self.handoff(first["receipt_dir"])[2])
            self.assertEqual(result["status"], "BLOCKED")
            self.assertIsNone(result["single_use_url"])
            send.assert_not_called()
            result = json.loads(self.handoff(second["receipt_dir"])[2])
            self.assertEqual(result["status"], "READY")
            self.assertEqual(send.call_args.args[0].root[0].quantities[0].quantity, 20)
            stale = json.loads(self.handoff(first["receipt_dir"])[2])
            self.assertEqual(stale["status"], "BLOCKED")
            self.assertIsNone(stale["single_use_url"])
            self.assertEqual(json.loads(self.handoff(second["receipt_dir"])[2]), result)
            send.assert_called_once()

    def test_handoff_checks_board_and_catalog_freshness_before_sending(self) -> None:
        for relative in ("examples/projects/controller/project.json", "catalog/parts.json"):
            with self.subTest(relative=relative):
                self.ready_order()
                changed = self.root / relative
                changed.write_text(changed.read_text() + "\n", encoding="utf-8")
                with patch("kicad_tooling.hwrepo.digikey_handoff.send") as send:
                    status, _, body = self.handoff()
                    self.assertEqual(status, 200)
                    self.assertEqual(json.loads(body)["status"], "BLOCKED")
                    self.assertIsNone(json.loads(body)["single_use_url"])
                    send.assert_not_called()
                self.assertIsNone(self.state.order)

    def test_handoff_changed_while_sending_does_not_return_stale_review_link(self) -> None:
        self.ready_order()
        def changed_reply(payload: DigiKeyHandoffPayload, *, list_name: str) -> DigiKeyHandoffReply:
            manifest = self.root / "examples/projects/controller/project.json"
            manifest.write_text(manifest.read_text() + "\n", encoding="utf-8")
            return DigiKeyHandoffReply(single_use_url="https://www.digikey.com/short/abc1234")
        with patch("kicad_tooling.hwrepo.digikey_handoff.send", side_effect=changed_reply) as send:
            status, _, body = self.handoff()
            self.assertEqual(status, 200)
            self.assertEqual(json.loads(body)["status"], "BLOCKED")
            self.assertIsNone(json.loads(body)["single_use_url"])
            self.assertIn("may already have received", " ".join(json.loads(body)["issues"]))
            self.handoff()
            send.assert_called_once()
        self.assertEqual(self.request("GET", "download/digikey.csv")[0], 409)

    def test_handoff_network_failure_preserves_csv_and_never_implicitly_retries(self) -> None:
        report = self.ready_order()
        with patch("kicad_tooling.hwrepo.digikey_handoff.send", side_effect=OSError("Connection lost")) as send:
            status, _, body = self.handoff()
            self.assertEqual(status, 200)
            self.assertEqual(json.loads(body)["status"], "ERROR")
            self.assertIsNone(json.loads(body)["single_use_url"])
            self.assertEqual(self.request("GET", "download/digikey.csv")[0], 200)
            self.assertEqual(self.handoff()[2], body)
            send.assert_called_once()
            with patch("kicad_tooling.hwrepo.parts_assistant.prepare", return_value=report), patch(
                    "kicad_tooling.hwrepo.parts_assistant.save_report"):
                self.assertEqual(self.request("POST", "order", "boards=3&spare_percent=0&spare_minimum=0")[0], 200)
            self.assertIsNone(self.state.handoff_result)
            self.handoff()
            self.assertEqual(send.call_count, 2)

    def test_cached_handoff_cannot_bypass_new_source_check(self) -> None:
        self.ready_order()
        reply = DigiKeyHandoffReply(single_use_url="https://www.digikey.com/short/abc1234")
        with patch("kicad_tooling.hwrepo.digikey_handoff.send", return_value=reply) as send:
            self.handoff()
            catalog = self.root / "catalog/parts.json"
            catalog.write_text(catalog.read_text() + "\n", encoding="utf-8")
            result = json.loads(self.handoff()[2])
            self.assertEqual(result["status"], "BLOCKED")
            self.assertIsNone(result["single_use_url"])
            send.assert_called_once()

    def test_order_form_passes_only_validated_quantities(self) -> None:
        report = PurchasingReport(project_id="controller", status="BLOCKED", receipt_dir="build/unused",
                                  issues=("Test capture unavailable",))
        with patch.object(Assistant, "prepare_order", return_value=report) as prepare:
            status, _, _ = self.request("POST", "order", urlencode({"boards": 5, "spare_percent": 10, "spare_minimum": 2}))
        self.assertEqual(status, 200)
        self.assertEqual(prepare.call_args.args[0], PurchasingPreferences(boards=5, spare_percent=10, spare_minimum=2))


if __name__ == "__main__":
    unittest.main()
