"""Synthetic external-interface protection-map and review-coverage fixtures."""

from __future__ import annotations

import hashlib
import unittest
from typing import Literal

from pydantic import ValidationError

from kicad_tooling.hwrepo.design_lint import _mapped_usb_c_protection_pins, candidates
from kicad_tooling.hwrepo.design_lint import evaluate as evaluate_design_lint
from kicad_tooling.hwrepo.external_protection import evaluate
from kicad_tooling.hwrepo.models import (
    AnalysisNotApplicable,
    ComponentContract,
    ConnectorCoverageEntry,
    ConnectorCoverageReport,
    ConnectorMappedPinEvidence,
    ContractCoachReport,
    DesignLintPolicy,
    DesignLintReport,
    DesignLintRuleOverride,
    ExternalProtectionChannelRequirement,
    ExternalProtectionDeviceRequirement,
    ExternalProtectionInterfaceRequirement,
    ExternalProtectionMap,
    NetlistContract,
    UsbCAnalysis,
    UsbCcLineRequirement,
    UsbCcResistorAttachment,
    UsbCNetPinAssignment,
    UsbCPortRequirement,
    UsbCProtectionAnalysis,
    UsbCProtectionComponentRequirement,
)


def usb_c_protection_requirement() -> UsbCAnalysis:
    """Build the minimal typed USB-C map needed by protection-coverage tests."""
    protection = UsbCProtectionAnalysis(
        basis="Synthetic reviewed CC protector pin map",
        components=(
            UsbCProtectionComponentRequirement(
                reference="D1",
                symbol="Synthetic:UsbProtection",
                footprint="Package_DFN:DFN-6",
                pins=(
                    UsbCNetPinAssignment(pin="D1.1", net="CC1"),
                    UsbCNetPinAssignment(pin="D1.2", net="GND"),
                ),
            ),
        ),
    )
    return UsbCAnalysis(
        basis="Synthetic USB-C source port for protection-coverage test",
        ports=(
            UsbCPortRequirement(
                id="host-port",
                basis="Reviewed synthetic USB-C receptacle pinout",
                connector="J1",
                role="source",
                cc1=UsbCcLineRequirement(
                    connector_pin="J1.4",
                    net="CC1",
                    attachment=UsbCcResistorAttachment(
                        kind="resistor",
                        behavior="rp",
                        reference="R1",
                        rail_net="+5V",
                        minimum_ohms=50_000,
                        maximum_ohms=60_000,
                    ),
                ),
                cc2=UsbCcLineRequirement(
                    connector_pin="J1.5",
                    net="CC2",
                    attachment=UsbCcResistorAttachment(
                        kind="resistor",
                        behavior="rp",
                        reference="R2",
                        rail_net="+5V",
                        minimum_ohms=50_000,
                        maximum_ohms=60_000,
                    ),
                ),
                vbus_net="VBUS_PORT",
                vbus_pins=(
                    UsbCNetPinAssignment(pin="J1.1", net="VBUS_PORT"),
                    UsbCNetPinAssignment(pin="U1.1", net="VBUS_SYSTEM"),
                ),
                ground_net="GND",
                ground_pins=("J1.2", "U1.5"),
                vbus_capacitance=AnalysisNotApplicable(
                    mode="not_applicable",
                    reason="Synthetic protection test does not assess port-side capacitance.",
                ),
                source_rail="+5V",
                protection=protection,
            ),
        ),
    )


def protection_map(
    *,
    disposition: Literal["required", "not_required"] = "required",
    unmapped_pin_reasons: dict[str, str] | None = None,
) -> ExternalProtectionMap:
    channels = (
        (
            ExternalProtectionChannelRequirement(
                device_reference="D1",
                signal_pin="D1.1",
                reference_pin="D1.2",
                reference_net="GND",
            ),
        )
        if disposition == "required"
        else ()
    )
    devices = (
        (
            ExternalProtectionDeviceRequirement(
                reference="D1",
                expected_symbol="Synthetic:TVS",
                expected_footprint="Synthetic:SOD323",
                pin_nets={"D1.1": "USB_DP", "D1.2": "GND"},
                unmapped_pin_reasons=unmapped_pin_reasons or {},
            ),
        )
        if disposition == "required"
        else ()
    )
    return ExternalProtectionMap(
        basis="Synthetic reviewed USB interface and protector pinout",
        interfaces=(
            ExternalProtectionInterfaceRequirement(
                connector_reference="J1",
                expected_connector_symbol="Synthetic:UsbPort",
                expected_connector_footprint="Synthetic:USB-C",
                connector_pin="J1.1",
                signal_net="USB_DP",
                disposition=disposition,
                basis=(
                    "Synthetic datasheet-mapped TVS channel"
                    if disposition == "required"
                    else "Synthetic reviewed interface has integrated protection"
                ),
                channels=channels,
            ),
        ),
        devices=devices,
    )


