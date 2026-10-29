"""Oversized clearance requirements must not be credited as native coverage."""

from __future__ import annotations

import hashlib
from decimal import Decimal
from pathlib import Path

import pytest

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.models import (
    ContractCoachReport,
    DesignLintPolicy,
    DesignLintRuleOverride,
)
from kicad_tooling.hwrepo.pcb_drc_models import PcbDrcMinMaxRequirement
from kicad_tooling.hwrepo.pcb_drc_rule_coverage import compare_native_rules
from kicad_tooling.hwrepo.pcb_drc_rule_parser import native_constraints
from kicad_tooling.hwrepo.pcb_mechanical_edge_clearance import mechanical_edge_rule_coverage_issue
from tests.design_lint_fixtures.pcb_signal_path import (
    compare,
    incomplete_signal_report,
    native_rules,
    path_map,
    signal_source_hashes,
    source_netlist,
)
from tests.test_pcb_drc_coverage import pair_map, rules_text
from tests.test_pcb_mechanical_edge_clearance import _requirement, _rule

pytestmark = [pytest.mark.design_lint, pytest.mark.pcb_lint]


@pytest.mark.parametrize(
    ("filename", "expected"),
    (
        ("board.kicad_dru", "2bdbcdf636da79cdca3ac67e60f57520300b8f5dda78cef2c319f359db2e41b2"),
        ("board.kicad_pro", "eadc610c8422b30f649a19d1f6a1e321eff56686e3bc005b8302a0d996c1ce43"),
        ("inside.kicad_pcb", "272c4377354b1b6c037fdd2189ec7a01fc9ccfc4478117430cb79c515b9ac66c"),
        ("outside.kicad_pcb", "eb60de363fa5466afe9e175d887ef5e90bc07d969d489677df2e1fb2edfce366"),
    ),
)
def test_native_clamp_fixture_sources_are_pinned(filename: str, expected: str) -> None:
    fixture = Path(__file__).parent / "fixtures/design_lint/drc-clearance-clamp" / filename
    assert hashlib.sha256(fixture.read_bytes()).hexdigest() == expected


@pytest.mark.parametrize(("mode", "status"), (("review", "REVIEW"), ("block", "FAIL")))
def test_clamped_signal_rule_obeys_project_disposition(mode: str, status: str) -> None:
    mapping = path_map()
    path = mapping.paths[0].model_copy(
        update={"length": None, "edge_clearance": PcbDrcMinMaxRequirement(min_nm=600_000_000)}
    )
    mapping = mapping.model_copy(update={"paths": (path,), "bundles": ()})
    rules = native_rules().replace("(min 2mm)", "(min 600mm)")
    (entry,) = compare(rules=rules, requirements=mapping)
    coverage = incomplete_signal_report(mapping)
    coverage = type(coverage).model_validate({**coverage.model_dump(), "entries": (entry,)})
    coach = ContractCoachReport(
        status="READY_FOR_REVIEW",
        project_id="synthetic-clamp",
        source_hashes=signal_source_hashes(),
        netlist_sha256="5" * 64,
        observed=source_netlist(),
    )
    policy = DesignLintPolicy(
        pcb_signal_path_rule_map=mapping,
        rules=(
            DesignLintRuleOverride(
                rule_id="pcb.signal_path_rule_coverage", mode=mode, reason="Synthetic policy"
            ),
        ),
    )
    report = evaluate("synthetic-clamp", coach, policy, pcb_signal_path_coverage=coverage)
    assert report.status == status
    finding = next(
        item for item in report.findings if item.rule_id == "pcb.signal_path_rule_coverage"
    )
    assert "500 mm" in finding.evidence["constraints"][0]


@pytest.mark.parametrize(
    ("minimum_nm", "expected_status"),
    (
        (499_999_999, "COVERED"),
        (500_000_000, "COVERED"),
        (500_000_001, "UNSUPPORTED"),
        (600_000_000, "UNSUPPORTED"),
    ),
)
def test_mapped_signal_edge_minimum_is_not_credited_above_audited_limit(
    minimum_nm: int, expected_status: str
) -> None:
    requirements = path_map()
    path = requirements.paths[0].model_copy(
        update={"length": None, "edge_clearance": PcbDrcMinMaxRequirement(min_nm=minimum_nm)}
    )
    requirements = requirements.model_copy(update={"paths": (path,), "bundles": ()})
    minimum_mm = Decimal(minimum_nm) / 1_000_000
    source = native_rules().replace(
        "(constraint edge_clearance (min 2mm))",
        f"(constraint edge_clearance (min {minimum_mm}mm))",
    )
    (entry,) = compare(rules=source, requirements=requirements)
    (edge,) = entry.constraints
    assert edge.status == expected_status
    assert edge.observed_min_nm == minimum_nm
    if expected_status == "UNSUPPORTED":
        assert "500 mm" in (edge.issue or "")
        assert "10.0.0 and 10.0.5" in (edge.issue or "")


@pytest.mark.parametrize(
    ("minimum_nm", "expected_status"),
    ((500_000_000, "COVERED"), (500_000_001, "UNSUPPORTED"), (600_000_000, "UNSUPPORTED")),
)
def test_mapped_pair_edge_minimum_is_not_credited_above_audited_limit(
    minimum_nm: int, expected_status: str
) -> None:
    mapping = pair_map()
    requirement = mapping.requirements[0].model_copy(
        update={
            "track_width": None,
            "diff_pair_gap": None,
            "skew": None,
            "uncoupled_length": None,
            "edge_clearance": PcbDrcMinMaxRequirement(min_nm=minimum_nm),
        }
    )
    minimum_mm = Decimal(minimum_nm) / 1_000_000
    source = rules_text().replace(
        "(constraint edge_clearance (min 1.0mm))",
        f"(constraint edge_clearance (min {minimum_mm}mm))",
    )
    (entry,) = compare_native_rules(
        mapping.model_copy(update={"requirements": (requirement,)}), source, frozenset()
    )
    (edge,) = entry.constraints
    assert edge.status == expected_status
    assert edge.observed_min_nm == minimum_nm


@pytest.mark.parametrize("version", ("10.0.0", "10.0.5", "10.0.6"))
@pytest.mark.parametrize(
    ("minimum_nm", "expected_issue"),
    ((500_000_000, False), (500_000_001, True), (600_000_000, True)),
)
def test_mechanical_edge_minimum_respects_audited_limit(
    version: str, minimum_nm: int, expected_issue: bool
) -> None:
    requirement = _requirement().model_copy(update={"minimum_clearance_nm": minimum_nm})
    minimum_mm = Decimal(minimum_nm) / 1_000_000
    mapped = _rule(minimum=f"{minimum_mm}mm").split("\n", 1)[1]
    anchor = '(rule "anchor" (severity ignore) (constraint physical_clearance (min 500mm)))'
    source = f"(version 1)\n{anchor}\n{mapped}"
    issue = mechanical_edge_rule_coverage_issue(
        requirement, native_constraints(source), kicad_version=version
    )
    if expected_issue:
        assert issue is not None
        assert "500 mm" in issue
        assert "10.0.0 and 10.0.5" in issue
    else:
        assert issue is None
