"""Behavioral checks for reusable hosted planning, shards and retained failures."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from kicad_tooling.ci_hosted import (
    HostedLog,
    electrical_lane,
    gate_result,
    markdown_checks,
    matrix_lane,
    native_lane,
    plan_lane,
    plan_scope,
    portable_lane,
    release_fixture,
    release_lane,
)
from kicad_tooling.hwrepo.contracts import write_model
from kicad_tooling.hwrepo.discovery import load_registry
from kicad_tooling.hwrepo.electrical_setup import initialize as init_electrical
from kicad_tooling.hwrepo.initialization import initialize
from kicad_tooling.hwrepo.layout import RepositoryLayout, layout
from kicad_tooling.hwrepo.models import AnalysisNotApplicable, ElectricalAnalysisContract
from kicad_tooling.hwrepo.sharding import ProjectShard, shard_projects
from kicad_tooling.hwrepo.template import preflight
from tests.support import TEST_ROOT, initialize_git, reference_root


class HostedCiTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="hosted-ci-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name) / "repository"
        shutil.copytree(
            reference_root(),
            self.root,
            ignore=shutil.ignore_patterns(".git", "build", "__pycache__"),
        )

    def test_shards_partition_a_tag_and_never_claim_full_acceptance(self) -> None:
        projects = ("z", "a", "c", "b", "d", "e")
        shards = [shard_projects(projects, f"{index}/3") for index in (1, 2, 3)]
        self.assertEqual(
            tuple(sorted(project for shard in shards for project in shard)), tuple(sorted(projects))
        )
        self.assertTrue(all(len(shard) == 2 for shard in shards))
        plan = plan_scope(
            self.root,
            event="local",
            base=None,
            focus="tag",
            value="training",
            exclude_tag=None,
            shard="1/2",
        )
        self.assertEqual(plan.scope, "focused")
        self.assertEqual(len(plan.projects), 3)
        self.assertIn("Partial project shard 1/2", plan.reasons)
        full_shard = plan_scope(
            self.root,
            event="local",
            base=None,
            focus="full",
            value=None,
            exclude_tag=None,
            shard="1/2",
        )
        self.assertEqual(full_shard.scope, "focused")
        self.assertEqual(len(full_shard.projects), 3)

    def test_bad_or_empty_shards_fail_before_checks(self) -> None:
        for value in ("0/2", "1/0", "3/2", "1:2", "", "2/3"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                ProjectShard.parse(value).select(("controller",))
        with self.assertRaisesRegex(ValueError, "base branch"):
            plan_scope(
                self.root,
                event="local",
                base=None,
                focus="branch",
                value=None,
                exclude_tag=None,
                shard=None,
            )

    def test_branch_focus_uses_the_same_git_impact_scope(self) -> None:
        initialize_git(self.root)

        def git(*args: str) -> str:
            return subprocess.run(
                ("git", "-C", str(self.root), *args), check=True, capture_output=True, text=True
            ).stdout.strip()

        git(
            "-c",
            "user.name=Test fixture",
            "-c",
            "user.email=fixture@example.invalid",
            "commit",
            "-qm",
            "Initial source",
        )
        base = git("rev-parse", "HEAD")
        board = self.root / "examples/projects/controller/kicad/controller.kicad_pcb"
        board.write_bytes(board.read_bytes() + b"\n")
        git("add", "--all")
        git(
            "-c",
            "user.name=Test fixture",
            "-c",
            "user.email=fixture@example.invalid",
            "commit",
            "-qm",
            "Board change",
        )
        plan = plan_scope(
            self.root,
            event="local",
            base=None,
            focus="branch",
            value=base,
            exclude_tag=None,
            shard=None,
        )
        self.assertEqual(plan.scope, "focused")
        self.assertEqual(plan.projects, ("controller",))
        pr_plan = plan_scope(
            self.root,
            event="pull_request",
            base=base,
            focus="full",
            value=None,
            exclude_tag=None,
            shard=None,
        )
        self.assertEqual(pr_plan, plan)
        pr_shard = plan_scope(
            self.root,
            event="pull_request",
            base=base,
            focus="full",
            value=None,
            exclude_tag=None,
            shard="1/1",
        )
        self.assertEqual(pr_shard.projects, plan.projects)
        self.assertIn("Partial project shard 1/1", pr_shard.reasons)

    def test_hosted_plan_and_native_matrix_outputs_agree_on_the_shard(self) -> None:
        destination = self.root / "github-output.txt"
        destination.write_text("", encoding="utf-8")
        args = argparse.Namespace(
            event="local",
            base="",
            focus="tag",
            value="training",
            exclude_tag="",
            shard="2/2",
            head="HEAD",
        )
        with patch.dict(os.environ, {"GITHUB_OUTPUT": str(destination)}):
            plan_lane(self.root, args, HostedLog(self.root, "plan"))
            plan = json.loads((self.root / "build/impact.json").read_text())
            matrix_lane(self.root, tuple(plan["projects"]), HostedLog(self.root, "matrix"))
        outputs = dict(line.split("=", 1) for line in destination.read_text().splitlines())
        selected = set(plan["projects"])
        self.assertEqual(outputs["scope"], "focused")
        self.assertEqual(set(outputs["projects"].split()), selected)
        self.assertEqual(json.loads(outputs["portable-matrix"])["os"], ["ubuntu-24.04"])
        self.assertEqual(outputs["has-projects"], "true")
        self.assertEqual(
            {entry["project"] for entry in json.loads(outputs["matrix"])["include"]},
            selected,
        )

    def test_focused_portable_lane_keeps_command_and_phase_logs(self) -> None:
        initialize_git(self.root)
        subprocess.run(
            (
                "git",
                "-C",
                str(self.root),
                "-c",
                "user.name=Test fixture",
                "-c",
                "user.email=fixture@example.invalid",
                "commit",
                "-qm",
                "Synthetic source",
            ),
            check=True,
            capture_output=True,
        )
        log = HostedLog(self.root, "portable")
        portable_lane(self.root, "focused", ("controller",), False, 2, log)
        log.finish()
        report = json.loads((self.root / "build/portable/portable.json").read_text())
        self.assertEqual(report["projects"], ["controller"])
        self.assertEqual(report["status"], "PASS")
        events = [json.loads(line) for line in log.events.read_text().splitlines()]
        self.assertTrue(
            any(item["stage"] == "portable-focused" and item["status"] == "PASS" for item in events)
        )
        self.assertTrue((log.directory / "portable-focused.stderr.log").is_file())

    def test_hosted_markdown_check_uses_the_installed_package_module(self) -> None:
        with patch.object(HostedLog, "run") as run:
            markdown_checks(self.root, HostedLog(self.root, "markdown"))
        commands = {call.args[0]: call.args[1] for call in run.call_args_list}
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

    def test_failed_command_retains_stdout_stderr_and_exit_code(self) -> None:
        log = HostedLog(self.root, "failure-probe")
        with (
            redirect_stderr(StringIO()) as live,
            self.assertRaisesRegex(RuntimeError, "failed \\(7\\)"),
        ):
            log.run(
                "probe",
                (
                    sys.executable,
                    "-c",
                    'import sys; print("out"); print("err", file=sys.stderr); sys.exit(7)',
                ),
                cwd=self.root,
            )
        self.assertIn("out", (log.directory / "probe.stdout.log").read_text())
        self.assertIn("err", (log.directory / "probe.stderr.log").read_text())
        self.assertIn("out", live.getvalue())
        self.assertIn('"exit_code": 7', log.events.read_text())

    def test_electrical_lane_is_explicit_about_missing_and_pending_requirements(self) -> None:
        log = HostedLog(self.root, "electrical")
        electrical_lane(self.root, "controller", log)
        self.assertIn("NOT_CONFIGURED", log.events.read_text())
        with self.assertRaisesRegex(ValueError, "no electrical contract"):
            electrical_lane(self.root, "controller", log, required=True)
        init_electrical(self.root, "controller", "47")
        with self.assertRaisesRegex(ValueError, "unresolved electrical requirements"):
            electrical_lane(self.root, "controller", log)

    def test_declared_applicability_runs_in_hosted_lane_without_native_tools(self) -> None:
        setup = init_electrical(self.root, "controller", "47")
        na = AnalysisNotApplicable(
            mode="not_applicable", reason="Synthetic orchestration test only"
        )
        write_model(
            self.root / setup.contract,
            ElectricalAnalysisContract(
                project_id="controller",
                ngspice_version="47",
                grounding=na,
                power=na,
                high_frequency=na,
            ),
        )
        log = HostedLog(self.root, "electrical")
        electrical_lane(self.root, "controller", log)
        report = json.loads((self.root / "build/electrical-controller.json").read_text())
        self.assertEqual(report["status"], "PASS")
        self.assertEqual({row["status"] for row in report["checks"]}, {"NOT_APPLICABLE"})
        from kicad_tooling.ci_matrix import build_matrix

        self.assertTrue(build_matrix(self.root, ("controller",)).include[0].electrical)

    @unittest.skipIf(sys.platform == "win32", "Hosted native orchestration uses a Unix runner")
    def test_native_lane_cannot_pass_when_declared_electrical_fails(self) -> None:
        initialize_git(self.root)
        subprocess.run(
            (
                "git",
                "-C",
                str(self.root),
                "-c",
                "user.name=Test fixture",
                "-c",
                "user.email=fixture@example.invalid",
                "commit",
                "-qm",
                "Synthetic source",
            ),
            check=True,
            capture_output=True,
        )
        log = HostedLog(self.root, "native")
        with (
            patch.object(log, "run") as run,
            patch(
                "kicad_tooling.ci_hosted.electrical_lane",
                side_effect=RuntimeError("Electrical measurement failed"),
            ) as electrical,
            self.assertRaisesRegex(RuntimeError, "Electrical measurement failed"),
        ):
            native_lane(
                self.root,
                project="controller",
                image="fixture@sha256:" + "a" * 64,
                pr_head="",
                fault_probes=True,
                log=log,
            )
        electrical.assert_called_once_with(
            self.root, "controller", log, native_summary="build/review/controller/summary.json"
        )
        stages = [call.args[0] for call in run.call_args_list]
        self.assertIn("native-check", stages)
        self.assertNotIn("fault-probes", stages)
        self.assertEqual(stages[-2:], ["source-diff", "index-diff"])

    def test_release_rehearsal_restores_examples_after_adoption_without_copying_live_data(
        self,
    ) -> None:
        self.assertEqual(initialize(self.root, "adopted-team").status, "PASS")
        private_paths = (
            "projects/private-board/design.txt",
            "products/private-product/design.txt",
            "libraries/private-library/design.txt",
            "hardware/private-board/design.txt",
        )
        for name in private_paths:
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                "Private live source must remain outside rehearsal.\n", encoding="utf-8"
            )
        (self.root / "kicad-tooling.toml").write_text(
            '[layout]\ndiscovery = "private-catalog/projects.json"\n'
            'products = "private-catalog/products.json"\nnew_project_root = "hardware"\n',
            encoding="utf-8",
        )
        (self.root / "LICENSE").write_text("Adopter-specific notice.\n", encoding="utf-8")
        # Neither live default catalogs nor custom layout catalogs define the fixture.
        (self.root / "catalog/projects.json").write_text("{}\n", encoding="utf-8")
        preserved = {
            name: (self.root / name).read_bytes()
            for name in (
                *private_paths,
                "kicad-tooling.toml",
                "template-adoption.json",
                "LICENSE",
                "catalog/projects.json",
                "examples/projects/arduino-uno-status-led/project.json",
            )
        }
        log = HostedLog(self.root, "release-fixture")
        run = log.run
        target = self.root / "build/rehearsal-source"

        def stop_before_native(
            stage: str, argv: tuple[str, ...], *, cwd: Path, **kwargs: object
        ) -> Path:
            if stage == "release-prepare":
                self.assertEqual(cwd, target)
                self.assertEqual(layout(cwd), RepositoryLayout())
                self.assertEqual(preflight(cwd).status, "PASS")
                self.assertEqual(
                    {project.id for project in load_registry(cwd).projects},
                    {project.id for project in load_registry(reference_root()).projects},
                )
                self.assertIn("arduino-uno-status-led", argv)
                raise RuntimeError("Native release reached with public reference catalog")
            self.assertFalse(kwargs)
            return run(stage, argv, cwd=cwd)

        with (
            patch.object(log, "run", side_effect=stop_before_native),
            self.assertRaisesRegex(
                RuntimeError, "Native release reached with public reference catalog"
            ),
        ):
            release_lane(self.root, log)
        for name, original in preserved.items():
            self.assertEqual((self.root / name).read_bytes(), original, name)
        for name in (*private_paths, "kicad-tooling.toml", "template-adoption.json"):
            self.assertFalse((target / name).exists(), name)
        self.assertEqual(
            (target / "LICENSE").read_bytes(),
            (TEST_ROOT / "fixtures/scaffold-license.txt").read_bytes(),
        )
        self.assertEqual(
            (target / "catalog/projects.json").read_bytes(),
            (self.root / "examples/catalog/projects.json").read_bytes(),
        )
        manifest = json.loads(
            (target / "examples/projects/arduino-uno-status-led/project.json").read_text()
        )
        self.assertEqual(
            manifest["release_exports"]["supplier_formats"], ["odb", "ipc2581", "ipcd356"]
        )
        status = subprocess.run(
            ("git", "status", "--porcelain=v1"),
            cwd=target,
            check=True,
            capture_output=True,
            text=True,
        )
        self.assertEqual(status.stdout, "")

    def test_release_rehearsal_requires_public_reference_fixtures(self) -> None:
        (self.root / "examples/catalog/projects.json").unlink()
        target = self.root / "build/rehearsal-source"
        with self.assertRaisesRegex(ValueError, "restore.*examples/catalog/projects.json"):
            release_fixture(self.root, target)
        self.assertFalse(target.exists())

    def test_release_rehearsal_rejects_public_fixture_symlinks_into_private_data(self) -> None:
        private = self.root / "projects/private-board"
        private.mkdir()
        (private / "secret.txt").write_text("Private source\n", encoding="utf-8")
        (self.root / "examples/projects/private-link").symlink_to(private, target_is_directory=True)
        target = self.root / "build/rehearsal-source"
        with self.assertRaisesRegex(ValueError, "must not follow a symlink"):
            release_fixture(self.root, target)
        self.assertFalse(target.exists())

    def test_final_gate_requires_rehearsal_only_for_complete_live_scope(self) -> None:
        gate_result("success", "focused", "success", "success", "success", "true", "skipped")
        gate_result("success", "full", "success", "success", "success", "true", "success")
        with self.assertRaises(ValueError):
            gate_result("success", "full", "success", "success", "success", "true", "skipped")
        with self.assertRaises(ValueError):
            gate_result("success", "focused", "success", "success", "skipped", "true", "skipped")


if __name__ == "__main__":
    unittest.main()
