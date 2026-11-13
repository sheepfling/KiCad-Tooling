"""Review exact native differential-pair rule scopes omitted from the map."""

from __future__ import annotations

import hashlib
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest

from kicad_tooling.hwrepo.design_lint_finding_models import DesignLintRuleOverride
from kicad_tooling.hwrepo.design_lint_policy_models import DesignLintPolicy
from kicad_tooling.hwrepo.pcb_differential_pair_unmapped import (
    unmapped_differential_pair_rule_candidates,
)
from kicad_tooling.hwrepo.pcb_drc_conditions import native_exact_diff_pair_condition
from kicad_tooling.hwrepo.pcb_drc_models import (
    PcbDifferentialPairRuleMap,
    PcbDifferentialPairRuleRequirement,
    PcbDrcMaximumRequirement,
    PcbDrcMinMaxRequirement,
)
from kicad_tooling.hwrepo.pcb_drc_rule_parser import native_constraints
from kicad_tooling.hwrepo.pcb_drc_source_evidence import BoundDrcEvidence
from kicad_tooling.hwrepo.project_models import ProjectConfig, ProjectKind

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.pcb_lint,
    pytest.mark.design_lint_rule(rule_id="pcb.differential_pair_unmapped_native_rule"),
]

RULE_ID = "pcb.differential_pair_unmapped_native_rule"
PAIR_COVERAGE_RULE_ID = "pcb.differential_pair_rule_coverage"


def _pair_map(*selectors: str) -> PcbDifferentialPairRuleMap:
    return PcbDifferentialPairRuleMap(
        basis="Synthetic reviewed differential-pair map",
        requirements=tuple(
            PcbDifferentialPairRuleRequirement(
                id=f"pair-{index}",
                basis="Synthetic exact-pair requirement",
                positive_net=f"{selector}P",
                negative_net=f"{selector}N",
                pair_selector=selector,
                track_width=PcbDrcMinMaxRequirement(min_nm=200_000),
                skew=PcbDrcMaximumRequirement(max_nm=100_000),
            )
            for index, selector in enumerate(selectors, start=1)
        ),
    )


def _native_rule(
    name: str,
    selector: str,
    *,
    constraint: str = "skew",
    condition: str | None = None,
    severity: str = "warning",
) -> str:
    selected_condition = f"A.inDiffPair('{selector}')" if condition is None else condition
    bound = "(min 0.2mm) (max 0.5mm)" if constraint == "track_width" else "(max 0.5mm)"
    return (
        f'(rule "{name}" (severity {severity}) (condition "{selected_condition}") '
        f"(constraint {constraint} {bound}))"
    )


def _evidence(tmp_path: Path, source: str) -> BoundDrcEvidence:
    project = tmp_path / "board.kicad_pro"
    project.write_text("{}", encoding="utf-8")
    return BoundDrcEvidence(
        project_path="projects/synthetic/board.kicad_pro",
        project_sha256="a" * 64,
        rules_path="projects/synthetic/board.kicad_dru",
        rules_sha256=hashlib.sha256(source.encode("utf-8")).hexdigest(),
        board_path="projects/synthetic/board.kicad_pcb",
        board_sha256="c" * 64,
        native_summary_path="build/native/summary.json",
        native_summary_sha256="d" * 64,
        native_drc_path="build/native/drc.json",
        native_drc_sha256="e" * 64,
        project_file=project,
        board_file=tmp_path / "board.kicad_pcb",
        summary_file=tmp_path / "summary.json",
        summary_sha256_before="d" * 64,
        drc_file=tmp_path / "drc.json",
        command_file=tmp_path / "drc.command.json",
        command_sha256="f" * 64,
        rules_source=source,
        ignored_checks=frozenset(),
    )


def _policy(pair_map: PcbDifferentialPairRuleMap | None, *, modes: dict[str, str] | None = None):
    overrides = tuple(
        DesignLintRuleOverride(
            rule_id=rule_id,
            mode=mode,  # type: ignore[arg-type]
            reason="Synthetic project policy",
        )
        for rule_id, mode in sorted((modes or {}).items())
    )
    return DesignLintPolicy(pcb_differential_pair_rule_map=pair_map, rules=overrides)


