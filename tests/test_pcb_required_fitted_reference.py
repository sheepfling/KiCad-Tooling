"""Project-authored PCB fitted-reference requirements and policy behavior."""

from __future__ import annotations

import hashlib
import json

import pytest

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.design_lint_candidate_aggregation import fingerprint
from kicad_tooling.hwrepo.design_lint_pcb_component_inventory_scan import (
    resolve_pcb_component_inventory_modes,
)
from kicad_tooling.hwrepo.design_lint_pcb_required_fitted_reference_candidates import (
    pcb_required_fitted_reference_candidates,
)
from kicad_tooling.hwrepo.models import (
    DesignLintIgnore,
    DesignLintPolicy,
    DesignLintRuleOverride,
    NetlistContract,
)
from kicad_tooling.hwrepo.pcb_component_inventory import (
    evaluate_native_component_inventory_coverage,
)
from kicad_tooling.hwrepo.pcb_component_population import (
    compare_schematic_pcb_population,
)
from kicad_tooling.hwrepo.pcb_connectivity_snapshot import PcbConnectivitySnapshot
from kicad_tooling.hwrepo.pcb_required_fitted_reference_checks import (
    compare_required_fitted_references,
    required_fitted_reference_map_sha256,
)
from kicad_tooling.hwrepo.pcb_required_fitted_reference_models import (
    PcbRequiredFittedReference,
    PcbRequiredFittedReferenceMap,
)
from tests.design_lint_fixtures.pcb_component_inventory import (
    BOARD_SHA256,
    NETLIST_SHA256,
    PROBE_SHA256,
    SNAPSHOT_SHA256,
    coach,
    netlist,
    snapshot,
)
from tests.design_lint_fixtures.pcb_component_inventory import (
    required_fitted_reference_coverage as _coverage,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.pcb_lint]
RULE = "pcb.required_fitted_reference"
FOOTPRINT = "Synthetic:Probe_Module"


def _requirement_map(
    *references: str,
    basis: str = "synthetic approved base assembly list",
) -> PcbRequiredFittedReferenceMap:
    """Create small independent requirements for synthetic component references."""
    return PcbRequiredFittedReferenceMap(
        basis=basis,
        requirements=tuple(
            PcbRequiredFittedReference(
                reference=reference,
                footprint=FOOTPRINT,
                basis="must be fitted in the base assembly",
            )
            for reference in references
        ),
    )


@pytest.mark.design_lint_rule(rule_id=RULE)
def test_explicit_requirement_catches_both_sources_marked_dnp() -> None:
    observed = netlist(components={"U1": FOOTPRINT}, dnp=("U1",))
    board = snapshot(
        "U1",
        schema_version="13",
        footprint_by_reference={"U1": FOOTPRINT},
        dnp_by_reference={"U1": True},
    )
    requirements = _requirement_map("U1")

    assert compare_schematic_pcb_population(observed, board) == ()
    (mismatch,) = compare_required_fitted_references(requirements, observed, board)
    assert mismatch.violations == ("schematic_component_dnp", "board_footprint_dnp")

    coverage = _coverage(observed, board, requirements)
    (candidate,) = pcb_required_fitted_reference_candidates(coverage)
    assert candidate.subject == "U1: required fitted component does not match source"
    assert "variant" not in candidate.evidence
    assert "variant_evidence" not in candidate.evidence
    assert candidate.evidence["violations"] == (
        "schematic_component_dnp",
        "board_footprint_dnp",
    )
    assert candidate.evidence["requirement_map_sha256"] == (
        required_fitted_reference_map_sha256(requirements),
    )

    report = evaluate(
        "synthetic-required-fitted-reference",
        coach(observed),
        DesignLintPolicy(pcb_required_fitted_reference_map=requirements),
        pcb_component_inventory_coverage=coverage,
    )
    (finding,) = tuple(item for item in report.findings if item.rule_id == RULE)
    assert report.status == "FAIL"
    assert finding.mode == "block"
    assert finding.disposition == "OPEN"


