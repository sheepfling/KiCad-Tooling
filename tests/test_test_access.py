"""Synthetic test-access requirements and deterministic schematic faults."""

from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Literal

from kicad_tooling.hwrepo.electrical import pending_sections
from kicad_tooling.hwrepo.models import (
    AnalysisNotApplicable,
    AnalysisPending,
    ElectricalAnalysisContract,
    ExcludedTestAccess,
    PcbAccessAnalysis,
    PcbAccessProbeObservation,
    PcbConnectivitySnapshot,
    PcbPadConnectivityObservation,
    RequiredTestAccess,
)
from kicad_tooling.hwrepo.models import (
    TestAccessAnalysis as AccessAnalysis,
)
from kicad_tooling.hwrepo.models import (
    TestAccessEndpointRequirement as AccessEndpointRequirement,
)
from kicad_tooling.hwrepo.models import (
    TestAccessProbeEnvelope as AccessProbeEnvelope,
)
from kicad_tooling.hwrepo.test_access import (
    evaluate_test_access_checks,
    pcb_access_probe_request_set,
    pcb_accessibility_checks,
    pcb_probe_envelope_checks,
)
from tests.test_control_inputs import control_netlist


def access_requirement(
    *,
    selection: str = "all",
    approach_side: Literal["front", "back", "either"] = "either",
) -> AccessAnalysis:
    return AccessAnalysis(
        basis="Synthetic connector pinout and factory reset access requirement",
        pcb_accessibility=AnalysisNotApplicable(
            mode="not_applicable",
            reason="Synthetic unit fixture tests the schematic stage only.",
        ),
        decisions=(
            RequiredTestAccess(
                mode="required",
                id="reset-access",
                basis="Synthetic service procedure requires reset access",
                net="RESET_N",
                selection=selection,
                endpoints=(
                    AccessEndpointRequirement(
                        kind="programming_connector",
                        reference="J1",
                        symbol="Synthetic:DB9",
                        footprint="Connector:Dsub-9_Male",
                        pin="J1.9",
                        electrical_type="passive",
                        approach_side=approach_side,
                    ),
                ),
            ),
            ExcludedTestAccess(
                mode="not_required",
                id="high-voltage-output",
                basis="Synthetic isolation and measurement review",
                net="HV_OUT",
                reason="The node is hazardous and is intentionally excluded from routine test access.",
            ),
        ),
    )


def probe_access_snapshot(
    front_nm: int | None,
    back_nm: int | None,
    *,
    back_exposed: bool = True,
    include_back: bool = True,
    aperture_shape: Literal["circle", "unsupported"] = "circle",
    aperture_diameter_nm: int | None = 1_000_000,
) -> PcbConnectivitySnapshot:
    pads = (
        PcbPadConnectivityObservation(
            pad="J1.9",
            net="RESET_N",
            footprint="Connector:Dsub-9_Male",
            dnp=False,
            connected_pads=("J1.9",),
            connected_zones=(),
            connected_islands=(),
            connected_vias=(),
        ),
        PcbPadConnectivityObservation(
            pad="J2.9",
            net="GND",
            footprint="Connector:Dsub-9_Male",
            dnp=False,
            connected_pads=("J2.9",),
            connected_zones=(),
            connected_islands=(),
            connected_vias=(),
        ),
    )
    return PcbConnectivitySnapshot(
        board_sha256="a" * 64,
        kicad_version="10.0.5",
        image="registry.example/kicad:10.0.5@sha256:" + "b" * 64,
        probe_sha256="c" * 64,
        zones_refilled=True,
        pads=pads,
        net_ties=(),
        zones=(),
        vias=(),
        access_probe_observations=(
            PcbAccessProbeObservation(
                endpoint="J1.9",
                side="front",
                target_net="RESET_N",
                target_exposed=True,
                obstacle="J2.9" if front_nm is not None else None,
                obstacle_net="GND" if front_nm is not None else None,
                distance_nm=front_nm,
                target_aperture_shape=aperture_shape,
                target_aperture_diameter_nm=aperture_diameter_nm,
            ),
            *(
                (
                    PcbAccessProbeObservation(
                        endpoint="J1.9",
                        side="back",
                        target_net="RESET_N",
                        target_exposed=back_exposed,
                        obstacle="J2.9" if back_exposed and back_nm is not None else None,
                        obstacle_net="GND" if back_exposed and back_nm is not None else None,
                        distance_nm=back_nm if back_exposed else None,
                        target_aperture_shape=aperture_shape if back_exposed else None,
                        target_aperture_diameter_nm=aperture_diameter_nm if back_exposed else None,
                    ),
                )
                if include_back
                else ()
            ),
        ),
    )


