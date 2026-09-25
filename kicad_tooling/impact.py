"""Explain which project lanes a Git change needs, with conservative fallback."""
from __future__ import annotations

import argparse
import re
import subprocess
from pathlib import Path

from .hwrepo.impact import plan_paths
from .hwrepo.models import ImpactPlan
from .hwrepo.selection import ProjectSelector, resolve_project_ids
from .hwrepo.sharding import shard_projects


def resolve_commit(root: Path, value: str) -> str:
    """Resolve a commit-ish after Git's option boundary before using it in a diff."""
    result = subprocess.run(
        ("git", "-C", str(root), "rev-parse", "--verify", "--end-of-options", value + "^{commit}"),
        capture_output=True, text=True, check=False,
    )
    commit = result.stdout.strip()
    if result.returncode or re.fullmatch(r"(?:[0-9a-f]{40}|[0-9a-f]{64})", commit) is None:
        raise ValueError(f"Cannot resolve commit reference {value!r}: {result.stderr.strip()}")
    return commit


def changed_paths(root: Path, base: str, head: str) -> tuple[str, ...]:
    """Include both sides of renames; commit IDs prevent caller-controlled Git options."""
    base_commit = resolve_commit(root, base)
    head_commit = resolve_commit(root, head)
    result = subprocess.run(
        ("git", "-C", str(root), "diff", "--no-ext-diff", "--no-textconv",
         "--name-only", "-z", "--no-renames", base_commit, head_commit, "--"),
        capture_output=True, check=False,
    )
    if result.returncode:
        detail = result.stderr.decode("utf-8", errors="replace").strip()
        raise ValueError(f"Cannot determine changed paths: {detail}")
    return tuple(path for path in result.stdout.decode("utf-8").split("\0") if path)


def build_plan(
    root: Path, *, base: str | None = None, head: str = "HEAD",
    paths: tuple[str, ...] | None = None, full: bool = False,
    select_project: str | None = None, select_tag: str | None = None,
    select_product: str | None = None, exclude_tag: str | None = None,
    shard: str | None = None,
) -> ImpactPlan:
    """Share CLI selection semantics with protocol clients without executing checks."""
    selectors = (select_project, select_tag, select_product)
    manual_selection = any(value is not None for value in selectors)
    modes = sum((base is not None, paths is not None, full,
                 *(value is not None for value in selectors)))
    if modes != 1:
        raise ValueError("Choose exactly one of base, paths, full or a manual project/tag/product selector")
    if exclude_tag and not manual_selection:
        raise ValueError("exclude_tag requires a manual project, tag or product selection")
    if manual_selection:
        if not (select_project or select_tag or select_product):
            raise ValueError("Manual selector value must not be empty")
        selector_name = "project" if select_project is not None else "tag" if select_tag is not None else "product"
        selector_value = select_project or select_tag or select_product
        selector = ProjectSelector(
            project_ids=(select_project,) if select_project else (),
            tags=(select_tag,) if select_tag else (),
            product_ids=(select_product,) if select_product else (),
            excluded_tags=(exclude_tag,) if exclude_tag else (),
        )
        plan = ImpactPlan(
            scope="focused", projects=resolve_project_ids(root, selector), changed_paths=(),
            reasons=(f"Manual {selector_name} selector: {selector_value}",),
        )
    else:
        selected_paths = changed_paths(root, base, head) if base is not None else paths or ()
        plan = plan_paths(root, selected_paths)
        if full:
            plan = plan.model_copy(update={"reasons": ("Full run requested",)})
    if shard is not None:
        projects = shard_projects(plan.projects, shard)
        plan = plan.model_copy(update={
            "scope": "focused", "projects": projects,
            "reasons": (*plan.reasons, f"Partial project shard {shard}"),
        })
    return plan


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--base", help="Base commit for a Git diff")
    source.add_argument("--path", action="append", dest="paths",
                        help="Plan one changed repository path directly; may be repeated")
    source.add_argument("--full", action="store_true", help="Request complete acceptance")
    source.add_argument("--select-project", help="Request one project lane")
    source.add_argument("--select-tag", help="Request lanes with one metadata tag")
    source.add_argument("--select-product", help="Request all member lanes of one product")
    parser.add_argument("--exclude-tag", help="Remove tagged lanes from a manual selection")
    parser.add_argument("--shard", help="One-based partial project shard INDEX/COUNT")
    parser.add_argument("--head", default="HEAD", help="Head commit (default: HEAD)")
    parser.add_argument("--format", choices=("json", "text"), default="json")
    args = parser.parse_args()
    root = args.root.resolve()
    try:
        plan = build_plan(
            root, base=args.base, head=args.head,
            paths=None if args.paths is None else tuple(args.paths), full=args.full,
            select_project=args.select_project, select_tag=args.select_tag,
            select_product=args.select_product, exclude_tag=args.exclude_tag,
            shard=args.shard,
        )
    except (OSError, UnicodeError, ValueError) as exc:
        parser.error(str(exc))
    if args.format == "json":
        print(plan.model_dump_json())
    else:
        print(f"Impact: {plan.scope.upper()}")
        print("Projects: " + (", ".join(plan.projects) or "none"))
        print("Documentation changed: " + ("yes" if plan.docs_changed else "no"))
        for reason in plan.reasons:
            print(f"Reason: {reason}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
