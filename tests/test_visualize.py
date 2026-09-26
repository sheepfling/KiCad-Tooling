"""End-user 3D receipts and failures at the KiCad runner boundary."""

from __future__ import annotations

import base64
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from kicad_tooling.hwrepo.models import (
    DEFAULT_THREE_D_VIEWS,
    CommandEvidence,
    EnvironmentCheck,
    TemplateDoctorReport,
)
from kicad_tooling.hwrepo.three_d import ThreeDReport, generate
from tests.support import reference_root

PROJECT = "arduino-uno-status-led"
BOARD = f"examples/projects/{PROJECT}/kicad/{PROJECT}.kicad_pcb"
PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVQIHWP4z8DwHwAFgAI/ScLttAAAAABJRU5ErkJggg=="
)
STEP = b"ISO-10303-21;\nHEADER;\nENDSEC;\nDATA;\nENDSEC;\nEND-ISO-10303-21;\n"
GLB = bytes.fromhex("676c5446020000001c000000080000004a534f4e7b7d202020202020")


def passing_doctor() -> TemplateDoctorReport:
    return TemplateDoctorReport(
        native_requested=True,
        checks=(
            EnvironmentCheck(
                id="native-runner",
                required=True,
                status="PASS",
                expected="exact KiCad",
                observed="local",
                next_action="Run the selected board export.",
            ),
        ),
        status="PASS",
    )


def evidence(
    args: tuple[str, ...], *, stdout: str = "", stderr: str = "", returncode: int = 0
) -> CommandEvidence:
    return CommandEvidence(
        argv=("fake-kicad-cli", *args),
        started_utc="2026-09-24T00:00:00+00:00",
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
    )


class VisualizeTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="visualize-test-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve() / "source"
        shutil.copytree(reference_root(), self.root, ignore=shutil.ignore_patterns(".git"))
        self.board = self.root / BOARD

    def cli(self, project: str, *options: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            (
                sys.executable,
                "-I",
                "-B",
                "-m",
                "kicad_tooling.visualize",
                "--root",
                str(self.root),
                "--project",
                project,
                *options,
                "--format",
                "json",
            ),
            cwd=Path(__file__).resolve().parents[1],
            capture_output=True,
            text=True,
            check=False,
            timeout=60,
        )

    def test_check_models_is_read_only_and_retains_a_coachable_receipt(self) -> None:
        original = self.board.read_bytes()
        result = self.cli(PROJECT, "--check-models")
        self.assertEqual(result.returncode, 0, result.stderr)
        report = ThreeDReport.model_validate_json(result.stdout)
        self.assertEqual((report.status, report.mode, report.runner), ("PASS", "inspect", "none"))
        self.assertEqual(report.board, BOARD)
        self.assertEqual(report.models.status if report.models else None, "REVIEW")
        self.assertEqual(len(report.models.footprints) if report.models else 0, 3)
        self.assertEqual(
            {finding.code for finding in report.models.findings} if report.models else set(),
            {"MODEL_UNASSIGNED"},
        )
        self.assertTrue(report.next_actions)
        self.assertFalse(report.commands)
        self.assertFalse(report.artifacts_sha256)
        receipt = Path(report.run_directory)
        self.assertTrue(receipt.is_relative_to(self.root / "build"))
        self.assertTrue((receipt / "models.json").is_file())
        self.assertTrue((receipt / "visualization.json").is_file())
        self.assertIn("model-inventory", (receipt / "events.log").read_text(encoding="utf-8"))
        self.assertEqual(json.loads((receipt / "run.json").read_text())["status"], "PASS")
        self.assertEqual(self.board.read_bytes(), original)
        self.assertEqual(
            report.source_sha256[BOARD],
            hashlib.sha256(original).hexdigest(),
        )

    def test_non_pcb_selection_explains_scope_without_starting_a_runner(self) -> None:
        result = self.cli("passive-signal-reference", "--check-models")
        self.assertEqual(result.returncode, 1, result.stderr)
        report = ThreeDReport.model_validate_json(result.stdout)
        self.assertEqual(report.status, "FAIL")
        self.assertIn("3D views require a PCB", report.error or "")
        self.assertIn("Repair the selected project", report.next_actions[0])
        self.assertEqual(report.runner, "none")
        self.assertFalse(report.commands)
        self.assertTrue((Path(report.run_directory) / "visualization.json").is_file())

    def test_broken_model_blocks_export_before_runner_selection(self) -> None:
        source = self.board.read_text(encoding="utf-8")
        marker = '(footprint "StatusLedTraining:Header_1x02"\n'
        self.assertIn(marker, source)
        self.board.write_text(
            source.replace(
                marker,
                marker + '    (model "${KIPRJMOD}/models/missing.step")\n',
                1,
            ),
            encoding="utf-8",
        )
        with patch(
            "kicad_tooling.hwrepo.three_d.doctor", side_effect=AssertionError("runner started")
        ):
            report = generate(self.root, PROJECT, output=Path("build/broken-model"))
        self.assertEqual(report.status, "FAIL")
        self.assertEqual(report.models.status if report.models else None, "FAIL")
        self.assertIn(
            "MODEL_PATH",
            {finding.code for finding in report.models.findings} if report.models else set(),
        )
        self.assertFalse(report.commands)
        self.assertFalse(report.artifacts_sha256)
        receipt = Path(report.run_directory)
        self.assertTrue((receipt / "models.json").is_file())
        self.assertFalse((receipt / "doctor.json").exists())

    def test_wrong_native_version_and_command_failure_keep_actionable_evidence(self) -> None:
        observed: list[tuple[str, ...]] = []

        def wrong_version(
            _root: Path,
            _output: Path,
            _config: object,
            _selected: str,
            _cli: str,
            args: tuple[str, ...],
            timeout: int = 300,
        ) -> CommandEvidence:
            _ = timeout
            observed.append(args)
            return evidence(args, stdout="9.0.0\n")

        with (
            patch("kicad_tooling.hwrepo.three_d.doctor", return_value=passing_doctor()),
            patch(
                "kicad_tooling.hwrepo.three_d._run_kicad",
                side_effect=wrong_version,
            ),
        ):
            version = generate(
                self.root, PROJECT, runner="local", output=Path("build/wrong-version")
            )
        self.assertEqual(version.status, "FAIL")
        self.assertEqual(observed, [("version",)])
        self.assertIn("Use exact KiCad 10.0.5", version.next_actions[0])
        self.assertTrue((Path(version.run_directory) / "version-command.json").is_file())

        def failed_render(
            _root: Path,
            _output: Path,
            _config: object,
            _selected: str,
            _cli: str,
            args: tuple[str, ...],
            timeout: int = 300,
        ) -> CommandEvidence:
            _ = timeout
            observed.append(args)
            if args == ("version",):
                return evidence(args, stdout="10.0.5\n")
            return evidence(args, stderr="cannot load model", returncode=3)

        observed.clear()
        with (
            patch("kicad_tooling.hwrepo.three_d.doctor", return_value=passing_doctor()),
            patch(
                "kicad_tooling.hwrepo.three_d._run_kicad",
                side_effect=failed_render,
            ),
        ):
            failed = generate(
                self.root, PROJECT, runner="local", output=Path("build/failed-render")
            )
        self.assertEqual(failed.status, "FAIL")
        self.assertEqual(len(observed), 2)
        self.assertIn("top-command.json", failed.next_actions[0])
        self.assertEqual(failed.commands["top"].stderr, "cannot load model")
        self.assertFalse(failed.artifacts_sha256)

    def test_success_exit_with_invalid_image_is_not_a_successful_export(self) -> None:
        def invalid_image(
            _root: Path,
            output: Path,
            _config: object,
            _selected: str,
            _cli: str,
            args: tuple[str, ...],
            timeout: int = 300,
        ) -> CommandEvidence:
            _ = timeout
            if args == ("version",):
                return evidence(args, stdout="10.0.5\n")
            (output / "top.png").write_bytes(b"not a PNG despite KiCad exit zero")
            return evidence(args)

        with (
            patch("kicad_tooling.hwrepo.three_d.doctor", return_value=passing_doctor()),
            patch(
                "kicad_tooling.hwrepo.three_d._run_kicad",
                side_effect=invalid_image,
            ),
        ):
            report = generate(
                self.root, PROJECT, runner="local", output=Path("build/invalid-image")
            )
        self.assertEqual(report.status, "FAIL")
        self.assertEqual(set(report.commands), {"version", "top"})
        self.assertFalse(report.artifacts_sha256)
        self.assertIn("missing or invalid", report.next_actions[0])
        self.assertTrue((Path(report.run_directory) / "top-command.json").is_file())

    def test_successful_exports_are_hashed_and_source_rewrites_invalidate_them(self) -> None:
        payloads = {f"{name}.png": PNG for name in DEFAULT_THREE_D_VIEWS}
        payloads.update({"board.step": STEP, "board.glb": GLB})

        def fake_export(
            _root: Path,
            output: Path,
            _config: object,
            _selected: str,
            _cli: str,
            args: tuple[str, ...],
            timeout: int = 300,
        ) -> CommandEvidence:
            _ = timeout
            if args == ("version",):
                return evidence(args, stdout="10.0.5\n")
            filename = Path(args[args.index("-o") + 1]).name
            (output / filename).write_bytes(payloads[filename])
            return evidence(args)

        original = self.board.read_bytes()
        with (
            patch("kicad_tooling.hwrepo.three_d.doctor", return_value=passing_doctor()),
            patch(
                "kicad_tooling.hwrepo.three_d._run_kicad",
                side_effect=fake_export,
            ),
        ):
            good = generate(self.root, PROJECT, runner="local", output=Path("build/good-export"))
        self.assertEqual(good.status, "PASS", good.next_actions)
        self.assertEqual(good.runner, "local")
        self.assertEqual(set(good.artifacts_sha256), set(payloads))
        for filename, payload in payloads.items():
            self.assertEqual(good.artifacts_sha256[filename], hashlib.sha256(payload).hexdigest())
            self.assertEqual((Path(good.run_directory) / filename).read_bytes(), payload)
        self.assertEqual(self.board.read_bytes(), original)

        def mutating_export(
            root: Path,
            output: Path,
            config: object,
            selected: str,
            cli: str,
            args: tuple[str, ...],
            timeout: int = 300,
        ) -> CommandEvidence:
            command = fake_export(root, output, config, selected, cli, args, timeout)
            if args != ("version",) and Path(args[args.index("-o") + 1]).name == "top.png":
                self.board.write_bytes(original + b"\n")
            return command

        with (
            patch("kicad_tooling.hwrepo.three_d.doctor", return_value=passing_doctor()),
            patch(
                "kicad_tooling.hwrepo.three_d._run_kicad",
                side_effect=mutating_export,
            ),
        ):
            changed = generate(
                self.root, PROJECT, runner="local", output=Path("build/source-changed")
            )
        self.assertEqual(changed.status, "FAIL")
        self.assertIn("source changed", changed.error or "")
        self.assertNotEqual(self.board.read_bytes(), original)

    def test_selected_views_render_only_requested_pngs_plus_exchange_geometry(self) -> None:
        payloads = {"back.png": PNG, "angled-90.png": PNG, "board.step": STEP, "board.glb": GLB}

        def fake_export(
            _root: Path,
            output: Path,
            _config: object,
            _selected: str,
            _cli: str,
            args: tuple[str, ...],
            timeout: int = 300,
        ) -> CommandEvidence:
            _ = timeout
            if args == ("version",):
                return evidence(args, stdout="10.0.5\n")
            filename = Path(args[args.index("-o") + 1]).name
            (output / filename).write_bytes(payloads[filename])
            return evidence(args)

        with (
            patch("kicad_tooling.hwrepo.three_d.doctor", return_value=passing_doctor()),
            patch(
                "kicad_tooling.hwrepo.three_d._run_kicad",
                side_effect=fake_export,
            ),
        ):
            report = generate(
                self.root,
                PROJECT,
                runner="local",
                views=("back", "angled-90"),
                output=Path("build/selected-views"),
            )
        self.assertEqual(report.status, "PASS", report.next_actions)
        self.assertEqual(set(report.commands), {"version", "back", "angled-90", "step", "glb"})
        self.assertEqual(set(report.artifacts_sha256), set(payloads))

    def test_duplicate_views_are_rejected_before_native_runner_selection(self) -> None:
        with patch("kicad_tooling.hwrepo.three_d.doctor") as native:
            report = generate(
                self.root, PROJECT, views=("top", "top"), output=Path("build/duplicate-views")
            )
        self.assertEqual(report.status, "FAIL")
        self.assertIn("must be unique", report.error or "")
        native.assert_not_called()


if __name__ == "__main__":
    unittest.main()
