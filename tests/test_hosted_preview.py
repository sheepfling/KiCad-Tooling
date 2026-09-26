"""Run portable preview orchestration with real child processes, without KiCad."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from kicad_tooling.ci_hosted import HostedCommandError, HostedLog, main
from kicad_tooling.hwrepo.hosted_preview import preview_lane


class HostedPreviewTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="preview with spaces-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve() / "project café"
        self.root.mkdir()
        self.output = self.root / "build/review with spaces"
        self.summary = self.root / "summary.md"
        self.environment = patch.dict(os.environ, {"GITHUB_STEP_SUMMARY": str(self.summary)})
        self.environment.start()
        self.addCleanup(self.environment.stop)

    def child(self, code: int, *, report: bool = True):
        run = HostedLog.run

        def launch(log: HostedLog, stage: str, argv: tuple[str, ...], *, cwd: Path) -> Path:
            self.assertEqual(
                argv[:7],
                (sys.executable, "-I", "-X", "utf8", "-B", "-m", "kicad_tooling.visualize"),
            )
            self.assertEqual(argv[argv.index("--project") + 1], "controller")
            self.assertEqual(Path(argv[argv.index("--root") + 1]), self.root)
            output = argv[argv.index("--output") + 1]
            script = (
                "import sys; from pathlib import Path; p=Path(sys.argv[1]); "
                + (
                    "p.mkdir(parents=True); "
                    "(p/'visualization.txt').write_text('review café <script> ```', encoding='utf-8'); "
                    if report
                    else ""
                )
                + "print('preview café'); print('diagnostic café', file=sys.stderr); "
                + f"sys.exit({code})"
            )
            return run(
                log, stage, (sys.executable, "-I", "-X", "utf8", "-c", script, output), cwd=cwd
            )

        return launch

    def test_success_retains_unicode_logs_and_escapes_summary(self) -> None:
        self.summary.write_text("Earlier stage\n", encoding="utf-8")
        with (
            patch.object(HostedLog, "run", self.child(0)),
            redirect_stdout(StringIO()) as stdout,
            redirect_stderr(StringIO()),
        ):
            preview_lane(
                self.root,
                "controller",
                HostedLog(self.root, "preview"),
                output=self.output,
                cli="C:/Program Files/KiCad/bin/kicad-cli.exe",
            )
        self.assertIn("preview café", stdout.getvalue())
        self.assertIn("café", (self.output / "cli.stdout.txt").read_text(encoding="utf-8"))
        self.assertIn(
            "diagnostic café", (self.output / "cli.stderr.txt").read_text(encoding="utf-8")
        )
        summary = self.summary.read_text(encoding="utf-8")
        self.assertTrue(summary.startswith("Earlier stage\n"))
        self.assertIn("&lt;script&gt;", summary)
        self.assertNotIn("<script>", summary)

    def test_failed_renderer_preserves_original_exit_and_partial_report(self) -> None:
        with (
            patch.object(HostedLog, "run", self.child(7)),
            patch.object(
                sys,
                "argv",
                [
                    "ci-hosted",
                    "--root",
                    str(self.root),
                    "preview",
                    "--project",
                    "controller",
                    "--output",
                    str(self.output),
                ],
            ),
            redirect_stdout(StringIO()),
            redirect_stderr(StringIO()),
        ):
            self.assertEqual(main(), 7)
        self.assertTrue((self.output / "visualization.txt").is_file())
        events = [
            json.loads(line)
            for line in (self.root / "build/ci-hosted/preview/events.jsonl")
            .read_text()
            .splitlines()
        ]
        self.assertTrue(any(event.get("exit_code") == 7 for event in events))
        self.assertEqual(events[-1]["status"], "FAIL")

    def test_early_failure_still_retains_logs_and_explains_missing_report(self) -> None:
        with (
            patch.object(HostedLog, "run", self.child(2, report=False)),
            redirect_stdout(StringIO()),
            redirect_stderr(StringIO()),
            self.assertRaises(HostedCommandError),
        ):
            preview_lane(
                self.root, "controller", HostedLog(self.root, "preview"), output=self.output
            )
        self.assertTrue((self.output / "cli.stderr.txt").is_file())
        self.assertIn("No visualization report", self.summary.read_text(encoding="utf-8"))

    def test_existing_output_is_never_overwritten_or_published_as_fresh(self) -> None:
        self.output.mkdir(parents=True)
        stale = self.output / "visualization.txt"
        stale.write_text("STALE PASS", encoding="utf-8")
        with (
            patch.object(HostedLog, "run") as run,
            redirect_stderr(StringIO()),
            self.assertRaisesRegex(ValueError, "already exists"),
        ):
            preview_lane(
                self.root, "controller", HostedLog(self.root, "preview"), output=self.output
            )
        run.assert_not_called()
        self.assertEqual(stale.read_text(), "STALE PASS")
        self.assertFalse(self.summary.exists())

    def test_source_or_external_output_is_rejected(self) -> None:
        for output in (
            self.root / "docs",
            self.root.parent / "elsewhere",
            self.root / "build/../docs",
            self.root / "build",
        ):
            with (
                self.subTest(output=output),
                redirect_stderr(StringIO()),
                self.assertRaises(ValueError),
            ):
                preview_lane(
                    self.root, "controller", HostedLog(self.root, "preview"), output=output
                )

    def test_local_run_needs_no_github_environment(self) -> None:
        os.environ.pop("GITHUB_STEP_SUMMARY", None)
        with (
            patch.object(HostedLog, "run", self.child(0)),
            redirect_stdout(StringIO()),
            redirect_stderr(StringIO()),
        ):
            preview_lane(
                self.root, "controller", HostedLog(self.root, "preview"), output=self.output
            )
        self.assertTrue((self.output / "cli.stdout.txt").is_file())
        self.assertFalse(self.summary.exists())

    def test_actions_project_environment_and_local_runner_are_forwarded(self) -> None:
        with (
            patch.dict(os.environ, {"PROJECT_ID": "controller"}),
            patch.object(
                sys, "argv", ["ci-hosted", "--root", str(self.root), "preview", "--runner", "local"]
            ),
            patch("kicad_tooling.ci_hosted.preview_lane") as preview,
            redirect_stderr(StringIO()),
        ):
            self.assertEqual(main(), 0)
        self.assertEqual(preview.call_args.args[:2], (self.root, "controller"))
        self.assertEqual(preview.call_args.kwargs["runner"], "local")


if __name__ == "__main__":
    unittest.main()
