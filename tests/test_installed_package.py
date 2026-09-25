"""Package boundary checks using a disposable project checkout."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from kicad_tooling.hwrepo.surface import inspect_tool_surfaces

SOURCE_ROOT = Path(__file__).resolve().parents[1]


class InstalledPackageTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="kicad-tooling-project-")
        self.addCleanup(self.temporary.cleanup)
        self.project = Path(self.temporary.name)
        (self.project / "catalog").mkdir()
        (self.project / "projects").mkdir()
        (self.project / "catalog/projects.json").write_text(json.dumps({
            "schema_version": "1",
            "catalogs": {
                "parts": "catalog/parts.json",
                "interfaces": "catalog/interfaces.json",
                "libraries": "catalog/libraries.json",
                "toolchains": "catalog/toolchains.json",
                "release_policies": "catalog/release-policies.json",
            },
            "project_roots": ["projects"],
        }))
        (self.project / "catalog/toolchains.json").write_text(
            '{"schema_version":"0.1","toolchains":[]}\n'
        )
        (self.project / "catalog/products.json").write_text(
            '{"schema_version":"1","products":[]}\n'
        )

    def run_cli(self, *args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
        environment = os.environ.copy()
        environment["PYTHONPATH"] = os.pathsep.join((
            str(SOURCE_ROOT), environment.get("PYTHONPATH", ""),
        ))
        return subprocess.run(
            (sys.executable, "-B", "-m", "kicad_tooling", *args),
            cwd=cwd or self.project, env=environment,
            capture_output=True, text=True, check=False,
        )

    def test_inventory_uses_project_checkout_not_package_source(self) -> None:
        result = self.run_cli("template", "list", "--format", "json")
        self.assertEqual(0, result.returncode, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual("PASS", report["status"])
        self.assertEqual([], report["projects"])

    def test_explicit_root_works_from_another_directory(self) -> None:
        result = self.run_cli(
            "template", "list", "--root", str(self.project), "--format", "json",
            cwd=SOURCE_ROOT,
        )
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual("PASS", json.loads(result.stdout)["status"])

    def test_surface_catalog_belongs_to_tooling_package(self) -> None:
        report = inspect_tool_surfaces(self.project)
        self.assertEqual("PASS", report.coverage_status, report.issues)
        self.assertEqual("PASS", report.parity_status, report.issues)


if __name__ == "__main__":
    unittest.main()
