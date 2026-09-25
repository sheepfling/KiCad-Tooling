"""The official provider follows assigned models and never publishes half a bundle."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from kicad_tooling.hwrepo.cad_download import fetch_official_footprint, inspect_cached_provenance

FOOTPRINT = b'''(footprint "Exact_Name"
 (version 20260206)
 (model "${KICAD10_3DMODEL_DIR}/Package.3dshapes/Different_Name.step"
  (offset (xyz 1 2 3)) (scale (xyz 1 1 1)) (rotate (xyz 0 0 90))))
'''
STEP = b"ISO-10303-21;\nHEADER;\nENDSEC;\nEND-ISO-10303-21;\n"
LICENSE = b"KiCad Libraries License: Creative Commons CC-BY-SA 4.0 with exception\n"
BASE = "https://gitlab.com/kicad/libraries/"


class CadDownloadTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="cad-download-test-")
        self.addCleanup(temporary.cleanup)
        self.cache = Path(temporary.name).resolve() / "cache"
        self.urls: list[str] = []

    def download(self, url: str, maximum: int) -> bytes:
        self.urls.append(url)
        if url.endswith("/Library.pretty/Exact_Name.kicad_mod"):
            return FOOTPRINT
        if url.endswith("/Package.3dshapes/Different_Name.step"):
            return STEP
        if url.endswith("/LICENSE.md"):
            return LICENSE
        raise AssertionError(f"Unexpected download: {url}")

    def fetch(self) -> Path:
        with patch("kicad_tooling.hwrepo.cad_download._download", side_effect=self.download):
            return fetch_official_footprint(self.cache, "Library:Exact_Name", "10.0.5")

    def test_exact_authored_association_transforms_licenses_and_offline_reuse(self) -> None:
        root = self.fetch()
        self.assertEqual((root / "Library.pretty/Exact_Name.kicad_mod").read_bytes(), FOOTPRINT)
        self.assertEqual((root.parent / "3dmodels/Package.3dshapes/Different_Name.step")
                         .read_bytes(), STEP)
        self.assertEqual(self.urls, [
            BASE + "kicad-footprints/-/raw/10.0.5/Library.pretty/Exact_Name.kicad_mod",
            BASE + "kicad-packages3D/-/raw/10.0.5/Package.3dshapes/Different_Name.step",
            BASE + "kicad-footprints/-/raw/10.0.5/LICENSE.md",
            BASE + "kicad-packages3D/-/raw/10.0.5/LICENSE.md",
        ])
        provenance = inspect_cached_provenance(root)
        self.assertEqual(len(provenance), 4)
        with patch("kicad_tooling.hwrepo.cad_download._download", side_effect=AssertionError("offline")):
            self.assertEqual(fetch_official_footprint(self.cache, "Library:Exact_Name", "10.0.5"),
                             root)

    def test_invalid_ids_versions_and_escaped_model_paths_never_fetch_guesses(self) -> None:
        for identifier, version in [
            ("Library:../Escape", "10.0.5"), ("../Library:Name", "10.0.5"),
            ("Library:Name%2Fescape", "10.0.5"), ("Library:Name", "latest"),
            ("Library:Name", "10.0.5/../../../master"), ("Library:Name", "01.0.0"),
        ]:
            with (self.subTest(identifier=identifier, version=version),
                  self.assertRaises(ValueError)):
                fetch_official_footprint(self.cache, identifier, version)
        for model in [
            "${KICAD10_3DMODEL_DIR}/../elsewhere.step", "https://example.com/model.step",
            "${KICAD9_3DMODEL_DIR}/Package.3dshapes/part.step",
            "${KICAD10_3DMODEL_DIR}/Package.3dshapes/../../part.step",
        ]:
            bad = FOOTPRINT.replace(
                b"${KICAD10_3DMODEL_DIR}/Package.3dshapes/Different_Name.step", model.encode())
            with self.subTest(model=model), patch("kicad_tooling.hwrepo.cad_download._download",
                                                 return_value=bad) as transfer:
                with self.assertRaises(ValueError):
                    fetch_official_footprint(self.cache, "Library:Exact_Name", "10.0.5")
                self.assertEqual(transfer.call_count, 1)
        self.assertEqual(list(self.cache.rglob("*.kicad_mod")), [])

    def test_wrong_identity_missing_model_or_non_cad_response_leaves_no_bundle(self) -> None:
        for source in [FOOTPRINT.replace(b'"Exact_Name"', b'"Other"'),
                       b'(footprint "Exact_Name")', b'<html>Error</html>']:
            with (patch("kicad_tooling.hwrepo.cad_download._download", return_value=source),
                  self.assertRaises(ValueError)):
                fetch_official_footprint(self.cache, "Library:Exact_Name", "10.0.5")
            self.assertEqual(list(self.cache.rglob("provenance.csv")), [])
        for response in [b"version https://git-lfs.github.com/spec/v1", b"<html>Sign in</html>"]:
            with (patch("kicad_tooling.hwrepo.cad_download._download",
                        side_effect=[FOOTPRINT, response]), self.assertRaises(ValueError)):
                fetch_official_footprint(self.cache, "Library:Exact_Name", "10.0.5")
            self.assertEqual(list(self.cache.rglob("*.kicad_mod")), [])

    def test_failure_at_each_transfer_is_atomic_and_retry_succeeds(self) -> None:
        for position in range(4):
            results = [FOOTPRINT, STEP, LICENSE, LICENSE][:position] + [ValueError("HTTP 404")]
            with (self.subTest(position=position),
                  patch("kicad_tooling.hwrepo.cad_download._download", side_effect=results),
                  self.assertRaisesRegex(ValueError, "HTTP 404")):
                fetch_official_footprint(self.cache, "Library:Exact_Name", "10.0.5")
            self.assertEqual(list(self.cache.rglob("*.kicad_mod")), [])
            self.assertEqual(list(self.cache.rglob(".cad-download-*")), [])
        self.assertTrue(self.fetch().is_dir())

    def test_tampered_cache_is_not_silently_reused_or_overwritten(self) -> None:
        root = self.fetch()
        target = root.parent / "3dmodels/Package.3dshapes/Different_Name.step"
        target.write_bytes(STEP + b"modified")
        with (patch("kicad_tooling.hwrepo.cad_download._download", side_effect=AssertionError("network")),
              self.assertRaisesRegex(ValueError, "cache asset changed")):
            fetch_official_footprint(self.cache, "Library:Exact_Name", "10.0.5")
        self.assertEqual(target.read_bytes(), STEP + b"modified")

    def test_redirect_and_oversized_or_empty_http_response_are_rejected(self) -> None:
        from kicad_tooling.hwrepo.cad_download import _download

        url = BASE + "kicad-footprints/-/raw/10.0.5/Library.pretty/Exact_Name.kicad_mod"
        with patch("kicad_tooling.hwrepo.cad_download.http.client.HTTPSConnection") as factory:
            response = factory.return_value.getresponse.return_value
            response.status = 302
            with self.assertRaisesRegex(ValueError, "HTTP 302"):
                _download(url, 100)
            self.assertEqual(factory.return_value.request.call_count, 1)
            response.status = 200
            response.getheader.return_value = "101"
            with self.assertRaisesRegex(ValueError, "size limit"):
                _download(url, 100)
            response.getheader.return_value = None
            response.read1.return_value = b"x" * 101
            with self.assertRaisesRegex(ValueError, "size limit"):
                _download(url, 100)
            response.read1.return_value = b""
            with self.assertRaisesRegex(ValueError, "empty"):
                _download(url, 100)
            with self.assertRaisesRegex(ValueError, "outside"):
                _download("https://example.com/model.step", 100)


if __name__ == "__main__":
    unittest.main()
