"""Explicit-root Git command adapter."""

from __future__ import annotations

from pathlib import Path

from kicad_tooling.git import git_output, run_git_bytes, run_git_text


def test_git_commands_use_the_explicit_root_and_keep_path_bytes(tmp_path: Path) -> None:
    run_git_text(tmp_path, "init", "-q")
    (tmp_path / "board source.kicad_pcb").write_text("(kicad_pcb)\n", encoding="utf-8")
    run_git_text(tmp_path, "add", "--all")

    root = git_output(tmp_path, "rev-parse", "--show-toplevel")
    tracked = run_git_bytes(tmp_path, "ls-files", "-z").stdout

    assert Path(root) == tmp_path.resolve()
    assert tracked == b"board source.kicad_pcb\0"


def test_git_runner_can_return_a_failed_command_for_domain_handling(tmp_path: Path) -> None:
    run_git_text(tmp_path, "init", "-q")
    result = run_git_text(tmp_path, "rev-parse", "--verify", "missing^{commit}", check=False)

    assert result.returncode != 0
    assert result.stderr
