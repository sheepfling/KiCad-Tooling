"""Resolve a prerelease lint tag's review scope from its annotated message."""

from __future__ import annotations

import argparse
import os
import re
import subprocess
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

LINT_AREAS = frozenset(
    {
        "design_lint",
        "catalog_lint",
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
    area: str | None
    rule_id: str | None
    native_fixtures: tuple[str, ...]

    @property
    def pytest_markexpr(self) -> str:
        if self.rule_id is not None:
            return f'design_lint and design_lint_rule(rule_id="{self.rule_id}")'
        if self.area is None:
            raise ValueError("lint gate scope has no selector")
        if self.area in {"design_lint", "architecture"}:
            return self.area
        return f"design_lint and {self.area}"


def configured_native_fixtures(repository: Path) -> frozenset[str]:
    """Return fixture switches already covered by the full acceptance workflow."""
    workflow = (repository / ".github/workflows/tooling.yml").read_text(encoding="utf-8")
    return frozenset(_NATIVE_FIXTURE_PATTERN.findall(workflow))


def active_design_lint_rule_ids() -> frozenset[str]:
    """Return active rule IDs from the installed package's validated catalog."""
    return frozenset(required_native_fixtures_by_rule())


def required_native_fixtures_by_rule() -> dict[str, tuple[str, ...]]:
    """Return required exact-native fixture switches for active rules."""
    from kicad_tooling.hwrepo.design_lint_catalog import rule_catalog

    return {
        str(rule.rule_id): tuple(rule.required_native_fixtures)
        for rule in rule_catalog().rules
        if rule.status == "active"
    }


def parse_tag_message(
    message: str,
    known_fixtures: frozenset[str],
    known_rule_ids: frozenset[str] = frozenset(),
    required_native_fixtures: Mapping[str, tuple[str, ...]] | None = None,
) -> LintGateScope:
    """Parse one area or active rule selector and native fixture declarations."""
    selectors = [
        (key.strip(), value.strip())
        for key, separator, value in (line.partition(":") for line in message.splitlines())
        if separator and key.strip() in {"Lint-Area", "Lint-Rule"}
    ]
    if len(selectors) != 1:
        raise ValueError("tag message must declare exactly one Lint-Area or Lint-Rule")

    selector, value = selectors[0]
    if selector == "Lint-Area":
        if value not in LINT_AREAS:
            expected = ", ".join(sorted(LINT_AREAS))
            raise ValueError(f"tag message declares an unsupported Lint-Area ({expected})")
        area, rule_id = value, None
    else:
        if value not in known_rule_ids:
            raise ValueError(f"tag message names an unknown or inactive Lint-Rule: {value!r}")
        area, rule_id = None, value

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
    required = set((required_native_fixtures or {}).get(rule_id or "", ()))
    missing = required - set(fixtures)
    if missing:
        raise ValueError(
            f"Lint-Rule {rule_id!r} requires Native-Fixture declarations: {sorted(missing)}"
        )
    return LintGateScope(area, rule_id, tuple(fixtures))


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
    native_fixtures_by_rule = required_native_fixtures_by_rule()
    return parse_tag_message(
        message,
        configured_native_fixtures(repository),
        frozenset(native_fixtures_by_rule),
        native_fixtures_by_rule,
    )


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
