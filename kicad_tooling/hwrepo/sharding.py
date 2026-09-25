"""Deterministic, explicitly partial project shards shared by CLI, MCP and CI."""
from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class ProjectShard:
    index: int
    count: int

    @classmethod
    def parse(cls, value: str) -> ProjectShard:
        match = re.fullmatch(r"([1-9][0-9]*)/([1-9][0-9]*)", value)
        if match is None:
            raise ValueError("Shard must use one-based INDEX/COUNT, for example 1/3")
        index, count = (int(part) for part in match.groups())
        if index > count:
            raise ValueError("Shard index must not exceed shard count")
        return cls(index, count)

    def select(self, projects: tuple[str, ...]) -> tuple[str, ...]:
        """Round-robin a stable sorted project set; never report an empty shard as PASS."""
        if self.count > len(projects):
            raise ValueError(
                f"{self.count} shards exceed {len(projects)} selected projects"
            )
        selected = tuple(project for position, project in enumerate(sorted(projects))
                         if position % self.count == self.index - 1)
        if not selected:
            raise ValueError(f"Shard {self.index}/{self.count} selected no projects")
        return selected

    def __str__(self) -> str:
        return f"{self.index}/{self.count}"


def shard_projects(projects: tuple[str, ...], value: str | None) -> tuple[str, ...]:
    return projects if value is None else ProjectShard.parse(value).select(projects)