def observed_netlist(
    *,
    fault: str | None = None,
    extra_device_pin: bool = False,
    dnp: tuple[str, ...] = (),
) -> NetlistContract:
    connector_nets = {"USB_DP": ("J1.1", "D1.1"), "USB_DM": ("J1.2",), "GND": ("D1.2",)}
    if fault == "protector-wrong-net":
        connector_nets = {"USB_DP": ("J1.1",), "USB_DM": ("J1.2", "D1.1"), "GND": ("D1.2",)}
    elif fault == "connector-wrong-net":
        connector_nets = {"USB_DP": ("D1.1",), "USB_DM": ("J1.1", "J1.2"), "GND": ("D1.2",)}
    component_pin_numbers = {
        "J1": ("1", "2"),
        "D1": ("1", "2", *(("3",) if extra_device_pin else ())),
    }
    return NetlistContract(
        components={
            "J1": ComponentContract(value="Synthetic USB connector", footprint="Synthetic:USB-C"),
            "D1": ComponentContract(value="Synthetic TVS", footprint="Synthetic:SOD323"),
        },
        nets=connector_nets,
        dnp_components=dnp,
        component_symbols={"J1": "Synthetic:UsbPort", "D1": "Synthetic:TVS"},
        pin_functions={"J1.1": "D+", "J1.2": "D-", "D1.1": "IO", "D1.2": "GND"},
        component_pin_numbers=component_pin_numbers,
    )


def connector_coverage() -> ConnectorCoverageReport:
    return ConnectorCoverageReport(
        status="COMPLETE",
        scope="Synthetic reviewed interface pin map",
        inventory_review_basis="Synthetic review covered the complete connector inventory",
        entries=(
            ConnectorCoverageEntry(
                reference="J1",
                status="COVERED",
                interface_id="usb-data",
                basis="Synthetic connector datasheet pinout",
                mapped_pins=(
                    ConnectorMappedPinEvidence(
                        interface_pin_number="1",
                        interface_signal="USB_D+",
                        component_pin="J1.1",
                        symbol_function="D+",
                        nets=("USB_DP",),
                    ),
                ),
            ),
        ),
    )


def protection_lint_report(
    requirements: ExternalProtectionMap | None,
    observed: NetlistContract,
) -> tuple[str, DesignLintReport]:
    """Bind the synthetic native-netlist model and project protection map to lint evidence."""
    netlist_sha256 = hashlib.sha256(observed.model_dump_json().encode("utf-8")).hexdigest()
    coverage = evaluate(requirements, observed, connector_coverage(), netlist_sha256)
    coach = ContractCoachReport(
        status="READY_FOR_REVIEW",
        project_id="synthetic-external-protection",
        netlist_sha256=netlist_sha256,
        observed=observed,
    )
    report = evaluate_design_lint(
        coach.project_id,
        coach,
        DesignLintPolicy(),
        external_protection_coverage=coverage,
    )
    return netlist_sha256, report


