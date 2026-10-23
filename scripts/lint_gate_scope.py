"""Resolve a prerelease lint tag's review scope from its annotated message."""

from __future__ import annotations

import argparse
import os
import re
import subprocess
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from kicad_tooling.pytest_scope import validate_test_module_files, validate_test_module_paths

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
    test_paths: tuple[str, ...] = ()

    @property
    def pytest_markexpr(self) -> str:
        if self.rule_id is not None:
            return (
                "design_lint and "
                f'(design_lint_rule(rule_id="{self.rule_id}") or rule_gate_integrity)'
            )
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
    """Parse a lint selector, optional test modules, and native fixture switches."""
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

    test_paths = validate_test_module_paths(
        value.strip()
        for key, separator, value in (line.partition(":") for line in message.splitlines())
        if separator and key.strip() == "Test-Path"
    )
    if test_paths and rule_id is not None:
        raise ValueError(
            "Test-Path cannot narrow a Lint-Rule selection; use its catalogued fixtures"
        )
    return LintGateScope(area, rule_id, tuple(fixtures), test_paths)


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
    return read_message_scope(message, repository)


def read_message_scope(message: str, repository: Path) -> LintGateScope:
    """Validate a proposed tag message against this checkout's workflow and catalog."""
    native_fixtures_by_rule = required_native_fixtures_by_rule()
    scope = parse_tag_message(
        message,
        configured_native_fixtures(repository),
        frozenset(native_fixtures_by_rule),
        native_fixtures_by_rule,
    )
    validate_test_module_files(scope.test_paths, repository)
    return scope


def write_github_scope(scope: LintGateScope, *, write_github_files: bool = True) -> None:
    """Publish validated values through GitHub Actions environment files."""
    output = os.environ.get("GITHUB_OUTPUT")
    if write_github_files and output:
        with Path(output).open("a", encoding="utf-8") as stream:
            stream.write(f"markexpr={scope.pytest_markexpr}\n")
            if scope.test_paths:
                stream.write(f"pytestpaths={','.join(scope.test_paths)}\n")
    else:
        print(f"markexpr={scope.pytest_markexpr}")
        if scope.test_paths:
            print(f"pytestpaths={','.join(scope.test_paths)}")

    environment = os.environ.get("GITHUB_ENV")
    if write_github_files and environment:
        with Path(environment).open("a", encoding="utf-8") as stream:
            stream.writelines(f"{fixture}=1\n" for fixture in scope.native_fixtures)
    else:
        for fixture in scope.native_fixtures:
            print(f"{fixture}=1")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    selector = parser.add_mutually_exclusive_group(required=True)
    selector.add_argument("--tag", help="Annotated prerelease Git tag to inspect")
    selector.add_argument(
        "--message-file",
        type=Path,
        help="Preflight a proposed annotated tag message before creating the tag",
    )
    args = parser.parse_args(argv)
    repository = Path(__file__).resolve().parents[1]
    if args.tag is not None:
        scope = read_tag_scope(args.tag, repository)
        write_github_scope(scope)
    else:
        message = args.message_file.read_text(encoding="utf-8")
        scope = read_message_scope(message, repository)
        write_github_scope(scope, write_github_files=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