def _scan(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    source: str,
    pair_map: PcbDifferentialPairRuleMap | None,
    *,
    modes: dict[str, str] | None = None,
):
    import kicad_tooling.hwrepo.pcb_differential_pair_unmapped_scan as owner

    evidence = _evidence(tmp_path, source)
    monkeypatch.setattr(owner, "source_bound_drc_evidence", lambda *_args: evidence)
    monkeypatch.setattr(owner, "verify_source_bound_drc_unchanged", lambda *_args: None)
    config = cast(
        ProjectConfig,
        SimpleNamespace(kind=ProjectKind.PCB, kicad_version="10.0.5"),
    )
    return owner.scan_unmapped_differential_pair_rules(
        tmp_path,
        config,
        _policy(pair_map, modes=modes),
        {},
        tmp_path / "build/native",
    )


def test_exact_native_pair_selector_missing_from_map_is_reviewed(tmp_path: Path) -> None:
    source = "(version 1)\n" + "\n".join(
        (
            _native_rule("motor-width", "MOTOR_", constraint="track_width"),
            _native_rule("motor-skew", "MOTOR_"),
            _native_rule("usb-skew", "USB_D_"),
        )
    )
    evidence = _evidence(tmp_path, source)

    (finding,) = unmapped_differential_pair_rule_candidates(
        _pair_map("USB_D_"),
        native_constraints(source),
        evidence,
        kicad_version="10.0.5",
    )

    assert finding.rule_id == RULE_ID
    assert finding.subject == (
        "MOTOR_: native differential-pair rule scope is absent from the project map"
    )
    assert finding.evidence["pair_selector"] == ("MOTOR_",)
    assert finding.evidence["native_rule_names"] == ("motor-skew", "motor-width")
    assert finding.evidence["native_constraints"] == ("skew", "track_width")
    assert finding.evidence["native_constraint_count"] == ("2",)
    assert finding.evidence["source_sha256"] == (
        hashlib.sha256(source.encode("utf-8")).hexdigest(),
    )
    assert finding.evidence["native_drc_kicad_version"] == ("10.0.5",)
    assert "does not infer pair identity" in finding.message


