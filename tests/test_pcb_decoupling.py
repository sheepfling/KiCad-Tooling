"""Synthetic regressions for mapped PCB decoupling placement requirements."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from kicad_tooling.hwrepo.design_lint import candidates, evaluate, fingerprint
from kicad_tooling.hwrepo.models import (
    ContractCoachReport,
    DesignLintIgnore,
    DesignLintPolicy,
    DesignLintRuleOverride,
    NetlistContract,
    PcbDecouplingCapacitor,
    PcbDecouplingMap,
)
from kicad_tooling.hwrepo.pcb_decoupling import pcb_decoupling_entries
from tests.pcb_decoupling_support import (
    CAP,
    RULE,
    coverage_report,
    mapping,
    requirement,
    snapshot,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.pcb_lint]


def test_wrong_net_disconnected_wrong_footprint_and_dnp_candidates_do_not_satisfy_requirement() -> (
    None
):
    caps = tuple(
        PcbDecouplingCapacitor(
            reference=reference,
            footprint=CAP,
            supply_pad=f"{reference}.1",
            return_pad=f"{reference}.2",
        )
        for reference in ("C1", "C2", "C3", "C4")
    )
    evidence = snapshot(
        distances_nm={"C1": 50000, "C2": 60000, "C3": 70000, "C4": 80000},
        wrong_supply_nets=frozenset({"C1.1"}),
        disconnected_supply=frozenset({"C2.1"}),
        dnp_caps=frozenset({"C3"}),
        footprints={"C4": "Synthetic:WrongCap"},
    )
    entry = pcb_decoupling_entries(mapping(requirement(capacitors=caps)), evidence)[0]
    assert entry.status == "INCOMPLETE"
    assert entry.selected_capacitors == ()
    assert all(not candidate.eligible for candidate in entry.candidates)
    assert "expected 'VDD'" in " ".join(entry.candidates[0].issues)
    assert "not connected" in " ".join(entry.candidates[1].issues)
    assert "do-not-populate" in " ".join(entry.candidates[2].issues)
    assert "expected 'Synthetic:Cap_0603'" in " ".join(entry.candidates[3].issues)


def test_exact_threshold_boundary_passes_and_all_policy_checks_each_candidate() -> None:
    caps = (
        PcbDecouplingCapacitor(reference="C1", footprint=CAP, supply_pad="C1.1", return_pad="C1.2"),
        PcbDecouplingCapacitor(reference="C2", footprint=CAP, supply_pad="C2.1", return_pad="C2.2"),
    )
    evidence = snapshot(distances_nm={"C1": 100000, "C2": 100001})
    any_entry = pcb_decoupling_entries(
        mapping(requirement(capacitors=caps, maximum_um=100, selection="any")), evidence
    )[0]
    all_entry = pcb_decoupling_entries(
        mapping(requirement(capacitors=caps, maximum_um=100, selection="all")), evidence
    )[0]
    assert any_entry.status == "COMPLETE"
    assert any_entry.selected_capacitors == ("C1",)
    assert all_entry.status == "INCOMPLETE"


def test_invalid_pin_mapping_and_unknown_fields_are_rejected() -> None:
    with pytest.raises(ValidationError):
        PcbDecouplingCapacitor(reference="C1", footprint=CAP, supply_pad="C2.1", return_pad="C1.2")
    with pytest.raises(ValidationError):
        PcbDecouplingMap.model_validate(
            {"basis": "synthetic", "requirements": [], "max_distance_um": 100}
        )


def test_near_rotated_and_shared_bank_candidates_satisfy_exact_mapping() -> None:
    cap = PcbDecouplingCapacitor(
        reference="C1", footprint=CAP, supply_pad="C1.1", return_pad="C1.2"
    )
    two_supply_requirements = mapping(
        requirement(capacitors=(cap,), id="core-a"),
        requirement(capacitors=(cap,), supply_pad="U1.3", return_pad="U1.4", id="core-b"),
    )
    observed = snapshot(distances_nm={"C1": 5000}, extra_ic_supply=True)
    entries = pcb_decoupling_entries(two_supply_requirements, observed)
    assert tuple(entry.status for entry in entries) == ("COMPLETE", "COMPLETE")
    assert entries[0].selected_capacitors == ("C1",)
    assert entries[0].candidates[0].distance_squared_nm2 == 25000000
    assert entries[0].candidates[0].distance_nm == 5000


def test_pad_inventory_order_preserves_distance_finding_and_boundary_repair_clears_it() -> None:
    caps = (
        PcbDecouplingCapacitor(reference="C1", footprint=CAP, supply_pad="C1.1", return_pad="C1.2"),
        PcbDecouplingCapacitor(reference="C2", footprint=CAP, supply_pad="C2.1", return_pad="C2.2"),
    )
    spec = mapping(requirement(capacitors=caps, maximum_um=100, selection="any"))
    evidence = snapshot(distances_nm={"C1": 101000, "C2": 110000})
    reordered_evidence = evidence.model_copy(
        update={
            "pads": tuple(
                pad.model_copy(update={"connected_pads": tuple(reversed(pad.connected_pads))})
                for pad in reversed(evidence.pads)
            )
        }
    )
    measured = coverage_report(spec, evidence)
    reordered_measured = coverage_report(spec, reordered_evidence)
    assert measured.entries == reordered_measured.entries
    assert measured.map_sha256 == reordered_measured.map_sha256
    assert measured.snapshot_sha256 != reordered_measured.snapshot_sha256
    native = ContractCoachReport(
        status="READY_FOR_REVIEW",
        project_id="synthetic-decoupling",
        observed=NetlistContract(components={}, nets={}),
        netlist_sha256="f" * 64,
    )
    policy = DesignLintPolicy(pcb_decoupling_map=spec)
    original = evaluate("synthetic-decoupling", native, policy, pcb_decoupling_coverage=measured)
    reordered = evaluate(
        "synthetic-decoupling", native, policy, pcb_decoupling_coverage=reordered_measured
    )
    original_finding = next(item for item in original.findings if item.rule_id == RULE)
    reordered_finding = next(item for item in reordered.findings if item.rule_id == RULE)
    assert original.status == "REVIEW"
    assert (original_finding.subject, original_finding.fingerprint, original_finding.evidence) == (
        reordered_finding.subject,
        reordered_finding.fingerprint,
        reordered_finding.evidence,
    )
    repaired_evidence = snapshot(distances_nm={"C1": 100000, "C2": 110000})
    repaired_measured = coverage_report(spec, repaired_evidence)
    repaired = evaluate(
        "synthetic-decoupling", native, policy, pcb_decoupling_coverage=repaired_measured
    )
    assert repaired_measured.entries[0].selected_capacitors == ("C1",)
    assert not any(item.rule_id == RULE for item in repaired.findings)


def test_distant_capacitor_exceeds_authored_center_distance_limit() -> None:
    entries = pcb_decoupling_entries(
        mapping(requirement(maximum_um=100)), snapshot(distances_nm={"C1": 100001})
    )
    assert entries[0].status == "INCOMPLETE"
    assert entries[0].candidates[0].distance_nm == 100001
    assert entries[0].selected_capacitors == ()
    assert "100 um center-distance limit" in entries[0].issues[0]


def test_no_threshold_emits_reviewable_measurement_and_honors_override_and_ignore() -> None:
    mapped = mapping(requirement(maximum_um=None))
    evidence = snapshot(distances_nm={"C1": 42500})
    measured = coverage_report(mapped, evidence)
    native = ContractCoachReport(
        status="READY_FOR_REVIEW",
        project_id="synthetic-decoupling",
        observed=NetlistContract(components={}, nets={}),
        netlist_sha256="f" * 64,
    )
    policy = DesignLintPolicy(pcb_decoupling_map=mapped)
    reviewed = evaluate("synthetic-decoupling", native, policy, pcb_decoupling_coverage=measured)
    finding = next(item for item in reviewed.findings if item.rule_id == RULE)
    blocking = evaluate(
        "synthetic-decoupling",
        native,
        policy.model_copy(
            update={
                "rules": (
                    DesignLintRuleOverride(
                        rule_id=RULE, mode="block", reason="Synthetic policy override test"
                    ),
                )
            }
        ),
        pcb_decoupling_coverage=measured,
    )
    ignored = evaluate(
        "synthetic-decoupling",
        native,
        policy.model_copy(
            update={
                "ignores": (
                    DesignLintIgnore(
                        rule_id=RULE,
                        fingerprint=fingerprint(
                            next(
                                item
                                for item in candidates(
                                    native.observed, pcb_decoupling_coverage=measured
                                )
                                if item.rule_id == RULE
                            )
                        ),
                        reason="Reviewed synthetic control case",
                    ),
                )
            }
        ),
        pcb_decoupling_coverage=measured,
    )
    assert reviewed.status == "REVIEW"
    assert "42.500 um" in finding.evidence["candidate_distances"][0]
    assert blocking.status == "FAIL"
    assert ignored.status == "PASS"
