"""Review exact native pad-pair length rules omitted from a signal-path map."""

from __future__ import annotations

from pathlib import Path

import pytest

from kicad_tooling.hwrepo.pcb_drc_rule_parser import native_constraints
from kicad_tooling.hwrepo.pcb_signal_path_rule_models import (
    PcbDrcMinMaxRequirement,
    PcbSignalPathRequirement,
    PcbSignalPathRuleMap,
)
from kicad_tooling.hwrepo.pcb_signal_path_unmapped_native import (
    unmapped_signal_path_from_to_length_rule_candidates,
)
from tests.pcb_signal_path_unmapped_rule_support import (
    FROM_TO_LENGTH_RULE_ID,
    bound_evidence,
    native_rule,
    scan,
)

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.pcb_lint,
    pytest.mark.design_lint_rule(rule_id=FROM_TO_LENGTH_RULE_ID),
]


def _path_map(*paths: tuple[str, str, str]) -> PcbSignalPathRuleMap:
    return PcbSignalPathRuleMap(
        basis="Synthetic reviewed endpoint coverage",
        paths=tuple(
            PcbSignalPathRequirement(
                id=f"path-{index}",
                basis="Synthetic exact endpoint route",
                net=net,
                from_pad=from_pad,
                to_pad=to_pad,
                length=PcbDrcMinMaxRequirement(max_nm=25_000_000),
            )
            for index, (net, from_pad, to_pad) in enumerate(paths, start=1)
        ),
    )


def test_unmapped_exact_from_to_length_pair_is_reviewed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    rule = native_rule(
        "data-route-length",
        "DATA",
        condition="A.fromTo('J1-2', 'U1-2')",
    )
    findings = scan(
        tmp_path,
        monkeypatch,
        "(version 1)\n" + rule,
        _path_map(("CLOCK", "J1.1", "U1.1")),
        {"CLOCK": ("J1.1", "U1.1"), "DATA": ("J1.2", "U1.2")},
    )

    (finding,) = tuple(item for item in findings if item.rule_id == FROM_TO_LENGTH_RULE_ID)
    assert finding.subject == "data-route-length: J1-2 to U1-2 is absent from signal-path coverage"
    assert finding.evidence["net"] == ("DATA",)
    assert finding.evidence["from_to_pads"] == ("J1-2 -> U1-2",)
    assert finding.evidence["native_length_bounds"] == ("min_nm=None;max_nm=25000000;issue=<none>",)
    assert finding.evidence["source_netlist_sha256"] == ("1" * 64,)
    assert "does not infer that the path is critical" in finding.message


def test_mapped_pair_in_either_order_and_split_source_nets_are_quiet(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    forward = "(version 1)\n" + native_rule(
        "data-route-length", "DATA", condition="A.fromTo('J1-2', 'U1-2')"
    )
    reverse = "(version 1)\n" + native_rule(
        "data-route-length", "DATA", condition="A.fromTo('U1-2', 'J1-2')"
    )
    mapped = _path_map(("DATA", "J1.2", "U1.2"))

    assert not scan(
        tmp_path,
        monkeypatch,
        forward,
        mapped,
        {"DATA": ("J1.2", "U1.2")},
    )
    assert not scan(
        tmp_path,
        monkeypatch,
        reverse,
        mapped,
        {"DATA": ("J1.2", "U1.2")},
    )
    assert not scan(
        tmp_path,
        monkeypatch,
        forward,
        _path_map(("CLOCK", "J1.1", "U1.1")),
        {"LEFT": ("J1.2",), "RIGHT": ("U1.2",)},
    )


def test_wildcard_compound_and_variable_from_to_scopes_are_not_guessed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = "\n".join(
        (
            "(version 1)",
            native_rule("wildcard", "DATA", condition="A.fromTo('J1-*', 'U1-*')"),
            native_rule(
                "compound",
                "DATA",
                condition="A.fromTo('J1-2', 'U1-2') && A.Layer == 'F.Cu'",
            ),
            native_rule(
                "variable",
                "DATA",
                condition="A.fromTo('${FROM_PAD}', '${TO_PAD}')",
            ),
        )
    )

    assert not scan(
        tmp_path,
        monkeypatch,
        source,
        _path_map(("CLOCK", "J1.1", "U1.1")),
        {"DATA": ("J1.2", "U1.2")},
    )


def test_from_to_mode_is_independent_and_coverage_off_skips_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = "(version 1)\n" + native_rule(
        "data-route-length", "DATA", condition="A.fromTo('J1-2', 'U1-2')"
    )
    requirements = _path_map(("CLOCK", "J1.1", "U1.1"))
    nets = {"CLOCK": ("J1.1", "U1.1"), "DATA": ("J1.2", "U1.2")}

    disabled = scan(
        tmp_path,
        monkeypatch,
        source,
        requirements,
        nets,
        from_to_length_mode="off",
    )
    assert not any(item.rule_id == FROM_TO_LENGTH_RULE_ID for item in disabled)

    import kicad_tooling.hwrepo.pcb_signal_path_unmapped_rule_scan as owner

    def unexpected_source_read(*_args: object) -> object:
        raise AssertionError("disabled coverage must not read source-bound DRC evidence")

    monkeypatch.setattr(owner, "source_bound_drc_evidence", unexpected_source_read)
    monkeypatch.setattr(owner, "verify_source_bound_drc_unchanged", lambda *_args: None)
    assert (
        scan(
            tmp_path,
            monkeypatch,
            source,
            requirements,
            nets,
            coverage_mode="off",
        )
        == ()
    )


def test_candidate_order_is_stable_and_repeated_rule_pairs_are_grouped() -> None:
    source = "\n".join(
        (
            "(version 1)",
            native_rule("zeta-route", "ZETA", condition="A.fromTo('J2-1', 'U2-1')"),
            native_rule("alpha-route", "ALPHA", condition="A.fromTo('J3-1', 'U3-1')"),
            native_rule("alpha-route", "ALPHA", condition="A.fromTo('J3-1', 'U3-1')"),
        )
    )
    constraints = native_constraints(source)
    reverse_constraints = native_constraints("\n".join(reversed(source.splitlines())))
    evidence = bound_evidence(source)
    nets = {
        "ZETA": ("J2.1", "U2.1"),
        "ALPHA": ("J3.1", "U3.1"),
    }
    first = unmapped_signal_path_from_to_length_rule_candidates(
        _path_map(("CLOCK", "J1.1", "U1.1")),
        constraints,
        evidence,
        current_net_names=nets,
        source_netlist_sha256="1" * 64,
        kicad_version="10.0.5",
    )
    second = unmapped_signal_path_from_to_length_rule_candidates(
        _path_map(("CLOCK", "J1.1", "U1.1")),
        reverse_constraints,
        evidence,
        current_net_names=dict(reversed(tuple(nets.items()))),
        source_netlist_sha256="1" * 64,
        kicad_version="10.0.5",
    )

    assert tuple(item.subject for item in first) == tuple(item.subject for item in second)
    assert tuple(item.subject for item in first) == (
        "alpha-route: J3-1 to U3-1 is absent from signal-path coverage",
        "zeta-route: J2-1 to U2-1 is absent from signal-path coverage",
    )
    assert first[0].evidence["native_rule_count"] == ("2",)
