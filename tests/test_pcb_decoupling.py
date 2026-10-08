"""Synthetic deterministic regressions for mapped PCB decoupling review."""

from __future__ import annotations

import hashlib
import unittest

from pydantic import ValidationError

from kicad_tooling.hwrepo.design_lint import candidates, evaluate, fingerprint
from kicad_tooling.hwrepo.models import (
    ContractCoachReport,
    DesignLintIgnore,
    DesignLintPolicy,
    DesignLintRuleOverride,
    NetlistContract,
    PcbConnectivitySnapshot,
    PcbDecouplingCapacitor,
    PcbDecouplingCoverageReport,
    PcbDecouplingMap,
    PcbDecouplingRequirement,
    PcbPadConnectivityObservation,
    PcbViaObservation,
)
from kicad_tooling.hwrepo.pcb_decoupling import pcb_decoupling_entries

IC = "Synthetic:IC_QFN"
CAP = "Synthetic:Cap_0603"
RULE = "pcb.decoupling_proximity"


def requirement(
    *,
    capacitors: tuple[PcbDecouplingCapacitor, ...] | None = None,
    maximum_um: int | None = 100,
    maximum_return_via_um: int | None = None,
    selection: str = "any",
    supply_pad: str = "U1.1",
    return_pad: str = "U1.2",
    id: str = "core-rail",
) -> PcbDecouplingRequirement:
    return PcbDecouplingRequirement(
        id=id,
        basis="Synthetic device pin map and placement review limit",
        ic_reference="U1",
        ic_footprint=IC,
        supply_pad=supply_pad,
        return_pad=return_pad,
        supply_net="VDD",
        return_net="GND",
        capacitors=capacitors
        or (
            PcbDecouplingCapacitor(
                reference="C1",
                footprint=CAP,
                supply_pad="C1.1",
                return_pad="C1.2",
            ),
        ),
        selection=selection,  # type: ignore[arg-type]
        max_distance_um=maximum_um,
        max_return_via_distance_um=maximum_return_via_um,
    )


def mapping(*items: PcbDecouplingRequirement) -> PcbDecouplingMap:
    return PcbDecouplingMap(
        basis="Synthetic reviewed component pin assignments",
        requirements=items or (requirement(),),
    )


