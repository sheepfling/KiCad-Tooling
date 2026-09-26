"""Hosted setup fails closed before running unverified archive contents."""
from __future__ import annotations

import io
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from kicad_tooling.hwrepo import simulator_setup as setup


class SimulatorSetupTests(unittest.TestCase):
    def test_exact_installed_version_needs_no_download_or_build(self) -> None:
        with (patch.object(setup, "exact_executable", return_value="/approved/ngspice"),
              patch.object(setup.urllib.request, "urlopen") as download):
            self.assertEqual(setup.ensure(Path("/unused"), "47", None, Mock()), "/approved/ngspice")
        download.assert_not_called()

    def test_unknown_version_missing_pin_or_unreviewed_version_never_downloads(self) -> None:
        with (patch.object(setup, "exact_executable", return_value=None),
              patch.object(setup.urllib.request, "urlopen") as download):
            for version in ("UNREVIEWED", "999999", "../47"):
                with self.subTest(version=version), self.assertRaises(ValueError):
                    setup.ensure(Path("/unused"), version, None, Mock())
        download.assert_not_called()

    def test_hash_mismatch_never_extracts_or_executes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            response = io.BytesIO(b"not the approved archive")
            response.url = "https://mirror.example.invalid/ngspice.tar.gz"  # type: ignore[attr-defined]
            log = Mock()
            with (patch.object(setup, "exact_executable", return_value=None),
                  patch.object(setup.shutil, "which", return_value="/compiler"),
                  patch.object(setup.urllib.request, "urlopen", return_value=response),
                  patch.object(setup, "unpack") as unpack,
                  self.assertRaisesRegex(ValueError, "SHA-256 mismatch")):
                setup.ensure(Path(temporary), "47", "0" * 64, log)
            unpack.assert_not_called()
            log.run.assert_not_called()

    def test_archive_rejects_escape_links_and_wrong_prefix_before_extracting(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for name, kind in (("../escape", tarfile.REGTYPE), ("ngspice-47/link", tarfile.SYMTYPE),
                               ("other/configure", tarfile.REGTYPE)):
                archive = root / "source.tar.gz"
                with tarfile.open(archive, "w:gz") as bundle:
                    member = tarfile.TarInfo(name)
                    member.type = kind
                    member.linkname = "../../escape"
                    bundle.addfile(member)
                with self.assertRaisesRegex(ValueError, "Unsafe"):
                    setup.unpack(archive, root / "unpacked", "47")
                self.assertFalse((root / "unpacked").exists())


if __name__ == "__main__":
    unittest.main()
