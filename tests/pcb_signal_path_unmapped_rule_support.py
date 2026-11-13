"""Shared source-bound fixtures for unmapped signal-path rule tests."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest

from kicad_tooling.hwrepo.design_lint_finding_models import DesignLintRuleOverride
from kicad_tooling.hwrepo.design_lint_policy_models import DesignLintPolicy
from kicad_tooling.hwrepo.design_lint_types import Candidate
from kicad_tooling.hwrepo.pcb_drc_source_evidence import BoundDrcEvidence
from kicad_tooling.hwrepo.pcb_signal_path_rule_models import (
    PcbDrcMinMaxRequirement,
    PcbSignalPathRequirement,
    PcbSignalPathRuleMap,
)
from kicad_tooling.hwrepo.project_models import ProjectConfig, ProjectKind

LENGTH_RULE_ID = "pcb.signal_path_unmapped_native_rule"
EDGE_CLEARANCE_RULE_ID = "pcb.signal_path_unmapped_edge_clearance_rule"
COVERAGE_RULE_ID = "pcb.signal_path_rule_coverage"


def native_rule(
    name: str,
    net: str,
    *,
    constraint: str = "length",
    bounds: str = "(max 25mm)",
    condition: str | None = None,
) -> str:
    """Build one compact synthetic native rule with an exact or supplied scope."""
    selector = f"A.NetName == '{net}'" if condition is None else condition
    return (
        f'(rule "{name}" (severity error) (condition "{selector}") '
        f"(constraint {constraint} {bounds}))"
    )


def path_map(*nets: str) -> PcbSignalPathRuleMap:
    """Build a reviewed synthetic map that covers only the listed nets."""
    return PcbSignalPathRuleMap(
        basis="Synthetic reviewed signal-path coverage",
        paths=tuple(
            PcbSignalPathRequirement(
                id=f"path-{index}",
                basis="Synthetic route requirement",
                net=net,
                from_pad=f"J1.{index}",
                to_pad=f"U1.{index}",
                length=PcbDrcMinMaxRequirement(max_nm=25_000_000),
            )
            for index, net in enumerate(nets, start=1)
        ),
    )


def policy(
    requirements: PcbSignalPathRuleMap,
    *,
    coverage_mode: str = "review",
    length_mode: str = "review",
    edge_clearance_mode: str = "review",
) -> DesignLintPolicy:
    """Return a policy with independently selectable path-map rule modes."""
    overrides = (
        (COVERAGE_RULE_ID, coverage_mode),
        (LENGTH_RULE_ID, length_mode),
        (EDGE_CLEARANCE_RULE_ID, edge_clearance_mode),
    )
    return DesignLintPolicy(
        pcb_signal_path_rule_map=requirements,
        rules=tuple(
            DesignLintRuleOverride(
                rule_id=rule_id,
                mode=mode,  # type: ignore[arg-type]
                reason="Synthetic test policy",
            )
            for rule_id, mode in overrides
        ),
    )


def bound_evidence(source: str) -> BoundDrcEvidence:
    """Return synthetic source-bound evidence without reading filesystem paths."""
    empty = Path("/synthetic/not-read")
    return BoundDrcEvidence(
        project_path="projects/synthetic/board.kicad_pro",
        project_sha256="a" * 64,
        rules_path="projects/synthetic/board.kicad_dru",
        rules_sha256="b" * 64,
        board_path="projects/synthetic/board.kicad_pcb",
        board_sha256="c" * 64,
        native_summary_path="build/native/summary.json",
        native_summary_sha256="d" * 64,
        native_drc_path="build/native/drc.json",
        native_drc_sha256="e" * 64,
        project_file=empty,
        board_file=empty,
        summary_file=empty,
        summary_sha256_before="d" * 64,
        drc_file=empty,
        command_file=empty,
        command_sha256="f" * 64,
        rules_source=source,
        ignored_checks=frozenset(),
    )


def scan(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    source: str,
    requirements: PcbSignalPathRuleMap,
    current_net_names: dict[str, object],
    *,
    coverage_mode: str = "review",
    length_mode: str = "review",
    edge_clearance_mode: str = "review",
) -> tuple[Candidate, ...]:
    """Invoke the source scan with controlled synthetic evidence."""
    import kicad_tooling.hwrepo.pcb_signal_path_unmapped_rule_scan as owner

    evidence = bound_evidence(source)
    monkeypatch.setattr(owner, "source_bound_drc_evidence", lambda *_args: evidence)
    monkeypatch.setattr(owner, "verify_source_bound_drc_unchanged", lambda *_args: None)
    config = cast(
        ProjectConfig,
        SimpleNamespace(kind=ProjectKind.PCB, kicad_version="10.0.5"),
    )
    return owner.scan_unmapped_signal_path_native_rules(
        tmp_path,
        config,
        policy(
            requirements,
            coverage_mode=coverage_mode,
            length_mode=length_mode,
            edge_clearance_mode=edge_clearance_mode,
        ),
        {},
        tmp_path / "build/native",
        current_net_names,
        "1" * 64,
    )
