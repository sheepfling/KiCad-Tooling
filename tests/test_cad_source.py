"""Exact identity, frozen inputs, bounded downloads and honest incomplete CAD failures."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from kicad_tooling.hwrepo.cad_source import _download, fetch
from kicad_tooling.hwrepo.cad_step import review as check_step
from kicad_tooling.hwrepo.models import CadBundleCheck

UUID = "a" * 32
OBJ = b"newmtl body\nendmtl\nv 0 0 0\nv 1 0 0\nv 0 1 0\nusemtl body\nf 1 2 3\n"
STEP = b"ISO-10303-21;\nEND-ISO-10303-21;\n"
WRL = b"#VRML V2.0 utf8\nShape { geometry IndexedFaceSet { } }\n"
SYMBOL = '''(kicad_symbol_lib (version 20211014)
 (symbol "ExactPart"
  (property "Manufacturer" "Exact Manufacturer")
  (property "MPN" "ExactPart")
  (property "LCSC Part" "C2040")
  (property "Footprint" "part:Package")))'''
FOOTPRINT = '''(module easyeda2kicad:Package (layer F.Cu)
 (model "${KIPRJMOD}/library/part.3dshapes/Model.wrl"
  (offset (xyz 0 0 0)) (scale (xyz 1 1 1)) (rotate (xyz 0 0 90))))'''


def response(*, supplier_id: str = "C2040", package: str = "Package", mpn: str = "ExactPart") -> bytes:
    return json.dumps({
        "success": True,
        "result": {"lcsc": {"number": supplier_id}, "dataStr": {"head": {"c_para": {
            "Supplier Part": supplier_id, "Manufacturer": "Exact Manufacturer",
            "Manufacturer Part": mpn, "package": package, "name": "ExactPart",
        }}}, "packageDetail": {"dataStr": {"shape": [
            "SVGNODE~" + json.dumps({"attrs": {"uuid": UUID, "title": "Model"}}),
        ]}}},
    }).encode()


class CadSourceTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="cad-source-test-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.calls: list[str] = []
        self.counter = 0
        self.document = response()
        self.converted = 0
        self.convert_error = False
        self.bad_model = False
        self.bad_identity = False
        self.missing_step = False

    def download(self, url: str, maximum: int) -> bytes:
        self.calls.append(url)
        if url.endswith("/components"):
            return self.document
        if "/3dmodel/" in url:
            return OBJ
        if "/qAxj6KHrDKw4blvCG8QJPs7Y/" in url:
            if self.missing_step:
                raise ValueError("CAD provider returned HTTP 404")
            return STEP
        raise AssertionError(url)

    def convert(self, bundle: Path, supplier_id: str, logs: Path) -> None:
        self.converted += 1
        self.assertEqual((bundle / f".easyeda_cache/{supplier_id}.json").read_bytes(), self.document)
        self.assertEqual((bundle / f".easyeda_cache/{UUID}.obj").read_bytes(), OBJ)
        self.assertEqual((bundle / f".easyeda_cache/{UUID}.step").read_bytes(),
                         b"" if self.missing_step else STEP)
        if self.convert_error:
            (logs / "converter.stderr").write_text("Missing source asset")
            raise ValueError("The CAD converter failed")
        symbol = SYMBOL.replace("ExactPart", "DifferentPart") if self.bad_identity else SYMBOL
        (bundle / "library/part.kicad_sym").write_text(symbol)
        (bundle / "library/part.pretty").mkdir()
        (bundle / "library/part.pretty/Package.kicad_mod").write_text(FOOTPRINT)
        (bundle / "library/part.3dshapes").mkdir()
        if not self.bad_model:
            (bundle / "library/part.3dshapes/Model.wrl").write_bytes(WRL)
        (bundle / "library/part.3dshapes/Model.step").write_bytes(STEP)

    def fetch(self, supplier_id: str = "C2040", **options):
        self.counter += 1
        with (patch("kicad_tooling.hwrepo.cad_source._download", side_effect=self.download),
              patch("kicad_tooling.hwrepo.cad_source._converter_digest", return_value="b" * 64),
              patch("kicad_tooling.hwrepo.cad_source._run_converter", side_effect=self.convert)):
            return fetch(self.root, supplier_id, self.root / f"build/receipt-{self.counter}", **options)

    def test_complete_bundle_preserves_authored_model_and_frozen_source_without_step_substitution(self):
        result = self.fetch(expected_mpn="ExactPart")
        self.assertEqual(result.status, "READY", result.issues)
        self.assertEqual(len(self.calls), 3)
        self.assertIsNotNone(result.bundle)
        bundle = Path(result.bundle_directory)
        self.assertEqual((bundle / "library/part.pretty/Package.kicad_mod").read_text(), FOOTPRINT)
        self.assertEqual((bundle.parent / "source/C2040.json").read_bytes(), self.document)
        self.assertEqual((bundle.parent / f"source/{UUID}.step").read_bytes(), STEP)
        self.assertEqual(list(bundle.rglob("*.step")), [])
        self.assertEqual(len(result.bundle.files), 3)
        self.assertIn("STEP mechanical export is not qualified", " ".join(result.issues))

    def test_optional_step_unavailable_keeps_complete_wrl_bundle_and_records_absence(self):
        self.missing_step = True
        result = self.fetch()
        self.assertEqual(result.status, "READY", result.issues)
        self.assertIn("Optional STEP source was not captured", " ".join(result.issues))
        source = Path(result.bundle_directory).parent / f"source/{UUID}.step"
        self.assertEqual(source.read_bytes(), b"")
        self.assertEqual(self.fetch().status, "READY")
        self.assertEqual(len(self.calls), 3)

    def test_step_review_blocks_missing_step_and_changed_cache_before_kicad(self):
        self.missing_step = True
        source = self.fetch()
        receipt = self.root / "build/step-review-missing"
        receipt.mkdir()
        with (patch("kicad_tooling.hwrepo.cad_step._docker") as docker,
              patch("kicad_tooling.hwrepo.cad_step.inspect_bundle",
                    return_value=CadBundleCheck(status="READY"))):
            report = check_step(self.root, "controller", source, receipt)
        self.assertEqual(report.status, "BLOCKED")
        self.assertIn("no source STEP", " ".join(report.issues))
        self.assertFalse(report.alignment_verified)
        docker.assert_not_called()
        self.missing_step = False
        fresh = self.fetch(refresh=True)
        Path(fresh.bundle_directory).joinpath("library/part.3dshapes/Model.wrl").write_bytes(b"changed")
        receipt = self.root / "build/step-review-changed"
        receipt.mkdir()
        with patch("kicad_tooling.hwrepo.cad_step._docker") as docker:
            report = check_step(self.root, "controller", fresh, receipt)
        self.assertEqual(report.status, "BLOCKED")
        self.assertIn("cache changed", " ".join(report.issues))
        docker.assert_not_called()

    def test_oversized_tampered_cache_blocks_before_reading_content(self):
        first = self.fetch()
        path = Path(first.bundle_directory) / "library/part.kicad_sym"
        with path.open("r+b") as stream:
            stream.truncate(65 * 1024 * 1024)
        result = self.fetch()
        self.assertEqual(result.status, "BLOCKED")
        self.assertIn("size limit", " ".join(result.issues))

    def test_cached_reuse_is_offline_and_does_not_require_converter_installation(self):
        first = self.fetch()
        with (patch("kicad_tooling.hwrepo.cad_source._download", side_effect=AssertionError("network")),
              patch("kicad_tooling.hwrepo.cad_source._converter_digest", side_effect=AssertionError("install"))):
            second = fetch(self.root, "C2040", self.root / "build/offline")
        self.assertEqual(second.status, "READY", second.issues)
        self.assertTrue(second.cache_hit)
        self.assertEqual(first.bundle, second.bundle)

    def test_explicit_refresh_retrieves_source_without_replacing_prior_snapshot(self):
        first = self.fetch()
        self.document = self.document.replace(b'"success": true', b'"note": "new", "success": true')
        second = self.fetch(refresh=True)
        self.assertEqual(second.status, "READY", second.issues)
        self.assertFalse(second.cache_hit)
        self.assertNotEqual(first.bundle_directory, second.bundle_directory)
        self.assertTrue(Path(first.bundle_directory).is_dir())
        self.assertEqual(self.converted, 2)

    def test_invalid_supplier_ids_never_touch_network(self):
        for identity in ["../C2040", "C0", "c2040", "C2040?url=x", "https://easyeda.com"]:
            with self.subTest(identity=identity):
                self.assertEqual(self.fetch(identity).status, "BLOCKED")
        self.assertEqual(self.calls, [])

    def test_mismatched_mpn_supplier_and_unsafe_filename_stop_before_model_fetch(self):
        for document, options in [
            (response(), {"expected_mpn": "Other"}),
            (response(supplier_id="C999"), {}),
            (response(package="../../escape"), {}),
        ]:
            self.document = document
            before = len(self.calls)
            with self.subTest(document=document):
                self.assertEqual(self.fetch(**options).status, "BLOCKED")
                self.assertEqual(len(self.calls) - before, 1)
        self.assertEqual(self.converted, 0)

    def test_missing_model_even_after_zero_exit_never_publishes_bundle(self):
        self.bad_model = True
        result = self.fetch()
        self.assertEqual(result.status, "BLOCKED")
        self.assertEqual(list(self.root.rglob("current.txt")), [])
        self.assertEqual(list(self.root.rglob("bundle.json")), [])

    def test_converted_symbol_identity_must_match_original_response(self):
        self.bad_identity = True
        result = self.fetch()
        self.assertEqual(result.status, "BLOCKED")
        self.assertIn("identity", " ".join(result.issues))
        self.assertEqual(list(self.root.rglob("bundle.json")), [])

    def test_converter_failure_leaves_receipt_and_no_usable_cache(self):
        self.convert_error = True
        result = self.fetch()
        self.assertEqual(result.status, "BLOCKED")
        self.assertTrue((Path(result.receipt_directory) / "converter.stderr").is_file())
        self.assertEqual(list(self.root.rglob("current.txt")), [])
        self.assertEqual(list(self.root.rglob(".cad-source-*")), [])

    def test_tampered_native_raw_and_extra_cache_files_block_without_refetch(self):
        for relative in ["bundle/library/part.kicad_sym", f"source/{UUID}.obj", "bundle/extra.txt"]:
            with self.subTest(relative=relative):
                first = self.fetch(refresh=True)
                cache = Path(first.bundle_directory).parent
                target = cache / relative
                original = target.read_bytes() if target.exists() else None
                target.write_bytes(b"tampered")
                before = len(self.calls)
                result = self.fetch()
                self.assertEqual(result.status, "BLOCKED")
                self.assertEqual(len(self.calls), before)
                if original is None:
                    target.unlink()
                else:
                    target.write_bytes(original)

    def test_missing_or_wrong_converter_gives_setup_action_without_network(self):
        import importlib.metadata
        for missing in [True, False]:
            with (patch("kicad_tooling.hwrepo.cad_source.importlib.metadata.distribution") as distribution,
                  patch("kicad_tooling.hwrepo.cad_source._download", side_effect=AssertionError("network"))):
                if missing:
                    distribution.side_effect = importlib.metadata.PackageNotFoundError("easyeda2kicad")
                else:
                    distribution.return_value.version = "0.8.0"
                result = fetch(self.root, "C2040", self.root / f"build/setup-{missing}")
                self.assertEqual(result.status, "BLOCKED")
                self.assertIn("install", " ".join(result.issues).lower())

    def test_download_rejects_redirect_large_empty_and_foreign_responses(self):
        url = "https://easyeda.com/api/products/C2040/components"
        with patch("kicad_tooling.hwrepo.cad_source.http.client.HTTPSConnection") as connection:
            response = connection.return_value.getresponse.return_value
            response.status = 302
            with self.assertRaisesRegex(ValueError, "HTTP 302"):
                _download(url, 100)
            response.status = 200
            response.getheader.side_effect = lambda name: "101" if name == "Content-Length" else None
            with self.assertRaisesRegex(ValueError, "size limit"):
                _download(url, 100)
            response.getheader.side_effect = lambda name: None
            response.read1.return_value = b"x" * 101
            with self.assertRaisesRegex(ValueError, "size limit"):
                _download(url, 100)
            response.read1.return_value = b""
            with self.assertRaisesRegex(ValueError, "empty"):
                _download(url, 100)
            with self.assertRaisesRegex(ValueError, "outside"):
                _download("https://evil.example/api/products/C2040/components", 100)


if __name__ == "__main__":
    unittest.main()
