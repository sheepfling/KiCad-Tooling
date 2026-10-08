"""Exact project-authored voltage limits for direct digital peer links."""

from __future__ import annotations

import unittest

from pydantic import ValidationError

from kicad_tooling.hwrepo.digital_peer_voltages import digital_peer_voltage_checks
from kicad_tooling.hwrepo.models import (
    ComponentContract,
    DigitalLogicInputLimits,
    DigitalLogicOutputLimits,
    DigitalPeerPinRequirement,
    DigitalPeerVoltageAnalysis,
    DigitalPeerVoltageLink,
    NetlistContract,
)


def requirement(
    *,
    output_high_minimum_v: float = 2.2,
    output_high_maximum_v: float = 3.3,
    output_low_maximum_v: float = 0.4,
    include_limits: bool = True,
) -> DigitalPeerVoltageAnalysis:
    limits = {
        "output_limits": DigitalLogicOutputLimits(
            low_minimum_v=0.0,
            low_maximum_v=output_low_maximum_v,
            high_minimum_v=output_high_minimum_v,
            high_maximum_v=output_high_maximum_v,
            source="Synthetic controller datasheet Rev A, Table 8",
            conditions="VDD=3.3 V, specified output load, full operating range",
        ),
        "input_limits": DigitalLogicInputLimits(
            absolute_minimum_v=-0.3,
            low_maximum_v=0.8,
            high_minimum_v=2.0,
            absolute_maximum_v=3.6,
            source="Synthetic peripheral datasheet Rev B, Table 4",
            conditions="VDD=3.3 V, full operating range",
        ),
    }
    if not include_limits:
        limits = {"output_limits": None, "input_limits": None}
    return DigitalPeerVoltageAnalysis(
        basis="Synthetic SPI data output mapped to a local peripheral input",
        links=(
            DigitalPeerVoltageLink(
                id="spi-mosi",
                basis="Reviewed controller-to-peripheral MOSI connection",
                driver=DigitalPeerPinRequirement(
                    reference="U1",
                    symbol="Synthetic:Controller",
                    footprint="Package_QFP:LQFP-48",
                    pin="U1.12",
                    net="SPI_MOSI",
                ),
                receiver=DigitalPeerPinRequirement(
                    reference="U2",
                    symbol="Synthetic:Peripheral",
                    footprint="Package_SO:SOIC-8",
                    pin="U2.3",
                    net="SPI_MOSI",
                ),
                **limits,
            ),
        ),
    )


def observed(*, fault: str | None = None) -> NetlistContract:
    u1_net = "SPI_MOSI"
    u2_net = "SPI_MOSI"
    dnp: tuple[str, ...] = ()
    if fault == "wrong-net":
        u2_net = "OTHER"
    elif fault == "dnp":
        dnp = ("U2",)
    elif fault == "wrong-symbol":
        pass
    nets = (
        {u1_net: ("U1.12", "U2.3")} if u1_net == u2_net else {u1_net: ("U1.12",), u2_net: ("U2.3",)}
    )
    return NetlistContract(
        components={
            "U1": ComponentContract(value="Synthetic controller", footprint="Package_QFP:LQFP-48"),
            "U2": ComponentContract(value="Synthetic peripheral", footprint="Package_SO:SOIC-8"),
        },
        nets=nets,
        component_symbols={
            "U1": "Synthetic:Controller",
            "U2": "Synthetic:OtherPeripheral"
            if fault == "wrong-symbol"
            else "Synthetic:Peripheral",
        },
        component_pin_numbers={"U1": ("12",), "U2": ("3",)},
        dnp_components=dnp,
    )


