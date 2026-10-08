"""Package gates use installed module entry points, never executable overrides."""

from __future__ import annotations

import re
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from scripts import ci


class PackageCiTests(unittest.TestCase):
    def test_workflow_enables_every_native_fixture_regression(self) -> None:
        repository = Path(__file__).resolve().parents[1]
        gated_fixtures: set[str] = set()
        for path in (repository / "tests").glob("test_*.py"):
            source = path.read_text(encoding="utf-8")
            gated_fixtures.update(
                re.findall(
                    r'os\.environ\.get\("(KICAD_RUN_NATIVE_[A-Z0-9_]+)"\)\s*==\s*"1"',
                    source,
                )
            )
        workflow = (repository / ".github/workflows/tooling.yml").read_text(encoding="utf-8")
        package_gate = workflow.split(
            "      - name: Check tooling and installed wheel against a separate project\n", 1
        )[1].split("      - name: Keep stage logs", 1)[0]
        self.assertIn(
            "run: python scripts/ci.py --project-root build/acceptance-template", package_gate
        )
        configured_fixtures = set(
            re.findall(
                r"^\s*(KICAD_RUN_NATIVE_[A-Z0-9_]+):\s*['\"]1['\"]\s*$",
                package_gate,
                flags=re.MULTILINE,
            )
        )
        self.assertTrue(gated_fixtures)
        self.assertEqual(
            gated_fixtures - configured_fixtures,
            set(),
            "Native fixture tests must run in the digest-pinned package acceptance job",
        )

    def test_wheel_must_include_the_runtime_design_lint_catalog(self) -> None:
        with tempfile.TemporaryDirectory(prefix="package-ci-wheel-") as temporary:
            wheel = Path(temporary) / "synthetic.whl"
            metadata = (
                "synthetic.dist-info/METADATA",
                "Name: kicad-team-tooling\nVersion: 1.0.0\n\n",
            )
            required = (
                "kicad_tooling/tool-surfaces.json",
                "kicad_tooling/py.typed",
                "kicad_tooling/markdown_check/__main__.py",
                "kicad_tooling/fixtures/foreign-eagle-board.xml",
                "kicad_tooling/fixtures/scaffold-license.txt",
                "kicad_tooling/hwrepo/fixtures/pcb-access-probe-envelope.kicad_pcb",
                "kicad_tooling/hwrepo/kicad_library_license.txt",
            )
            with zipfile.ZipFile(wheel, "w") as archive:
                archive.writestr(*metadata)
                for path in required:
                    archive.writestr(path, "synthetic")
            with self.assertRaisesRegex(ValueError, "design-lint-rules.json"):
                ci.wheel_contents(wheel)

    def test_distribution_build_clears_stale_staging_without_removing_receipts(self) -> None:
        with tempfile.TemporaryDirectory(prefix="package-ci-build-cache-") as temporary:
            root = Path(temporary)
            stale_module = root / "build/lib/kicad_tooling/hwrepo/removed_rule.py"
            stale_bdist = root / "build/bdist.synthetic"
            stale_temp = root / "build/temp.synthetic"
            receipt = root / "build/ci/run-1/events.jsonl"
            native_receipt = root / "build/native/run-1/snapshot.json"
            for path in (
                stale_module,
                stale_bdist / "payload",
                stale_temp / "payload",
                receipt,
                native_receipt,
            ):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("generated", encoding="utf-8")

            with patch.object(ci, "ROOT", root):
                ci.clear_distribution_build_cache()

            self.assertFalse((root / "build/lib").exists())
            self.assertFalse(stale_bdist.exists())
            self.assertFalse(stale_temp.exists())
            self.assertEqual(receipt.read_text(encoding="utf-8"), "generated")
            self.assertEqual(native_receipt.read_text(encoding="utf-8"), "generated")

    def test_markdown_check_is_an_isolated_module(self) -> None:
        with (
            tempfile.TemporaryDirectory(prefix="package-ci-module-") as temporary,
            patch.object(ci, "ROOT", Path(temporary)),
            patch.object(ci.sys, "argv", ["scripts/ci.py"]),
            patch.object(ci, "stage") as stage,
            patch.object(ci, "build_distributions", side_effect=StopIteration("after checks")),
            self.assertRaisesRegex(StopIteration, "after checks"),
        ):
            stage.return_value.stdout = str(Path(temporary) / "kicad_tooling/__init__.py")
            ci.main()
        commands = {call.args[0]: call.args[1] for call in stage.call_args_list}
        self.assertEqual(
            commands["rumdl"],
            (
                sys.executable,
                "-I",
                "-m",
                "kicad_tooling.markdown_check",
                "check",
                ".",
                "--no-cache",
            ),
        )

    def test_stale_install_is_rejected_before_regressions(self) -> None:
        with (
            tempfile.TemporaryDirectory(prefix="package-ci-install-") as temporary,
            patch.object(ci, "ROOT", Path(temporary)),
            patch.object(ci.sys, "argv", ["scripts/ci.py"]),
            patch.object(ci, "stage") as stage,
        ):
            stage.return_value.stdout = str(Path(temporary) / "other/kicad_tooling/__init__.py")
            self.assertEqual(ci.main(), 1)
        self.assertEqual([call.args[0] for call in stage.call_args_list], ["development-install"])

    def test_native_schematic_geometry_gate_is_opt_in_at_package_level(self) -> None:
        with (
            tempfile.TemporaryDirectory(prefix="package-ci-native-geometry-") as temporary,
            patch.object(ci, "ROOT", Path(temporary)),
            patch.object(ci.sys, "argv", ["scripts/ci.py"]),
            patch.dict(ci.os.environ, {"KICAD_RUN_NATIVE_SCHEMATIC_GEOMETRY": "1"}),
            patch.object(ci, "stage") as stage,
            patch("kicad_tooling.hwrepo.native_geometry_lane.run") as native_geometry,
            patch.object(ci, "build_distributions", side_effect=StopIteration("after checks")),
            self.assertRaisesRegex(StopIteration, "after checks"),
        ):
            stage.return_value.stdout = str(Path(temporary) / "kicad_tooling/__init__.py")
            ci.main()
        native_geometry.assert_called_once()
        self.assertEqual(native_geometry.call_args.args[0], Path(temporary))
        self.assertEqual(native_geometry.call_args.args[1].parent, Path(temporary) / "build/ci")
        self.assertIs(native_geometry.call_args.args[2], stage)