class ExternalProtectionTests(unittest.TestCase):
    def test_exact_tvs_channel_matches_native_component_pin_and_net_inventory(self) -> None:
        report = evaluate(protection_map(), observed_netlist(), connector_coverage(), "a" * 64)
        self.assertEqual(report.status, "COMPLETE")
        self.assertEqual(report.netlist_sha256, "a" * 64)
        self.assertEqual(report.entries[0].status, "PROTECTED")
        self.assertEqual(report.entries[0].device_references, ("D1",))

    def test_explicit_not_required_decision_remains_covered(self) -> None:
        report = evaluate(
            protection_map(disposition="not_required"),
            observed_netlist(),
            connector_coverage(),
            "b" * 64,
        )
        self.assertEqual(report.status, "COMPLETE")
        self.assertEqual(report.entries[0].status, "NOT_REQUIRED")
        self.assertIn("integrated protection", report.entries[0].basis or "")

    def test_wrong_connector_or_protector_net_is_a_project_requirement_mismatch(self) -> None:
        for fault in ("connector-wrong-net", "protector-wrong-net"):
            with self.subTest(fault=fault):
                report = evaluate(
                    protection_map(),
                    observed_netlist(fault=fault),
                    connector_coverage(),
                    "c" * 64,
                )
                self.assertEqual(report.status, "INCOMPLETE")
                self.assertEqual(report.entries[0].status, "INCOMPLETE")

    def test_wrong_identity_dnp_and_unaccounted_device_pin_fail(self) -> None:
        wrong_identity = protection_map().model_copy(
            update={
                "devices": (
                    protection_map()
                    .devices[0]
                    .model_copy(update={"expected_symbol": "Synthetic:WrongProtector"}),
                )
            }
        )
        for requirements, observed in (
            (wrong_identity, observed_netlist()),
            (protection_map(), observed_netlist(dnp=("D1",))),
            (protection_map(), observed_netlist(extra_device_pin=True)),
        ):
            report = evaluate(requirements, observed, connector_coverage(), "d" * 64)
            self.assertEqual(report.status, "INCOMPLETE")
            self.assertTrue(report.entries[0].issues)

    def test_explicit_unmapped_pin_reason_and_usb_c_contract_suppress_duplicate_prompt(
        self,
    ) -> None:
        mapped = protection_map(unmapped_pin_reasons={"D1.3": "Synthetic NC package pin"})
        observed = observed_netlist(extra_device_pin=True)
        accepted = evaluate(mapped, observed, connector_coverage(), "e" * 64)
        self.assertEqual(accepted.entries[0].status, "PROTECTED")
        usb_c_owned = evaluate(
            None,
            observed,
            connector_coverage(),
            "e" * 64,
            handled_by_existing_contract={"J1.1": "USB_DP"},
            electrical_contract_path="examples/project/tests/electrical.json",
            electrical_contract_sha256="f" * 64,
        )
        self.assertEqual(usb_c_owned.entries[0].status, "HANDLED_BY_EXISTING_CONTRACT")
        duplicate = evaluate(
            protection_map(),
            observed_netlist(),
            connector_coverage(),
            "e" * 64,
            handled_by_existing_contract={"J1.1": "USB_DP"},
        )
        self.assertEqual(duplicate.entries[0].status, "INCOMPLETE")
        self.assertIn("already covered", duplicate.entries[0].issues[0])

    def test_usb_c_protection_map_covers_only_matching_signal_pins(self) -> None:
        requirement = usb_c_protection_requirement()
        port = requirement.ports[0]
        assert isinstance(port.protection, UsbCProtectionAnalysis)
        component = port.protection.components[0].model_copy(
            update={
                "pins": (
                    UsbCNetPinAssignment(pin="D1.1", net="USB_DP"),
                    UsbCNetPinAssignment(pin="D1.2", net="GND"),
                )
            }
        )
        protection = port.protection.model_copy(update={"components": (component,)})
        analysis = requirement.model_copy(
            update={"ports": (port.model_copy(update={"protection": protection}),)}
        )
        coverage = ConnectorCoverageReport(
            status="COMPLETE",
            scope="Synthetic USB-C interface map",
            inventory_review_basis="Synthetic review covered the complete connector inventory",
            entries=(
                ConnectorCoverageEntry(
                    reference="J1",
                    status="COVERED",
                    mapped_pins=(
                        ConnectorMappedPinEvidence(
                            interface_pin_number="6",
                            interface_signal="USB_D+",
                            component_pin="J1.6",
                            nets=("USB_DP",),
                        ),
                        ConnectorMappedPinEvidence(
                            interface_pin_number="2",
                            interface_signal="GND",
                            component_pin="J1.2",
                            nets=("GND",),
                        ),
                    ),
                ),
            ),
        )
        handled = _mapped_usb_c_protection_pins(analysis, coverage)
        self.assertEqual(handled, {"J1.6": "USB_DP"})

        observed = observed_netlist().model_copy(
            update={
                "nets": {
                    **observed_netlist().nets,
                    "USB_DP": ("J1.6", "D1.1"),
                },
                "component_pin_numbers": {
                    **observed_netlist().component_pin_numbers,
                    "J1": ("1", "2", "6"),
                },
            }
        )
        report = evaluate(
            None,
            observed,
            coverage,
            "a" * 64,
            handled_by_existing_contract=handled,
        )
        data_line = next(item for item in report.entries if item.connector_pin == "J1.6")
        ground = next(item for item in report.entries if item.connector_pin == "J1.2")
        self.assertEqual(data_line.status, "HANDLED_BY_EXISTING_CONTRACT")
        self.assertEqual(ground.status, "UNDECLARED")

    def test_missing_applicability_is_a_review_candidate_and_policy_can_block_it(self) -> None:
        observed = observed_netlist()
        coverage = evaluate(None, observed, connector_coverage(), "f" * 64)
        self.assertEqual(coverage.status, "UNDECLARED")
        self.assertEqual(coverage.entries[0].connector_pin, "J1.1")
        candidates_found = candidates(
            observed,
            external_protection_coverage=coverage,
        )
        protection_findings = [
            item
            for item in candidates_found
            if item.rule_id == "protection.unreviewed_interface_pin"
        ]
        self.assertEqual(len(protection_findings), 1)
        self.assertIn("does not assume protection is needed", protection_findings[0].message)

        coach = ContractCoachReport(
            status="READY_FOR_REVIEW",
            project_id="synthetic",
            netlist_sha256="f" * 64,
            observed=observed,
        )
        review = evaluate_design_lint(
            "synthetic",
            coach,
            DesignLintPolicy(),
            external_protection_coverage=coverage,
        )
        self.assertEqual(review.status, "REVIEW")
        blocked = evaluate_design_lint(
            "synthetic",
            coach,
            DesignLintPolicy(
                rules=(
                    DesignLintRuleOverride(
                        rule_id="protection.unreviewed_interface_pin",
                        mode="block",
                        reason="Synthetic project requires an applicability decision",
                    ),
                )
            ),
            external_protection_coverage=coverage,
        )
        self.assertEqual(blocked.status, "FAIL")

    def test_unreviewed_protection_prompt_is_order_stable_and_authored_decision_clears_it(
        self,
    ) -> None:
        source = observed_netlist()
        source_sha256, original = protection_lint_report(None, source)
        rule_id = "protection.unreviewed_interface_pin"
        original_findings = {
            item.subject: (item.fingerprint, item.evidence)
            for item in original.findings
            if item.rule_id == rule_id
        }
        self.assertEqual(len(original_findings), 1)

        reordered_source = source.model_copy(
            update={
                "components": dict(reversed(tuple(source.components.items()))),
                "nets": dict(reversed(tuple(source.nets.items()))),
                "component_symbols": dict(reversed(tuple(source.component_symbols.items()))),
                "pin_functions": dict(reversed(tuple(source.pin_functions.items()))),
                "component_pin_numbers": dict(
                    reversed(tuple(source.component_pin_numbers.items()))
                ),
            }
        )
        reordered_sha256, reordered = protection_lint_report(None, reordered_source)
        self.assertNotEqual(source_sha256, reordered_sha256)
        reordered_findings = {
            item.subject: (item.fingerprint, item.evidence)
            for item in reordered.findings
            if item.rule_id == rule_id
        }
        self.assertEqual(reordered_findings, original_findings)

        explicitly_not_required = protection_map(disposition="not_required")
        decided_sha256, decided = protection_lint_report(explicitly_not_required, source)
        self.assertEqual(decided_sha256, source_sha256)
        self.assertNotIn(rule_id, {item.rule_id for item in decided.findings})

    def test_mapped_protection_mismatch_is_order_stable_and_native_repair_clears_it(
        self,
    ) -> None:
        requirements = protection_map()
        source = observed_netlist(fault="protector-wrong-net")
        source_sha256, original = protection_lint_report(requirements, source)
        rule_id = "protection.mapped_device_mismatch"
        original_findings = {
            item.subject: (item.fingerprint, item.evidence)
            for item in original.findings
            if item.rule_id == rule_id
        }
        self.assertEqual(len(original_findings), 1)

        reordered_source = source.model_copy(
            update={
                "components": dict(reversed(tuple(source.components.items()))),
                "nets": dict(reversed(tuple(source.nets.items()))),
                "component_symbols": dict(reversed(tuple(source.component_symbols.items()))),
                "pin_functions": dict(reversed(tuple(source.pin_functions.items()))),
                "component_pin_numbers": dict(
                    reversed(tuple(source.component_pin_numbers.items()))
                ),
            }
        )
        reordered_sha256, reordered = protection_lint_report(requirements, reordered_source)
        self.assertNotEqual(source_sha256, reordered_sha256)
        reordered_findings = {
            item.subject: (item.fingerprint, item.evidence)
            for item in reordered.findings
            if item.rule_id == rule_id
        }
        self.assertEqual(reordered_findings, original_findings)

        repaired_sha256, repaired = protection_lint_report(requirements, observed_netlist())
        self.assertNotEqual(source_sha256, repaired_sha256)
        self.assertNotIn(rule_id, {item.rule_id for item in repaired.findings})

    def test_map_rejects_wrong_device_pin_ownership_and_duplicate_connector_pin(self) -> None:
        with self.assertRaisesRegex(ValidationError, "belong to the declared device"):
            ExternalProtectionChannelRequirement(
                device_reference="D1",
                signal_pin="D2.1",
                reference_pin="D1.2",
                reference_net="GND",
            )
        duplicate = protection_map().model_dump(mode="python")
        duplicate["interfaces"] = (duplicate["interfaces"][0], duplicate["interfaces"][0])
        with self.assertRaisesRegex(ValidationError, "interface pins must be unique"):
            ExternalProtectionMap.model_validate(duplicate)


if __name__ == "__main__":
    unittest.main()