class DigitalPeerVoltageTests(unittest.TestCase):
    def checks(self, spec: DigitalPeerVoltageAnalysis | None = None, *, fault: str | None = None):
        result = digital_peer_voltage_checks(spec or requirement(), observed(fault=fault))
        return {item.id: item for item in result}

    def test_authored_spi_limits_pass_at_exactly_supported_ranges(self) -> None:
        checks = self.checks()
        self.assertEqual(checks["digital-peer-voltage/spi-mosi/driver/identity"].status, "PASS")
        self.assertEqual(checks["digital-peer-voltage/spi-mosi/receiver/pin"].status, "PASS")
        compatibility = checks["digital-peer-voltage/spi-mosi/compatibility"]
        self.assertEqual(compatibility.status, "PASS")
        self.assertAlmostEqual(compatibility.observed, 0.2)
        self.assertIn("Synthetic controller datasheet", compatibility.detail)
        self.assertIn("VDD=3.3 V", compatibility.detail)

    def test_output_low_high_and_absolute_limit_faults_fail(self) -> None:
        cases = (
            (requirement(output_low_maximum_v=0.9), "output-low maximum"),
            (requirement(output_high_minimum_v=1.8), "high minimum"),
            (requirement(output_high_maximum_v=5.0), "absolute input range"),
        )
        for spec, evidence in cases:
            with self.subTest(evidence=evidence):
                result = self.checks(spec)["digital-peer-voltage/spi-mosi/compatibility"]
                self.assertEqual(result.status, "FAIL")
                self.assertIn("Minimum margin=", result.detail)

    def test_tolerant_receiver_and_exact_limit_boundaries_are_valid_controls(self) -> None:
        tolerant = requirement(output_high_maximum_v=5.0)
        link_data = tolerant.links[0].model_dump()
        link_data["input_limits"]["absolute_maximum_v"] = 5.5
        link_data["input_limits"]["high_minimum_v"] = 2.2
        tolerant_link = DigitalPeerVoltageLink.model_validate(link_data)
        tolerant_spec = DigitalPeerVoltageAnalysis(
            basis="Synthetic receiver explicitly rated for the driver's full range",
            links=(tolerant_link,),
        )
        self.assertEqual(
            self.checks(tolerant_spec)["digital-peer-voltage/spi-mosi/compatibility"].status,
            "PASS",
        )

        boundary_data = tolerant.links[0].model_dump()
        boundary_data["output_limits"].update(
            {"low_maximum_v": 0.8, "high_minimum_v": 2.0, "high_maximum_v": 5.0}
        )
        boundary_data["input_limits"].update(
            {"low_maximum_v": 0.8, "high_minimum_v": 2.0, "absolute_maximum_v": 5.0}
        )
        boundary_spec = DigitalPeerVoltageAnalysis(
            basis="Synthetic exact-boundary logic limits",
            links=(DigitalPeerVoltageLink.model_validate(boundary_data),),
        )
        boundary = self.checks(boundary_spec)["digital-peer-voltage/spi-mosi/compatibility"]
        self.assertEqual(boundary.status, "PASS")
        self.assertAlmostEqual(boundary.observed or 0.0, 0.0)

    def test_stale_symbol_or_dnp_pin_map_suppresses_voltage_claim(self) -> None:
        for fault in ("wrong-symbol", "dnp"):
            with self.subTest(fault=fault):
                checks = self.checks(fault=fault)
                self.assertEqual(
                    checks["digital-peer-voltage/spi-mosi/receiver/identity"].status, "FAIL"
                )
                self.assertEqual(
                    checks["digital-peer-voltage/spi-mosi/compatibility"].status, "NOT_APPLICABLE"
                )

    def test_wrong_native_net_assignment_is_localized_and_not_compared(self) -> None:
        checks = self.checks(fault="wrong-net")
        self.assertEqual(checks["digital-peer-voltage/spi-mosi/receiver/pin"].status, "FAIL")
        self.assertIn(
            "U2.3 is assigned to OTHER", checks["digital-peer-voltage/spi-mosi/receiver/pin"].detail
        )
        self.assertEqual(
            checks["digital-peer-voltage/spi-mosi/compatibility"].status, "NOT_APPLICABLE"
        )

    def test_missing_limits_are_visible_as_not_configured(self) -> None:
        checks = self.checks(requirement(include_limits=False))
        result = checks["digital-peer-voltage/spi-mosi/compatibility"]
        self.assertEqual(result.status, "NOT_CONFIGURED")
        self.assertIn("VOL/VOH", result.detail)
        self.assertIn("VIL/VIH", result.detail)

    def test_contract_requires_direct_distinct_endpoints_and_unique_ids(self) -> None:
        base = requirement().links[0]
        mismatched_map = base.model_dump()
        mismatched_map["receiver"]["net"] = "OTHER"
        with self.assertRaisesRegex(ValidationError, "same net"):
            DigitalPeerVoltageLink.model_validate(mismatched_map)
        duplicate = base.model_copy(update={"id": "SPI-MOSI"})
        with self.assertRaisesRegex(ValidationError, "IDs must be unique"):
            DigitalPeerVoltageAnalysis(basis="duplicate map guard", links=(base, duplicate))


if __name__ == "__main__":
    unittest.main()