def snapshot(
    *,
    distances_nm: dict[str, int] | None = None,
    wrong_supply_nets: frozenset[str] = frozenset(),
    disconnected_supply: frozenset[str] = frozenset(),
    dnp_caps: frozenset[str] = frozenset(),
    footprints: dict[str, str] | None = None,
    extra_ic_supply: bool = False,
    return_vias_nm: dict[str, tuple[tuple[int, int], ...]] | None = None,
    unconnected_vias_nm: tuple[tuple[int, int], ...] = (),
) -> PcbConnectivitySnapshot:
    distances_nm = distances_nm or {"C1": 80_000}
    footprints = footprints or {}
    supply_refs = ["U1.1"]
    return_refs = ["U1.2"]
    cap_refs = [f"{reference}.{pin}" for reference in distances_nm for pin in ("1", "2")]
    return_vias_nm = return_vias_nm or {}
    via_ids_by_cap: dict[str, tuple[str, ...]] = {}
    vias: list[PcbViaObservation] = []
    for reference, locations in return_vias_nm.items():
        ids: list[str] = []
        for index, (x_nm, y_nm) in enumerate(locations):
            via_id = hashlib.sha256(f"{reference}-connected-via-{index}".encode()).hexdigest()
            ids.append(via_id)
            vias.append(
                PcbViaObservation(
                    id=via_id,
                    net="GND",
                    x_nm=x_nm,
                    y_nm=y_nm,
                    start_layer="F.Cu",
                    end_layer="In1.Cu",
                    diameter_nm=600_000,
                    drill_nm=300_000,
                    kind="through",
                    multiplicity=1,
                )
            )
        via_ids_by_cap[reference.casefold()] = tuple(ids)
    for index, (x_nm, y_nm) in enumerate(unconnected_vias_nm):
        via_id = hashlib.sha256(f"unconnected-via-{index}".encode()).hexdigest()
        vias.append(
            PcbViaObservation(
                id=via_id,
                net="GND",
                x_nm=x_nm,
                y_nm=y_nm,
                start_layer="F.Cu",
                end_layer="In1.Cu",
                diameter_nm=600_000,
                drill_nm=300_000,
                kind="through",
                multiplicity=1,
            )
        )
    if extra_ic_supply:
        supply_refs.append("U1.3")
        return_refs.append("U1.4")
    pads: list[PcbPadConnectivityObservation] = []
    for reference in (*supply_refs, *return_refs, *cap_refs):
        component = reference.rsplit(".", 1)[0]
        pin = reference.rsplit(".", 1)[1]
        is_supply = pin == "1" or reference in supply_refs
        net = "VDD" if is_supply else "GND"
        if reference in wrong_supply_nets and is_supply:
            net = "ALT_VDD"
        group = supply_refs if is_supply else return_refs
        if component.startswith("C"):
            group = [*group, reference]
        if reference in disconnected_supply:
            connected = (reference,)
        else:
            connected = tuple(dict.fromkeys((reference, *group)))
        if component.startswith("C"):
            x = distances_nm[component]
            y = 0 if pin == "1" else 20_000
            # These are native world coordinates after the footprint's rotation.
            position = (x, y)
        elif reference == "U1.1":
            position = (0, 0)
        elif reference == "U1.2":
            position = (0, 20_000)
        elif reference == "U1.3":
            position = (0, 40_000)
        else:
            position = (0, 60_000)
        pads.append(
            PcbPadConnectivityObservation(
                pad=reference,
                net=net,
                footprint=footprints.get(component, IC if component == "U1" else CAP),
                dnp=component in dnp_caps,
                connected_pads=connected,
                connected_zones=(),
                connected_islands=(),
                connected_vias=(
                    via_ids_by_cap.get(component.casefold(), ())
                    if component.startswith("C") and pin == "2"
                    else ()
                ),
                positions_nm=(position,),
            )
        )
    return PcbConnectivitySnapshot(
        schema_version="5",
        board_sha256="a" * 64,
        kicad_version="10.0.5",
        image="ghcr.io/example/kicad:10.0.5@sha256:" + "b" * 64,
        probe_sha256="c" * 64,
        zones_refilled=True,
        pads=tuple(pads),
        net_ties=(),
        zones=(),
        vias=tuple(vias),
        access_probe_observations=(),
        access_probe_requests_sha256=None,
    )


def coverage_report(
    mapped: PcbDecouplingMap, evidence: PcbConnectivitySnapshot
) -> PcbDecouplingCoverageReport:
    entries = pcb_decoupling_entries(mapped, evidence)
    return PcbDecouplingCoverageReport(
        status="COMPLETE" if all(item.status == "COMPLETE" for item in entries) else "INCOMPLETE",
        mode="review",
        map_sha256=hashlib.sha256(mapped.model_dump_json().encode("utf-8")).hexdigest(),
        board_path="projects/synthetic/project.kicad_pcb",
        board_sha256=evidence.board_sha256,
        snapshot_path="build/design-lint/pcb-decoupling/snapshot.json",
        snapshot_sha256=hashlib.sha256(evidence.model_dump_json().encode("utf-8")).hexdigest(),
        probe_sha256=evidence.probe_sha256,
        kicad_version=evidence.kicad_version,
        image=evidence.image,
        netlist_sha256="f" * 64,
        entries=entries,
    )