@pytest.mark.design_lint_rule(rule_id=RULE)
def test_matching_fitted_reference_is_a_quiet_control() -> None:
    observed = netlist(components={"U1": FOOTPRINT})
    board = snapshot("U1", footprint_by_reference={"U1": FOOTPRINT})

    coverage = _coverage(observed, board, _requirement_map("U1"))

    assert coverage.required_fitted_reference_coverage.status == "COMPLETE"
    assert coverage.required_fitted_reference_coverage.mismatches == ()
    assert pcb_required_fitted_reference_candidates(coverage) == ()


@pytest.mark.design_lint_rule(rule_id=RULE)
@pytest.mark.parametrize(
    ("observed", "board", "expected"),
    (
        (
            netlist(components={"R1": FOOTPRINT}),
            snapshot("U1", footprint_by_reference={"U1": FOOTPRINT}),
            ("schematic_reference_missing",),
        ),
        (
            netlist(components={"U1": FOOTPRINT}),
            snapshot(),
            ("board_footprint_missing",),
        ),
        (
            netlist(components={"U1": "Synthetic:Other"}),
            snapshot("U1", footprint_by_reference={"U1": "Synthetic:Other"}),
            ("schematic_footprint_mismatch", "board_footprint_mismatch"),
        ),
    ),
    ids=("missing-from-schematic", "missing-from-board", "wrong-footprint"),
)
def test_explicit_requirement_reports_source_mismatches(
    observed: NetlistContract,
    board: PcbConnectivitySnapshot,
    expected: tuple[str, ...],
) -> None:
    (mismatch,) = compare_required_fitted_references(_requirement_map("U1"), observed, board)

    assert mismatch.violations == expected


@pytest.mark.design_lint_rule(rule_id=RULE)
def test_optional_symbol_and_part_identity_are_compared_exactly() -> None:
    observed = netlist(components={"U1": FOOTPRINT}).model_copy(
        update={"component_symbols": {"U1": "Synthetic:Observed"}}
    )
    requirement = PcbRequiredFittedReference(
        reference="U1",
        footprint=FOOTPRINT,
        basis="must be fitted",
        symbol="Synthetic:Expected",
        part_id="synthetic-approved-part",
    )
    requirements = PcbRequiredFittedReferenceMap(
        basis="synthetic identity list",
        requirements=(requirement,),
    )

    (mismatch,) = compare_required_fitted_references(
        requirements,
        observed,
        snapshot("U1", footprint_by_reference={"U1": FOOTPRINT}),
    )
    assert mismatch.violations == ("schematic_symbol_mismatch", "schematic_part_id_mismatch")
    assert mismatch.observed_symbol == "Synthetic:Observed"
    assert mismatch.observed_part_id is None


