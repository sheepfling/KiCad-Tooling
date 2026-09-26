"""Real linked Git worktrees retain their metadata relationships in native commands."""

from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from kicad_tooling.hwrepo import releasing
from kicad_tooling.hwrepo.container_git import CONTAINER_COMMON, git_metadata_mounts
from kicad_tooling.hwrepo.discovery import load_config, load_registry
from kicad_tooling.verify import container_command
from tests.support import initialize_git, reference_root


class ContainerGitTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="container-git-")
        self.addCleanup(temporary.cleanup)
        self.parent = Path(temporary.name).resolve()
        self.root = self.parent / "main source"
        self.root.mkdir()
        (self.root / "README.md").write_text("Synthetic Git source\n", encoding="utf-8")
        initialize_git(self.root)
        self.git(
            self.root,
            "-c",
            "user.name=Test fixture",
            "-c",
            "user.email=fixture@example.invalid",
            "commit",
            "-qm",
            "Synthetic source",
        )
        self.worktree = self.parent / "linked source"
        self.git(self.root, "worktree", "add", "--detach", str(self.worktree), "HEAD")

    @staticmethod
    def git(root: Path, *args: str) -> str:
        return subprocess.run(
            ("git", "-C", str(root), *args), check=True, capture_output=True, text=True
        ).stdout.strip()

    @staticmethod
    def environment(arguments: tuple[str, ...]) -> dict[str, str]:
        return dict(
            arguments[index + 1].split("=", 1)
            for index, value in enumerate(arguments)
            if value == "-e"
        )

    def test_standard_clone_does_not_add_mounts_or_environment(self) -> None:
        with patch("kicad_tooling.hwrepo.container_git.subprocess.run") as probe:
            self.assertEqual(git_metadata_mounts(self.root), ())
        probe.assert_not_called()
        command = container_command(
            self.root,
            "synthetic-image",
            "controller",
            self.root / "build/deps",
            self.root / "build/native",
        )
        self.assertFalse(any(value.startswith("GIT_") for value in command))
        self.assertEqual(command.count("--mount"), 1)

    def test_linked_metadata_mount_preserves_common_directory_relationship(self) -> None:
        main_commit = self.git(self.root, "rev-parse", "HEAD")
        (self.worktree / "README.md").write_text(
            "Distinct linked-worktree source\n", encoding="utf-8"
        )
        self.git(
            self.worktree,
            "-c",
            "user.name=Test fixture",
            "-c",
            "user.email=fixture@example.invalid",
            "commit",
            "-qam",
            "Linked-only change",
        )
        selected_commit = self.git(self.worktree, "rev-parse", "HEAD")
        self.assertNotEqual(selected_commit, main_commit)
        arguments = git_metadata_mounts(self.worktree)
        git_dir = Path(self.git(self.worktree, "rev-parse", "--absolute-git-dir")).resolve()
        common = (self.root / ".git").resolve()
        expected_git = f"{CONTAINER_COMMON}/{git_dir.relative_to(common).as_posix()}"
        self.assertEqual(arguments.count("--mount"), 1)
        self.assertIn(
            f"type=bind,source={common.as_posix()},target={CONTAINER_COMMON},readonly", arguments
        )
        environment = self.environment(arguments)
        self.assertEqual(
            environment,
            {
                "GIT_DIR": expected_git,
                "GIT_COMMON_DIR": CONTAINER_COMMON,
                "GIT_WORK_TREE": "/work",
                "GIT_OPTIONAL_LOCKS": "0",
            },
        )
        # Replay equivalent host mappings against real Git. Metadata and source
        # identity are unchanged; this is not a substitute for the Docker smoke test.
        host_environment = {
            **os.environ,
            **environment,
            "GIT_DIR": str(git_dir),
            "GIT_COMMON_DIR": str(common),
            "GIT_WORK_TREE": str(self.worktree),
        }
        commit = subprocess.run(
            ("git", "rev-parse", "HEAD"),
            cwd=self.worktree,
            env=host_environment,
            text=True,
            capture_output=True,
            check=True,
        ).stdout.strip()
        self.assertEqual(commit, selected_commit)
        self.assertNotEqual(commit, main_commit)
        files = subprocess.run(
            ("git", "ls-files"),
            cwd=self.worktree,
            env=host_environment,
            text=True,
            capture_output=True,
            check=True,
        ).stdout.splitlines()
        self.assertEqual(files, ["README.md"])

    def test_verify_command_includes_worktree_mapping_before_image(self) -> None:
        image = "synthetic@sha256:" + "a" * 64
        command = container_command(
            self.worktree,
            image,
            "controller",
            self.worktree / "build/deps",
            self.worktree / "build/native",
        )
        environment = self.environment(command)
        self.assertEqual(environment["GIT_WORK_TREE"], "/work")
        self.assertIn("/worktrees/", environment["GIT_DIR"])
        self.assertLess(command.index("GIT_OPTIONAL_LOCKS=0"), command.index(image))
        self.assertEqual(command[command.index("--project") + 1], "controller")

    def test_release_validation_and_export_share_the_worktree_mapping(self) -> None:
        reference = reference_root()
        project = next(
            item for item in load_registry(reference).projects if item.id == "controller"
        )
        config = load_config(reference, project.config)
        real_run = subprocess.run
        commands: list[tuple[str, ...]] = []

        def execute(argv, **kwargs):
            if argv[0] == "docker":
                commands.append(argv)
                return subprocess.CompletedProcess(
                    argv, 0, stdout="Synthetic native result", stderr=""
                )
            return real_run(argv, **kwargs)

        for export_only in (False, True):
            with (
                patch("kicad_tooling.hwrepo.releasing.load_config", return_value=config),
                patch("kicad_tooling.hwrepo.releasing.subprocess.run", side_effect=execute),
            ):
                releasing.run_native(
                    self.worktree,
                    project,
                    self.worktree / f"build/run-{export_only}/native",
                    None,
                    Path("build/deps"),
                    export_only=export_only,
                )
        self.assertEqual(len(commands), 2)
        for command in commands:
            self.assertEqual(self.environment(command)["GIT_COMMON_DIR"], CONTAINER_COMMON)
            self.assertTrue(
                any(value.endswith(f"target={CONTAINER_COMMON},readonly") for value in command)
            )
        self.assertIn("kicad_tooling.validate", commands[0])
        self.assertIn("kicad_tooling.release", commands[1])

    def test_invalid_gitfile_and_linked_git_entry_fail_before_docker(self) -> None:
        (self.worktree / ".git").write_text("gitdir: /not/a/git/directory\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Cannot resolve"):
            git_metadata_mounts(self.worktree)
        (self.worktree / ".git").unlink()
        try:
            (self.worktree / ".git").symlink_to(self.root / ".git", target_is_directory=True)
        except OSError:
            self.skipTest("Directory symlinks unavailable")
        with self.assertRaisesRegex(ValueError, "linked .git"):
            git_metadata_mounts(self.worktree)

    def test_unsupported_git_directory_relationship_is_rejected(self) -> None:
        git_dir = self.parent / "separate-git"
        git_dir.mkdir()
        (git_dir / "HEAD").write_text("ref: refs/heads/main\n")
        output = f"{git_dir}\n{self.root / '.git'}\n{self.worktree}\n"
        with (
            patch(
                "kicad_tooling.hwrepo.container_git.subprocess.run",
                return_value=subprocess.CompletedProcess([], 0, stdout=output),
            ),
            self.assertRaisesRegex(ValueError, "inside its common"),
        ):
            git_metadata_mounts(self.worktree)

    def test_separate_git_dir_uses_the_common_mount_root(self) -> None:
        output = f"{self.root / '.git'}\n{self.root / '.git'}\n{self.worktree}\n"
        with patch(
            "kicad_tooling.hwrepo.container_git.subprocess.run",
            return_value=subprocess.CompletedProcess([], 0, stdout=output),
        ):
            arguments = git_metadata_mounts(self.worktree)
        self.assertEqual(self.environment(arguments)["GIT_DIR"], CONTAINER_COMMON)

    def test_unsafe_mount_delimiters_and_wrong_root_are_rejected(self) -> None:
        bad_common = self.parent / "metadata,invalid"
        (bad_common / "objects").mkdir(parents=True)
        (bad_common / "HEAD").write_text("ref: refs/heads/main\n")
        for output, message in (
            (f"{bad_common}\n{bad_common}\n{self.worktree}\n", "mount characters"),
            (f"{self.root / '.git'}\n{self.root / '.git'}\n{self.root}\n", "selected worktree"),
        ):
            with (
                self.subTest(message=message),
                patch(
                    "kicad_tooling.hwrepo.container_git.subprocess.run",
                    return_value=subprocess.CompletedProcess([], 0, stdout=output),
                ),
                self.assertRaisesRegex(ValueError, message),
            ):
                git_metadata_mounts(self.worktree)


if __name__ == "__main__":
    unittest.main()
