"""Scope hosted CI work and publish GitHub Actions outputs."""

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path

from .hwrepo.models import ImpactPlan
from .impact import build_plan


def write_action_outputs(values: Mapping[str, str]) -> None:
    """Append single-line values to the GitHub Actions output file when present."""
    destination = os.environ.get("GITHUB_OUTPUT")
    if destination is None:
        return
    with Path(destination).open("a", encoding="utf-8") as stream:
        for key, value in values.items():
            if "\n" in value or "\r" in value:
                raise ValueError(f"Multiline GitHub output is not allowed: {key}")
            stream.write(f"{key}={value}\n")


def plan_scope(
    root: Path,
    *,
    event: str,
    base: str | None,
    focus: str,
    value: str | None,
    exclude_tag: str | None,
    shard: str | None,
    head: str = "HEAD",
) -> ImpactPlan:
    """Use the same typed impact planner for PRs, branch diffs and manual cohorts."""
    if event == "pull_request":
        if not base:
            raise ValueError("Pull-request planning requires a base commit")
        if focus != "full" or value or exclude_tag:
            raise ValueError("Pull-request planning uses its Git diff, not manual focus inputs")
        return build_plan(root, base=base, head=head, shard=shard)
    if focus == "branch":
        if not value:
            raise ValueError("Branch focus requires the base branch or commit in value")
        if exclude_tag:
            raise ValueError("exclude_tag is available only with project/product/tag focus")
        return build_plan(root, base=value, head=head, shard=shard)
    if focus in {"project", "product", "tag"}:
        if not value:
            raise ValueError(f"{focus} focus requires a value")
        if focus == "project":
            return build_plan(root, select_project=value, exclude_tag=exclude_tag, shard=shard)
        if focus == "product":
            return build_plan(root, select_product=value, exclude_tag=exclude_tag, shard=shard)
        return build_plan(root, select_tag=value, exclude_tag=exclude_tag, shard=shard)
    if focus == "full":
        if value or exclude_tag:
            raise ValueError("Full focus does not take a value or exclude_tag")
        return build_plan(root, full=True, shard=shard)
    raise ValueError(f"Unknown CI focus: {focus}")
