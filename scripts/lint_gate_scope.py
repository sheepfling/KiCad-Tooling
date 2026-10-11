"""Resolve a prerelease lint tag's review scope from its annotated message."""

from __future__ import annotations

import argparse
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

LINT_AREAS = frozenset(
    {
        "design_lint",
        "architecture",
        "schematic_lint",
        "schematic_text_lint",
        "schematic_connectivity_lint",
        "schematic_hierarchy_lint",
        "component_lint",
        "connector_lint",
        "interface_lint",
        "power_lint",
        "evidence_lint",
        "pcb_lint",
        "pcb_reference_lint",
        "return_path_lint",
        "parity_lint",
    }
)
_NATIVE_FIXTURE_PATTERN = re.compile(
    r"^\s*(KICAD_RUN_NATIVE_[A-Z0-9_]+):\s*['\"]1['\"]\s*$", re.MULTILINE
)


@dataclass(frozen=True)
class LintGateScope:
    area: str
    native_fixtures: tuple[str, ...]

    @property
    def pytest_markexpr(self) -> str:
        if self.area in {"design_lint", "architecture"}:
            return self.area
        return f"design_lint and {self.area}"


def configured_native_fixtures(repository: Path) -> frozenset[str]:
    """Return fixture switches already covered by the full acceptance workflow."""
    workflow = (repository / ".github/workflows/tooling.yml").read_text(encoding="utf-8")
    return frozenset(_NATIVE_FIXTURE_PATTERN.findall(workflow))


def parse_tag_message(message: str, known_fixtures: frozenset[str]) -> LintGateScope:
    """Parse the exact marker and native fixture declarations for one lint gate."""
    areas = [
        value.strip()
        for key, separator, value in (line.partition(":") for line in message.splitlines())
        if separator and key.strip() == "Lint-Area"
    ]
    if len(areas) != 1 or areas[0] not in LINT_AREAS:
        expected = ", ".join(sorted(LINT_AREAS))
        raise ValueError(f"tag message must declare exactly one supported Lint-Area ({expected})")

    fixtures = [
        value.strip()
        for key, separator, value in (line.partition(":") for line in message.splitlines())
        if separator and key.strip() == "Native-Fixture"
    ]
    if len(fixtures) != len(set(fixtures)):
        raise ValueError("tag message declares a Native-Fixture more than once")
    unknown = set(fixtures) - known_fixtures
    if unknown:
        raise ValueError(
            f"tag message names fixtures absent from full acceptance: {sorted(unknown)}"
        )
    return LintGateScope(areas[0], tuple(fixtures))


def read_tag_scope(tag_name: str, repository: Path) -> LintGateScope:
    """Read an annotated Git tag and validate its scoped-test declarations."""
    if not tag_name.startswith("v") or not re.fullmatch(r"[A-Za-z0-9.+_-]+", tag_name):
        raise ValueError(f"invalid version tag name: {tag_name!r}")
    result = subprocess.run(
        ("git", "cat-file", "tag", f"refs/tags/{tag_name}"),
        cwd=repository,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode:
        raise ValueError(f"prerelease lint tag {tag_name} must be annotated")
    _, separator, message = result.stdout.partition("\n\n")
    if not separator:
        raise ValueError(f"annotated lint tag {tag_name} has no message")
    return parse_tag_message(message, configured_native_fixtures(repository))


def write_github_scope(scope: LintGateScope) -> None:
    """Publish validated values through GitHub Actions environment files."""
    output = os.environ.get("GITHUB_OUTPUT")
    if output:
        with Path(output).open("a", encoding="utf-8") as stream:
            stream.write(f"markexpr={scope.pytest_markexpr}\n")
    else:
        print(f"markexpr={scope.pytest_markexpr}")

    environment = os.environ.get("GITHUB_ENV")
    if environment:
        with Path(environment).open("a", encoding="utf-8") as stream:
            stream.writelines(f"{fixture}=1\n" for fixture in scope.native_fixtures)
    else:
        for fixture in scope.native_fixtures:
            print(f"{fixture}=1")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag", required=True, help="Annotated prerelease Git tag to inspect")
    args = parser.parse_args()
    repository = Path(__file__).resolve().parents[1]
    scope = read_tag_scope(args.tag, repository)
    write_github_scope(scope)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