@pytest.mark.design_lint_rule(rule_id=RULE)
def test_map_order_and_observation_order_do_not_change_results() -> None:
    requirements = _requirement_map("U1", "U2")
    reversed_requirements = _requirement_map("U2", "U1")
    observed = netlist(components={"U2": FOOTPRINT, "U1": FOOTPRINT}, dnp=("U1",))
    board = snapshot(
        "U2",
        "u1",
        footprint_by_reference={"U1": FOOTPRINT, "U2": FOOTPRINT},
        dnp_by_reference={"U1": True},
    )

    assert required_fitted_reference_map_sha256(requirements) == (
        required_fitted_reference_map_sha256(reversed_requirements)
    )
    legacy_payload = {
        "schema_version": requirements.schema_version,
        "basis": requirements.basis,
        "requirements": [
            item.model_dump(mode="json")
            for item in sorted(
                requirements.requirements, key=lambda item: item.reference.casefold()
            )
        ],
    }
    expected_legacy_hash = hashlib.sha256(
        json.dumps(legacy_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    assert required_fitted_reference_map_sha256(requirements) == expected_legacy_hash
    assert compare_required_fitted_references(requirements, observed, board) == (
        compare_required_fitted_references(reversed_requirements, observed, board)
    )


@pytest.mark.design_lint_rule(rule_id=RULE)
def test_rule_mode_is_quiet_without_requirements_and_blocking_with_them() -> None:
    assert (
        resolve_pcb_component_inventory_modes(DesignLintPolicy()).required_fitted_reference == "off"
    )
    assert (
        resolve_pcb_component_inventory_modes(
            DesignLintPolicy(pcb_required_fitted_reference_map=_requirement_map("U1"))
        ).required_fitted_reference
        == "block"
    )
    assert (
        resolve_pcb_component_inventory_modes(
            DesignLintPolicy(
                pcb_required_fitted_reference_map=_requirement_map("U1"),
                rules=(DesignLintRuleOverride(rule_id=RULE, mode="review", reason="review first"),),
            )
        ).required_fitted_reference
        == "review"
    )


@pytest.mark.design_lint_rule(rule_id=RULE)
def test_enabled_rule_without_a_map_blocks_instead_of_passing() -> None:
    coverage = evaluate_native_component_inventory_coverage(
        netlist(),
        snapshot("U1"),
        mode="off",
        netlist_sha256=NETLIST_SHA256,
        board_path="synthetic/controller.kicad_pcb",
        board_sha256=BOARD_SHA256,
        snapshot_path="build/design-lint/native/snapshot.json",
        snapshot_sha256=SNAPSHOT_SHA256,
        probe_sha256=PROBE_SHA256,
        required_fitted_reference_mode="block",
    )

    assert coverage.status == "COMPLETE"
    assert coverage.required_fitted_reference_coverage.status == "BLOCKED"
    (candidate,) = pcb_required_fitted_reference_candidates(coverage)
    assert "no project-authored fitted-reference map" in candidate.evidence["coverage_issue"][0]
    report = evaluate(
        "synthetic-required-fitted-reference",
        coach(netlist()),
        DesignLintPolicy(
            rules=(DesignLintRuleOverride(rule_id=RULE, mode="block", reason="map required"),)
        ),
        pcb_component_inventory_coverage=coverage,
    )
    assert report.status == "BLOCKED"
    assert any("no project-authored fitted-reference map" in item for item in report.issues)


@pytest.mark.design_lint_rule(rule_id=RULE)
def test_project_mode_and_exact_ignore_are_applied_to_requirements() -> None:
    observed = netlist(components={"U1": FOOTPRINT}, dnp=("U1",))
    board = snapshot(
        "U1",
        footprint_by_reference={"U1": FOOTPRINT},
        dnp_by_reference={"U1": True},
    )
    requirements = _requirement_map("U1")
    coverage = _coverage(observed, board, requirements, mode="review")
    (candidate,) = pcb_required_fitted_reference_candidates(coverage)
    review = DesignLintPolicy(
        pcb_required_fitted_reference_map=requirements,
        rules=(DesignLintRuleOverride(rule_id=RULE, mode="review", reason="verify assembly"),),
    )
    report = evaluate(
        "synthetic-required-fitted-reference",
        coach(observed),
        review,
        pcb_component_inventory_coverage=coverage,
    )
    (finding,) = tuple(item for item in report.findings if item.rule_id == RULE)
    assert finding.mode == "review"
    assert finding.disposition == "OPEN"

    ignored_policy = review.model_copy(
        update={
            "ignores": (
                DesignLintIgnore(
                    rule_id=RULE,
                    fingerprint=fingerprint(candidate),
                    reason="approved fitted-reference exception",
                ),
            )
        }
    )
    ignored = evaluate(
        "synthetic-required-fitted-reference",
        coach(observed),
        ignored_policy,
        pcb_component_inventory_coverage=coverage,
    )
    (ignored_finding,) = tuple(item for item in ignored.findings if item.rule_id == RULE)
    assert ignored_finding.disposition == "IGNORED"

    changed_map = _requirement_map("U1", basis="changed approved assembly list")
    changed_coverage = _coverage(observed, board, changed_map, mode="review")
    stale = evaluate(
        "synthetic-required-fitted-reference",
        coach(observed),
        ignored_policy,
        pcb_component_inventory_coverage=changed_coverage,
    )
    (stale_finding,) = tuple(item for item in stale.findings if item.rule_id == RULE)
    assert stale_finding.disposition == "OPEN"
    assert tuple(item.rule_id for item in stale.stale_ignores) == (RULE,)

    disabled = _coverage(observed, board, requirements, mode="off")
    assert pcb_required_fitted_reference_candidates(disabled) == ()
