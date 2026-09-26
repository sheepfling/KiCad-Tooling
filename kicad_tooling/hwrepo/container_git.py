"""Expose linked-worktree Git metadata read-only to native Python containers."""
from __future__ import annotations

import subprocess
from pathlib import Path

CONTAINER_COMMON = "/kicad-git/common"


def git_metadata_mounts(root: Path) -> tuple[str, ...]:
    """Preserve observed Git identity when a worktree's gitfile points outside /work.

    A normal clone already includes .git in the /work mount and is unchanged.
    Mount the common directory once, preserving the git-dir's location beneath it;
    splitting those directories across mounts can break Git's relative commondir
    references. Environment overrides are confined to the container invocation.
    """
    root = root.resolve(strict=True)
    gitfile = root / ".git"
    if gitfile.is_symlink():
        raise ValueError("Native container Git metadata cannot use a linked .git entry")
    if gitfile.is_dir():
        return ()
    if not gitfile.is_file():
        raise ValueError("Native container checks require a Git checkout with a .git entry")
    try:
        result = subprocess.run(
            ("git", "-c", f"safe.directory={root.as_posix()}", "-C", str(root),
             "rev-parse", "--path-format=absolute", "--git-dir", "--git-common-dir", "--show-toplevel"),
            text=True, capture_output=True, check=True, timeout=30,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise ValueError("Cannot resolve linked-worktree Git metadata for the native container") from exc
    names = result.stdout.splitlines()
    if len(names) != 3 or any(not name or not Path(name).is_absolute() for name in names):
        raise ValueError("Git did not return three absolute metadata/worktree paths")
    git_dir, common_dir, observed_root = (Path(name).resolve(strict=True) for name in names)
    if observed_root != root:
        raise ValueError("Git metadata does not describe the selected worktree root")
    if (not git_dir.is_dir() or not common_dir.is_dir()
            or not (git_dir / "HEAD").is_file() or not (common_dir / "objects").is_dir()):
        raise ValueError("Linked-worktree Git metadata is incomplete")
    if not git_dir.is_relative_to(common_dir):
        raise ValueError("Native containers require the Git directory to be inside its common directory")
    source = common_dir.as_posix()
    relative = git_dir.relative_to(common_dir).as_posix()
    if any(character in source for character in (",", '"')) or any(ord(character) < 32 for character in source):
        raise ValueError("Git common-directory path contains unsupported Docker mount characters")
    if any(ord(character) < 32 for character in relative):
        raise ValueError("Git directory path contains unsupported control characters")
    container_git = CONTAINER_COMMON if relative == "." else f"{CONTAINER_COMMON}/{relative}"
    return (
        "--mount", f"type=bind,source={source},target={CONTAINER_COMMON},readonly",
        "-e", f"GIT_DIR={container_git}",
        "-e", f"GIT_COMMON_DIR={CONTAINER_COMMON}",
        "-e", "GIT_WORK_TREE=/work",
        "-e", "GIT_OPTIONAL_LOCKS=0",
    )
