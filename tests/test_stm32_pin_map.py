"""Synthetic STM32 CubeMX and KiCad pin-map comparison regressions."""

from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path

from pydantic import ValidationError

from kicad_tooling.hwrepo.design_lint import (
    evaluate,
    scan_stm32_pin_maps,
)
from kicad_tooling.hwrepo.models import (
    ComponentContract,
    ContractCoachReport,
    DesignLintIgnore,
    DesignLintPolicy,
    DesignLintRuleOverride,
    NetlistContract,
    Stm32CubeMxPinMap,
    Stm32PinExclusion,
    Stm32PinMapCoverageReport,
    Stm32PinRequirement,
)
from kicad_tooling.hwrepo.stm32_pin_map import (
    parse_cubemx_ioc,
    stm32_pin_map_mismatches,
)

_ROOT = Path(__file__).resolve().parents[1]
_IOC_FIXTURE = _ROOT / "tests/fixtures/design_lint/stm32-pin-map/valid.ioc"
_IOC_RELATIVE = "tests/fixtures/design_lint/stm32-pin-map/valid.ioc"
_NETLIST_SHA256 = "a" * 64


def sample_map(ioc_path: str = _IOC_RELATIVE) -> Stm32CubeMxPinMap:
    return Stm32CubeMxPinMap(
        id="main-mcu",
        basis="Synthetic reviewed STM32F103 package pin table",
        reference="U1",
        expected_symbol="Synthetic:STM32F103",
        expected_part="STM32F103C8T6",
        ioc_path=ioc_path,
        package_pins=("PA0", "PB6", "PB7", "PA13"),
        pins=(
            Stm32PinRequirement(
                port_pin="PA0",
                symbol_pin="1",
                expected_net="USER_BUTTON",
                accepted_ioc_signals=("GPIO_Input",),
                accepted_ioc_gpio_labels=("BUTTON",),
            ),
            Stm32PinRequirement(
                port_pin="PB6",
                symbol_pin="2",
                expected_net="I2C_SCL",
                accepted_ioc_signals=("I2C1_SCL",),
                accepted_ioc_gpio_labels=("SCL",),
            ),
            Stm32PinRequirement(
                port_pin="PB7",
                symbol_pin="3",
                expected_net="I2C_SDA",
                accepted_ioc_signals=("I2C1_SDA",),
                accepted_ioc_gpio_labels=("SDA",),
            ),
        ),
        exclusions=(
            Stm32PinExclusion(
                port_pin="PA13", reason="Reserved for the reviewed SWD debug interface"
            ),
        ),
    )


def sample_netlist(*, wrong_symbol: bool = False, dnp: bool = False) -> NetlistContract:
    return NetlistContract(
        components={"U1": ComponentContract(value="STM32F103C8T6", footprint="Synthetic:LQFP-48")},
        nets={
            "USER_BUTTON": ("U1.1",),
            "I2C_SCL": ("U1.2",),
            "I2C_SDA": ("U1.3",),
        },
        dnp_components=("U1",) if dnp else (),
        component_symbols={"U1": "Synthetic:WrongPart" if wrong_symbol else "Synthetic:STM32F103"},
        component_pin_numbers={"U1": ("1", "2", "3", "34")},
    )


def coach(observed: NetlistContract) -> ContractCoachReport:
    return ContractCoachReport(
        status="READY_FOR_REVIEW",
        project_id="synthetic-stm32-map",
        observed=observed,
        netlist_sha256=_NETLIST_SHA256,
    )