def probe_access_requirement(
    *, approach_side: Literal["front", "back", "either"]
) -> AccessAnalysis:
    requirement = access_requirement(approach_side=approach_side)
    decision = requirement.decisions[0]
    assert isinstance(decision, RequiredTestAccess)
    endpoint = decision.endpoints[0].model_copy(
        update={
            "probe_envelope": AccessProbeEnvelope(
                tip_diameter_mm=0.8,
                clearance_mm=0.1,
            )
        }
    )
    decision = decision.model_copy(update={"endpoints": (endpoint,)})
    return requirement.model_copy(
        update={
            "pcb_accessibility": PcbAccessAnalysis(basis="Synthetic surface probe envelope"),
            "decisions": (decision, *requirement.decisions[1:]),
        }
    )


class TestAccessChecksTests(unittest.TestCase):
    def rows(self, *, selection: str = "all", fault: str | None = None):
        return {
            row.id: row
            for row in evaluate_test_access_checks(
                access_requirement(selection=selection), control_netlist(fault=fault)
            )
        }

    def test_required_programming_pin_passes_and_exclusion_is_explicit(self) -> None:
        rows = self.rows()
        self.assertEqual(rows["test-access/schematic/reset-access"].status, "PASS")
        self.assertIn("RESET_N", rows["test-access/schematic/reset-access"].detail)
        self.assertEqual(
            rows["test-access/schematic/high-voltage-output"].status,
            "NOT_APPLICABLE",
        )
        self.assertIn(
            "intentionally excluded", rows["test-access/schematic/high-voltage-output"].detail
        )

    def test_excluded_net_must_remain_present_or_be_re_reviewed(self) -> None:
        row = self.rows(fault="missing-excluded-net")["test-access/schematic/high-voltage-output"]
        self.assertEqual(row.status, "FAIL")
        self.assertIn("exclusion is stale", row.detail)

    def test_component_netlist_faults_fail_the_declared_endpoint(self) -> None:
        cases = (
            ("missing-component", "J1 is absent"),
            ("wrong-footprint", "footprint is"),
            ("endpoint-dnp", "J1 is marked DNP"),
        )
        for fault, expected in cases:
            with self.subTest(fault=fault):
                row = self.rows(fault=fault)["test-access/schematic/reset-access"]
                self.assertEqual(row.status, "FAIL")
                self.assertIn(expected, row.detail)

    def test_endpoint_must_match_symbol_pin_net_and_electrical_type(self) -> None:
        observed = control_netlist()
        variants = (
            observed.model_copy(
                update={
                    "component_symbols": {**observed.component_symbols, "J1": "Synthetic:Other"}
                }
            ),
            observed.model_copy(
                update={
                    "nets": {
                        **observed.nets,
                        "OTHER": ("J1.9",),
                        "RESET_N": tuple(pin for pin in observed.nets["RESET_N"] if pin != "J1.9"),
                    }
                }
            ),
            observed.model_copy(
                update={"pin_electrical_types": {**observed.pin_electrical_types, "J1.9": "input"}}
            ),
            observed.model_copy(
                update={"component_pin_numbers": {**observed.component_pin_numbers, "J1": ("1",)}}
            ),
        )
        for observed_variant in variants:
            with self.subTest(observed=observed_variant):
                row = evaluate_test_access_checks(access_requirement(), observed_variant)[0]
                self.assertEqual(row.status, "FAIL")

    def test_any_selection_accepts_one_matching_endpoint(self) -> None:
        spec = access_requirement(selection="any")
        decision = spec.decisions[0]
        assert isinstance(decision, RequiredTestAccess)
        alternate = decision.model_copy(
            update={
                "endpoints": (
                    decision.endpoints[0].model_copy(update={"reference": "J2", "pin": "J2.9"}),
                    decision.endpoints[0],
                )
            }
        )
        spec = spec.model_copy(update={"decisions": (alternate, *spec.decisions[1:])})
        row = evaluate_test_access_checks(spec, control_netlist())[0]
        self.assertEqual(row.status, "PASS")
        self.assertIn("J1.9", row.detail)

    def test_contract_rejects_duplicate_net_decisions_and_misowned_pins(self) -> None:
        raw = access_requirement().model_dump()
        raw["decisions"] = (
            *raw["decisions"],
            raw["decisions"][0] | {"id": "duplicate-reset"},
        )
        with self.assertRaisesRegex(ValueError, "one explicit decision"):
            AccessAnalysis.model_validate(raw)
        with self.assertRaisesRegex(ValueError, "must belong"):
            AccessEndpointRequirement.model_validate(
                {
                    "kind": "test_point",
                    "reference": "TP1",
                    "symbol": "TestPoint:TestPoint",
                    "footprint": "TestPoint:TestPoint_Pad_D1.0mm",
                    "pin": "J1.1",
                    "electrical_type": "passive",
                }
            )
        decision = access_requirement().decisions[0]
        assert isinstance(decision, RequiredTestAccess)
        endpoint = decision.endpoints[0]
        with self.assertRaisesRegex(ValueError, "approach_side"):
            AccessEndpointRequirement.model_validate(
                endpoint.model_dump() | {"approach_side": "top"}
            )

    def test_probe_envelope_requires_pcb_stage_and_finite_positive_dimensions(self) -> None:
        with self.assertRaisesRegex(ValueError, "require the PCB accessibility stage"):
            AccessAnalysis.model_validate(
                access_requirement().model_dump()
                | {
                    "decisions": (
                        access_requirement()
                        .decisions[0]
                        .model_copy(
                            update={
                                "endpoints": (
                                    access_requirement()
                                    .decisions[0]
                                    .endpoints[0]
                                    .model_copy(
                                        update={
                                            "probe_envelope": AccessProbeEnvelope(
                                                tip_diameter_mm=0.8,
                                                clearance_mm=0.1,
                                            )
                                        }
                                    ),
                                )
                            }
                        )
                        .model_dump(),
                        *access_requirement().model_dump()["decisions"][1:],
                    )
                }
            )
        with self.assertRaises(ValueError):
            AccessProbeEnvelope(tip_diameter_mm=float("inf"), clearance_mm=0.1)
        with self.assertRaises(ValueError):
            AccessProbeEnvelope(tip_diameter_mm=0.8, clearance_mm=-0.01)

    def test_probe_request_sides_and_clearance_boundary_are_deterministic(self) -> None:
        requirement = access_requirement(approach_side="either")
        decision = requirement.decisions[0]
        assert isinstance(decision, RequiredTestAccess)
        endpoint = decision.endpoints[0].model_copy(
            update={
                "probe_envelope": AccessProbeEnvelope(
                    tip_diameter_mm=0.8,
                    clearance_mm=0.1,
                )
            }
        )
        decision = decision.model_copy(update={"endpoints": (endpoint,)})
        requirement = requirement.model_copy(
            update={
                "pcb_accessibility": PcbAccessAnalysis(basis="Synthetic surface probe envelope"),
                "decisions": (decision, *requirement.decisions[1:]),
            }
        )
        requests = pcb_access_probe_request_set(requirement)
        self.assertIsNotNone(requests)
        assert requests is not None
        self.assertEqual(
            [(item.endpoint, item.side, item.net) for item in requests.requests],
            [("J1.9", "back", "RESET_N"), ("J1.9", "front", "RESET_N")],
        )

        exact_boundary = {
            row.id: row
            for row in pcb_probe_envelope_checks(
                requirement, probe_access_snapshot(499_999, 500_000)
            )
        }["test-access/pcb-probe-envelope/reset-access"]
        self.assertEqual(exact_boundary.status, "PASS")
        self.assertIn("front", exact_boundary.detail)
        self.assertIn("back", exact_boundary.detail)

        both_too_close = {
            row.id: row
            for row in pcb_probe_envelope_checks(
                requirement, probe_access_snapshot(499_999, 499_999)
            )
        }["test-access/pcb-probe-envelope/reset-access"]
        self.assertEqual(both_too_close.status, "FAIL")
        self.assertIn("0.499999 mm", both_too_close.detail)

        exposed_front_only = {
            row.id: row
            for row in pcb_probe_envelope_checks(
                requirement,
                probe_access_snapshot(None, None, back_exposed=False),
            )
        }["test-access/pcb-probe-envelope/reset-access"]
        self.assertEqual(exposed_front_only.status, "PASS")
        self.assertIn("back: target pad has no exposed", exposed_front_only.detail)

    def test_probe_tip_must_fit_circular_target_aperture_at_exact_boundary(self) -> None:
        exact = {
            row.id: row
            for row in pcb_probe_envelope_checks(
                probe_access_requirement(approach_side="front"),
                probe_access_snapshot(
                    500_000,
                    500_000,
                    include_back=False,
                    aperture_diameter_nm=1_000_000,
                ),
            )
        }["test-access/pcb-probe-envelope/reset-access"]
        self.assertEqual(exact.status, "PASS")
        self.assertIn("required tip-plus-clearance diameter is 1 mm", exact.detail)

        undersize = {
            row.id: row
            for row in pcb_probe_envelope_checks(
                probe_access_requirement(approach_side="front"),
                probe_access_snapshot(
                    500_000,
                    500_000,
                    include_back=False,
                    aperture_diameter_nm=999_999,
                ),
            )
        }["test-access/pcb-probe-envelope/reset-access"]
        self.assertEqual(undersize.status, "FAIL")
        self.assertIn("circular target mask aperture is 0.999999 mm", undersize.detail)

    def test_non_circular_target_aperture_is_not_approximated(self) -> None:
        row = {
            item.id: item
            for item in pcb_probe_envelope_checks(
                probe_access_requirement(approach_side="front"),
                probe_access_snapshot(
                    500_000,
                    500_000,
                    include_back=False,
                    aperture_shape="unsupported",
                    aperture_diameter_nm=None,
                ),
            )
        }["test-access/pcb-probe-envelope/reset-access"]
        self.assertEqual(row.status, "FAIL")
        self.assertIn("shape is unsupported", row.detail)

    def test_probe_observation_rejects_partial_obstacle_measurement(self) -> None:
        with self.assertRaisesRegex(ValueError, "needs its measured distance"):
            PcbAccessProbeObservation(
                endpoint="J1.9",
                side="front",
                target_net="RESET_N",
                target_exposed=True,
                obstacle="J2.9",
                obstacle_net="GND",
                distance_nm=None,
            )

    def test_pending_pcb_stage_remains_a_policy_coverage_gap(self) -> None:
        access = AccessAnalysis(
            basis="Synthetic required test-access scope",
            pcb_accessibility=AnalysisPending(reason="Review PCB pad access"),
            decisions=(
                ExcludedTestAccess(
                    mode="not_required",
                    id="hazardous-output",
                    basis="Synthetic safety review",
                    net="HV_OUT",
                    reason="No routine probe access is approved.",
                ),
            ),
        )
        not_applicable = AnalysisNotApplicable(
            mode="not_applicable", reason="Synthetic fixture scope"
        )
        contract = ElectricalAnalysisContract(
            project_id="synthetic",
            ngspice_version="UNREVIEWED",
            grounding=not_applicable,
            power=not_applicable,
            high_frequency=not_applicable,
            test_access=access,
        )
        self.assertIn("test_access.pcb_accessibility", pending_sections(contract))

    def test_pcb_stage_checks_placed_pad_net_and_surface_layers(self) -> None:
        requirement = access_requirement(approach_side="front")
        pcb_requirement = requirement.model_copy(
            update={
                "pcb_accessibility": PcbAccessAnalysis(
                    basis="Synthetic PCB programming pad evidence"
                )
            }
        )
        with TemporaryDirectory(prefix="synthetic-test-access-") as temporary:
            board_path = Path(temporary) / "board.kicad_pcb"
            board_path.write_text(
                '(kicad_pcb (version 20250114) (net 0 "") (net 1 "RESET_N") '
                '(footprint "Connector:Dsub-9_Male" (layer "F.Cu") '
                '(property "Reference" "J1") '
                '(pad "9" thru_hole circle (at 0 0) (size 2 2) '
                '(layers "*.Cu" "*.Mask") (net 1 "RESET_N"))) '
                '(footprint "Package_SO:SOIC-8" (layer "F.Cu") '
                '(property "Reference" "U5") '
                '(pad "1" smd rect (at 0 0) (size 1 1) '
                '(layers "F.Cu" "F.Mask") (net 0 ""))))',
                encoding="utf-8",
            )
            rows = {
                row.id: row
                for row in pcb_accessibility_checks(
                    pcb_requirement, pcb_requirement.pcb_accessibility, board_path
                )
            }
        self.assertEqual(rows["test-access/pcb-accessibility/reset-access"].status, "PASS")
        self.assertIn(
            "solder-mask layer declaration",
            rows["test-access/pcb-accessibility/reset-access"].detail,
        )
        self.assertIn(
            "J1.9 (front, back)", rows["test-access/pcb-accessibility/reset-access"].detail
        )
        self.assertIn("probe clearance", rows["test-access/pcb-accessibility/reset-access"].detail)
        self.assertEqual(
            rows["test-access/pcb-accessibility/high-voltage-output"].status,
            "NOT_APPLICABLE",
        )

    def test_pcb_stage_enforces_project_authored_approach_side(self) -> None:
        cases = (
            ("front", '"F.Cu" "F.Mask"', "PASS"),
            ("back", '"F.Cu" "F.Mask"', "FAIL"),
            ("back", '"B.Cu" "B.Mask"', "PASS"),
            ("either", '"F.Cu" "F.Mask"', "PASS"),
        )
        with TemporaryDirectory(prefix="synthetic-test-access-side-") as temporary:
            board_path = Path(temporary) / "board.kicad_pcb"
            for approach_side, layers, expected_status in cases:
                with self.subTest(approach_side=approach_side, layers=layers):
                    requirement = access_requirement(approach_side=approach_side).model_copy(
                        update={
                            "pcb_accessibility": PcbAccessAnalysis(
                                basis="Synthetic required probe approach side"
                            )
                        }
                    )
                    board_path.write_text(
                        '(kicad_pcb (version 20250114) (net 0 "") (net 1 "RESET_N") '
                        '(footprint "Connector:Dsub-9_Male" (layer "F.Cu") '
                        '(property "Reference" "J1") '
                        f'(pad "9" thru_hole circle (at 0 0) (size 2 2) (layers {layers}) '
                        '(net 1 "RESET_N"))))',
                        encoding="utf-8",
                    )
                    row = next(
                        item
                        for item in pcb_accessibility_checks(
                            requirement,
                            requirement.pcb_accessibility,
                            board_path,
                        )
                        if item.id == "test-access/pcb-accessibility/reset-access"
                    )
                    self.assertEqual(row.status, expected_status)
                    if approach_side == "back" and "F.Cu" in layers:
                        self.assertIn("expected a back-side approach", row.detail)

    def test_pcb_stage_rejects_missing_wrong_net_and_mask_covered_access(self) -> None:
        requirement = access_requirement().model_copy(
            update={
                "pcb_accessibility": PcbAccessAnalysis(
                    basis="Synthetic PCB programming pad evidence"
                )
            }
        )
        valid_board = (
            '(kicad_pcb (version 20250114) (net 0 "") (net 1 "RESET_N") '
            '(footprint "Connector:Dsub-9_Male" (layer "F.Cu") '
            '(property "Reference" "J1") '
            '(pad "9" thru_hole circle (at 0 0) (size 2 2) '
            '(layers "*.Cu" "*.Mask") (net 1 "RESET_N"))))'
        )
        cases = (
            (
                valid_board.replace('(property "Reference" "J1")', '(property "Reference" "J2")'),
                "no placed footprint",
            ),
            (
                valid_board.replace('(net 1 "RESET_N")', '(net 1 "OTHER")', 1).replace(
                    '(net 1 "RESET_N")', '(net 1 "OTHER")', 1
                ),
                "PCB pad is on",
            ),
            (
                valid_board.replace('"*.Cu" "*.Mask"', '"*.Cu"'),
                "no outer copper and solder-mask layer declaration",
            ),
            (
                valid_board.replace(
                    '(property "Reference" "J1")',
                    '(property "Reference" "J1") (property "DNP" "yes")',
                ),
                "marked DNP",
            ),
        )
        with TemporaryDirectory(prefix="synthetic-test-access-") as temporary:
            board_path = Path(temporary) / "board.kicad_pcb"
            for source, expected in cases:
                with self.subTest(expected=expected):
                    board_path.write_text(source, encoding="utf-8")
                    row = next(
                        item
                        for item in pcb_accessibility_checks(
                            requirement, requirement.pcb_accessibility, board_path
                        )
                        if item.id == "test-access/pcb-accessibility/reset-access"
                    )
                    self.assertEqual(row.status, "FAIL")
                    self.assertIn(expected, row.detail)


if __name__ == "__main__":
    unittest.main()
