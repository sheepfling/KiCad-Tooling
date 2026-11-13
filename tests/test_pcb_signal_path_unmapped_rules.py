"""Review exact native length-rule nets omitted from a signal-path map."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest

from kicad_tooling.hwrepo.design_lint_finding_models import DesignLintRuleOverride
from kicad_tooling.hwrepo.design_lint_policy_models import DesignLintPolicy
from kicad_tooling.hwrepo.design_lint_types import Candidate
from kicad_tooling.hwrepo.pcb_drc_rule_parser import native_constraints
from kicad_tooling.hwrepo.pcb_drc_source_evidence import BoundDrcEvidence
from kicad_tooling.hwrepo.pcb_signal_path_rule_models import (
    PcbDrcMinMaxRequirement,
    PcbSignalPathRequirement,
    PcbSignalPathRuleMap,
)
from kicad_tooling.hwrepo.project_models import ProjectConfig, ProjectKind

RULE_ID = "pcb.signal_path_unmapped_native_rule"
COVERAGE_RULE_ID = "pcb.signal_path_rule_coverage"
pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.pcb_lint,
    pytest.mark.design_lint_rule(rule_id=RULE_ID),
]


def _rule(name: str, net: str, *, condition: str | None = None) -> str:
    selector = f"A.NetName == '{net}'" if condition is None else condition
    return (
        f'(rule "{name}" (severity error) (condition "{selector}") (constraint length (max 25mm)))'
    )


def _map(*nets: str) -> PcbSignalPathRuleMap:
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


def _policy(
    requirements: PcbSignalPathRuleMap,
    *,
    coverage_mode: str = "review",
    rule_mode: str = "review",
) -> DesignLintPolicy:
    return DesignLintPolicy(
        pcb_signal_path_rule_map=requirements,
        rules=(
            DesignLintRuleOverride(
                rule_id=COVERAGE_RULE_ID,
                mode=coverage_mode,  # type: ignore[arg-type]
                reason="Synthetic test policy",
            ),
            DesignLintRuleOverride(
                rule_id=RULE_ID,
                mode=rule_mode,  # type: ignore[arg-type]
                reason="Synthetic test policy",
            ),
        ),
    )


def _evidence(source: str) -> BoundDrcEvidence:
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


def _scan(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    source: str,
    requirements: PcbSignalPathRuleMap,
    current_net_names: dict[str, object],
    *,
    coverage_mode: str = "review",
    rule_mode: str = "review",
) -> tuple[Candidate, ...]:
    import kicad_tooling.hwrepo.pcb_signal_path_unmapped_rule_scan as owner

    evidence = _evidence(source)
    monkeypatch.setattr(owner, "source_bound_drc_evidence", lambda *_args: evidence)
    monkeypatch.setattr(owner, "verify_source_bound_drc_unchanged", lambda *_args: None)
    config = cast(
        ProjectConfig,
        SimpleNamespace(kind=ProjectKind.PCB, kicad_version="10.0.5"),
    )
    return owner.scan_unmapped_signal_path_length_rules(
        tmp_path,
        config,
        _policy(requirements, coverage_mode=coverage_mode, rule_mode=rule_mode),
        {},
        tmp_path / "build/native",
        current_net_names,
        "1" * 64,
    )


def test_unmapped_exact_length_rule_for_source_net_is_reviewed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    findings = _scan(
        tmp_path,
        monkeypatch,
        "(version 1)\n" + _rule("data-route-length", "DATA"),
        _map("CLOCK"),
        {"DATA": ()},
    )

    (finding,) = findings
    assert finding.rule_id == RULE_ID
    assert finding.subject == "data-route-length: DATA is absent from signal-path coverage"
    assert finding.evidence["net"] == ("DATA",)
    assert finding.evidence["native_length_bounds"] == ("min_nm=None;max_nm=25000000;issue=<none>",)
    assert finding.evidence["source_sha256"] == ("b" * 64,)
    assert finding.evidence["source_netlist_sha256"] == ("1" * 64,)
    assert "does not infer that the net is critical" in finding.message


def test_mapped_or_source_absent_net_does_not_prompt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = "(version 1)\n" + _rule("data-route-length", "DATA")

    mapped = _scan(tmp_path, monkeypatch, source, _map("DATA"), {"DATA": ()})
    absent = _scan(tmp_path, monkeypatch, source, _map("CLOCK"), {"CLOCK": ()})

    assert not mapped
    assert not absent


def test_nonliteral_length_scope_is_not_guessed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = "\n".join(
        (
            "(version 1)",
            _rule("data-family", "DATA", condition="A.NetName =~ 'DATA.*'"),
            _rule("compound", "DATA", condition="A.NetName == 'DATA' && A.Layer == 'F.Cu'"),
        )
    )

    assert not _scan(tmp_path, monkeypatch, source, _map("CLOCK"), {"DATA": ()})


def test_map_coverage_and_rule_modes_gate_the_prompt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import kicad_tooling.hwrepo.pcb_signal_path_unmapped_rule_scan as owner

    def unexpected_source_read(*_args: object) -> BoundDrcEvidence:
        raise AssertionError("disabled scope must not read source-bound DRC evidence")

    monkeypatch.setattr(owner, "source_bound_drc_evidence", unexpected_source_read)
    monkeypatch.setattr(owner, "verify_source_bound_drc_unchanged", lambda *_args: None)
    config = cast(
        ProjectConfig,
        SimpleNamespace(kind=ProjectKind.PCB, kicad_version="10.0.5"),
    )
    for coverage_mode, rule_mode in (("off", "review"), ("review", "off")):
        assert (
            owner.scan_unmapped_signal_path_length_rules(
                tmp_path,
                config,
                _policy(_map("CLOCK"), coverage_mode=coverage_mode, rule_mode=rule_mode),
                {},
                tmp_path / "build/native",
                {"DATA": ()},
                "1" * 64,
            )
            == ()
        )


def test_rule_and_map_order_do_not_change_candidate_order() -> None:
    source = "\n".join(
        (
            "(version 1)",
            _rule("zeta-length", "ZETA"),
            _rule("alpha-length", "ALPHA"),
        )
    )
    constraints = native_constraints(source)
    reverse_constraints = native_constraints("\n".join(reversed(source.splitlines())))
    evidence = _evidence(source)
    from kicad_tooling.hwrepo.pcb_signal_path_unmapped_native import (
        unmapped_signal_path_length_rule_candidates,
    )

    first = unmapped_signal_path_length_rule_candidates(
        _map("CLOCK", "SECOND"),
        constraints,
        evidence,
        current_net_names={"ZETA": (), "ALPHA": ()},
        source_netlist_sha256="1" * 64,
        kicad_version="10.0.5",
    )
    second = unmapped_signal_path_length_rule_candidates(
        _map("SECOND", "CLOCK"),
        reverse_constraints,
        evidence,
        current_net_names={"ALPHA": (), "ZETA": ()},
        source_netlist_sha256="1" * 64,
        kicad_version="10.0.5",
    )

    assert tuple(item.subject for item in first) == tuple(item.subject for item in second)
    assert tuple(item.subject for item in first) == (
        "alpha-length: ALPHA is absent from signal-path coverage",
        "zeta-length: ZETA is absent from signal-path coverage",
    )
