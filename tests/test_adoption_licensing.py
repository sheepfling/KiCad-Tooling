"""Adoption keeps the company's first commit independent of the root template notice."""
from __future__ import annotations

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from kicad_tooling.hwrepo.initialization import initialize
from kicad_tooling.hwrepo.licensing import template_license
from kicad_tooling.hwrepo.template import bootstrap, preflight
from tests.support import initialize_git, reference_root


class AdoptionLicensingTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="kicad-license-adoption-")
        self.addCleanup(temporary.cleanup)
        self.parent = Path(temporary.name).resolve()
        self.root = self.parent / "template"
        shutil.copytree(reference_root(), self.root, ignore=shutil.ignore_patterns(".git"))
        self.original = (self.root / "LICENSE").read_bytes()
        self.notice = "examples/vendor/LICENSE"
        (self.root / self.notice).parent.mkdir()
        (self.root / self.notice).write_bytes(b"Synthetic third-party notice; preserve verbatim.\n")
        initialize_git(self.root)
        self.commit(self.root)

    def git(self, root: Path, *args: str) -> str:
        return subprocess.run(("git", "-C", str(root), *args), check=True,
                              capture_output=True, text=True).stdout.strip()

    def commit(self, root: Path) -> None:
        self.git(root, "add", "--all")
        self.git(root, "-c", "user.name=Scaffold licensing test", "-c",
                 "user.email=fixture@example.invalid", "commit", "-qm", "Synthetic adoption fixture")

    def test_company_first_commit_contains_its_own_root_license(self) -> None:
        self.assertEqual(template_license(self.root), self.root / "LICENSE")
        destination = self.parent / "company"
        report = bootstrap(self.root, destination, "company-hardware")
        self.assertEqual(report.status, "PASS", report.issues)
        self.assertEqual(report.removed, ("LICENSE",))
        self.assertFalse((destination / "LICENSE").exists())
        self.assertFalse((destination / ".git").exists())
        self.assertEqual((self.root / "LICENSE").read_bytes(), self.original)
        self.assertEqual(initialize(destination, "company-hardware").status, "PASS")
        self.assertEqual(preflight(destination).status, "PASS")
        self.assertEqual((destination / self.notice).read_bytes(), (self.root / self.notice).read_bytes())
        company_notice = "Synthetic company license fixture: all rights reserved."
        (destination / "LICENSE").write_text(company_notice, encoding="utf-8")
        initialize_git(destination)
        self.commit(destination)
        self.assertEqual(self.git(destination, "rev-list", "--count", "HEAD"), "1")
        self.assertEqual(self.git(destination, "show", "HEAD:LICENSE"), company_notice)

    def test_init_removes_the_template_notice_once_and_preserves_later_choices(self) -> None:
        report = initialize(self.root, "company-hardware")
        self.assertEqual(report.status, "PASS", report.issues)
        self.assertEqual(report.removed, ("LICENSE",))
        self.assertFalse((self.root / "LICENSE").exists())
        self.assertTrue((self.root / self.notice).exists())
        for choice in (b"A company's chosen terms.\n", self.original):
            (self.root / "LICENSE").write_bytes(choice)
            repeated = initialize(self.root, "company-hardware")
            self.assertEqual(repeated.changed, ())
            self.assertEqual(repeated.removed, ())
            self.assertEqual((self.root / "LICENSE").read_bytes(), choice)

    def test_changed_or_replaced_root_licenses_are_never_removed(self) -> None:
        for index, notice in enumerate((b"A company's chosen terms.\n", self.original + b"\n")):
            with self.subTest(index=index):
                (self.root / "LICENSE").write_bytes(notice)
                self.commit(self.root)
                destination = self.parent / f"company-{index}"
                report = bootstrap(self.root, destination, "company-hardware")
                self.assertEqual(report.status, "PASS", report.issues)
                self.assertEqual(report.removed, ())
                result = initialize(destination, "company-hardware")
                self.assertEqual(result.status, "PASS", result.issues)
                self.assertEqual(result.removed, ())
                self.assertEqual((destination / "LICENSE").read_bytes(), notice)
                self.assertEqual((destination / self.notice).read_bytes(), (self.root / self.notice).read_bytes())

    def test_no_root_license_is_a_valid_adoption_start(self) -> None:
        (self.root / "LICENSE").unlink()
        self.commit(self.root)
        destination = self.parent / "company"
        self.assertEqual(bootstrap(self.root, destination, "company-hardware").removed, ())
        result = initialize(destination, "company-hardware")
        self.assertEqual(result.status, "PASS", result.issues)
        self.assertEqual(result.removed, ())

    def test_init_rolls_back_if_license_cleanup_fails_after_removal(self) -> None:
        tracked = self.git(self.root, "ls-files", "-z").split("\0")
        before = {name: (self.root / name).read_bytes() for name in tracked if name}
        original_unlink = Path.unlink

        def fail_after_removal(path: Path, *args, **kwargs) -> None:
            original_unlink(path, *args, **kwargs)
            if path == self.root / "LICENSE":
                raise OSError("Simulated failure after removing the template notice")

        with patch.object(Path, "unlink", fail_after_removal):
            report = initialize(self.root, "company-hardware")
        self.assertEqual(report.status, "FAIL")
        self.assertEqual({name: (self.root / name).read_bytes() for name in before}, before)
        self.assertFalse((self.root / "template-adoption.json").exists())


if __name__ == "__main__":
    unittest.main()
