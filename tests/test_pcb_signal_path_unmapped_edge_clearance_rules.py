"""Review exact native edge-clearance nets omitted from a signal-path map."""

from __future__ import annotations

from pathlib import Path

import pytest

from kicad_tooling.hwrepo.pcb_drc_rule_parser import native_constraints
from kicad_tooling.hwrepo.pcb_signal_path_unmapped_native import (
    unmapped_signal_path_edge_clearance_rule_candidates,
)
from tests.pcb_signal_path_unmapped_rule_support import (
    EDGE_CLEARANCE_RULE_ID,
    LENGTH_RULE_ID,
    bound_evidence,
    native_rule,
    path_map,
    scan,
)

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.pcb_lint,
    pytest.mark.design_lint_rule(rule_id=EDGE_CLEARANCE_RULE_ID),
]


def test_unmapped_exact_edge_clearance_rule_for_source_net_is_reviewed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    rule = native_rule(
        "data-board-edge-clearance",
        "DATA",
        constraint="edge_clearance",
        bounds="(min 1.5mm)",
    )
    findings = scan(tmp_path, monkeypatch, "(version 1)\n" + rule, path_map("CLOCK"), {"DATA": ()})

    (finding,) = findings
    assert finding.rule_id == EDGE_CLEARANCE_RULE_ID
    assert finding.subject == "data-board-edge-clearance: DATA is absent from signal-path coverage"
    assert finding.evidence["net"] == ("DATA",)
    assert finding.evidence["native_edge_clearance_bounds"] == (
        "min_nm=1500000;max_nm=None;issue=<none>",
    )
    assert finding.evidence["source_netlist_sha256"] == ("1" * 64,)
    assert "does not infer that the net is critical" in finding.message


def test_mapped_or_source_absent_edge_clearance_net_is_quiet(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = "(version 1)\n" + native_rule(
        "data-edge-clearance",
        "DATA",
        constraint="edge_clearance",
        bounds="(min 1.5mm)",
    )

    mapped = scan(tmp_path, monkeypatch, source, path_map("DATA"), {"DATA": ()})
    source_absent = scan(tmp_path, monkeypatch, source, path_map("CLOCK"), {"CLOCK": ()})

    assert not mapped
    assert not source_absent


def test_nonliteral_edge_clearance_scopes_are_not_guessed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = "\n".join(
        (
            "(version 1)",
            native_rule(
                "data-family-edge-clearance",
                "DATA",
                constraint="edge_clearance",
                bounds="(min 1.5mm)",
                condition="A.NetName =~ 'DATA.*'",
            ),
            native_rule(
                "compound-edge-clearance",
                "DATA",
                constraint="edge_clearance",
                bounds="(min 1.5mm)",
                condition="A.NetName == 'DATA' && A.Layer == 'F.Cu'",
            ),
        )
    )

    assert not scan(tmp_path, monkeypatch, source, path_map("CLOCK"), {"DATA": ()})


def test_length_and_edge_clearance_overrides_are_independent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = "\n".join(
        (
            "(version 1)",
            native_rule("data-length", "DATA"),
            native_rule(
                "data-edge-clearance",
                "DATA",
                constraint="edge_clearance",
                bounds="(min 1.5mm)",
            ),
        )
    )

    only_edge_clearance = scan(
        tmp_path,
        monkeypatch,
        source,
        path_map("CLOCK"),
        {"DATA": ()},
        length_mode="off",
    )
    only_length = scan(
        tmp_path,
        monkeypatch,
        source,
        path_map("CLOCK"),
        {"DATA": ()},
        edge_clearance_mode="off",
    )

    assert tuple(item.rule_id for item in only_edge_clearance) == (EDGE_CLEARANCE_RULE_ID,)
    assert tuple(item.rule_id for item in only_length) == (LENGTH_RULE_ID,)


def test_edge_clearance_candidate_order_is_stable_under_rule_and_map_order() -> None:
    source = "\n".join(
        (
            "(version 1)",
            native_rule("zeta-edge", "ZETA", constraint="edge_clearance", bounds="(min 1mm)"),
            native_rule("alpha-edge", "ALPHA", constraint="edge_clearance", bounds="(min 1mm)"),
        )
    )
    evidence = bound_evidence(source)
    constraints = native_constraints(source)
    reverse_constraints = native_constraints("\n".join(reversed(source.splitlines())))
    first = unmapped_signal_path_edge_clearance_rule_candidates(
        path_map("CLOCK", "SECOND"),
        constraints,
        evidence,
        current_net_names={"ZETA": (), "ALPHA": ()},
        source_netlist_sha256="1" * 64,
        kicad_version="10.0.5",
    )
    second = unmapped_signal_path_edge_clearance_rule_candidates(
        path_map("SECOND", "CLOCK"),
        reverse_constraints,
        evidence,
        current_net_names={"ALPHA": (), "ZETA": ()},
        source_netlist_sha256="1" * 64,
        kicad_version="10.0.5",
    )

    assert tuple(item.subject for item in first) == tuple(item.subject for item in second)
    assert tuple(item.subject for item in first) == (
        "alpha-edge: ALPHA is absent from signal-path coverage",
        "zeta-edge: ZETA is absent from signal-path coverage",
    )