class Stm32PinMapTests(unittest.TestCase):
    def test_correct_netlist_and_cube_mx_values_are_a_control(self) -> None:
        content = _IOC_FIXTURE.read_bytes()
        document = parse_cubemx_ioc(content)
        self.assertEqual(document.issues, ())
        mismatches = stm32_pin_map_mismatches(
            sample_map(),
            sample_netlist(),
            document,
            ioc_sha256=hashlib.sha256(content).hexdigest(),
            map_sha256="b" * 64,
            netlist_sha256=_NETLIST_SHA256,
        )
        self.assertEqual(mismatches, ())

    def test_netlist_or_cube_mx_drift_emits_mismatch(self) -> None:
        content = (
            _IOC_FIXTURE.read_bytes()
            .replace(b"PA0.Signal=GPIO_Input", b"PA0.Signal=GPIO_Output")
            .replace(b"PA0.GPIO_Label=BUTTON", b"PA0.GPIO_Label=STATUS_LED")
        )
        document = parse_cubemx_ioc(content)
        mapped = sample_map()
        mismatches = stm32_pin_map_mismatches(
            mapped,
            sample_netlist(),
            document,
            ioc_sha256=hashlib.sha256(content).hexdigest(),
            map_sha256="b" * 64,
            netlist_sha256=_NETLIST_SHA256,
        )
        self.assertEqual(tuple(item.port_pin for item in mismatches), ("PA0",))
        self.assertTrue(any("signal is GPIO_Output" in issue for issue in mismatches[0].issues))
        self.assertTrue(any("GPIO label is STATUS_LED" in issue for issue in mismatches[0].issues))

        wrong_netlist = sample_netlist().model_copy(
            update={"nets": {"OTHER": ("U1.1",), "I2C_SCL": ("U1.2",), "I2C_SDA": ("U1.3",)}}
        )
        wrong_net_mismatches = stm32_pin_map_mismatches(
            mapped,
            wrong_netlist,
            parse_cubemx_ioc(_IOC_FIXTURE.read_bytes()),
            ioc_sha256="c" * 64,
            map_sha256="b" * 64,
            netlist_sha256=_NETLIST_SHA256,
        )
        self.assertTrue(
            any("U1.1 is on OTHER" in issue for issue in wrong_net_mismatches[0].issues)
        )

    def test_identity_dnp_and_missing_ioc_pin_faults_are_visible(self) -> None:
        content = (
            _IOC_FIXTURE.read_bytes()
            .replace(b"PA0.GPIO_Label=BUTTON\n", b"")
            .replace(b"PA0.Signal=GPIO_Input\n", b"")
        )
        document = parse_cubemx_ioc(content)
        mismatches = stm32_pin_map_mismatches(
            sample_map(),
            sample_netlist(wrong_symbol=True, dnp=True),
            document,
            ioc_sha256=hashlib.sha256(content).hexdigest(),
            map_sha256="b" * 64,
            netlist_sha256=_NETLIST_SHA256,
        )
        self.assertEqual(len(mismatches), 3)
        first_issues = mismatches[0].issues
        self.assertTrue(any("symbol is Synthetic:WrongPart" in issue for issue in first_issues))
        self.assertTrue(any("marked DNP" in issue for issue in first_issues))
        self.assertTrue(any("has no assignment for PA0" in issue for issue in first_issues))

    def test_exact_aliases_and_reasoned_package_exclusions_are_accepted(self) -> None:
        aliased_content = (
            _IOC_FIXTURE.read_bytes()
            .replace(b"PB6.Signal=I2C1_SCL", b"PB6.Signal=I2C1_SCL_ALT")
            .replace(b"PB6.GPIO_Label=SCL", b"PB6.GPIO_Label=CLOCK")
        )
        aliased_map = sample_map().model_copy(
            update={
                "pins": (
                    sample_map().pins[0],
                    sample_map()
                    .pins[1]
                    .model_copy(
                        update={
                            "accepted_ioc_signals": ("I2C1_SCL_ALT",),
                            "accepted_ioc_gpio_labels": ("CLOCK",),
                        }
                    ),
                    sample_map().pins[2],
                )
            }
        )
        mismatches = stm32_pin_map_mismatches(
            aliased_map,
            sample_netlist(),
            parse_cubemx_ioc(aliased_content),
            ioc_sha256=hashlib.sha256(aliased_content).hexdigest(),
            map_sha256="b" * 64,
            netlist_sha256=_NETLIST_SHA256,
        )
        self.assertEqual(mismatches, ())
        self.assertEqual(aliased_map.exclusions[0].port_pin, "PA13")

    def test_cubemx_alternate_function_and_escaped_pin_suffixes_are_supported(self) -> None:
        document = parse_cubemx_ioc(
            b"PC13-ANTI_TAMP.Signal=GPIO_Output\n"
            b"PH0\\ -\\ OSC_IN.Signal=RCC_OSC_IN\n"
            b"PA13-JTMS/SWDIO.Signal=SYS_JTMS-SWDIO\n"
        )
        self.assertEqual(document.issues, ())
        self.assertEqual({pin.port_pin for pin in document.pins.values()}, {"PC13", "PH0", "PA13"})
        self.assertEqual(document.pins["ph0"].raw_key, "PH0\\ -\\ OSC_IN")

    def test_package_pin_inventory_requires_exact_map_or_reasoned_exclusion(self) -> None:
        payload = sample_map().model_dump(mode="python")
        payload["exclusions"] = ()
        with self.assertRaisesRegex(ValidationError, "Every CubeMX package pin"):
            Stm32CubeMxPinMap.model_validate(payload, strict=True)
        with self.assertRaisesRegex(ValidationError, "Generic CubeMX GPIO signals"):
            Stm32PinRequirement(
                port_pin="PA0",
                symbol_pin="1",
                expected_net="USER_BUTTON",
                accepted_ioc_signals=("GPIO_Input",),
                accepted_ioc_gpio_labels=None,
            )

    def test_duplicate_or_unsupported_ioc_assignments_block_coverage(self) -> None:
        duplicate = parse_cubemx_ioc(b"PB6.Signal=I2C1_SCL\nPB6.Signal=I2C1_SDA\n")
        self.assertTrue(any("duplicate CubeMX Signal" in issue for issue in duplicate.issues))
        unsupported = parse_cubemx_ioc(b"PBA.Bad.Signal=UART1_TX\n")
        self.assertTrue(any("unsupported CubeMX pin key" in issue for issue in unsupported.issues))

        with tempfile.TemporaryDirectory(prefix="stm32-ioc-blocked-") as temporary:
            root = Path(temporary)
            source = root / "firmware/controller.ioc"
            source.parent.mkdir()
            source.write_bytes(b"PB6.Signal=I2C1_SCL\nPB6.Signal=I2C1_SDA\n")
            report = scan_stm32_pin_maps(
                root,
                DesignLintPolicy(stm32_pin_maps=(sample_map("firmware/controller.ioc"),)),
                sample_netlist(),
                _NETLIST_SHA256,
            )
        self.assertEqual(report.status, "BLOCKED")
        self.assertIn("duplicate CubeMX Signal", report.issue or "")

    def test_conflicting_alternate_function_suffixes_block_coverage(self) -> None:
        content = b"PA13-JTMS.Signal=SYS_JTMS-SWDIO\nPA13-SWDIO.Signal=SYS_SWDIO\n"
        reversed_content = b"PA13-SWDIO.Signal=SYS_SWDIO\nPA13-JTMS.Signal=SYS_JTMS-SWDIO\n"
        for candidate in (content, reversed_content):
            with self.subTest(candidate=candidate):
                document = parse_cubemx_ioc(candidate)
                self.assertEqual(len(document.issues), 1)
                self.assertIn("both identify PA13", document.issues[0])

        with tempfile.TemporaryDirectory(prefix="stm32-ioc-collision-") as temporary:
            root = Path(temporary)
            source = root / "firmware/controller.ioc"
            source.parent.mkdir()
            source.write_bytes(content)
            report = scan_stm32_pin_maps(
                root,
                DesignLintPolicy(stm32_pin_maps=(sample_map("firmware/controller.ioc"),)),
                sample_netlist(),
                _NETLIST_SHA256,
            )
        self.assertEqual(report.status, "BLOCKED")
        self.assertIn("both identify PA13", report.issue or "")

    def test_ioc_pin_assignment_order_preserves_coverage_and_source_binding(self) -> None:
        lines = _IOC_FIXTURE.read_bytes().splitlines()
        reordered = b"\n".join((lines[0], *reversed(lines[1:]))) + b"\n"
        pin_map = sample_map("firmware/controller.ioc")
        policy = DesignLintPolicy(stm32_pin_maps=(pin_map,))

        def scan(content: bytes) -> Stm32PinMapCoverageReport:
            with tempfile.TemporaryDirectory(prefix="stm32-ioc-order-") as temporary:
                root = Path(temporary)
                source = root / "firmware/controller.ioc"
                source.parent.mkdir()
                source.write_bytes(content)
                return scan_stm32_pin_maps(root, policy, sample_netlist(), _NETLIST_SHA256)

        original_report = scan(_IOC_FIXTURE.read_bytes())
        reordered_report = scan(reordered)
        self.assertEqual(original_report.status, "COMPLETE")
        self.assertEqual(reordered_report.status, "COMPLETE")
        self.assertEqual(original_report.mismatches, reordered_report.mismatches)
        self.assertEqual(original_report.unmapped_devices, reordered_report.unmapped_devices)
        self.assertEqual(original_report.mapped_pin_count, reordered_report.mapped_pin_count)
        self.assertEqual(original_report.excluded_pin_count, reordered_report.excluded_pin_count)
        self.assertNotEqual(
            original_report.ioc_source_hashes["firmware/controller.ioc"],
            reordered_report.ioc_source_hashes["firmware/controller.ioc"],
        )

    def test_ioc_source_is_hash_bound_and_rule_policy_is_configurable(self) -> None:
        with tempfile.TemporaryDirectory(prefix="stm32-ioc-policy-") as temporary:
            root = Path(temporary)
            source = root / "firmware/controller.ioc"
            source.parent.mkdir()
            source.write_bytes(_IOC_FIXTURE.read_bytes())
            pin_map = sample_map("firmware/controller.ioc")
            policy = DesignLintPolicy(stm32_pin_maps=(pin_map,))
            observed = sample_netlist()
            coverage = scan_stm32_pin_maps(root, policy, observed, _NETLIST_SHA256)
            report = evaluate(
                "synthetic-stm32-map", coach(observed), policy, stm32_pin_map_coverage=coverage
            )
            self.assertEqual(report.status, "PASS")
            source_sha256 = hashlib.sha256(source.read_bytes()).hexdigest()
            self.assertEqual(report.source_hashes["firmware/controller.ioc"], source_sha256)
            self.assertEqual(coverage.ioc_source_hashes["firmware/controller.ioc"], source_sha256)

            source.write_bytes(source.read_bytes().replace(b"I2C1_SCL", b"I2C1_SDA", 1))
            faulty_coverage = scan_stm32_pin_maps(root, policy, observed, _NETLIST_SHA256)
            review = evaluate(
                "synthetic-stm32-map",
                coach(observed),
                policy,
                stm32_pin_map_coverage=faulty_coverage,
            )
            finding = next(
                item for item in review.findings if item.rule_id == "mcu.stm32_cubemx_pin_map"
            )
            self.assertEqual(review.status, "REVIEW")
            self.assertEqual(faulty_coverage.status, "COMPLETE")

            blocked = evaluate(
                "synthetic-stm32-map",
                coach(observed),
                policy.model_copy(
                    update={
                        "rules": (
                            DesignLintRuleOverride(
                                rule_id="mcu.stm32_cubemx_pin_map",
                                mode="block",
                                reason="The reviewed firmware pin map is a release requirement",
                            ),
                        )
                    }
                ),
                stm32_pin_map_coverage=faulty_coverage,
            )
            self.assertEqual(blocked.status, "FAIL")

            ignored = evaluate(
                "synthetic-stm32-map",
                coach(observed),
                policy.model_copy(
                    update={
                        "ignores": (
                            DesignLintIgnore(
                                rule_id=finding.rule_id,
                                fingerprint=finding.fingerprint,
                                reason="Reviewed synthetic alternate firmware configuration",
                            ),
                        )
                    }
                ),
                stm32_pin_map_coverage=faulty_coverage,
            )
            self.assertEqual(ignored.status, "PASS")
            ignored_finding = next(
                item for item in ignored.findings if item.rule_id == finding.rule_id
            )
            self.assertEqual(ignored_finding.disposition, "IGNORED")

            source.write_text(
                source.read_text(encoding="utf-8").replace(
                    "PB6.Signal=I2C1_SDA", "PB6.Signal=I2C1_SCK", 1
                ),
                encoding="utf-8",
            )
            changed_after_ignore = scan_stm32_pin_maps(root, policy, observed, _NETLIST_SHA256)
            stale_ignore_report = evaluate(
                "synthetic-stm32-map",
                coach(observed),
                policy.model_copy(
                    update={
                        "ignores": (
                            DesignLintIgnore(
                                rule_id=finding.rule_id,
                                fingerprint=finding.fingerprint,
                                reason="Reviewed synthetic alternate firmware configuration",
                            ),
                        )
                    }
                ),
                stm32_pin_map_coverage=changed_after_ignore,
            )
            self.assertEqual(stale_ignore_report.status, "REVIEW")
            self.assertEqual(len(stale_ignore_report.stale_ignores), 1)
            self.assertEqual(stale_ignore_report.stale_ignores[0].fingerprint, finding.fingerprint)
            self.assertTrue(
                any(
                    item.rule_id == finding.rule_id and item.disposition == "OPEN"
                    for item in stale_ignore_report.findings
                )
            )

            disabled_policy = policy.model_copy(
                update={
                    "rules": (
                        DesignLintRuleOverride(
                            rule_id="mcu.stm32_cubemx_pin_map",
                            mode="off",
                            reason="This fixture is testing a firmware variant without CubeMX",
                        ),
                    )
                }
            )
            disabled_coverage = scan_stm32_pin_maps(
                root, disabled_policy, observed, _NETLIST_SHA256
            )
            disabled = evaluate(
                "synthetic-stm32-map",
                coach(observed),
                disabled_policy,
                stm32_pin_map_coverage=disabled_coverage,
            )
            self.assertEqual(disabled.status, "PASS")
            self.assertEqual(disabled.stm32_pin_map_coverage.status, "DISABLED")

    def test_unmapped_fitted_stm32_is_reviewed_and_dnp_is_controlled(self) -> None:
        report = evaluate("synthetic-stm32-map", coach(sample_netlist()), DesignLintPolicy())
        self.assertEqual(report.status, "REVIEW")
        self.assertEqual(report.stm32_pin_map_coverage.status, "INCOMPLETE")
        self.assertEqual(report.stm32_pin_map_coverage.unmapped_devices[0].reference, "U1")

        dnp_report = evaluate(
            "synthetic-stm32-map",
            coach(sample_netlist(dnp=True)),
            DesignLintPolicy(),
        )
        self.assertEqual(dnp_report.status, "PASS")
        self.assertEqual(dnp_report.stm32_pin_map_coverage.status, "NOT_REQUESTED")


if __name__ == "__main__":
    unittest.main()