def test_source_scan_uses_the_bound_rule_text_and_keeps_deterministic_grouping(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = "(version 1)\n" + "\n".join(
        (
            _native_rule("beta-skew", "MOTOR_"),
            _native_rule("alpha-width", "MOTOR_", constraint="track_width"),
            _native_rule("mapped-skew", "USB_D_"),
        )
    )
    findings = _scan(tmp_path, monkeypatch, source, _pair_map("USB_D_"))

    assert len(findings) == 1
    finding = findings[0]
    assert finding.evidence["native_rule_names"] == ("alpha-width", "beta-skew")
    assert finding.evidence["native_conditions"] == ("A.inDiffPair('MOTOR_')",)
    assert finding.evidence["map_sha256"]


def test_native_rule_order_does_not_change_review_grouping(tmp_path: Path) -> None:
    rules = (
        _native_rule("alpha-skew", "MOTOR_"),
        _native_rule("beta-width", "AUX_", constraint="track_width"),
    )
    first_source = "(version 1)\n" + "\n".join(rules)
    reversed_source = "(version 1)\n" + "\n".join(reversed(rules))
    requirements = _pair_map("USB_D_")
    first = unmapped_differential_pair_rule_candidates(
        requirements,
        native_constraints(first_source),
        _evidence(tmp_path, first_source),
        kicad_version="10.0.5",
    )
    reversed_order = unmapped_differential_pair_rule_candidates(
        requirements,
        native_constraints(reversed_source),
        _evidence(tmp_path, reversed_source),
        kicad_version="10.0.5",
    )

    assert tuple((item.subject, item.evidence["native_rule_names"]) for item in first) == tuple(
        (item.subject, item.evidence["native_rule_names"]) for item in reversed_order
    )
    assert tuple(item.subject for item in first) == (
        "AUX_: native differential-pair rule scope is absent from the project map",
        "MOTOR_: native differential-pair rule scope is absent from the project map",
    )


def test_mapped_selector_and_non_pair_rules_are_quiet(tmp_path: Path) -> None:
    source = "(version 1)\n" + "\n".join(
        (
            _native_rule("usb-skew", "USB_D_"),
            _native_rule("unmapped-length", "MOTOR_", constraint="length"),
        )
    )

    assert not unmapped_differential_pair_rule_candidates(
        _pair_map("USB_D_"),
        native_constraints(source),
        _evidence(tmp_path, source),
        kicad_version="10.0.5",
    )


@pytest.mark.parametrize(
    "condition",
    (
        "A.inDiffPair('MOTOR_*')",
        "A.inDiffPair('${PAIR}')",
        "A.inDiffPair('MOTOR_') && A.Layer == 'F.Cu'",
        "A.inDiffPair('MOTOR_') || A.inDiffPair('USB_D_')",
    ),
    ids=("wildcard", "variable", "compound-and", "compound-or"),
)
def test_nonliteral_or_compound_pair_conditions_are_skipped(
    condition: str,
) -> None:
    assert native_exact_diff_pair_condition(condition) is None


def test_literal_pair_selector_parser_is_exact() -> None:
    assert native_exact_diff_pair_condition("A.inDiffPair('USB_D_')") == "USB_D_"
    assert native_exact_diff_pair_condition("A.inDiffPair('usb_d_')") == "usb_d_"


def test_nonliteral_rules_do_not_emit_candidates(tmp_path: Path) -> None:
    source = "(version 1)\n" + "\n".join(
        _native_rule(f"unsupported-{index}", "ignored", condition=condition)
        for index, condition in enumerate(
            (
                "A.inDiffPair('MOTOR_*')",
                "A.inDiffPair('${PAIR}')",
                "A.inDiffPair('MOTOR_') && A.Layer == 'F.Cu'",
            )
        )
    )

    assert not unmapped_differential_pair_rule_candidates(
        _pair_map("USB_D_"),
        native_constraints(source),
        _evidence(tmp_path, source),
        kicad_version="10.0.5",
    )


@pytest.mark.parametrize(
    ("rule_mode", "pair_mode"),
    (("off", "review"), ("review", "off")),
    ids=("unmapped-rule-disabled", "pair-coverage-disabled"),
)
def test_disabled_rules_do_not_read_native_sources(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    rule_mode: str,
    pair_mode: str,
) -> None:
    import kicad_tooling.hwrepo.pcb_differential_pair_unmapped_scan as owner

    monkeypatch.setattr(
        owner,
        "source_bound_drc_evidence",
        lambda *_args: pytest.fail("disabled pair scope must not read source evidence"),
    )
    config = cast(
        ProjectConfig,
        SimpleNamespace(kind=ProjectKind.PCB, kicad_version="10.0.5"),
    )

    assert not owner.scan_unmapped_differential_pair_rules(
        tmp_path,
        config,
        _policy(
            _pair_map("USB_D_"),
            modes={RULE_ID: rule_mode, PAIR_COVERAGE_RULE_ID: pair_mode},
        ),
        {},
        tmp_path / "build/native",
    )


def test_missing_map_and_non_pcb_projects_do_not_read_native_sources(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import kicad_tooling.hwrepo.pcb_differential_pair_unmapped_scan as owner

    monkeypatch.setattr(
        owner,
        "source_bound_drc_evidence",
        lambda *_args: pytest.fail("unconfigured pair scope must not read source evidence"),
    )
    pcb = cast(ProjectConfig, SimpleNamespace(kind=ProjectKind.PCB, kicad_version="10.0.5"))
    schematic = cast(
        ProjectConfig,
        SimpleNamespace(kind=ProjectKind.SCHEMATIC, kicad_version="10.0.5"),
    )

    assert not owner.scan_unmapped_differential_pair_rules(
        tmp_path, pcb, _policy(None), {}, tmp_path / "build/native"
    )
    assert not owner.scan_unmapped_differential_pair_rules(
        tmp_path, schematic, _policy(_pair_map("USB_D_")), {}, tmp_path / "build/native"
    )
