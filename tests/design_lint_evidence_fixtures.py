"""Small synthetic coverage records shared by report evidence tests."""

from __future__ import annotations

from typing import Literal

from kicad_tooling.hwrepo.crystal_network_models import (
    CrystalNetworkCoverageEntry,
    CrystalNetworkCoverageReport,
)
from kicad_tooling.hwrepo.external_protection_models import (
    ExternalProtectionCoverageEntry,
    ExternalProtectionCoverageReport,
)
from kicad_tooling.hwrepo.rc_filter_models import RcFilterCoverageEntry, RcFilterCoverageReport
from kicad_tooling.hwrepo.regulator_feedback_models import (
    RegulatorFeedbackCoverageEntry,
    RegulatorFeedbackCoverageReport,
)


def external_protection_coverage(
    status: Literal["COMPLETE", "INCOMPLETE", "UNDECLARED"], netlist_sha256: str
) -> ExternalProtectionCoverageReport:
    entry_status = "PROTECTED" if status == "COMPLETE" else status
    return ExternalProtectionCoverageReport(
        status=status,
        netlist_sha256=netlist_sha256,
        entries=(
            ExternalProtectionCoverageEntry(
                connector_reference="J1",
                connector_pin="J1.1",
                status=entry_status,
            ),
        ),
    )


def crystal_coverage(netlist_sha256: str) -> CrystalNetworkCoverageReport:
    return CrystalNetworkCoverageReport(
        status="COMPLETE",
        netlist_sha256=netlist_sha256,
        entries=(
            CrystalNetworkCoverageEntry(
                oscillator_reference="U1",
                resonator_reference="Y1",
                load_capacitor_references=("C1", "C2"),
                status="OUT_OF_RANGE",
                target_minimum_load_pf=10,
                target_maximum_load_pf=12,
                minimum_stray_capacitance_pf=1,
                maximum_stray_capacitance_pf=3,
                basis="Synthetic coverage comparison",
            ),
        ),
    )


def regulator_coverage(netlist_sha256: str) -> RegulatorFeedbackCoverageReport:
    return RegulatorFeedbackCoverageReport(
        status="COMPLETE",
        netlist_sha256=netlist_sha256,
        entries=(
            RegulatorFeedbackCoverageEntry(
                id="main-rail",
                regulator_reference="U1",
                status="OUT_OF_RANGE",
                output_net="VOUT",
                reference_net="GND",
                feedback_reference_minimum_v=0.79,
                feedback_reference_maximum_v=0.81,
                target_output_minimum_v=5,
                target_output_maximum_v=5.2,
                basis="Synthetic coverage comparison",
            ),
        ),
    )


def rc_filter_coverage(netlist_sha256: str) -> RcFilterCoverageReport:
    return RcFilterCoverageReport(
        status="COMPLETE",
        netlist_sha256=netlist_sha256,
        entries=(
            RcFilterCoverageEntry(
                id="input-filter",
                resistor_reference="R1",
                capacitor_reference="C1",
                status="OUT_OF_RANGE",
                input_net="VIN",
                filtered_net="VOUT",
                reference_net="GND",
                target_minimum_corner_hz=1,
                target_maximum_corner_hz=2,
                nominal_resistance_range_ohms=(1, 2),
                nominal_capacitance_range_pf=(1, 2),
                basis="Synthetic coverage comparison",
            ),
        ),
    )