class PcbDecouplingTests(unittest.TestCase):
    def test_near_rotated_and_shared_bank_candidates_satisfy_exact_mapping(self) -> None:
        cap = PcbDecouplingCapacitor(
            reference="C1", footprint=CAP, supply_pad="C1.1", return_pad="C1.2"
        )
        two_supply_requirements = mapping(
            requirement(capacitors=(cap,), id="core-a"),
            requirement(
                capacitors=(cap,),
                supply_pad="U1.3",
                return_pad="U1.4",
                id="core-b",
            ),
        )
        observed = snapshot(distances_nm={"C1": 5_000}, extra_ic_supply=True)

        entries = pcb_decoupling_entries(two_supply_requirements, observed)

        self.assertEqual(tuple(entry.status for entry in entries), ("COMPLETE", "COMPLETE"))
        self.assertEqual(entries[0].selected_capacitors, ("C1",))
        self.assertEqual(entries[0].candidates[0].distance_squared_nm2, 25_000_000)
        self.assertEqual(entries[0].candidates[0].distance_nm, 5_000)

    def test_distant_capacitor_exceeds_authored_center_distance_limit(self) -> None:
        entries = pcb_decoupling_entries(
            mapping(requirement(maximum_um=100)), snapshot(distances_nm={"C1": 100_001})
        )

        self.assertEqual(entries[0].status, "INCOMPLETE")
        self.assertEqual(entries[0].candidates[0].distance_nm, 100_001)
        self.assertEqual(entries[0].selected_capacitors, ())
        self.assertIn("100 um center-distance limit", entries[0].issues[0])

    def test_native_connected_return_via_at_inclusive_authored_boundary_passes(self) -> None:
        evidence = snapshot(
            distances_nm={"C1": 80_000},
            return_vias_nm={"C1": ((120_000, 20_000), (200_000, 20_000))},
        )
        entries = pcb_decoupling_entries(
            mapping(requirement(maximum_um=None, maximum_return_via_um=40)), evidence
        )

        self.assertEqual(entries[0].status, "COMPLETE")
        self.assertEqual(entries[0].selected_capacitors, ("C1",))
        candidate = entries[0].candidates[0]
        self.assertEqual(candidate.connected_return_via_count, 2)
        self.assertEqual(candidate.return_via_distance_nm, 40_000)
        self.assertEqual(
            candidate.nearest_return_via_id,
            next(item for item in evidence.pads if item.pad == "C1.2").connected_vias[0],
        )
        self.assertIn("No project IC-to-cap distance threshold", entries[0].issues[0])

    def test_distant_or_absent_connected_return_via_does_not_satisfy_map(self) -> None:
        spec = mapping(requirement(maximum_um=100, maximum_return_via_um=40))
        distant = pcb_decoupling_entries(
            spec,
            snapshot(
                distances_nm={"C1": 80_000},
                return_vias_nm={"C1": ((120_001, 20_000),)},
            ),
        )[0]
        absent = pcb_decoupling_entries(
            spec,
            snapshot(
                distances_nm={"C1": 80_000},
                unconnected_vias_nm=((80_000, 20_000),),
            ),
        )[0]

        self.assertEqual(distant.status, "INCOMPLETE")
        self.assertEqual(distant.selected_capacitors, ())
        self.assertEqual(distant.candidates[0].return_via_distance_nm, 40_001)
        self.assertIn("the project limit is 40 um", " ".join(distant.candidates[0].issues))
        self.assertEqual(absent.status, "INCOMPLETE")
        self.assertEqual(absent.candidates[0].connected_return_via_count, 0)
        self.assertIn("no native-connected via", " ".join(absent.candidates[0].issues))

    def test_legacy_snapshot_without_connected_via_inventory_is_incomplete(self) -> None:
        current = snapshot(distances_nm={"C1": 80_000})
        legacy_data = current.model_dump(mode="python")
        legacy_data["schema_version"] = "2"
        legacy_data.pop("vias")
        for pad in legacy_data["pads"]:
            pad.pop("connected_vias")
        legacy = PcbConnectivitySnapshot.model_validate(legacy_data)

        entry = pcb_decoupling_entries(
            mapping(requirement(maximum_um=100, maximum_return_via_um=40)), legacy
        )[0]

        self.assertEqual(entry.status, "INCOMPLETE")
        self.assertIn(
            "native connected-via evidence",
            " ".join(entry.candidates[0].issues).casefold(),
        )
        self.assertNotIn("no native-connected via", " ".join(entry.candidates[0].issues))

    def test_supply_distance_and_return_via_must_belong_to_same_selected_capacitor(self) -> None:
        capacitors = (
            PcbDecouplingCapacitor(
                reference="C1", footprint=CAP, supply_pad="C1.1", return_pad="C1.2"
            ),
            PcbDecouplingCapacitor(
                reference="C2", footprint=CAP, supply_pad="C2.1", return_pad="C2.2"
            ),
        )
        entry = pcb_decoupling_entries(
            mapping(
                requirement(
                    capacitors=capacitors,
                    maximum_um=100,
                    maximum_return_via_um=40,
                    selection="any",
                )
            ),
            snapshot(
                distances_nm={"C1": 80_000, "C2": 500_000},
                return_vias_nm={"C2": ((540_000, 20_000),)},
            ),
        )[0]

        self.assertEqual(entry.status, "INCOMPLETE")
        self.assertEqual(entry.selected_capacitors, ())
        self.assertEqual(entry.candidates[0].distance_nm, 80_000)
        self.assertIsNone(entry.candidates[0].return_via_distance_nm)
        self.assertEqual(entry.candidates[1].return_via_distance_nm, 40_000)

    def test_return_via_order_is_stable_and_moving_it_past_limit_clears_candidate(self) -> None:
        spec = mapping(requirement(maximum_um=100, maximum_return_via_um=40))
        connected = snapshot(
            distances_nm={"C1": 80_000},
            return_vias_nm={"C1": ((120_000, 20_000), (100_000, 20_000))},
        )
        reordered = connected.model_copy(
            update={
                "vias": tuple(reversed(connected.vias)),
                "pads": tuple(
                    item.model_copy(update={"connected_vias": tuple(reversed(item.connected_vias))})
                    for item in reversed(connected.pads)
                ),
            }
        )
        fault = snapshot(
            distances_nm={"C1": 80_000},
            return_vias_nm={"C1": ((120_001, 20_000),)},
        )

        passing_entry = pcb_decoupling_entries(spec, connected)[0]
        reordered_entry = pcb_decoupling_entries(spec, reordered)[0]
        fault_entry = pcb_decoupling_entries(spec, fault)[0]

        self.assertEqual(passing_entry, reordered_entry)
        self.assertEqual(passing_entry.selected_capacitors, ("C1",))
        self.assertEqual(fault_entry.status, "INCOMPLETE")
        self.assertEqual(fault_entry.selected_capacitors, ())

    def test_pad_inventory_order_preserves_distance_finding_and_boundary_repair_clears_it(
        self,
    ) -> None:
        caps = (
            PcbDecouplingCapacitor(
                reference="C1", footprint=CAP, supply_pad="C1.1", return_pad="C1.2"
            ),
            PcbDecouplingCapacitor(
                reference="C2", footprint=CAP, supply_pad="C2.1", return_pad="C2.2"
            ),
        )
        spec = mapping(requirement(capacitors=caps, maximum_um=100, selection="any"))
        evidence = snapshot(distances_nm={"C1": 101_000, "C2": 110_000})
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
        self.assertEqual(measured.entries, reordered_measured.entries)
        self.assertEqual(measured.map_sha256, reordered_measured.map_sha256)
        self.assertNotEqual(measured.snapshot_sha256, reordered_measured.snapshot_sha256)

        native = ContractCoachReport(
            status="READY_FOR_REVIEW",
            project_id="synthetic-decoupling",
            observed=NetlistContract(components={}, nets={}),
            netlist_sha256="f" * 64,
        )
        policy = DesignLintPolicy(pcb_decoupling_map=spec)
        original = evaluate(
            "synthetic-decoupling", native, policy, pcb_decoupling_coverage=measured
        )
        reordered = evaluate(
            "synthetic-decoupling", native, policy, pcb_decoupling_coverage=reordered_measured
        )
        original_finding = next(item for item in original.findings if item.rule_id == RULE)
        reordered_finding = next(item for item in reordered.findings if item.rule_id == RULE)
        self.assertEqual(original.status, "REVIEW")
        self.assertEqual(
            (original_finding.subject, original_finding.fingerprint, original_finding.evidence),
            (reordered_finding.subject, reordered_finding.fingerprint, reordered_finding.evidence),
        )

        repaired_evidence = snapshot(distances_nm={"C1": 100_000, "C2": 110_000})
        repaired_measured = coverage_report(spec, repaired_evidence)
        repaired = evaluate(
            "synthetic-decoupling", native, policy, pcb_decoupling_coverage=repaired_measured
        )
        self.assertEqual(repaired_measured.entries[0].selected_capacitors, ("C1",))
        self.assertFalse(any(item.rule_id == RULE for item in repaired.findings))

    def test_exact_threshold_boundary_passes_and_all_policy_checks_each_candidate(self) -> None:
        caps = (
            PcbDecouplingCapacitor(
                reference="C1", footprint=CAP, supply_pad="C1.1", return_pad="C1.2"
            ),
            PcbDecouplingCapacitor(
                reference="C2", footprint=CAP, supply_pad="C2.1", return_pad="C2.2"
            ),
        )
        evidence = snapshot(distances_nm={"C1": 100_000, "C2": 100_001})
        any_entry = pcb_decoupling_entries(
            mapping(requirement(capacitors=caps, maximum_um=100, selection="any")), evidence
        )[0]
        all_entry = pcb_decoupling_entries(
            mapping(requirement(capacitors=caps, maximum_um=100, selection="all")), evidence
        )[0]

        self.assertEqual(any_entry.status, "COMPLETE")
        self.assertEqual(any_entry.selected_capacitors, ("C1",))
        self.assertEqual(all_entry.status, "INCOMPLETE")

    def test_wrong_net_disconnected_wrong_footprint_and_dnp_candidates_do_not_satisfy_requirement(
        self,
    ) -> None:
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
            distances_nm={"C1": 50_000, "C2": 60_000, "C3": 70_000, "C4": 80_000},
            wrong_supply_nets=frozenset({"C1.1"}),
            disconnected_supply=frozenset({"C2.1"}),
            dnp_caps=frozenset({"C3"}),
            footprints={"C4": "Synthetic:WrongCap"},
        )

        entry = pcb_decoupling_entries(mapping(requirement(capacitors=caps)), evidence)[0]

        self.assertEqual(entry.status, "INCOMPLETE")
        self.assertEqual(entry.selected_capacitors, ())
        self.assertTrue(all(not candidate.eligible for candidate in entry.candidates))
        self.assertIn("expected 'VDD'", " ".join(entry.candidates[0].issues))
        self.assertIn("not connected", " ".join(entry.candidates[1].issues))
        self.assertIn("do-not-populate", " ".join(entry.candidates[2].issues))
        self.assertIn("expected 'Synthetic:Cap_0603'", " ".join(entry.candidates[3].issues))

    def test_no_threshold_emits_reviewable_measurement_and_honors_override_and_ignore(self) -> None:
        mapped = mapping(requirement(maximum_um=None))
        evidence = snapshot(distances_nm={"C1": 42_500})
        measured = coverage_report(mapped, evidence)
        native = ContractCoachReport(
            status="READY_FOR_REVIEW",
            project_id="synthetic-decoupling",
            observed=NetlistContract(components={}, nets={}),
            netlist_sha256="f" * 64,
        )
        policy = DesignLintPolicy(pcb_decoupling_map=mapped)

        reviewed = evaluate(
            "synthetic-decoupling",
            native,
            policy,
            pcb_decoupling_coverage=measured,
        )
        finding = next(item for item in reviewed.findings if item.rule_id == RULE)
        blocking = evaluate(
            "synthetic-decoupling",
            native,
            policy.model_copy(
                update={
                    "rules": (
                        DesignLintRuleOverride(
                            rule_id=RULE,
                            mode="block",
                            reason="Synthetic policy override test",
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
                                        native.observed,
                                        pcb_decoupling_coverage=measured,
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

        self.assertEqual(reviewed.status, "REVIEW")
        self.assertIn("42.500 um", finding.evidence["candidate_distances"][0])
        self.assertEqual(blocking.status, "FAIL")
        self.assertEqual(ignored.status, "PASS")

    def test_invalid_pin_mapping_and_unknown_fields_are_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            PcbDecouplingCapacitor(
                reference="C1", footprint=CAP, supply_pad="C2.1", return_pad="C1.2"
            )
        with self.assertRaises(ValidationError):
            PcbDecouplingMap.model_validate(
                {"basis": "synthetic", "requirements": [], "max_distance_um": 100}
            )


if __name__ == "__main__":
    unittest.main()
